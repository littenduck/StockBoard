import numpy
import pandas

from stock_benchmark_backend import fundamental_series

FILED_2020 = "2020-02-10"
FILED_2021 = "2021-02-10"
DAY_INDEX = pandas.date_range("2019-06-01", FILED_2021, freq="D")  # a full daily index, as the company table uses


def annual(start, end, value, filed):
    return {"start": start, "end": end, "val": value, "filed": filed, "form": "10-K"}


def instant(end, value, filed):
    return {"end": end, "val": value, "filed": filed, "form": "10-K"}


def two_year_company_facts():
    """Two annual reports: 2019 (filed 2020) and 2020 (filed 2021), with figures that pass every Piotroski test in 2020."""
    def flow(concept, value_2019, value_2020):
        return {"units": {"USD": [annual("2019-01-01", "2019-12-31", value_2019, FILED_2020),
                                  annual("2020-01-01", "2020-12-31", value_2020, FILED_2021)]}}

    def balance(concept, value_2019, value_2020):
        return {"units": {"USD": [instant("2019-12-31", value_2019, FILED_2020), instant("2020-12-31", value_2020, FILED_2021)]}}

    us_gaap = {
        "NetIncomeLoss": flow("NetIncomeLoss", 10, 15),
        "NetCashProvidedByUsedInOperatingActivities": flow("cfo", 20, 30),
        "PaymentsToAcquirePropertyPlantAndEquipment": flow("capex", 5, 5),
        "ShareBasedCompensation": flow("sbc", 2, 3),
        "Revenues": flow("revenue", 200, 260),
        "GrossProfit": flow("gross", 100, 143),
        "Assets": balance("assets", 100, 120),
        "AssetsCurrent": balance("ca", 50, 70),
        "LiabilitiesCurrent": balance("cl", 25, 25),
        "LongTermDebt": balance("ltd", 40, 30),
    }
    dei = {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        instant("2019-12-31", 100, FILED_2020), instant("2020-12-31", 95, FILED_2021)]}}}
    return {"facts": {"us-gaap": us_gaap, "dei": dei}}


def test_piotroski_score_and_accruals_match_hand_calculation_for_2020():
    table = fundamental_series.fundamental_series_build_table(two_year_company_facts(), DAY_INDEX)
    filed_day = table.loc[FILED_2021]
    assert filed_day["piotroski_f_score"] == 9
    assert numpy.isclose(filed_day["accruals_percent_of_average_total_assets"], (15 - 30) / 110 * 100)
    assert numpy.isclose(filed_day["free_cash_flow_after_stock_compensation"], (30 - 5) - 3)


def test_piotroski_is_unknown_without_a_year_earlier():
    table = fundamental_series.fundamental_series_build_table(two_year_company_facts(), DAY_INDEX)
    assert pandas.isna(table.loc[FILED_2020, "piotroski_f_score"])


def test_each_piotroski_test_is_a_yes_or_no_on_the_same_inputs():
    now = {name: pandas.Series([1.0], index=pandas.DatetimeIndex([pandas.Timestamp("2021-02-10")])) for name in
           ["return_on_assets", "operating_cash_flow", "operating_cash_flow_on_assets", "long_term_debt_on_assets",
            "current_ratio", "shares", "gross_margin", "asset_turnover"]}
    tests, inputs = fundamental_series.build_piotroski_tests(now)
    assert len(tests) == 9 and len(inputs) == 16


def test_revenue_growth_is_the_latest_quarter_against_the_same_quarter_a_year_earlier():
    """Yahoo's revenueGrowth for AAPL: quarter ended 2026-06-27 (109.417 bn) against 2025-06-28 (94.036 bn), about 16.4%."""
    from stock_benchmark_backend import edgar_data
    facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        {"start": "2025-03-30", "end": "2025-06-28", "val": 94_036_000_000, "filed": "2025-08-01", "form": "10-Q"},
        {"start": "2026-03-29", "end": "2026-06-27", "val": 109_417_000_000, "filed": "2026-07-31", "form": "10-Q"},
    ]}}}}}
    growth = fundamental_series.fundamental_series_build_latest_quarter_growth(
        edgar_data.edgar_data_extract_fact_table(facts, ["Revenues"]))
    assert numpy.isclose(growth.loc[pandas.Timestamp("2026-07-31")], (109_417 / 94_036 - 1) * 100)


