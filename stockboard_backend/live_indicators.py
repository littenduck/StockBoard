"""Fetch the slower sources for the live dashboard and keep them for a while so a ten minute refresh does not ask again.

Market wide figures come from the history series (FRED, Cboe, CNN, AAII): the latest value counts only if it is recent enough.
Company figures come from yfinance (info, estimates, ratings, insider trades) and SEC EDGAR (multi year growth), each kept for a time.
"""
import datetime
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Optional, Tuple

import pandas
import yfinance

from stockboard_backend import (cboe_data, company_indicators, edgar_data, finra_data, fundamental_series, history_series, macro_data,
                                sentiment_data)
from stockboard_backend.strategy_evaluation import IndicatorValue

SERIES_CACHE_SECONDS = 30 * 60
COMPANY_CACHE_SECONDS = 60 * 60
SERIES_WORKER_COUNT = 6
SHORT_INTEREST_MAX_AGE_DAYS = 45
EDGAR_START_DAY = datetime.date(2020, 1, 1)
EDGAR_INDICATOR_ID_LIST = [
    "revenue_three_year_cagr_percent", "eps_three_year_cagr_percent", "return_on_invested_capital_percent",
    "free_cash_flow_year_over_year_change", "interest_coverage_ratio", "shares_outstanding_year_over_year_percent",
]
DAILY_DAYS, WEEKLY_DAYS, MONTHLY_DAYS, QUARTERLY_DAYS = 10, 16, 100, 270
# A series is used only while its newest observation is no older than this, so a source that stops updating reads unknown.
# Monthly and quarterly observations are dated the first day of their period and published one to three months later, hence the long limits.
MAX_AGE_DAYS_BY_SERIES_INDICATOR_ID = {
    "federal_funds_target_rate_not_raised_in_182_days": DAILY_DAYS,
    "six_month_treasury_bill_yield_minus_federal_funds_rate": DAILY_DAYS,
    "high_yield_credit_spread_twenty_day_change_basis_points": DAILY_DAYS,
    "moodys_baa_minus_ten_year_treasury_spread": DAILY_DAYS,
    "treasury_ten_year_minus_two_year_spread": DAILY_DAYS,
    "treasury_ten_year_minus_three_month_spread": DAILY_DAYS,
    "us_epu_thirty_day_average_percentile_five_year": DAILY_DAYS,
    "put_call_ratio_total_five_day_average": 7,
    "fear_greed_index": 5,
    "initial_jobless_claims_four_week_average": WEEKLY_DAYS,
    "federal_reserve_total_assets_thirteen_week_change_percent": WEEKLY_DAYS,
    "aaii_bullish_percent": WEEKLY_DAYS,
    "aaii_bullish_minus_bearish_percent": WEEKLY_DAYS,
    "consumer_price_index_year_over_year_percent": MONTHLY_DAYS,
    "core_pce_price_index_year_over_year_percent": MONTHLY_DAYS,
    "sahm_rule_recession_indicator": MONTHLY_DAYS,
    "chicago_fed_national_activity_index_three_month_average": MONTHLY_DAYS,
    "m2_money_supply_year_over_year_percent": MONTHLY_DAYS,
    "trade_policy_uncertainty_ten_year_percentile": MONTHLY_DAYS,
    "market_value_to_gdp_percent": QUARTERLY_DAYS,
}
series_cache: Dict[str, object] = {"loaded_at": 0.0, "value_by_id": {}}
company_cache: Dict[str, Tuple[float, dict]] = {}
edgar_cache: Dict[Tuple[str, datetime.date], Dict[str, float]] = {}
cache_lock = threading.Lock()


def live_indicators_extract_latest_value(series: pandas.Series, max_age_days: int, today: datetime.date):
    """The newest value, or None when the series is empty or its newest observation is too old."""
    series = series.dropna()
    if series.empty or (today - series.index[-1].date()).days > max_age_days:
        return None
    latest = series.iloc[-1]
    return bool(latest) if series.dtype == bool else round(float(latest), 4)


def live_indicators_fetch_series_indicator_value_by_id(today: Optional[datetime.date] = None) -> Dict[str, IndicatorValue]:
    """FRED, Cboe, CNN and AAII figures. One failed source only drops its own indicators. Kept for 30 minutes."""
    with cache_lock:
        if time.time() - series_cache["loaded_at"] < SERIES_CACHE_SECONDS and series_cache["value_by_id"]:
            return dict(series_cache["value_by_id"])
    today = today or datetime.date.today()
    macro_data.fred_series_cache.clear()
    cboe_data.index_history_cache.clear()
    sentiment_data.aaii_table_cache.clear()
    try:
        cboe_data.cboe_data_update_total_put_call_cache(history_series.PUT_CALL_CACHE_FILE_PATH)
    except Exception as error:  # the cache keeps whatever days it already has
        print("put/call cache update failed:", error)

    def fetch_one(indicator_id: str) -> Tuple[str, Optional[IndicatorValue]]:
        try:
            value = live_indicators_extract_latest_value(
                history_series.HISTORY_SERIES_BUILDER_BY_INDICATOR_ID[indicator_id](),
                MAX_AGE_DAYS_BY_SERIES_INDICATOR_ID[indicator_id], today)
        except Exception as error:
            print("series failed:", indicator_id, error)
            return indicator_id, None
        return indicator_id, None if value is None else IndicatorValue(indicator_id, value, "history series")

    with ThreadPoolExecutor(max_workers=SERIES_WORKER_COUNT) as executor:
        result_list = list(executor.map(fetch_one, MAX_AGE_DAYS_BY_SERIES_INDICATOR_ID))
    value_by_id = {indicator_id: value for indicator_id, value in result_list if value is not None}
    with cache_lock:
        series_cache.update(loaded_at=time.time(), value_by_id=value_by_id)
    return dict(value_by_id)


