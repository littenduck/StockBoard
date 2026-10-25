"""Build the dashboard snapshot and refresh it in the background."""
import dataclasses
import datetime
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from stockboard_backend import (company_indicators, event_calendar, indicator_calculation, live_indicators, macro_data,
                                market_data, option_chain, snapshot_storage, strategy_evaluation)
from stockboard_backend.settings_loader import ApplicationSettings, PROJECT_DIRECTORY
from stockboard_backend.strategy_evaluation import IndicatorValue, StrategyDefinition

SNAPSHOT_FILE_PATH = os.path.join(PROJECT_DIRECTORY, "data", "latest_snapshot.json")
SECTOR_ETF_SYMBOL_LIST = sorted(set(company_indicators.SECTOR_ETF_BY_SECTOR_NAME.values()))
MARKET_GAUGE_SYMBOL_LIST = ["^VIX", "^VXN", "^VVIX", "^VIX3M", "^GSPC", "CL=F", "DX-Y.NYB", "SPY", "RSP"] + SECTOR_ETF_SYMBOL_LIST
SUPPORT_LOW_TRADING_DAY_COUNT = 60
COVERED_CALL_MINIMUM_DAYS, COVERED_CALL_MAXIMUM_DAYS = 25, 35
HISTORY_PERIOD = "1y"
SYMBOL_WORKER_COUNT = 4
POLL_SECONDS = 60
SNAPSHOT_SCHEMA_VERSION = 4
SPARKLINE_TRADING_DAY_COUNT = 60


def refresh_scheduler_fetch_series_or_none(fetch_function):
    try:
        return fetch_function()
    except Exception as error:  # a failed source only makes its indicators unknown
        print("fetch failed:", fetch_function.__name__, error)
        return None


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
    support_price: Optional[float] = None, dividend_snapshot: Optional[dict] = None,
) -> Dict[str, Dict[str, IndicatorValue]]:
    expiration_date_list = option_session.expiration_date_list()
    indicator_by_window_label = {}
    for window in settings.option_expiration_window_list:
        expiration_date = option_chain.option_chain_determine_expiration_within_day_window(
            expiration_date_list, window.minimum_days, window.maximum_days, today)
        selected_contract = None
        if expiration_date is not None:
            put_table = option_session.put_table(expiration_date)
            selected_contract = option_chain.option_chain_determine_representative_put_contract_from_table(
                put_table, underlying_price, expiration_date, today,
                settings.target_absolute_delta, risk_free_rate_percent)
        value_by_id = indicator_calculation.indicator_calculation_build_option_indicator_value_by_id(
            selected_contract, realized_volatility_percent, underlying_price, support_price,
            None if selected_contract is None else option_chain.option_chain_calculate_put_skew_points(
                put_table, underlying_price, selected_contract.days_to_expiration,
                risk_free_rate_percent))
        if expiration_date is not None:
            value_by_id.update(refresh_scheduler_build_option_life_indicator_value_by_id(
                settings, today, expiration_date, dividend_snapshot or {}))
        indicator_by_window_label[window.label] = value_by_id
    return indicator_by_window_label