def test_roe_uses_average_equity_cash_includes_current_securities_and_debt_includes_commercial_paper():
    """Each figure is checked against Apple's Yahoo values: ROE 148.75%, totalCash 62.399 bn, totalDebt 84.344 bn (here a small example)."""
    def balance(value_2019, value_2020):
        return {"units": {"USD": [instant("2019-12-31", value_2019, FILED_2020), instant("2020-12-31", value_2020, FILED_2021)]}}
    facts = two_year_company_facts()
    us_gaap = facts["facts"]["us-gaap"]
    us_gaap["StockholdersEquity"] = balance(100, 120)
    us_gaap["CashAndCashEquivalentsAtCarryingValue"] = balance(50, 60)
    us_gaap["MarketableSecuritiesCurrent"] = balance(10, 20)
    us_gaap["CommercialPaper"] = balance(0, 5)
    us_gaap["OperatingIncomeLoss"] = {"units": {"USD": [annual("2020-01-01", "2020-12-31", 50, FILED_2021)]}}
    us_gaap["DepreciationDepletionAndAmortization"] = {"units": {"USD": [annual("2020-01-01", "2020-12-31", 10, FILED_2021)]}}
    table = fundamental_series.fundamental_series_build_table(facts, DAY_INDEX)
    filed_day = table.loc[FILED_2021]
    # ROE: 15 / ((100 + 120) / 2) * 100
    assert numpy.isclose(filed_day["return_on_equity_percent"], 15 / 110 * 100)
    # Debt: long-term debt 30 plus commercial paper 5; cash: 60 plus 20 of current securities.
    # Net debt = (30 + 5) - (60 + 20) = -45; EBITDA = 50 + 10 = 60; ratio -0.75.
    assert numpy.isclose(filed_day["net_debt_to_ebitda"], -45 / 60)


def test_debt_parts_come_from_one_filing_and_stale_lease_lines_are_left_out():
    """Yahoo totalDebt = noncurrent + current long-term debt + commercial paper, plus leases only when the same filing reports them.
    Here the 2019 lease line is older than the 2020 debt, so it is not part of today's debt (-0.75 = (35 - 80) / 60)."""
    def balance(value_2019, value_2020):
        return {"units": {"USD": [instant("2019-12-31", value_2019, FILED_2020), instant("2020-12-31", value_2020, FILED_2021)]}}
    facts = two_year_company_facts()
    us_gaap = facts["facts"]["us-gaap"]
    del us_gaap["LongTermDebt"]
    us_gaap["LongTermDebtNoncurrent"] = balance(40, 30)
    us_gaap["LongTermDebtCurrent"] = {"units": {"USD": [instant("2020-12-31", 5, FILED_2021)]}}
    us_gaap["OperatingLeaseLiabilityNoncurrent"] = {"units": {"USD": [instant("2019-12-31", 10, FILED_2020)]}}
    us_gaap["CashAndCashEquivalentsAtCarryingValue"] = balance(50, 60)
    us_gaap["MarketableSecuritiesCurrent"] = balance(10, 20)
    us_gaap["OperatingIncomeLoss"] = {"units": {"USD": [annual("2020-01-01", "2020-12-31", 50, FILED_2021)]}}
    us_gaap["DepreciationDepletionAndAmortization"] = {"units": {"USD": [annual("2020-01-01", "2020-12-31", 10, FILED_2021)]}}
    table = fundamental_series.fundamental_series_build_table(facts, DAY_INDEX)
    assert numpy.isclose(table.loc[FILED_2021, "net_debt_to_ebitda"], -45 / 60)
