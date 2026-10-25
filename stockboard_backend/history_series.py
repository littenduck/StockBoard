"""Time series of the indicator values behind the rules, rebuilt from free history (FRED and Cboe).

Each indicator id used in config/rules.yaml maps to a function that returns a pandas.Series indexed by date, with the value the
rule's operator tests. A backtest reads these series; the live dashboard will use the same definitions.
Run `python -m stockboard_backend.history_series` to fetch every series and compare it with the catalog.
"""
import os
from typing import Callable, Dict, Optional

import pandas

from stockboard_backend import cboe_data, edgar_data, finra_data, fundamental_series, macro_data, reference_data, sentiment_data
from stockboard_backend.settings_loader import PROJECT_DIRECTORY

PUT_CALL_CACHE_FILE_PATH = os.path.join(PROJECT_DIRECTORY, "data", "cache", cboe_data.PUT_CALL_CACHE_FILE_NAME)
TRADING_DAYS_PER_MONTH = 21
EPU_FIVE_YEAR_DAYS = 5 * 365
EPU_THIRTY_DAYS = 30
TRADE_UNCERTAINTY_TEN_YEAR_MONTHS = 120


# ---- pure calculations on series --------------------------------------------------------------------------------------------

def history_series_calculate_difference(first: pandas.Series, second: pandas.Series) -> pandas.Series:
    joined = pandas.concat([first, second], axis=1, join="inner").dropna()
    return joined.iloc[:, 0] - joined.iloc[:, 1]


def history_series_calculate_is_below(first: pandas.Series, second: pandas.Series) -> pandas.Series:
    joined = pandas.concat([first, second], axis=1, join="inner").dropna()
    return joined.iloc[:, 0] < joined.iloc[:, 1]


def history_series_calculate_ratio(numerator: pandas.Series, denominator: pandas.Series) -> pandas.Series:
    joined = pandas.concat([numerator, denominator], axis=1, join="inner").dropna()
    return joined.iloc[:, 0] / joined.iloc[:, 1]


def history_series_calculate_change(series: pandas.Series, observations: int, scale: float = 1.0) -> pandas.Series:
    return ((series - series.shift(observations)) * scale).dropna()


def history_series_calculate_percent_change(series: pandas.Series, observations: int) -> pandas.Series:
    return ((series / series.shift(observations) - 1) * 100).dropna()


def history_series_calculate_rolling_mean(series: pandas.Series, observations: int) -> pandas.Series:
    return series.rolling(observations).mean().dropna()


def history_series_calculate_rolling_percentile_rank(series: pandas.Series, window: int) -> pandas.Series:
    """Share of the earlier values in the window that are below the current value, 0 to 100."""
    def rank(values) -> float:
        return float((values[:-1] < values[-1]).mean() * 100)
    return series.rolling(window).apply(rank, raw=True).dropna()


def history_series_calculate_not_raised(rate_series: pandas.Series, calendar_days: int) -> pandas.Series:
    """True on days when the rate is not higher than it was `calendar_days` days earlier."""
    daily = rate_series.resample("D").ffill()
    earlier = daily.shift(calendar_days)
    return (daily <= earlier)[earlier.notna()]


def history_series_calculate_market_value_to_gdp_percent(equities_millions: pandas.Series, gdp_billions: pandas.Series) -> pandas.Series:
    """Fed Z.1 equities are in millions of dollars, GDP in billions."""
    return history_series_calculate_ratio(equities_millions / 1000, gdp_billions) * 100


# ---- the builders -----------------------------------------------------------------------------------------------------------

def fred(series_id: str) -> pandas.Series:
    return macro_data.macro_data_fetch_fred_series_cached(series_id)


def history_series_build_federal_funds_target_rate() -> pandas.Series:
    """The target (upper bound after 2008) as one series: DFEDTAR to 2008-12-15, DFEDTARU after."""
    upper = fred("DFEDTARU")
    return pandas.concat([fred("DFEDTAR")[fred("DFEDTAR").index < upper.index[0]], upper])