def live_indicators_fetch_company_snapshot(symbol: str) -> dict:
    """info, eps_trend, recommendations_summary and insider_transactions from yfinance; each piece may come back None."""
    with cache_lock:
        cached = company_cache.get(symbol)
        if cached and time.time() - cached[0] < COMPANY_CACHE_SECONDS:
            return cached[1]
    ticker = yfinance.Ticker(symbol)
    snapshot = {"info": None, "eps_trend": None, "recommendations_summary": None, "insider_transactions": None, "calendar": None}
    try:
        snapshot["info"] = ticker.info
    except Exception as error:
        print("company data failed:", symbol, "info", error)
    is_fund = isinstance(snapshot["info"], dict) and snapshot["info"].get("quoteType") == "ETF"
    for key in () if is_fund else ("eps_trend", "recommendations_summary", "insider_transactions", "calendar"):  # a fund has none of these
        try:
            snapshot[key] = getattr(ticker, key)
        except Exception as error:
            print("company data failed:", symbol, key, error)
    try:
        snapshot["short_interest"] = finra_data.finra_data_fetch_short_interest_table(symbol)
    except Exception as error:
        print("short interest failed:", symbol, error)
        snapshot["short_interest"] = None
    with cache_lock:
        company_cache[symbol] = (time.time(), snapshot)
    return snapshot


def live_indicators_build_company_indicator_value_by_id(symbol: str, today: datetime.date) -> Dict[str, IndicatorValue]:
    snapshot = live_indicators_fetch_company_snapshot(symbol)
    info = snapshot["info"] if isinstance(snapshot["info"], dict) else {}
    value_by_id = company_indicators.company_indicators_build_info_indicator_value_by_id(info)
    value_by_id.update(company_indicators.company_indicators_build_estimate_indicator_value_by_id(
        snapshot["eps_trend"], snapshot["recommendations_summary"], company_indicators.company_indicators_get_number(info, "forwardPE")))
    value_by_id.update(company_indicators.company_indicators_build_insider_indicator_value_by_id(
        snapshot["insider_transactions"], company_indicators.company_indicators_get_number(info, "sharesOutstanding"), today))
    value_by_id.update(live_indicators_build_short_interest_indicator_value_by_id(
        snapshot["short_interest"], company_indicators.company_indicators_get_number(info, "sharesOutstanding"), today))
    return {key: IndicatorValue(key, value, "yfinance") for key, value in value_by_id.items()}


def live_indicators_build_short_interest_indicator_value_by_id(
    short_interest: Optional[pandas.DataFrame], shares_outstanding: Optional[float], today: datetime.date,
) -> Dict[str, float]:
    """FINRA publishes twice a month; a figure older than 45 days is not used."""
    if short_interest is None or short_interest.empty or not shares_outstanding:
        return {}
    if (today - short_interest.index[-1].date()).days > SHORT_INTEREST_MAX_AGE_DAYS:
        return {}
    return {"short_interest_percent_of_shares_outstanding": round(float(short_interest["short_shares"].iloc[-1]) / shares_outstanding * 100, 4)}


def live_indicators_fetch_edgar_indicator_value_by_id(symbol: str, today: datetime.date) -> Dict[str, IndicatorValue]:
    """Multi year growth and interest coverage from SEC filings. Needs EDGAR_CONTACT; a fund or an unknown ticker gives nothing."""
    if not os.environ.get("EDGAR_CONTACT"):
        return {}
    key = (symbol, today)
    with cache_lock:
        cached = edgar_cache.get(key)
    if cached is None:
        try:
            company_facts = edgar_data.edgar_data_fetch_company_facts(symbol)
            days = pandas.date_range(EDGAR_START_DAY, today, freq="D")
            last_row = fundamental_series.fundamental_series_build_table(company_facts, days).iloc[-1]
            cached = {name: round(float(last_row[name]), 4) for name in EDGAR_INDICATOR_ID_LIST if pandas.notna(last_row[name])}
        except Exception as error:  # funds have no company facts; a failed download tries again tomorrow
            print("edgar failed:", symbol, error)
            cached = {}
        with cache_lock:
            edgar_cache[key] = cached
    return {name: IndicatorValue(name, value, "SEC EDGAR") for name, value in cached.items()}
