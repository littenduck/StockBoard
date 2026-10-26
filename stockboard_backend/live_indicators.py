"""Fetch the slower sources for the live dashboard, each through the fetch cache so a source is asked only when it is due.

Every function that reaches the network takes the FetchCache and names its fetch group (see config/indicators.yaml); the cache decides, from the
group's fetch_every, market_hours_only and fetch_at, whether to ask again or hand back the last answer. Values carry observed_at so a value older
than its indicator's max_age is dropped later (indicator_registry_drop_stale_values).
"""
import dataclasses
import datetime
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import pandas
import yfinance

from stockboard_backend import (cboe_data, company_indicators, dolthub_data, edgar_data, finra_data, fundamental_series, history_series,
                                macro_data, sentiment_data, yahoo_company)
from stockboard_backend.fetch_cache import FetchCache
from stockboard_backend.indicator_registry import IndicatorRegistry
from stockboard_backend.strategy_evaluation import IndicatorValue

SERIES_WORKER_COUNT = 6
SERIES_GROUP_ID_LIST = ["fred", "cboe_put_call", "cnn", "aaii", "reference_files"]
SHORT_INTEREST_MAX_AGE_DAYS = 45
EDGAR_START_DAY = datetime.date(2018, 1, 1)  # six years of days: the PE median needs five years of earnings and prices
EDGAR_INDICATOR_ID_LIST = [
    "revenue_three_year_cagr_percent", "eps_three_year_cagr_percent", "return_on_invested_capital_percent",
    "free_cash_flow_year_over_year_change", "interest_coverage_ratio", "shares_outstanding_year_over_year_percent",
    "price_earnings_ttm_to_five_year_median_ratio",
]
SPMO_SYMBOL = "SPMO"
# These three come with the price figures (they carry a daily change), so the series job leaves them alone.
MADE_WITH_PRICE_FIGURES_INDICATOR_ID_SET = {
    "treasury_ten_year_yield", "treasury_ten_year_yield_twenty_day_change_basis_points", "high_yield_credit_spread_basis_points",
}


def live_indicators_stamp(value_by_id: Dict[str, IndicatorValue], observed_at: Optional[float]) -> Dict[str, IndicatorValue]:
    """Give every value that has no observation time the time its source was asked."""
    return {key: value if value.observed_at is not None or observed_at is None else dataclasses.replace(value, observed_at=observed_at)
            for key, value in value_by_id.items()}


def live_indicators_extract_latest_value(series: pandas.Series):
    """(newest value, time of its observation as epoch seconds), or None when the series is empty."""
    series = series.dropna()
    if series.empty:
        return None
    latest = series.iloc[-1]
    return (bool(latest) if series.dtype == bool else round(float(latest), 4)), series.index[-1].to_pydatetime().replace(
        tzinfo=datetime.timezone.utc).timestamp()


# ---- market wide series: FRED, Cboe, CNN, AAII and the reference files -----------------------------------------------------------

def live_indicators_run_series_job(indicator_id_list: List[str], group_id: str) -> Dict[str, IndicatorValue]:
    """Rebuild each indicator's series and keep its newest value. One failed series only drops its own indicator."""
    macro_data.fred_series_cache.clear()  # these module caches only spare repeat downloads inside one job
    cboe_data.index_history_cache.clear()
    sentiment_data.aaii_table_cache.clear()
    if group_id == "cboe_put_call":
        try:
            cboe_data.cboe_data_update_total_put_call_cache(history_series.PUT_CALL_CACHE_FILE_PATH)
        except Exception as error:  # the cache keeps whatever days it already has
            print("put/call cache update failed:", error)

    def fetch_one(indicator_id: str) -> Optional[IndicatorValue]:
        try:
            latest = live_indicators_extract_latest_value(history_series.HISTORY_SERIES_BUILDER_BY_INDICATOR_ID[indicator_id]())
        except Exception as error:
            print("series failed:", indicator_id, error)
            return None
        return None if latest is None else IndicatorValue(indicator_id, latest[0], "history series", observed_at=latest[1])

    with ThreadPoolExecutor(max_workers=SERIES_WORKER_COUNT) as executor:
        value_list = list(executor.map(fetch_one, indicator_id_list))
    return {value.indicator_id: value for value in value_list if value is not None}


