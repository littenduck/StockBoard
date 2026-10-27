"""Build the dashboard snapshot and refresh it in the background."""
import dataclasses
import datetime
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from stock_benchmark_backend import (company_indicators, fetch_store, event_calendar, indicator_calculation, indicator_registry, live_indicators, market_data,
                                option_chain, rule_catalog, snapshot_storage, strategy_evaluation, yahoo_company, yahoo_gate)
from stock_benchmark_backend.fetch_cache import FetchCache
from stock_benchmark_backend.run_log import run_log_write
from stock_benchmark_backend.settings_loader import ApplicationSettings, PROJECT_DIRECTORY
from stock_benchmark_backend.strategy_evaluation import IndicatorValue, StrategyDefinition

DATA_DIRECTORY = os.path.join(PROJECT_DIRECTORY, "data")
SNAPSHOT_FILE_PATH = os.path.join(DATA_DIRECTORY, "latest_snapshot.json")
SECTOR_ETF_SYMBOL_LIST = sorted(set(company_indicators.SECTOR_ETF_BY_SECTOR_NAME.values()))
MARKET_GAUGE_SYMBOL_LIST = ["^VIX", "^VXN", "^VVIX", "^VIX3M", "^GSPC", "CL=F", "DX-Y.NYB", "SPY", "RSP"] + SECTOR_ETF_SYMBOL_LIST
SUPPORT_LOW_TRADING_DAY_COUNT = 60
COVERED_CALL_MINIMUM_DAYS, COVERED_CALL_MAXIMUM_DAYS = 25, 35
HISTORY_PERIOD = "1y"
SYMBOL_WORKER_COUNT = 4
POLL_SECONDS = 60
SNAPSHOT_SCHEMA_VERSION = 6
SPARKLINE_TRADING_DAY_COUNT = 60
TREASURY_INDICATOR_NAME_LIST = ["treasury_ten_year_yield", "treasury_ten_year_yield_twenty_day_change_basis_points"]
HIGH_YIELD_INDICATOR_NAME_LIST = ["high_yield_credit_spread_basis_points"]
fetch_cache_holder: Dict[str, Optional[FetchCache]] = {"cache": None}
price_reload_state: Dict[str, Any] = {"day": None, "missing": None}


def refresh_scheduler_get_fetch_cache(settings: ApplicationSettings) -> FetchCache:
    """The one cache of the process, built from config/indicators.yaml on first use."""
    if fetch_cache_holder["cache"] is None:
        yahoo_gate.yahoo_gate_install()
        registry = indicator_registry.indicator_registry_load_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "indicators.yaml"))
        fetch_cache_holder["cache"] = FetchCache(registry, lambda now: market_data.market_data_determine_whether_us_market_is_open(
            datetime.datetime.fromtimestamp(now, datetime.timezone.utc), settings.market_holiday_date_set, settings.market_early_close_date_set),
            store_directory=DATA_DIRECTORY)
    return fetch_cache_holder["cache"]


def refresh_scheduler_find_next_ex_dividend_date(snapshot: dict) -> Optional[datetime.date]:
    """The last known ex-dividend date (info first, then the calendar); later ones are projected from it."""
    info = snapshot.get("info") if isinstance(snapshot.get("info"), dict) else {}
    if isinstance(info.get("exDividendDate"), (int, float)):
        return datetime.datetime.fromtimestamp(info["exDividendDate"], datetime.timezone.utc).date()
    calendar = snapshot.get("calendar") if isinstance(snapshot.get("calendar"), dict) else {}
    return calendar.get("Ex-Dividend Date")