def history_series_build_total_put_call_ratio() -> pandas.Series:
    return cboe_data.cboe_data_build_total_put_call_ratio_series(PUT_CALL_CACHE_FILE_PATH)


def cboe(index_name: str) -> pandas.Series:
    return cboe_data.cboe_data_fetch_index_history_series_cached(index_name)


HISTORY_SERIES_BUILDER_BY_INDICATOR_ID: Dict[str, Callable[[], pandas.Series]] = {
    # MAC: policy, rates, credit, inflation, jobs, oil, money
    "federal_funds_target_rate_not_raised_in_182_days":
        lambda: history_series_calculate_not_raised(history_series_build_federal_funds_target_rate(), 182),
    "six_month_treasury_bill_yield_minus_federal_funds_rate":
        lambda: history_series_calculate_difference(fred("DGS6MO"), fred("DFF")),
    "treasury_ten_year_yield": lambda: fred("DGS10"),
    "treasury_ten_year_yield_twenty_day_change_basis_points":
        lambda: history_series_calculate_change(fred("DGS10"), 20, 100),
    "high_yield_credit_spread_basis_points": lambda: fred("BAMLH0A0HYM2") * 100,
    "high_yield_credit_spread_twenty_day_change_basis_points":
        lambda: history_series_calculate_change(fred("BAMLH0A0HYM2"), 20, 100),
    "moodys_baa_minus_ten_year_treasury_spread": lambda: fred("BAA10Y"),
    "treasury_ten_year_minus_two_year_spread": lambda: fred("T10Y2Y"),
    "treasury_ten_year_minus_three_month_spread": lambda: fred("T10Y3M"),
    "consumer_price_index_year_over_year_percent":
        lambda: history_series_calculate_percent_change(fred("CPIAUCSL"), 12),
    "core_pce_price_index_year_over_year_percent":
        lambda: history_series_calculate_percent_change(fred("PCEPILFE"), 12),
    "sahm_rule_recession_indicator": lambda: fred("SAHMREALTIME"),
    "initial_jobless_claims_four_week_average":
        lambda: history_series_calculate_rolling_mean(fred("ICSA"), 4),
    "chicago_fed_national_activity_index_three_month_average": lambda: fred("CFNAIMA3"),
    "wti_crude_oil_price": lambda: fred("DCOILWTICO"),
    "wti_crude_oil_one_month_change_percent":
        lambda: history_series_calculate_percent_change(fred("DCOILWTICO"), TRADING_DAYS_PER_MONTH),
    "m2_money_supply_year_over_year_percent":
        lambda: history_series_calculate_percent_change(fred("M2SL"), 12),
    "federal_reserve_total_assets_thirteen_week_change_percent":
        lambda: history_series_calculate_percent_change(fred("WALCL"), 13),
    # VAL and EVT built from FRED
    "market_value_to_gdp_percent":
        lambda: history_series_calculate_market_value_to_gdp_percent(fred("NCBEILQ027S"), fred("GDP")),
    "trade_policy_uncertainty_ten_year_percentile":
        lambda: history_series_calculate_rolling_percentile_rank(fred("EPUTRADE"), TRADE_UNCERTAINTY_TEN_YEAR_MONTHS),
    "us_epu_thirty_day_average_percentile_five_year":
        lambda: history_series_calculate_rolling_percentile_rank(
            history_series_calculate_rolling_mean(fred("USEPUINDXD"), EPU_THIRTY_DAYS), EPU_FIVE_YEAR_DAYS),
    # SEN and VOL built from Cboe
    "vix_level": lambda: cboe("VIX"),
    "vix_term_structure_is_contango": lambda: history_series_calculate_is_below(cboe("VIX"), cboe("VIX3M")),
    "vxn_to_vix_ratio": lambda: history_series_calculate_ratio(cboe("VXN"), cboe("VIX")),
    "vix_to_twenty_day_average_ratio":
        lambda: history_series_calculate_ratio(cboe("VIX"), history_series_calculate_rolling_mean(cboe("VIX"), 20)),
    "put_call_ratio_total_five_day_average":
        lambda: history_series_calculate_rolling_mean(history_series_build_total_put_call_ratio(), 5),
    # SEN from CNN, AAII and NAAIM
    "fear_greed_index": lambda: sentiment_data.sentiment_data_fetch_cnn_fear_greed_series(),
    "aaii_bullish_percent": lambda: sentiment_data.sentiment_data_fetch_aaii_survey_table()["bullish_percent"],
    "aaii_bullish_minus_bearish_percent":
        lambda: sentiment_data.sentiment_data_fetch_aaii_survey_table()["bullish_minus_bearish_percent"],
    "naaim_exposure_index": lambda: sentiment_data.sentiment_data_fetch_naaim_exposure_series(),
    # VAL and EVT from reference files
    "shiller_cape": lambda: reference_data.reference_data_fetch_shiller_cape_series(),
    "damodaran_implied_equity_risk_premium_percent": lambda: reference_data.reference_data_fetch_damodaran_implied_premium_series(),
    "geopolitical_risk_index_thirty_day_average_percentile_five_year":
        lambda: reference_data.reference_data_fetch_geopolitical_risk_percentile_series(),
}


