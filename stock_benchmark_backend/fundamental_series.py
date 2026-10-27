"""Company fundamentals as they were known on each day, built from SEC EDGAR filings (and a price series for the valuation ratios).

build_table returns one row per calendar day with a column for each indicator id used in config/rules.yaml. Figures are
trailing twelve months (see edgar_data). Return on invested capital is approximate: operating income taxed at 21% over equity plus
debt minus cash. EBITDA is operating income plus depreciation and amortization.
"""
from typing import Optional

import numpy
import pandas

from stock_benchmark_backend import edgar_data

CONCEPT_NAME_LIST_BY_MEASURE = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    # AMD and some others report cost of revenue excluding D&A; Yahoo's gross margin uses that line (AMD 55.72%).
    "cost_of_revenue": ["CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization", "CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    # Yahoo's ROE and EPS exclude discontinued operations (AMD: continuing 6.469 bn against 6.434 bn total net income).
    "net_income": ["IncomeLossFromContinuingOperations", "NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capital_expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    # Total D&A from the cash-flow statement. Yahoo's EBITDA for AMD = 6.488 + 2.260 + 0.813 bn, so when the total line is absent the
    # parts are added (see depreciation_and_amortization below). A standalone "Depreciation" is not total D&A and is not used.
    "depreciation_and_amortization": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
    "other_depreciation_and_amortization": ["OtherDepreciationAndAmortization", "Depreciation"],
    "amortization_of_intangible_assets": ["AmortizationOfIntangibleAssets"],
    "interest_expense": ["InterestExpense", "InterestExpenseDebt"],
    "dividends_paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "equity": ["StockholdersEquity"],
    # Yahoo's totalDebt = long-term debt including its current part. Each part is read from the same filing (see build_table).
    "long_term_debt": ["LongTermDebt"],
    "long_term_debt_noncurrent": ["LongTermDebtNoncurrent"],
    "long_term_debt_current": ["LongTermDebtCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "total_assets": ["Assets"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "share_based_compensation": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
    # Several companies tag the same item differently; the fact table keeps the first filed value for each period across all names.
    "marketable_securities_current": ["MarketableSecuritiesCurrent", "ShortTermInvestments", "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
                                     "DebtSecuritiesCurrent"],
    "commercial_paper": ["CommercialPaper"],
    "operating_lease_liability_current": ["OperatingLeaseLiabilityCurrent"],
    "operating_lease_liability_noncurrent": ["OperatingLeaseLiabilityNoncurrent"],
}
# Measures that are balance-sheet values (one value per date) rather than flows over twelve months.
INSTANT_MEASURE_SET = {"equity", "cash", "total_assets", "current_assets", "current_liabilities", "marketable_securities_current",
                       "commercial_paper", "long_term_debt", "long_term_debt_noncurrent", "long_term_debt_current",
                       "operating_lease_liability_current", "operating_lease_liability_noncurrent"}
CORPORATE_TAX_RATE = 0.21
DAYS_PER_YEAR = 365
YEAR_COUNT_FOR_GROWTH = 3
PRICE_EARNINGS_HISTORY_DAYS = 5 * 365


# A value stays in force until the next report. If the company stops tagging an item (or stops filing), the last value must not be
# carried forward forever: after this many days it is unknown. A 10-K comes at least once a year, so 400 days covers a normal gap.
MAX_FILED_VALUE_AGE_DAYS = 400


def fundamental_series_build_filed_date_series(sparse_series: pandas.Series, day_index: pandas.DatetimeIndex) -> pandas.Series:
    """The filing date behind the value carried to each day (NaT where there is no value yet)."""
    if sparse_series.empty:
        return pandas.Series(pandas.NaT, index=day_index)
    filed_on = pandas.Series(sparse_series.index, index=sparse_series.index)
    return filed_on.reindex(day_index.union(sparse_series.index)).ffill().reindex(day_index)


def fundamental_series_build_daily_series(sparse_series: pandas.Series, day_index: pandas.DatetimeIndex) -> pandas.Series:
    """The last filed value carried forward to every day, unknown once it is older than MAX_FILED_VALUE_AGE_DAYS.
    Found when NVDA stopped tagging marketable securities: its 2025 value was used as today's cash for years."""
    if sparse_series.empty:
        return pandas.Series(numpy.nan, index=day_index)
    sparse_series = sparse_series.sort_index()
    combined_index = day_index.union(sparse_series.index)
    value = sparse_series.reindex(combined_index).ffill().reindex(day_index)
    filed_on = pandas.Series(sparse_series.index, index=sparse_series.index).reindex(combined_index).ffill().reindex(day_index)
    age_days = (pandas.Series(day_index, index=day_index) - filed_on).dt.days
    return value.mask(age_days > MAX_FILED_VALUE_AGE_DAYS)


def fundamental_series_look_back(series: pandas.Series, days: int) -> pandas.Series:
    """The value from `days` days earlier, lined up with today's date."""
    return series.shift(days, freq="D").reindex(series.index)


def fundamental_series_percent_growth(series: pandas.Series, days: int) -> pandas.Series:
    earlier = fundamental_series_look_back(series, days)
    return ((series / earlier - 1) * 100).where(earlier > 0)


def fundamental_series_compound_growth(series: pandas.Series, years: int) -> pandas.Series:
    """Yearly growth rate in percent; undefined when either end is not positive."""
    earlier = fundamental_series_look_back(series, years * DAYS_PER_YEAR)
    valid = (series > 0) & (earlier > 0)
    return (((series / earlier) ** (1 / years) - 1) * 100).where(valid)


def build_piotroski_tests(series_by_name: dict):
    """Piotroski's nine yes/no tests, each compared with the same figure a year earlier. Returns the tests and every series they use
    (so a day is scored only when all of them are known). Input names: return_on_assets, operating_cash_flow, operating_cash_flow_on_assets,
    long_term_debt_on_assets, current_ratio, shares, gross_margin, asset_turnover."""
    now, year_ago = series_by_name, {name: fundamental_series_look_back(series, DAYS_PER_YEAR) for name, series in series_by_name.items()}
    tests = [
        now["return_on_assets"] > 0,
        now["operating_cash_flow"] > 0,
        now["return_on_assets"] > year_ago["return_on_assets"],
        now["operating_cash_flow_on_assets"] > now["return_on_assets"],
        now["long_term_debt_on_assets"] < year_ago["long_term_debt_on_assets"],
        now["current_ratio"] > year_ago["current_ratio"],
        now["shares"] <= year_ago["shares"],
        now["gross_margin"] > year_ago["gross_margin"],
        now["asset_turnover"] > year_ago["asset_turnover"],
    ]
    return tests, list(now.values()) + list(year_ago.values())


QUARTER_DAY_RANGE = (80, 100)
DATE_MATCH_TOLERANCE_DAYS = 10


def fundamental_series_build_latest_quarter_growth(revenue_fact_table: pandas.DataFrame) -> pandas.Series:
    """Revenue growth as Yahoo shows it: the latest reported quarter against the same quarter a year earlier, in percent,
    stamped with the filing date of the latest quarter.

    Reproduces Yahoo's revenueGrowth for AAPL. On the quarter ended 2026-06-27 Apple reported 109.417 bn USD; the quarter
    ended 2025-06-28 was 94.036 bn USD. 109.417 / 94.036 - 1 = 16.35%, Yahoo shows 16.4%.
    Not the trailing twelve months: that gave 14.2% for the same date (see build_table).
    A fiscal Q4 is only in the 10-K, so it is absent here (its quarter is then the latest one that was reported as a 10-Q).
    """
    if revenue_fact_table.empty:
        return pandas.Series(dtype=float)
    quarter = revenue_fact_table.dropna(subset=["start"]).copy()
    quarter["days"] = (quarter["end"] - quarter["start"]).dt.days
    quarter = quarter[quarter["days"].between(*QUARTER_DAY_RANGE)].sort_values(["filed", "end"]).drop_duplicates(subset=["end"], keep="first")
    value_by_end = quarter.set_index("end")["val"].astype(float).sort_index()
    growth_by_filed_date = {}
    for _, row in quarter.iterrows():
        year_earlier_end = row["end"] - pandas.Timedelta(days=DAYS_PER_YEAR)
        is_same_quarter = [abs(end - year_earlier_end) <= pandas.Timedelta(days=DATE_MATCH_TOLERANCE_DAYS) for end in value_by_end.index]
        same_quarter_year_earlier = value_by_end[is_same_quarter]
        if len(same_quarter_year_earlier) and same_quarter_year_earlier.iloc[0] > 0:
            growth_by_filed_date[row["filed"]] = (row["val"] / same_quarter_year_earlier.iloc[0] - 1) * 100
    return pandas.Series(growth_by_filed_date, dtype=float).sort_index()


def fundamental_series_divide(numerator: pandas.Series, denominator: pandas.Series) -> pandas.Series:
    return (numerator / denominator).where(denominator != 0)


def fundamental_series_build_table(
        company_facts: dict, day_index: pandas.DatetimeIndex, price_series: Optional[pandas.Series] = None) -> pandas.DataFrame:
    measure = {}
    filed_date_by_measure = {}  # the day each value was last filed, to check that items come from the same report
    for name, concept_name_list in CONCEPT_NAME_LIST_BY_MEASURE.items():
        fact_table = edgar_data.edgar_data_extract_fact_table(company_facts, concept_name_list)
        sparse = edgar_data.edgar_data_build_instant_series(fact_table) if name in INSTANT_MEASURE_SET \
            else edgar_data.edgar_data_build_trailing_twelve_month_series(fact_table)
        measure[name] = fundamental_series_build_daily_series(sparse, day_index)
        if name in INSTANT_MEASURE_SET:
            filed_date_by_measure[name] = fundamental_series_build_filed_date_series(sparse, day_index)
    # Yahoo's EPS is from continuing operations; the plain diluted EPS is the fallback for companies that do not report that line.
    eps_table = edgar_data.edgar_data_extract_fact_table(
        company_facts, ["IncomeLossFromContinuingOperationsPerDilutedShare", "EarningsPerShareDiluted"], "USD/shares")
    measure["eps"] = fundamental_series_build_daily_series(edgar_data.edgar_data_build_trailing_twelve_month_series(eps_table), day_index)
    shares_table = edgar_data.edgar_data_extract_fact_table(
        company_facts, ["EntityCommonStockSharesOutstanding"], "shares", taxonomy="dei")
    measure["shares"] = fundamental_series_build_daily_series(edgar_data.edgar_data_build_instant_series(shares_table), day_index)

    # Cash as Yahoo counts it: cash and equivalents plus current marketable securities (AAPL: 39.544 + 22.855 = 62.399 bn, Yahoo totalCash).
    measure["cash"] = measure["cash"] + measure["marketable_securities_current"].fillna(0).where(measure["cash"].notna())

    # Debt as Yahoo counts it: long-term debt including its current part, plus commercial paper, plus each lease line.
    # Long-term debt: LongTermDebt when tagged (it already includes the current part); otherwise noncurrent + current.
    # Every part must come from the same filing as the debt it is added to: a value from an older report is not today's debt
    # (AAPL: 82.3 + 2.0 = 84.3 bn, Yahoo totalDebt 84.344; NVDA: 33.37 + 0.51 + 4.99 leases = 38.86 bn, Yahoo totalDebt).
    long_term_debt = measure["long_term_debt"]
    debt_from_parts = (measure["long_term_debt_noncurrent"] + measure["long_term_debt_current"].fillna(0)).where(
        measure["long_term_debt_noncurrent"].notna())
    debt_base = long_term_debt.where(long_term_debt.notna(), debt_from_parts)
    debt_filed_on = filed_date_by_measure["long_term_debt"].where(long_term_debt.notna(), filed_date_by_measure["long_term_debt_noncurrent"])
    lease_current_in_debt_filing = measure["operating_lease_liability_current"].where(
        filed_date_by_measure["operating_lease_liability_current"] == debt_filed_on, 0).fillna(0)
    lease_noncurrent_in_debt_filing = measure["operating_lease_liability_noncurrent"].where(
        filed_date_by_measure["operating_lease_liability_noncurrent"] == debt_filed_on, 0).fillna(0)
    measure["debt"] = debt_base + measure["commercial_paper"].fillna(0).where(debt_base.notna()) + (
        lease_current_in_debt_filing + lease_noncurrent_in_debt_filing).where(debt_base.notna())

    revenue = measure["revenue"]
    latest_quarter_growth = fundamental_series_build_latest_quarter_growth(
        edgar_data.edgar_data_extract_fact_table(company_facts, CONCEPT_NAME_LIST_BY_MEASURE["revenue"]))
    # Gross profit as Yahoo computes it: revenue minus cost of revenue (cost excluding D&A first); the reported GrossProfit line is the fallback.
    gross_profit = (revenue - measure["cost_of_revenue"]).where(measure["cost_of_revenue"].notna(), measure["gross_profit"])
    # Our free cash flow = operating cash flow minus property purchases. Yahoo's freeCashflow in the info feed does not follow any SEC
    # combination we could find (AAPL 107.72 bn against 136.68 bn), so the two are different figures and are labelled as such.
    free_cash_flow = measure["operating_cash_flow"] - measure["capital_expenditure"].abs()
    # Total D&A is the cash-flow line when tagged; otherwise the parts (depreciation, intangible amortization) for the same period are added.
    parts_of_depreciation_and_amortization = (measure["other_depreciation_and_amortization"].fillna(0)
                                              + measure["amortization_of_intangible_assets"].fillna(0)).where(
        measure["other_depreciation_and_amortization"].notna() | measure["amortization_of_intangible_assets"].notna())
    depreciation_and_amortization = measure["depreciation_and_amortization"].where(
        measure["depreciation_and_amortization"].notna(), parts_of_depreciation_and_amortization)
    ebitda = measure["operating_income"] + depreciation_and_amortization
    net_debt = measure["debt"] - measure["cash"]
    invested_capital = measure["equity"] + measure["debt"] - measure["cash"]
    total_assets = measure["total_assets"]
    return_on_assets = fundamental_series_divide(measure["net_income"], total_assets)
    operating_cash_flow_on_assets = fundamental_series_divide(measure["operating_cash_flow"], total_assets)
    long_term_debt_on_assets = fundamental_series_divide(measure["debt"], total_assets)
    current_ratio = fundamental_series_divide(measure["current_assets"], measure["current_liabilities"])
    gross_margin = fundamental_series_divide(gross_profit, revenue)
    asset_turnover = fundamental_series_divide(revenue, total_assets)
    average_total_assets = (total_assets + fundamental_series_look_back(total_assets, DAYS_PER_YEAR)) / 2
    piotroski_test_list, piotroski_input_list = build_piotroski_tests(
        {"return_on_assets": return_on_assets, "operating_cash_flow": measure["operating_cash_flow"],
         "operating_cash_flow_on_assets": operating_cash_flow_on_assets, "long_term_debt_on_assets": long_term_debt_on_assets,
         "current_ratio": current_ratio, "shares": measure["shares"], "gross_margin": gross_margin, "asset_turnover": asset_turnover})
    piotroski_complete = pandas.concat(piotroski_input_list, axis=1).notna().all(axis=1)
    piotroski_f_score = sum(test.astype(float) for test in piotroski_test_list).where(piotroski_complete)
    table = pandas.DataFrame({
        "trailing_twelve_month_eps": measure["eps"],
        "revenue_year_over_year_percent": fundamental_series_build_daily_series(latest_quarter_growth, day_index),
        "revenue_three_year_cagr_percent": fundamental_series_compound_growth(revenue, YEAR_COUNT_FOR_GROWTH),
        "eps_three_year_cagr_percent": fundamental_series_compound_growth(measure["eps"], YEAR_COUNT_FOR_GROWTH),
        "return_on_invested_capital_percent":
            fundamental_series_divide(measure["operating_income"] * (1 - CORPORATE_TAX_RATE), invested_capital) * 100,
        # Yahoo's returnOnEquity: net income over the average of equity a year apart (AAPL: 128.93 / ((65.83 + 107.52) / 2) = 148.75%).
        "return_on_equity_percent": fundamental_series_divide(
            measure["net_income"], (measure["equity"] + fundamental_series_look_back(measure["equity"], DAYS_PER_YEAR)) / 2) * 100,
        "gross_margin_percent": fundamental_series_divide(gross_profit, revenue) * 100,
        "trailing_twelve_month_free_cash_flow": free_cash_flow,
        "free_cash_flow_year_over_year_change": free_cash_flow - fundamental_series_look_back(free_cash_flow, DAYS_PER_YEAR),
        "net_debt_to_ebitda": fundamental_series_divide(net_debt, ebitda).where(ebitda > 0),
        "interest_coverage_ratio": fundamental_series_divide(measure["operating_income"], measure["interest_expense"]),
        "operating_cash_flow_to_net_income_ratio":
            fundamental_series_divide(measure["operating_cash_flow"], measure["net_income"]).where(measure["net_income"] > 0),
        "shares_outstanding_year_over_year_percent": fundamental_series_percent_growth(measure["shares"], DAYS_PER_YEAR),
        "dividend_to_free_cash_flow_ratio":
            fundamental_series_divide(measure["dividends_paid"].abs(), free_cash_flow).where(free_cash_flow > 0),
        "accruals_percent_of_average_total_assets":
            fundamental_series_divide(measure["net_income"] - measure["operating_cash_flow"], average_total_assets) * 100,
        "free_cash_flow_after_stock_compensation": free_cash_flow - measure["share_based_compensation"],
        "piotroski_f_score": piotroski_f_score,
    }, index=day_index)
    if price_series is not None and not price_series.empty:
        price = price_series.reindex(day_index.union(price_series.index)).ffill().reindex(day_index)
        market_cap = price * measure["shares"]
        price_earnings = fundamental_series_divide(price, measure["eps"]).where(measure["eps"] > 0)
        median_price_earnings = price_earnings.rolling(PRICE_EARNINGS_HISTORY_DAYS, min_periods=DAYS_PER_YEAR).median()
        table["market_capitalization_billion_usd"] = market_cap / 1e9
        table["free_cash_flow_yield_percent"] = fundamental_series_divide(free_cash_flow, market_cap) * 100
        # Yahoo prices enterprise value at the previous close (AMD: 516.79 x 1.632475 + 4.276 - 13.111 = 87.31 times EBITDA).
        previous_close = price.shift(1)
        enterprise_value = previous_close * measure["shares"] + net_debt
        table["enterprise_value_to_ebitda"] = fundamental_series_divide(enterprise_value, ebitda).where(ebitda > 0)
        table["price_earnings_ttm_to_five_year_median_ratio"] = fundamental_series_divide(price_earnings, median_price_earnings)
    return table


if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    days = pandas.date_range("2010-01-01", pandas.Timestamp.today().normalize(), freq="D")
    result = fundamental_series_build_table(edgar_data.edgar_data_fetch_company_facts(ticker), days)
    print(result.dropna(how="all").iloc[[0, len(result) // 2, -1]].T.to_string())