def refresh_scheduler_build_option_indicator_value_by_window_label(
    option_session: option_chain.OptionChainSession, underlying_price: float, realized_volatility_percent: Optional[float],
    settings: ApplicationSettings, risk_free_rate_percent: float, today: datetime.date,
    support_price: Optional[float] = None,
) -> Tuple[Dict[str, Dict[str, IndicatorValue]], Dict[str, Optional[datetime.date]]]:
    """Per window: the indicators of the selected put, and the expiration date chosen (the event rules need it even without a quote)."""
    expiration_date_list = option_session.expiration_date_list()
    indicator_by_window_label = {}
    expiration_date_by_window_label = {}
    for window in settings.option_expiration_window_list:
        expiration_date = option_chain.option_chain_determine_expiration_within_day_window(
            expiration_date_list, window.minimum_days, window.maximum_days, today)
        selected_contract = None
        if expiration_date is not None:
            put_table = option_session.put_table(expiration_date)
            selected_contract = option_chain.option_chain_determine_representative_put_contract_from_table(
                put_table, underlying_price, expiration_date, today,
                settings.target_absolute_delta, risk_free_rate_percent)
        value_by_name = indicator_calculation.indicator_calculation_build_option_indicator_value_by_name(
            selected_contract, realized_volatility_percent, underlying_price, support_price,
            None if selected_contract is None else option_chain.option_chain_calculate_put_skew_points(
                put_table, underlying_price, selected_contract.days_to_expiration,
                risk_free_rate_percent))
        indicator_by_window_label[window.label] = value_by_name
        expiration_date_by_window_label[window.label] = expiration_date
    return indicator_by_window_label, expiration_date_by_window_label


def refresh_scheduler_build_covered_call_indicator_value_by_name(
    option_session: option_chain.OptionChainSession, underlying_price: float, today: datetime.date,
) -> Dict[str, IndicatorValue]:
    """The covered call the rules describe: about 30 days out, struck about 10% above the price. Strikes need no live quote."""
    try:
        expiration_date = option_chain.option_chain_determine_expiration_within_day_window(
            option_session.expiration_date_list(), COVERED_CALL_MINIMUM_DAYS, COVERED_CALL_MAXIMUM_DAYS, today)
        if expiration_date is None:
            return {}
        premium_percent = option_chain.option_chain_determine_covered_call_strike_premium_percent(
            option_session.call_table(expiration_date), underlying_price)
    except Exception as error:
        print("covered call failed:", option_session.symbol, error)
        return {}
    value_by_name = {"selected_call_days_to_expiration": (expiration_date - today).days}
    if premium_percent is not None:
        value_by_name["selected_call_strike_premium_percent"] = premium_percent
    return {key: IndicatorValue(key, value, "yfinance option chain") for key, value in value_by_name.items()}


def refresh_scheduler_build_option_life_indicator_value_by_name(
    settings: ApplicationSettings, today: datetime.date, expiration_date: datetime.date, dividend_snapshot: dict,
) -> Dict[str, IndicatorValue]:
    """Event answers for the days between today and the expiration. They need no option quote, so they are known after hours too."""
    covered_until = event_calendar.event_calendar_build_covered_until_by_event_name(settings.macro_event_covered_until)
    value_by_name = event_calendar.event_calendar_build_option_life_indicator_value_by_name(
        settings.macro_event_calendar, covered_until, today, expiration_date)
    info = dividend_snapshot.get("info") if isinstance(dividend_snapshot.get("info"), dict) else {}
    if info.get("dividendRate") or info.get("dividendYield"):
        last_ex_date = refresh_scheduler_find_next_ex_dividend_date(dividend_snapshot)
        value_by_name["no_ex_dividend_date_inside_option_life"] = None if last_ex_date is None else not (
            event_calendar.event_calendar_project_next_ex_dividend_date_list(last_ex_date, today, expiration_date))
    elif "trailingEps" in info:
        value_by_name["no_ex_dividend_date_inside_option_life"] = True  # a company that pays no dividend has no ex-dividend date
    return {key: IndicatorValue(key, value, "calendar") for key, value in value_by_name.items() if value is not None}


def refresh_scheduler_fetch_option_indicators(
    symbol: str, price_history, realized_volatility, ten_year_yield, settings: ApplicationSettings, today: datetime.date,
) -> dict:
    """The option job of one symbol: the window indicators, the expiration chosen per window and the covered call. Asks Yahoo."""
    option_session = option_chain.OptionChainSession(symbol)
    price = float(price_history["Close"].iloc[-1])
    value_by_window_label, expiration_by_window_label = refresh_scheduler_build_option_indicator_value_by_window_label(
        option_session, price, None if realized_volatility is None else realized_volatility.value, settings,
        ten_year_yield.value if ten_year_yield else option_chain.DEFAULT_RISK_FREE_RATE_PERCENT, today,
        float(price_history["Close"].iloc[-SUPPORT_LOW_TRADING_DAY_COUNT:].min()))
    return {"value_by_window_label": value_by_window_label, "expiration_by_window_label": expiration_by_window_label,
            "covered_call": refresh_scheduler_build_covered_call_indicator_value_by_name(option_session, price, today)}