def refresh_scheduler_build_covered_call_indicator_value_by_id(
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
    value_by_id = {"selected_call_days_to_expiration": (expiration_date - today).days}
    if premium_percent is not None:
        value_by_id["selected_call_strike_premium_percent"] = premium_percent
    return {key: IndicatorValue(key, value, "yfinance option chain") for key, value in value_by_id.items()}


def refresh_scheduler_build_option_life_indicator_value_by_id(
    settings: ApplicationSettings, today: datetime.date, expiration_date: datetime.date, dividend_snapshot: dict,
) -> Dict[str, IndicatorValue]:
    """Event answers for the days between today and the expiration. They need no option quote, so they are known after hours too."""
    covered_until = event_calendar.event_calendar_build_covered_until_by_event_name(settings.macro_event_covered_until)
    value_by_id = event_calendar.event_calendar_build_option_life_indicator_value_by_id(
        settings.macro_event_calendar, covered_until, today, expiration_date)
    info = dividend_snapshot.get("info") if isinstance(dividend_snapshot.get("info"), dict) else {}
    if info.get("dividendRate") or info.get("dividendYield"):
        last_ex_date = refresh_scheduler_find_next_ex_dividend_date(dividend_snapshot)
        value_by_id["no_ex_dividend_date_inside_option_life"] = None if last_ex_date is None else not (
            event_calendar.event_calendar_project_next_ex_dividend_date_list(last_ex_date, today, expiration_date))
    elif "trailingEps" in info:
        value_by_id["no_ex_dividend_date_inside_option_life"] = True  # a company that pays no dividend has no ex-dividend date
    return {key: IndicatorValue(key, value, "calendar") for key, value in value_by_id.items() if value is not None}


def refresh_scheduler_evaluate_symbol_for_all_strategies(
    symbol: str, price_history, shared_indicator_value_by_id: Dict[str, IndicatorValue],
    settings: ApplicationSettings, strategy_definition_by_id: Dict[str, StrategyDefinition],
    market_history_by_symbol: Optional[Dict[str, object]] = None,
) -> dict:
    today = datetime.date.today()
    market_history_by_symbol = market_history_by_symbol or {}
    try:
        company_snapshot = live_indicators.live_indicators_fetch_company_snapshot(symbol)
        company_indicator_value_by_id = live_indicators.live_indicators_build_company_indicator_value_by_id(symbol, today)
    except Exception as error:  # a symbol without company data keeps its price indicators
        print("company data failed:", symbol, error)
        company_snapshot, company_indicator_value_by_id = {}, {}
    company_indicator_value_by_id.update(live_indicators.live_indicators_fetch_edgar_indicator_value_by_id(symbol, today))
    company_indicator_value_by_id.update(live_indicators.live_indicators_fetch_implied_volatility_indicator_value_by_id(symbol, today))
    spmo_rank = live_indicators.live_indicators_fetch_spmo_rank_by_symbol().get(symbol)
    if spmo_rank is not None:
        company_indicator_value_by_id["spmo_holding_rank"] = IndicatorValue("spmo_holding_rank", spmo_rank, "yfinance SPMO")
    option_session = option_chain.OptionChainSession(symbol)
    company_indicator_value_by_id.update(refresh_scheduler_build_covered_call_indicator_value_by_id(
        option_session, float(price_history["Close"].iloc[-1]), today))
    info = company_snapshot.get("info") if isinstance(company_snapshot.get("info"), dict) else {}
    sector_etf_symbol = company_indicators.company_indicators_find_sector_etf_symbol(info)
    spy_history, sector_history = market_history_by_symbol.get("SPY"), market_history_by_symbol.get(sector_etf_symbol)
    try:
        next_earnings_date = market_data.market_data_fetch_next_earnings_date_by_symbol(symbol)
        is_earnings_date_known = True
    except Exception as error:
        print("earnings failed:", symbol, error)
        next_earnings_date, is_earnings_date_known = None, False
    symbol_indicator_value_by_id = indicator_calculation.indicator_calculation_build_symbol_indicator_value_by_id(
        price_history, is_earnings_date_known, next_earnings_date,
        settings.option_expiration_window_list[0].maximum_days, today,
        None if spy_history is None else spy_history["Close"], None if sector_history is None else sector_history["Close"])

    realized_volatility = symbol_indicator_value_by_id.get("realized_volatility_thirty_day")
    ten_year_yield = shared_indicator_value_by_id.get("treasury_ten_year_yield")
    try:
        option_indicator_by_window_label = refresh_scheduler_build_option_indicator_value_by_window_label(
            option_session, float(price_history["Close"].iloc[-1]),
            None if realized_volatility is None else realized_volatility.value, settings,
            ten_year_yield.value if ten_year_yield else option_chain.DEFAULT_RISK_FREE_RATE_PERCENT, today,
            float(price_history["Close"].iloc[-SUPPORT_LOW_TRADING_DAY_COUNT:].min()), company_snapshot)
    except Exception as error:
        print("option chain failed:", symbol, error)
        option_indicator_by_window_label = {}

    combined_indicator_value_by_id = {**shared_indicator_value_by_id, **company_indicator_value_by_id, **symbol_indicator_value_by_id}
    last_price = symbol_indicator_value_by_id["last_price"]
    return {
        "symbol": symbol,
        "price": last_price.value,
        "change_value": last_price.change_value,
        "change_unit": last_price.change_unit,
        "sparkline_close_price_list": [
            round(float(price), 2) for price in price_history["Close"].iloc[-SPARKLINE_TRADING_DAY_COUNT:]],
        "evaluation_by_strategy_id": {
            strategy_id: dataclasses.asdict(strategy_evaluation.strategy_evaluation_evaluate_strategy_for_symbol(
                strategy_definition, symbol, combined_indicator_value_by_id, option_indicator_by_window_label))
            for strategy_id, strategy_definition in strategy_definition_by_id.items()
        },
    }


def refresh_scheduler_build_calendar_indicator_value_by_id(
    settings: ApplicationSettings, today: datetime.date,
) -> Dict[str, IndicatorValue]:
    """Answers that depend on the date only (and on the release calendar in config/settings.yaml)."""
    covered_until = event_calendar.event_calendar_build_covered_until_by_event_name(settings.macro_event_covered_until)
    jobs_report_is_near = event_calendar.event_calendar_determine_whether_jobs_report_is_within_one_day(
        settings.macro_event_calendar, covered_until, today)
    value_by_id = {
        "no_quadruple_witching_in_next_five_trading_days":
            not event_calendar.event_calendar_determine_whether_quadruple_witching_is_within_trading_days(today),
        "is_spmo_rebalance_window": event_calendar.event_calendar_determine_whether_spmo_rebalance_month(today),
        "no_jobs_report_within_one_day": None if jobs_report_is_near is None else not jobs_report_is_near,
    }
    return {key: IndicatorValue(key, value, "calendar") for key, value in value_by_id.items() if value is not None}


def refresh_scheduler_build_dashboard_snapshot(
    settings: ApplicationSettings, strategy_definition_by_id: Dict[str, StrategyDefinition],
) -> dict:
    failed_symbol_list: List[str] = []
    market_history_by_symbol = market_data.market_data_fetch_daily_price_history_for_symbol_list(
        MARKET_GAUGE_SYMBOL_LIST, HISTORY_PERIOD)
    shared_indicator_value_by_id = indicator_calculation.indicator_calculation_build_market_indicator_value_by_id(
        market_history_by_symbol,
        refresh_scheduler_fetch_series_or_none(macro_data.macro_data_fetch_treasury_ten_year_yield_series),
        refresh_scheduler_fetch_series_or_none(macro_data.macro_data_fetch_high_yield_credit_spread_series))

    shared_indicator_value_by_id.update(refresh_scheduler_fetch_series_or_none(
        live_indicators.live_indicators_fetch_series_indicator_value_by_id) or {})
    shared_indicator_value_by_id.update(refresh_scheduler_build_calendar_indicator_value_by_id(settings, datetime.date.today()))
    ten_year_yield = shared_indicator_value_by_id.get("treasury_ten_year_yield")
    shared_indicator_value_by_id.update(live_indicators.live_indicators_build_equity_risk_premium_indicator_value_by_id(
        None if ten_year_yield is None else ten_year_yield.value))

    symbol_history_by_symbol = market_data.market_data_fetch_daily_price_history_for_symbol_list(
        settings.watchlist_symbol_list, HISTORY_PERIOD)
    symbol_list = [s for s in settings.watchlist_symbol_list if s in symbol_history_by_symbol]
    failed_symbol_list += [s for s in settings.watchlist_symbol_list if s not in symbol_history_by_symbol]

    def evaluate_symbol_or_none(symbol: str) -> Optional[dict]:
        try:
            return refresh_scheduler_evaluate_symbol_for_all_strategies(
                symbol, symbol_history_by_symbol[symbol], shared_indicator_value_by_id, settings,
                strategy_definition_by_id, market_history_by_symbol)
        except Exception as error:  # one broken symbol must not abort the whole snapshot
            print("symbol failed:", symbol, error)
            return None

    with ThreadPoolExecutor(max_workers=SYMBOL_WORKER_COUNT) as executor:
        symbol_result_or_none_list = list(executor.map(evaluate_symbol_or_none, symbol_list))
    symbol_result_list = [result for result in symbol_result_or_none_list if result is not None]
    failed_symbol_list += [s for s, r in zip(symbol_list, symbol_result_or_none_list) if r is None]

    market_indicator_card_list = []
    for indicator_setting in settings.market_indicator_list:
        indicator_value = shared_indicator_value_by_id.get(indicator_setting.indicator_id)
        market_indicator_card_list.append({
            "indicator_id": indicator_setting.indicator_id, "display_name": dataclasses.asdict(indicator_setting.display_name),
            "is_higher_value_risky": indicator_setting.is_higher_value_risky,
            "value": None if indicator_value is None else indicator_value.value,
            "change_value": None if indicator_value is None else indicator_value.change_value,
            "change_unit": None if indicator_value is None else indicator_value.change_unit,
        })
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": refresh_scheduler_get_current_exchange_time_text(),
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
    snapshot = refresh_scheduler_build_dashboard_snapshot(settings, strategy_definition_by_id)
    snapshot_storage.snapshot_storage_save_snapshot_to_json_file(snapshot, SNAPSHOT_FILE_PATH)
    return snapshot


def refresh_scheduler_determine_whether_refresh_is_due(settings: ApplicationSettings) -> bool:
    """Due when there is no snapshot yet, or the market is open and the snapshot is old enough."""
    snapshot = snapshot_storage.snapshot_storage_load_snapshot_from_json_file(SNAPSHOT_FILE_PATH)
    if snapshot is None or snapshot.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        return True
    is_market_open = market_data.market_data_determine_whether_us_market_is_open(
        datetime.datetime.now(datetime.timezone.utc), settings.market_holiday_date_set,
        settings.market_early_close_date_set)
    age_minutes = (time.time() - os.path.getmtime(SNAPSHOT_FILE_PATH)) / 60
    return is_market_open and age_minutes >= settings.refresh_interval_minutes


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
    from stockboard_backend import rule_catalog, settings_loader, strategy_loader
    loaded_settings = settings_loader.settings_loader_load_settings_from_yaml_file(
        os.path.join(PROJECT_DIRECTORY, "config", "settings.yaml"))
    loaded_strategies = strategy_loader.strategy_loader_load_all_strategy_definitions_from_directory(
        os.path.join(PROJECT_DIRECTORY, "strategies"), rule_catalog.rule_catalog_load_rule_catalog_from_yaml_file(
            os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml")))
    result = refresh_scheduler_refresh_snapshot_file(loaded_settings, loaded_strategies)
    print(result["generated_at"], len(result["symbol_result_list"]), "symbols, failed:", result["failed_symbol_list"])
    for symbol_result in result["symbol_result_list"]:
        evaluation = symbol_result["evaluation_by_strategy_id"][loaded_settings.default_strategy_id]
        print(symbol_result["symbol"], "pass:", evaluation["is_pass"], "score:", evaluation["score_percent"],
              "unknown:", evaluation["unknown_weight_ratio"])