def live_indicators_fetch_series_value_by_id(fetch_cache: FetchCache) -> Dict[str, IndicatorValue]:
    """The newest value of every market wide series indicator, each group asked only when due."""
    registry: IndicatorRegistry = fetch_cache.registry
    value_by_id: Dict[str, IndicatorValue] = {}
    for group_id in SERIES_GROUP_ID_LIST:
        indicator_id_list = [indicator.indicator_id for indicator in registry.indicator_by_id.values()
                             if indicator.fetch_group == group_id and indicator.status == "built"
                             and indicator.indicator_id in history_series.HISTORY_SERIES_BUILDER_BY_INDICATOR_ID
                             and indicator.indicator_id not in MADE_WITH_PRICE_FIGURES_INDICATOR_ID_SET]
        value_by_group, _ = fetch_cache.get(
            group_id, None, lambda ids=indicator_id_list, group=group_id: live_indicators_run_series_job(ids, group), default={})
        value_by_id.update(value_by_group)
    return value_by_id


def live_indicators_fetch_treasury_series(fetch_cache: FetchCache) -> Tuple[Optional[pandas.Series], Optional[pandas.Series]]:
    """The 10-year yield and the high yield spread (FRED group), used for the sidebar cards and the risk free rate."""
    def fetch():
        macro_data.fred_series_cache.clear()
        return macro_data.macro_data_fetch_treasury_ten_year_yield_series(), macro_data.macro_data_fetch_high_yield_credit_spread_series()
    series_pair, _ = fetch_cache.get("fred", "treasury", fetch, default=(None, None))
    return series_pair


# ---- company figures from yfinance --------------------------------------------------------------------------------------------

def live_indicators_fetch_company_snapshot(fetch_cache: FetchCache, symbol: str) -> dict:
    """info, eps_trend, recommendations_summary, insider_transactions and calendar, from one Yahoo request (a fund simply has fewer)."""
    snapshot, fetched_at = fetch_cache.get(
        "yahoo_company", symbol, lambda: yahoo_company.yahoo_company_fetch_snapshot(symbol), default={"info": None})
    return {**snapshot, "fetched_at": fetched_at}


def live_indicators_build_company_indicator_value_by_id(snapshot: dict, today: datetime.date) -> Dict[str, IndicatorValue]:
    info = snapshot["info"] if isinstance(snapshot.get("info"), dict) else {}
    value_by_id = company_indicators.company_indicators_build_info_indicator_value_by_id(info)
    value_by_id.update(company_indicators.company_indicators_build_estimate_indicator_value_by_id(
        snapshot.get("eps_trend"), snapshot.get("recommendations_summary"), company_indicators.company_indicators_get_number(info, "forwardPE")))
    value_by_id.update(company_indicators.company_indicators_build_insider_indicator_value_by_id(
        snapshot.get("insider_transactions"), company_indicators.company_indicators_get_number(info, "sharesOutstanding"), today))
    value_by_id = {key: IndicatorValue(key, value, "yfinance") for key, value in value_by_id.items()}
    return live_indicators_stamp(value_by_id, snapshot.get("fetched_at"))


def live_indicators_fetch_short_interest_indicator_value_by_id(
    fetch_cache: FetchCache, symbol: str, shares_outstanding: Optional[float], today: datetime.date,
) -> Dict[str, IndicatorValue]:
    table, _ = fetch_cache.get("finra", symbol, lambda: finra_data.finra_data_fetch_short_interest_table(symbol), default=None)
    value_by_id = live_indicators_build_short_interest_indicator_value_by_id(table, shares_outstanding, today)
    observed_at = None if table is None or table.empty else table.index[-1].to_pydatetime().replace(tzinfo=datetime.timezone.utc).timestamp()
    return {key: IndicatorValue(key, value, "FINRA", observed_at=observed_at) for key, value in value_by_id.items()}


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