FUNDAMENTALS_ASPECT_NAME = "Fundamentals"
# The company groups of the Fundamentals aspect; MAC (macro) is in that aspect too but describes the market, not the company.
COMPANY_FUNDAMENTAL_GROUP_SET = {"IND", "QUA", "MGT", "VAL", "ACC"}
fundamental_indicator_info_by_name: Optional[Dict[str, dict]] = None


def refresh_scheduler_get_fundamental_indicator_info() -> Dict[str, dict]:
    """Indicators used by rules in the Fundamentals aspect (IND, QUA, MGT, VAL, ACC): {indicator_name: {group_id, unit}}.
    Loaded once from config/rules.yaml, so the financial panel lists the numbers the rules use, grouped as the rules are."""
    global fundamental_indicator_info_by_name
    if fundamental_indicator_info_by_name is None:
        catalog = rule_catalog.rule_catalog_load_rule_catalog_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml"))
        aspect_by_group = {group.group_id: group.aspect.en if group.aspect else None for group in catalog.rule_group_list}
        info_by_name = {}
        for entry in catalog.rule_entry_by_id.values():
            if entry.indicator and entry.group_id in COMPANY_FUNDAMENTAL_GROUP_SET and aspect_by_group.get(entry.group_id) == FUNDAMENTALS_ASPECT_NAME:
                indicator = catalog.indicator_registry.indicator_by_name.get(entry.indicator)
                # Only numbers about this company: market-wide indicators (scope market, such as the equity risk premium) are left out.
                if indicator and indicator.scope == "symbol":
                    info_by_name[entry.indicator] = {"group_id": entry.group_id, "unit": indicator.unit}
        fundamental_indicator_info_by_name = info_by_name
    return fundamental_indicator_info_by_name


# Yahoo's quoteType in plain words. Anything else (index, mutual fund, crypto ...) is "other".
ASSET_TYPE_BY_QUOTE_TYPE = {"EQUITY": "stock", "ETF": "etf"}


def refresh_scheduler_build_asset_type(info: dict) -> str:
    return ASSET_TYPE_BY_QUOTE_TYPE.get(info.get("quoteType"), "other")


def refresh_scheduler_build_not_applicable_evaluation(strategy_id: str, symbol: str) -> dict:
    """A strategy that does not apply to this asset type: no pass, no score, nothing unknown to count. The page shows a dash."""
    return {"strategy_id": strategy_id, "symbol": symbol, "is_pass": None, "score_percent": None, "unknown_weight_ratio": 0.0,
            "gate_result_list": [], "not_applicable": True}


def refresh_scheduler_build_fundamental_value_list(indicator_value_by_name: Dict[str, IndicatorValue]) -> List[dict]:
    """The fundamental numbers of one symbol with their unit and source, for the financial panel (only the ones that have a value)."""
    info_by_name = refresh_scheduler_get_fundamental_indicator_info()
    return [{"indicator_name": name, "group_id": info_by_name[name]["group_id"], "unit": info_by_name[name]["unit"],
             "value": indicator_value_by_name[name].value, "source": indicator_value_by_name[name].source}
            for name in sorted(info_by_name) if name in indicator_value_by_name and indicator_value_by_name[name].value is not None]


