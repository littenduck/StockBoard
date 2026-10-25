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

from stockboard_backend import (cboe_data, company_indicators, dolthub_data, edgar_data, finra_data, fundamental_series, history_series,
                                macro_data, sentiment_data)
from stockboard_backend.strategy_evaluation import IndicatorValue

SERIES_CACHE_SECONDS = 30 * 60
COMPANY_CACHE_SECONDS = 60 * 60
SERIES_WORKER_COUNT = 6
SHORT_INTEREST_MAX_AGE_DAYS = 45
EDGAR_START_DAY = datetime.date(2018, 1, 1)  # six years of days: the PE median needs five years of earnings and prices
EDGAR_INDICATOR_ID_LIST = [
    "revenue_three_year_cagr_percent", "eps_three_year_cagr_percent", "return_on_invested_capital_percent",
    "free_cash_flow_year_over_year_change", "interest_coverage_ratio", "shares_outstanding_year_over_year_percent",
    "price_earnings_ttm_to_five_year_median_ratio",
]
SLOW_COMPANY_CACHE_SECONDS = 6 * 60 * 60
SPMO_SYMBOL = "SPMO"
FAILED_RETRY_SECONDS = 15 * 60
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
    "shiller_cape": 45,
    "damodaran_implied_equity_risk_premium_percent": 75,
    "geopolitical_risk_index_thirty_day_average_percentile_five_year": 14,
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


def live_indicators_fetch_price_series_or_none(symbol: str) -> Optional[pandas.Series]:
    try:
        close = yfinance.Ticker(symbol).history(period="7y", auto_adjust=False)["Close"]
        close.index = close.index.tz_localize(None).normalize()
        return close
    except Exception as error:
        print("price history failed:", symbol, error)
        return None


def live_indicators_fetch_edgar_indicator_value_by_id(symbol: str, today: datetime.date) -> Dict[str, IndicatorValue]:
    """Multi year growth, interest coverage, the PE against its five year median and the audit check, from SEC filings.
    Needs EDGAR_CONTACT; a fund or an unknown ticker gives nothing. Kept for the day."""
    if not os.environ.get("EDGAR_CONTACT"):
        return {}
    key = (symbol, today)
    with cache_lock:
        cached = edgar_cache.get(key)
    if cached is None:
        cached = {}
        try:
            company_facts = edgar_data.edgar_data_fetch_company_facts(symbol)
            days = pandas.date_range(EDGAR_START_DAY, today, freq="D")
            table = fundamental_series.fundamental_series_build_table(company_facts, days, live_indicators_fetch_price_series_or_none(symbol))
            last_row = table.iloc[-1]
            cached = {name: round(float(last_row[name]), 4) for name in EDGAR_INDICATOR_ID_LIST
                      if name in table.columns and pandas.notna(last_row[name])}
            has_problem = edgar_data.edgar_data_find_audit_or_late_filing_problem(edgar_data.edgar_data_fetch_submissions(symbol), today)
            cached["no_audit_or_late_filing_problem_in_last_365_days"] = not has_problem
        except Exception as error:  # funds have no company facts; a failed download tries again tomorrow
            print("edgar failed:", symbol, error)
        with cache_lock:
            edgar_cache[key] = cached
    return {name: IndicatorValue(name, value, "SEC EDGAR") for name, value in cached.items()}


def live_indicators_fetch_implied_volatility_indicator_value_by_id(symbol: str, today: datetime.date) -> Dict[str, IndicatorValue]:
    """IV percentile over a year and IV against a month ago, from the DoltHub history. Kept for six hours."""
    key = f"iv:{symbol}"
    with cache_lock:
        cached = company_cache.get(key)
    if cached and time.time() - cached[0] < SLOW_COMPANY_CACHE_SECONDS:
        value_by_id = cached[1]
    else:
        try:
            value_by_id = dolthub_data.dolthub_data_build_indicator_value_by_id(
                dolthub_data.dolthub_data_fetch_implied_volatility_series(symbol, today), today)
            loaded_at = time.time()
        except Exception as error:
            print("implied volatility history failed:", symbol, error)
            value_by_id, loaded_at = {}, time.time() - SLOW_COMPANY_CACHE_SECONDS + FAILED_RETRY_SECONDS  # try again in 15 minutes
        with cache_lock:
            company_cache[key] = (loaded_at, value_by_id)
    return {name: IndicatorValue(name, value, "DoltHub") for name, value in value_by_id.items()}


def live_indicators_fetch_spmo_rank_by_symbol() -> Dict[str, int]:
    """Rank in SPMO's ten largest holdings (1 is the largest). A stock outside the ten has no rank here: its rules read unknown."""
    with cache_lock:
        cached = company_cache.get("spmo")
    if cached and time.time() - cached[0] < SLOW_COMPANY_CACHE_SECONDS:
        return cached[1]
    try:
        holding_table = yfinance.Ticker(SPMO_SYMBOL).funds_data.top_holdings
        rank_by_symbol = {str(symbol).upper(): rank for rank, symbol in enumerate(holding_table.index, start=1)}
    except Exception as error:
        print("SPMO holdings failed:", error)
        rank_by_symbol = {}
    with cache_lock:
        company_cache["spmo"] = (time.time(), rank_by_symbol)
    return rank_by_symbol


def live_indicators_build_equity_risk_premium_indicator_value_by_id(ten_year_yield_percent: Optional[float]) -> Dict[str, IndicatorValue]:
    """Earnings yield of the S&P 500 (from SPY's trailing PE) minus the 10-year Treasury yield, in percent points."""
    try:
        trailing_pe = company_indicators.company_indicators_get_number(live_indicators_fetch_company_snapshot("SPY")["info"] or {}, "trailingPE")
    except Exception as error:
        print("S&P 500 PE failed:", error)
        return {}
    if not trailing_pe or trailing_pe <= 0 or ten_year_yield_percent is None:
        return {}
    value = round(100 / trailing_pe - ten_year_yield_percent, 3)
    return {"equity_risk_premium_simple_percent": IndicatorValue("equity_risk_premium_simple_percent", value, "yfinance SPY, FRED DGS10")}