# ---- SEC EDGAR, DoltHub, SPMO -------------------------------------------------------------------------------------------------

def live_indicators_fetch_edgar_indicator_value_by_id(fetch_cache: FetchCache, symbol: str, today: datetime.date) -> Dict[str, IndicatorValue]:
    """Multi year growth, interest coverage, the PE against its five year median and the audit check, from SEC filings.
    Needs EDGAR_CONTACT. A fund or a ticker SEC does not list gives nothing, and is not asked again until the next due time."""
    if not os.environ.get("EDGAR_CONTACT"):
        return {}

    def fetch() -> Dict[str, float]:
        try:
            company_facts = edgar_data.edgar_data_fetch_company_facts(symbol)
        except KeyError:
            return {}  # not a company SEC lists (a fund)
        days = pandas.date_range(EDGAR_START_DAY, today, freq="D")
        table = fundamental_series.fundamental_series_build_table(company_facts, days, live_indicators_fetch_price_series_or_none(symbol))
        last_row = table.iloc[-1]
        value_by_name = {name: round(float(last_row[name]), 4) for name in EDGAR_INDICATOR_ID_LIST
                         if name in table.columns and pandas.notna(last_row[name])}
        has_problem = edgar_data.edgar_data_find_audit_or_late_filing_problem(edgar_data.edgar_data_fetch_submissions(symbol), today)
        value_by_name["no_audit_or_late_filing_problem_in_last_365_days"] = not has_problem
        return value_by_name

    value_by_name, fetched_at = fetch_cache.get("edgar", symbol, fetch, default={})
    return live_indicators_stamp({name: IndicatorValue(name, value, "SEC EDGAR") for name, value in value_by_name.items()}, fetched_at)


def live_indicators_fetch_implied_volatility_indicator_value_by_id(
    fetch_cache: FetchCache, symbol: str, today: datetime.date,
) -> Dict[str, IndicatorValue]:
    """IV percentile over a year and IV against a month ago, from the DoltHub history."""
    def fetch() -> Dict[str, float]:
        return dolthub_data.dolthub_data_build_indicator_value_by_id(dolthub_data.dolthub_data_fetch_implied_volatility_series(symbol, today), today)
    value_by_name, fetched_at = fetch_cache.get("dolthub_iv", symbol, fetch, default={})
    return live_indicators_stamp({name: IndicatorValue(name, value, "DoltHub") for name, value in value_by_name.items()}, fetched_at)


def live_indicators_fetch_spmo_rank_by_symbol(fetch_cache: FetchCache) -> Dict[str, int]:
    """Rank in SPMO's ten largest holdings (1 is the largest). A stock outside the ten has no rank here: its rules read unknown."""
    def fetch() -> Dict[str, int]:
        holding_table = yfinance.Ticker(SPMO_SYMBOL).funds_data.top_holdings
        return {str(symbol).upper(): rank for rank, symbol in enumerate(holding_table.index, start=1)}
    rank_by_symbol, _ = fetch_cache.get("spmo_holdings", None, fetch, default={})
    return rank_by_symbol


def live_indicators_build_equity_risk_premium_indicator_value_by_id(
    spy_snapshot: dict, ten_year_yield_percent: Optional[float],
) -> Dict[str, IndicatorValue]:
    """Earnings yield of the S&P 500 (from SPY's trailing PE) minus the 10-year Treasury yield, in percent points."""
    trailing_pe = company_indicators.company_indicators_get_number(spy_snapshot.get("info") or {}, "trailingPE")
    if not trailing_pe or trailing_pe <= 0 or ten_year_yield_percent is None:
        return {}
    value = round(100 / trailing_pe - ten_year_yield_percent, 3)
    return live_indicators_stamp({"equity_risk_premium_simple_percent": IndicatorValue(
        "equity_risk_premium_simple_percent", value, "yfinance SPY, FRED DGS10")}, spy_snapshot.get("fetched_at"))