def refresh_scheduler_evaluate_symbol_for_all_strategies(
    symbol: str, price_history, shared_indicator_value_by_name: Dict[str, IndicatorValue],
    settings: ApplicationSettings, strategy_definition_by_id: Dict[str, StrategyDefinition],
    market_history_by_symbol: Optional[Dict[str, object]] = None, fetch_cache: Optional[FetchCache] = None,
    price_fetched_at: Optional[float] = None,
) -> dict:
    today = datetime.date.today()
    now = time.time()
    fetch_cache = fetch_cache or refresh_scheduler_get_fetch_cache(settings)
    registry = fetch_cache.registry
    market_history_by_symbol = market_history_by_symbol or {}
    company_snapshot = yahoo_company.yahoo_company_overlay_quote(
        live_indicators.live_indicators_fetch_company_snapshot(fetch_cache, symbol), fetch_cache.peek("yahoo_quote", "all", {}).get(symbol))
    info = company_snapshot.get("info") if isinstance(company_snapshot.get("info"), dict) else {}
    asset_type = refresh_scheduler_build_asset_type(info)
    shares_outstanding = company_indicators.company_indicators_get_number(info, "sharesOutstanding")
    company_indicator_value_by_name = live_indicators.live_indicators_build_company_indicator_value_by_name(company_snapshot, today)
    company_indicator_value_by_name.update(live_indicators.live_indicators_fetch_short_interest_indicator_value_by_name(
        fetch_cache, symbol, shares_outstanding, today))
    company_indicator_value_by_name.update(live_indicators.live_indicators_fetch_edgar_indicator_value_by_name(fetch_cache, symbol, today))
    if settings.fetch_dolthub_iv_history:  # off by default: no strategy uses the IV history and the free server is slow
        company_indicator_value_by_name.update(live_indicators.live_indicators_fetch_implied_volatility_indicator_value_by_name(fetch_cache, symbol, today))
    spmo_rank = live_indicators.live_indicators_fetch_spmo_rank_by_symbol(fetch_cache).get(symbol)
    if spmo_rank is not None:
        company_indicator_value_by_name["spmo_holding_rank"] = IndicatorValue("spmo_holding_rank", spmo_rank, "yfinance SPMO", observed_at=now)

    sector_etf_symbol = company_indicators.company_indicators_find_sector_etf_symbol(info)
    spy_history, sector_history = market_history_by_symbol.get("SPY"), market_history_by_symbol.get(sector_etf_symbol)
    is_earnings_date_known = info is not None and bool(info)
    next_earnings_date = market_data.market_data_find_next_earnings_date_in_calendar(company_snapshot.get("calendar"), today)
    symbol_indicator_value_by_name = live_indicators.live_indicators_stamp(
        indicator_calculation.indicator_calculation_build_symbol_indicator_value_by_name(
            price_history, is_earnings_date_known, next_earnings_date, settings.option_expiration_window_list[0].maximum_days, today,
            None if spy_history is None else spy_history["Close"], None if sector_history is None else sector_history["Close"]),
        price_fetched_at)

    options, options_fetched_at = fetch_cache.get(
        "yahoo_options", symbol, lambda: refresh_scheduler_fetch_option_indicators(
            symbol, price_history, symbol_indicator_value_by_name.get("realized_volatility_thirty_day"),
            shared_indicator_value_by_name.get("treasury_ten_year_yield"), settings, today), default={})
    company_indicator_value_by_name.update(live_indicators.live_indicators_stamp(options.get("covered_call", {}), options_fetched_at))
    option_indicator_by_window_label = {}
    for window_label, value_by_name in options.get("value_by_window_label", {}).items():
        window_value_by_name = dict(live_indicators.live_indicators_stamp(value_by_name, options_fetched_at))
        expiration_date = options["expiration_by_window_label"].get(window_label)
        if expiration_date is not None:  # event answers need no quote and are worked out fresh every time
            window_value_by_name.update(live_indicators.live_indicators_stamp(
                refresh_scheduler_build_option_life_indicator_value_by_name(settings, today, expiration_date, company_snapshot), now))
        option_indicator_by_window_label[window_label] = indicator_registry.indicator_registry_drop_stale_values(window_value_by_name, registry, now)

    combined_indicator_value_by_name = indicator_registry.indicator_registry_drop_stale_values(
        {**shared_indicator_value_by_name, **company_indicator_value_by_name, **symbol_indicator_value_by_name}, registry, now)
    last_price = symbol_indicator_value_by_name["last_price"]
    return {
        "symbol": symbol,
        "price": last_price.value,
        "fundamental_value_list": refresh_scheduler_build_fundamental_value_list(combined_indicator_value_by_name),
        "change_value": last_price.change_value,
        "change_unit": last_price.change_unit,
        "sparkline_close_price_list": [
            round(float(price), 2) for price in price_history["Close"].iloc[-SPARKLINE_TRADING_DAY_COUNT:]],
        "asset_type": asset_type,
        "evaluation_by_strategy_id": {
            strategy_id: (refresh_scheduler_build_not_applicable_evaluation(strategy_id, symbol)
                          if strategy_definition.asset_type_list is not None and asset_type not in strategy_definition.asset_type_list
                          else dataclasses.asdict(strategy_evaluation.strategy_evaluation_evaluate_strategy_for_symbol(
                              strategy_definition, symbol, combined_indicator_value_by_name, option_indicator_by_window_label)))
            for strategy_id, strategy_definition in strategy_definition_by_id.items()
        },
    }


