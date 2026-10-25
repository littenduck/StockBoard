"""Company fundamentals as they were known on each day, built from SEC EDGAR filings (and a price series for the valuation ratios).

build_table returns one row per calendar day with a column for each indicator id used in config/rules.yaml. Figures are
trailing twelve months (see edgar_data). Return on invested capital is approximate: operating income taxed at 21% over equity plus
debt minus cash. EBITDA is operating income plus depreciation and amortization.
"""
from typing import Optional

import numpy
import pandas

from stockboard_backend import edgar_data

CONCEPT_NAME_LIST_BY_MEASURE = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capital_expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "depreciation_and_amortization": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization", "Depreciation"],
    "interest_expense": ["InterestExpense", "InterestExpenseDebt"],
    "dividends_paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "equity": ["StockholdersEquity"],
    "debt": ["LongTermDebt", "LongTermDebtNoncurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
}
INSTANT_MEASURE_SET = {"equity", "debt", "cash"}
CORPORATE_TAX_RATE = 0.21
DAYS_PER_YEAR = 365
YEAR_COUNT_FOR_GROWTH = 3
PRICE_EARNINGS_HISTORY_DAYS = 5 * 365


def fundamental_series_build_daily_series(sparse_series: pandas.Series, day_index: pandas.DatetimeIndex) -> pandas.Series:
    """The last filed value carried forward to every day."""
    if sparse_series.empty:
        return pandas.Series(numpy.nan, index=day_index)
    return sparse_series.sort_index().reindex(day_index.union(sparse_series.index)).ffill().reindex(day_index)


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


def fundamental_series_divide(numerator: pandas.Series, denominator: pandas.Series) -> pandas.Series:
    return (numerator / denominator).where(denominator != 0)


def fundamental_series_build_table(
        company_facts: dict, day_index: pandas.DatetimeIndex, price_series: Optional[pandas.Series] = None) -> pandas.DataFrame:
    measure = {}
    for name, concept_name_list in CONCEPT_NAME_LIST_BY_MEASURE.items():
        fact_table = edgar_data.edgar_data_extract_fact_table(company_facts, concept_name_list)
        sparse = edgar_data.edgar_data_build_instant_series(fact_table) if name in INSTANT_MEASURE_SET \
            else edgar_data.edgar_data_build_trailing_twelve_month_series(fact_table)
        measure[name] = fundamental_series_build_daily_series(sparse, day_index)
    eps_table = edgar_data.edgar_data_extract_fact_table(company_facts, ["EarningsPerShareDiluted"], "USD/shares")
    measure["eps"] = fundamental_series_build_daily_series(edgar_data.edgar_data_build_trailing_twelve_month_series(eps_table), day_index)
    shares_table = edgar_data.edgar_data_extract_fact_table(
        company_facts, ["EntityCommonStockSharesOutstanding"], "shares", taxonomy="dei")
    measure["shares"] = fundamental_series_build_daily_series(edgar_data.edgar_data_build_instant_series(shares_table), day_index)

    revenue = measure["revenue"]
    gross_profit = measure["gross_profit"].fillna(revenue - measure["cost_of_revenue"])
    free_cash_flow = measure["operating_cash_flow"] - measure["capital_expenditure"].abs()
    ebitda = measure["operating_income"] + measure["depreciation_and_amortization"]
    net_debt = measure["debt"] - measure["cash"]
    invested_capital = measure["equity"] + measure["debt"] - measure["cash"]
    table = pandas.DataFrame({
        "trailing_twelve_month_eps": measure["eps"],
        "revenue_year_over_year_percent": fundamental_series_percent_growth(revenue, DAYS_PER_YEAR),
        "revenue_three_year_cagr_percent": fundamental_series_compound_growth(revenue, YEAR_COUNT_FOR_GROWTH),
        "eps_three_year_cagr_percent": fundamental_series_compound_growth(measure["eps"], YEAR_COUNT_FOR_GROWTH),
        "return_on_invested_capital_percent":
            fundamental_series_divide(measure["operating_income"] * (1 - CORPORATE_TAX_RATE), invested_capital) * 100,
        "return_on_equity_percent": fundamental_series_divide(measure["net_income"], measure["equity"]) * 100,
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
    }, index=day_index)
    if price_series is not None and not price_series.empty:
        price = price_series.reindex(day_index.union(price_series.index)).ffill().reindex(day_index)
        market_cap = price * measure["shares"]
        price_earnings = fundamental_series_divide(price, measure["eps"]).where(measure["eps"] > 0)
        median_price_earnings = price_earnings.rolling(PRICE_EARNINGS_HISTORY_DAYS, min_periods=DAYS_PER_YEAR).median()
        table["market_capitalization_billion_usd"] = market_cap / 1e9
        table["free_cash_flow_yield_percent"] = fundamental_series_divide(free_cash_flow, market_cap) * 100
        table["enterprise_value_to_ebitda"] = fundamental_series_divide(market_cap + net_debt, ebitda).where(ebitda > 0)
        table["price_earnings_ttm_to_five_year_median_ratio"] = fundamental_series_divide(price_earnings, median_price_earnings)
    return table


if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    days = pandas.date_range("2010-01-01", pandas.Timestamp.today().normalize(), freq="D")
    result = fundamental_series_build_table(edgar_data.edgar_data_fetch_company_facts(ticker), days)
    print(result.dropna(how="all").iloc[[0, len(result) // 2, -1]].T.to_string())
