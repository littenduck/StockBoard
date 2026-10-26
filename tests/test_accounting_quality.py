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