def refresh_scheduler_build_calendar_indicator_value_by_name(
    settings: ApplicationSettings, today: datetime.date,
) -> Dict[str, IndicatorValue]:
    """Answers that depend on the date only (and on the release calendar in config/settings.yaml)."""
    covered_until = event_calendar.event_calendar_build_covered_until_by_event_name(settings.macro_event_covered_until)
    jobs_report_is_near = event_calendar.event_calendar_determine_whether_jobs_report_is_within_one_day(
        settings.macro_event_calendar, covered_until, today)
    value_by_name = {
        "no_quadruple_witching_in_next_five_trading_days":
            not event_calendar.event_calendar_determine_whether_quadruple_witching_is_within_trading_days(today),
        "is_spmo_rebalance_window": event_calendar.event_calendar_determine_whether_spmo_rebalance_month(today),
        "no_jobs_report_within_one_day": None if jobs_report_is_near is None else not jobs_report_is_near,
    }
    return {key: IndicatorValue(key, value, "calendar") for key, value in value_by_name.items() if value is not None}


def refresh_scheduler_load_price_history_by_symbol(
    symbol_list: List[str], fetch_cache: FetchCache,
) -> Tuple[Dict[str, object], Optional[float]]:
    """Daily history once a day (and again after the close), with today's bar taken from one batched quote request.
    Returns (history by symbol, time the prices were taken)."""
    def download():
        return market_data.market_data_fetch_daily_price_history_for_symbol_list(symbol_list, HISTORY_PERIOD)

    history_by_symbol, history_fetched_at = fetch_cache.get("yahoo_history", "all", download, default={})
    missing_symbol_list = [symbol for symbol in symbol_list if symbol not in history_by_symbol]
    if missing_symbol_list and price_reload_state["missing"] != missing_symbol_list:  # a symbol added since the history was kept: load it once now
        price_reload_state["missing"] = missing_symbol_list
        fetch_cache.force_due("yahoo_history", "all")
        history_by_symbol, history_fetched_at = fetch_cache.get("yahoo_history", "all", download, default={})
    quote_by_symbol, quote_fetched_at = fetch_cache.get(
        "yahoo_quote", "all", lambda: market_data.market_data_fetch_latest_quote_by_symbol(symbol_list), default={})
    if not quote_by_symbol:
        return history_by_symbol, history_fetched_at  # the batched request failed: yesterday's close until it works again
    merged_by_symbol, needs_reload = {}, False
    for symbol, history in history_by_symbol.items():
        if symbol in quote_by_symbol:
            merged_by_symbol[symbol], symbol_needs_reload = market_data.market_data_merge_quote_into_history(history, quote_by_symbol[symbol])
            needs_reload = needs_reload or symbol_needs_reload
        else:
            merged_by_symbol[symbol] = history
    today = datetime.date.today()
    if needs_reload and price_reload_state["day"] != today:  # a split or an ex-dividend day: the adjusted history must be loaded again, once a day
        price_reload_state["day"] = today
        fetch_cache.force_due("yahoo_history", "all")
        return refresh_scheduler_load_price_history_by_symbol(symbol_list, fetch_cache)
    return merged_by_symbol, quote_fetched_at