def history_series_build_company_indicator_table(ticker: str, price_series: Optional[pandas.Series] = None) -> pandas.DataFrame:
    """One column per company indicator id (QUA, MGT, VAL, LIQ and the short interest rule), one row per day since 2010.
    The price series (daily close) is needed for the valuation and market capitalization columns."""
    company_facts = edgar_data.edgar_data_fetch_company_facts(ticker)
    days = pandas.date_range("2010-01-01", pandas.Timestamp.today().normalize(), freq="D")
    table = fundamental_series.fundamental_series_build_table(company_facts, days, price_series)
    shares_table = edgar_data.edgar_data_extract_fact_table(
        company_facts, ["EntityCommonStockSharesOutstanding"], "shares", taxonomy="dei")
    short_percent = finra_data.finra_data_calculate_short_interest_percent_of_shares(
        finra_data.finra_data_fetch_short_interest_table(ticker), edgar_data.edgar_data_build_instant_series(shares_table))
    table["short_interest_percent_of_shares_outstanding"] = short_percent.reindex(days.union(short_percent.index)).ffill().reindex(days)
    return table


def history_series_build_by_indicator_id(indicator_id: str) -> pandas.Series:
    return HISTORY_SERIES_BUILDER_BY_INDICATOR_ID[indicator_id]()


def history_series_build_point_in_time_cpi_year_over_year(as_of_date_list) -> pandas.Series:
    """CPI inflation as a backtest may see it: revisions after each date are not allowed to leak back (ALFRED vintages)."""
    return macro_data.macro_data_build_point_in_time_year_over_year_series("CPIAUCSL", as_of_date_list)


def history_series_check_against_catalog() -> None:
    import yaml
    with open(os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml"), encoding="utf8") as catalog_file:
        rule_list = yaml.safe_load(catalog_file)["rule_list"]
    rule_list_by_indicator: Dict[str, list] = {}
    for rule in rule_list:
        if rule.get("indicator") in HISTORY_SERIES_BUILDER_BY_INDICATOR_ID:
            rule_list_by_indicator.setdefault(rule["indicator"], []).append(rule)
    print(f"{'indicator':62s} {'catalog start':13s} {'first':10s} {'last':10s} {'rows':>6s}  last value")
    for indicator_id, builder in HISTORY_SERIES_BUILDER_BY_INDICATOR_ID.items():
        rules = rule_list_by_indicator.get(indicator_id, [])
        catalog_start = ",".join(sorted({str(rule.get("history_start")) for rule in rules})) or "-"
        try:
            series = builder()
            print(f"{indicator_id:62s} {catalog_start:13s} {series.index[0].date()!s:10s} {series.index[-1].date()!s:10s} {len(series):6d}  {series.iloc[-1]}")
        except Exception as error:  # the report must list every indicator, even when one source fails
            print(f"{indicator_id:62s} {catalog_start:13s} FAILED {error!r}")


if __name__ == "__main__":
    history_series_check_against_catalog()
