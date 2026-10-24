"""Build the dashboard snapshot and refresh it in the background."""
import dataclasses
import datetime
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from stockboard_backend import (indicator_calculation, macro_data, market_data, option_chain,
                                snapshot_storage, strategy_evaluation)
from stockboard_backend.settings_loader import ApplicationSettings, PROJECT_DIRECTORY
from stockboard_backend.strategy_evaluation import IndicatorValue, StrategyDefinition

SNAPSHOT_FILE_PATH = os.path.join(PROJECT_DIRECTORY, "data", "latest_snapshot.json")
MARKET_GAUGE_SYMBOL_LIST = ["^VIX", "^VXN", "^VVIX", "^VIX3M", "^GSPC"]
HISTORY_PERIOD = "1y"
SYMBOL_WORKER_COUNT = 4
POLL_SECONDS = 60
SNAPSHOT_SCHEMA_VERSION = 2
SPARKLINE_TRADING_DAY_COUNT = 60


def refresh_scheduler_fetch_series_or_none(fetch_function):
    try:
        return fetch_function()
    except Exception as error:  # a failed source only makes its indicators unknown
        print("fetch failed:", fetch_function.__name__, error)
        return None


def refresh_scheduler_build_option_indicator_value_by_window_label(
    symbol: str, underlying_price: float, realized_volatility_percent: Optional[float],
    settings: ApplicationSettings, risk_free_rate_percent: float, today: datetime.date,
) -> Dict[str, Dict[str, IndicatorValue]]:
    expiration_date_list = option_chain.option_chain_fetch_expiration_date_list_by_symbol(symbol)
    put_table_by_expiration_date = {}
    indicator_by_window_label = {}
    for window in settings.option_expiration_window_list:
        expiration_date = option_chain.option_chain_determine_expiration_within_day_window(
            expiration_date_list, window.minimum_days, window.maximum_days, today)
        selected_contract = None
        if expiration_date is not None:
            if expiration_date not in put_table_by_expiration_date:
                put_table_by_expiration_date[expiration_date] = (
                    option_chain.option_chain_fetch_put_contract_table_by_symbol_and_expiration(symbol, expiration_date))
            selected_contract = option_chain.option_chain_determine_representative_put_contract_from_table(
                put_table_by_expiration_date[expiration_date], underlying_price, expiration_date, today,
                settings.target_absolute_delta, risk_free_rate_percent)
        indicator_by_window_label[window.label] = (
            indicator_calculation.indicator_calculation_build_option_indicator_value_by_id(
                selected_contract, realized_volatility_percent))
    return indicator_by_window_label


def refresh_scheduler_evaluate_symbol_for_all_strategies(
    symbol: str, price_history, shared_indicator_value_by_id: Dict[str, IndicatorValue],
    settings: ApplicationSettings, strategy_definition_by_id: Dict[str, StrategyDefinition],
) -> dict:
    today = datetime.date.today()
    try:
        next_earnings_date = market_data.market_data_fetch_next_earnings_date_by_symbol(symbol)
        is_earnings_date_known = True
    except Exception as error:
        print("earnings failed:", symbol, error)
        next_earnings_date, is_earnings_date_known = None, False
    symbol_indicator_value_by_id = indicator_calculation.indicator_calculation_build_symbol_indicator_value_by_id(
        price_history, is_earnings_date_known, next_earnings_date,
        settings.option_expiration_window_list[0].maximum_days, today)

    realized_volatility = symbol_indicator_value_by_id.get("realized_volatility_thirty_day")
    ten_year_yield = shared_indicator_value_by_id.get("treasury_ten_year_yield")
    try:
        option_indicator_by_window_label = refresh_scheduler_build_option_indicator_value_by_window_label(
            symbol, float(price_history["Close"].iloc[-1]),
            None if realized_volatility is None else realized_volatility.value, settings,
            ten_year_yield.value if ten_year_yield else option_chain.DEFAULT_RISK_FREE_RATE_PERCENT, today)
    except Exception as error:
        print("option chain failed:", symbol, error)
        option_indicator_by_window_label = {}

    combined_indicator_value_by_id = {**shared_indicator_value_by_id, **symbol_indicator_value_by_id}
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

    symbol_history_by_symbol = market_data.market_data_fetch_daily_price_history_for_symbol_list(
        settings.watchlist_symbol_list, HISTORY_PERIOD)
    symbol_list = [s for s in settings.watchlist_symbol_list if s in symbol_history_by_symbol]
    failed_symbol_list += [s for s in settings.watchlist_symbol_list if s not in symbol_history_by_symbol]

    def evaluate_symbol_or_none(symbol: str) -> Optional[dict]:
        try:
            return refresh_scheduler_evaluate_symbol_for_all_strategies(
                symbol, symbol_history_by_symbol[symbol], shared_indicator_value_by_id, settings,
                strategy_definition_by_id)
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
            "indicator_id": indicator_setting.indicator_id, "display_name": indicator_setting.display_name,
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
    from stockboard_backend import settings_loader, strategy_loader
    loaded_settings = settings_loader.settings_loader_load_settings_from_yaml_file(
        os.path.join(PROJECT_DIRECTORY, "config", "settings.yaml"))
    loaded_strategies = strategy_loader.strategy_loader_load_all_strategy_definitions_from_directory(
        os.path.join(PROJECT_DIRECTORY, "strategies"))
    result = refresh_scheduler_refresh_snapshot_file(loaded_settings, loaded_strategies)
    print(result["generated_at"], len(result["symbol_result_list"]), "symbols, failed:", result["failed_symbol_list"])
    for symbol_result in result["symbol_result_list"]:
        evaluation = symbol_result["evaluation_by_strategy_id"][loaded_settings.default_strategy_id]
        print(symbol_result["symbol"], "pass:", evaluation["is_pass"], "score:", evaluation["score_percent"],
              "unknown:", evaluation["unknown_weight_ratio"])