def refresh_scheduler_build_dashboard_snapshot(
    settings: ApplicationSettings, strategy_definition_by_id: Dict[str, StrategyDefinition], fetch_cache: Optional[FetchCache] = None,
) -> dict:
    fetch_cache = fetch_cache or refresh_scheduler_get_fetch_cache(settings)
    registry = fetch_cache.registry
    now = time.time()
    today = datetime.date.today()
    failed_symbol_list: List[str] = []
    all_symbol_list = list(dict.fromkeys(MARKET_GAUGE_SYMBOL_LIST + settings.watchlist_symbol_list))
    history_by_symbol, price_fetched_at = refresh_scheduler_load_price_history_by_symbol(all_symbol_list, fetch_cache)
    market_history_by_symbol = {symbol: history_by_symbol[symbol] for symbol in MARKET_GAUGE_SYMBOL_LIST if symbol in history_by_symbol}
    market_fetched_at = price_fetched_at
    ten_year_series, high_yield_series = live_indicators.live_indicators_fetch_treasury_series(fetch_cache)
    shared_indicator_value_by_name = live_indicators.live_indicators_stamp(
        indicator_calculation.indicator_calculation_build_market_indicator_value_by_name(
            market_history_by_symbol, ten_year_series, high_yield_series), market_fetched_at)
    for indicator_name_list, series in ((TREASURY_INDICATOR_NAME_LIST, ten_year_series), (HIGH_YIELD_INDICATOR_NAME_LIST, high_yield_series)):
        for indicator_name in indicator_name_list:  # a FRED figure is as old as its newest observation, not as old as the request
            if indicator_name in shared_indicator_value_by_name and series is not None and len(series):
                shared_indicator_value_by_name[indicator_name] = dataclasses.replace(
                    shared_indicator_value_by_name[indicator_name], observed_at=series.index[-1].to_pydatetime().replace(tzinfo=datetime.timezone.utc).timestamp())
    shared_indicator_value_by_name.update(live_indicators.live_indicators_fetch_series_value_by_name(fetch_cache))
    shared_indicator_value_by_name.update(live_indicators.live_indicators_stamp(
        refresh_scheduler_build_calendar_indicator_value_by_name(settings, today), now))
    ten_year_yield = shared_indicator_value_by_name.get("treasury_ten_year_yield")
    shared_indicator_value_by_name.update(live_indicators.live_indicators_build_equity_risk_premium_indicator_value_by_name(
        yahoo_company.yahoo_company_overlay_quote(
            live_indicators.live_indicators_fetch_company_snapshot(fetch_cache, "SPY"), fetch_cache.peek("yahoo_quote", "all", {}).get("SPY")), None if ten_year_yield is None else ten_year_yield.value))
    shared_indicator_value_by_name = indicator_registry.indicator_registry_drop_stale_values(shared_indicator_value_by_name, registry, now)

    symbol_history_by_symbol = {symbol: history_by_symbol[symbol] for symbol in settings.watchlist_symbol_list if symbol in history_by_symbol}
    symbol_fetched_at = price_fetched_at
    symbol_list = [s for s in settings.watchlist_symbol_list if s in symbol_history_by_symbol]
    failed_symbol_list += [s for s in settings.watchlist_symbol_list if s not in symbol_history_by_symbol]

    def evaluate_symbol_or_none(symbol: str) -> Optional[dict]:
        started = time.perf_counter()
        try:
            result = refresh_scheduler_evaluate_symbol_for_all_strategies(
                symbol, symbol_history_by_symbol[symbol], shared_indicator_value_by_name, settings,
                strategy_definition_by_id, market_history_by_symbol, fetch_cache, symbol_fetched_at)
            run_log_write("symbol {} ok {:.2f}s".format(symbol, time.perf_counter() - started))
            return result
        except Exception as error:  # one broken symbol must not abort the whole snapshot
            run_log_write("symbol {} FAILED {:.2f}s {}".format(symbol, time.perf_counter() - started, str(error)[:120]))
            return None

    with ThreadPoolExecutor(max_workers=SYMBOL_WORKER_COUNT) as executor:
        symbol_result_or_none_list = list(executor.map(evaluate_symbol_or_none, symbol_list))
    symbol_result_list = [result for result in symbol_result_or_none_list if result is not None]
    failed_symbol_list += [s for s, r in zip(symbol_list, symbol_result_or_none_list) if r is None]

    market_indicator_card_list = []
    for indicator_setting in settings.market_indicator_list:
        indicator_value = shared_indicator_value_by_name.get(indicator_setting.indicator_name)
        market_indicator_card_list.append({
            "indicator_name": indicator_setting.indicator_name, "display_name": dataclasses.asdict(indicator_setting.display_name),
            "is_higher_value_risky": indicator_setting.is_higher_value_risky,
            "value": None if indicator_value is None else indicator_value.value,
            "change_value": None if indicator_value is None else indicator_value.change_value,
            "change_unit": None if indicator_value is None else indicator_value.change_unit,
        })
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": refresh_scheduler_get_current_exchange_time_text(),
        "prices_as_of": None if symbol_fetched_at is None else datetime.datetime.fromtimestamp(
            symbol_fetched_at, market_data.NEW_YORK_TIME_ZONE).replace(microsecond=0).isoformat(),
        "market_indicator_card_list": market_indicator_card_list,
        "symbol_result_list": symbol_result_list,
        "failed_symbol_list": failed_symbol_list,
    }


def refresh_scheduler_get_current_exchange_time_text() -> str:
    """ISO 8601 in New York time with offset, for example 2026-10-23T15:52:19-04:00."""
    return datetime.datetime.now(market_data.NEW_YORK_TIME_ZONE).replace(microsecond=0).isoformat()


def refresh_scheduler_refresh_snapshot_file(
    settings: ApplicationSettings, strategy_definition_by_id: Dict[str, StrategyDefinition],
) -> dict:
    started = time.perf_counter()
    snapshot = refresh_scheduler_build_dashboard_snapshot(settings, strategy_definition_by_id)
    snapshot_storage.snapshot_storage_save_snapshot_to_json_file(snapshot, SNAPSHOT_FILE_PATH)
    for symbol_result in snapshot["symbol_result_list"]:  # the same results, one file per symbol: data/symbols/<SYMBOL>/result.json
        snapshot_storage.snapshot_storage_save_snapshot_to_json_file(symbol_result, os.path.join(
            DATA_DIRECTORY, "symbols", fetch_store.fetch_store_safe_name(symbol_result["symbol"]), "result.json"))
    run_log_write("refresh done {:.1f}s symbols ok {} failed {} {}".format(
        time.perf_counter() - started, len(snapshot["symbol_result_list"]), len(snapshot["failed_symbol_list"]), snapshot["failed_symbol_list"]))
    return snapshot


def refresh_scheduler_determine_whether_refresh_is_due(settings: ApplicationSettings, fetch_cache: Optional[FetchCache] = None) -> bool:
    """Due when there is no snapshot yet, when its symbols are not the ones in config/symbols.yaml, when the market is open and the snapshot is old enough, or when some source is due again
    (this also catches the after-hours times in config/indicators.yaml: prices after the close, slow data before the open)."""
    snapshot = snapshot_storage.snapshot_storage_load_snapshot_from_json_file(SNAPSHOT_FILE_PATH)
    if snapshot is None or snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        return True
    followed_symbol_set = {card["symbol"] for card in snapshot.get("symbol_result_list", [])} | set(snapshot.get("failed_symbol_list", []))
    if followed_symbol_set != set(settings.watchlist_symbol_list):
        return True  # config/symbols.yaml changed: build the snapshot again now, not at the next due time
    is_market_open = market_data.market_data_determine_whether_us_market_is_open(
        datetime.datetime.now(datetime.timezone.utc), settings.market_holiday_date_set,
        settings.market_early_close_date_set)
    age_minutes = (time.time() - os.path.getmtime(SNAPSHOT_FILE_PATH)) / 60
    if is_market_open and age_minutes >= settings.refresh_interval_minutes:
        return True
    return (fetch_cache or refresh_scheduler_get_fetch_cache(settings)).is_anything_due()


def refresh_scheduler_start_background_refresh_thread(
    settings: ApplicationSettings, strategy_definition_by_id: Dict[str, StrategyDefinition],
) -> threading.Thread:
    def loop() -> None:
        while True:
            try:
                if refresh_scheduler_determine_whether_refresh_is_due(settings):
                    refresh_scheduler_refresh_snapshot_file(settings, strategy_definition_by_id)
            except Exception as error:  # keep the loop alive through network or data errors
                print("refresh failed:", error)
            time.sleep(POLL_SECONDS)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__" and "--once" in sys.argv:
    from stock_benchmark_backend import rule_catalog, settings_loader, strategy_loader
    loaded_settings = settings_loader.settings_loader_load_settings_from_yaml_file(
        os.path.join(PROJECT_DIRECTORY, "config", "settings.yaml"))
    loaded_strategies = strategy_loader.strategy_loader_load_all_strategy_definitions_from_directory(
        os.path.join(PROJECT_DIRECTORY, "config", "strategies"), rule_catalog.rule_catalog_load_rule_catalog_from_yaml_file(
            os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml")))
    result = refresh_scheduler_refresh_snapshot_file(loaded_settings, loaded_strategies)
    print(result["generated_at"], len(result["symbol_result_list"]), "symbols, failed:", result["failed_symbol_list"])
    for symbol_result in result["symbol_result_list"]:
        evaluation = symbol_result["evaluation_by_strategy_id"][loaded_settings.default_strategy_id]
        print(symbol_result["symbol"], "pass:", evaluation["is_pass"], "score:", evaluation["score_percent"],
              "unknown:", evaluation["unknown_weight_ratio"])
