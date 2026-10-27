import os
import pandas
import pytest

from stock_benchmark_backend import edgar_data, fundamental_series


def fact(start, end, val, filed, form):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


def company_facts(**concept_fact_list):
    return {"facts": {"us-gaap": {name: {"units": {"USD": facts}} for name, facts in concept_fact_list.items()}}}


REVENUE_FACTS = [
    fact("2019-01-01", "2019-12-31", 400, "2020-02-10", "10-K"),
    fact("2019-01-01", "2019-03-31", 90, "2019-05-05", "10-Q"),
    fact("2020-01-01", "2020-03-31", 110, "2020-05-05", "10-Q"),
    fact("2020-01-01", "2020-06-30", 230, "2020-08-05", "10-Q"),
    fact("2020-04-01", "2020-06-30", 120, "2020-08-05", "10-Q"),
    fact("2019-01-01", "2019-06-30", 200, "2019-08-05", "10-Q"),
    fact("2019-01-01", "2019-12-31", 405, "2021-02-10", "10-K"),  # restated later: must not replace the first filing
]


def test_trailing_twelve_months_from_annual_and_year_to_date_figures():
    table = edgar_data.edgar_data_extract_fact_table(company_facts(Revenues=REVENUE_FACTS), ["Revenues"])
    series = edgar_data.edgar_data_build_trailing_twelve_month_series(table)
    assert series.loc["2020-02-10"] == 400
    assert series.loc["2020-05-05"] == 400 + 110 - 90        # the quarter only
    assert series.loc["2020-08-05"] == 400 + 230 - 200       # the six months, not the 120 quarter


def test_earliest_filing_and_earlier_concept_name_win_for_a_period():
    facts = company_facts(
        SalesRevenueNet=[fact("2019-01-01", "2019-12-31", 400, "2020-02-10", "10-K")],
        Revenues=[fact("2019-01-01", "2019-12-31", 999, "2021-02-10", "10-K")])
    table = edgar_data.edgar_data_extract_fact_table(facts, ["Revenues", "SalesRevenueNet"])
    assert table["val"].tolist() == [400]


def test_other_forms_and_missing_concepts_are_ignored():
    facts = company_facts(Revenues=[fact("2019-01-01", "2019-12-31", 1, "2020-02-10", "8-K")])
    assert edgar_data.edgar_data_extract_fact_table(facts, ["Revenues"]).empty
    assert edgar_data.edgar_data_extract_fact_table(facts, ["Nothing"]).empty
    assert edgar_data.edgar_data_build_trailing_twelve_month_series(edgar_data.edgar_data_extract_fact_table(facts, ["Nothing"])).empty


def test_instant_series_is_stamped_with_the_filing_date():
    facts = company_facts(StockholdersEquity=[
        {"end": "2019-12-31", "val": 50, "filed": "2020-02-10", "form": "10-K"},
        {"end": "2020-03-31", "val": 60, "filed": "2020-05-05", "form": "10-Q"}])
    series = edgar_data.edgar_data_build_instant_series(edgar_data.edgar_data_extract_fact_table(facts, ["StockholdersEquity"]))
    assert series.loc["2020-05-05"] == 60 and len(series) == 2


def test_user_agent_carries_the_contact_from_the_environment(monkeypatch):
    monkeypatch.setenv("EDGAR_CONTACT", "me@example.org")
    assert edgar_data.edgar_data_build_identity().endswith("me@example.org")


def test_fundamental_table_derives_margins_growth_and_valuation():
    facts = company_facts(
        Revenues=REVENUE_FACTS, GrossProfit=[fact("2019-01-01", "2019-12-31", 200, "2020-02-10", "10-K")],
        NetCashProvidedByUsedInOperatingActivities=[fact("2019-01-01", "2019-12-31", 120, "2020-02-10", "10-K")],
        PaymentsToAcquirePropertyPlantAndEquipment=[fact("2019-01-01", "2019-12-31", 20, "2020-02-10", "10-K")])
    facts["facts"]["dei"] = {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
        {"end": "2020-01-31", "val": 10, "filed": "2020-02-10", "form": "10-K"}]}}}
    days = pandas.date_range("2020-02-01", "2020-03-01", freq="D")
    price = pandas.Series(50.0, index=days)
    table = fundamental_series.fundamental_series_build_table(facts, days, price)
    last = table.iloc[-1]
    assert last["gross_margin_percent"] == pytest.approx(50.0)
    assert last["trailing_twelve_month_free_cash_flow"] == 100
    assert last["market_capitalization_billion_usd"] == pytest.approx(500 / 1e9)
    assert last["free_cash_flow_yield_percent"] == pytest.approx(20.0)
    assert pandas.isna(table.iloc[0]["revenue_year_over_year_percent"])  # a year earlier nothing was filed yet


def test_fetch_json_sends_the_identity_through_edgartools(monkeypatch):
    monkeypatch.setenv("EDGAR_CONTACT", "me@example.org")
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)
    seen = {}
    monkeypatch.setattr(edgar_data, "download_json", lambda url: seen.setdefault("url", url) and {"ok": True})
    assert edgar_data.edgar_data_fetch_json("https://data.sec.gov/x.json") == {"ok": True}
    assert os.environ["EDGAR_IDENTITY"].endswith("me@example.org")


def test_every_sec_override_name_is_a_column_of_the_company_table():
    from stock_benchmark_backend import live_indicators
    days = pandas.date_range("2020-01-01", periods=3, freq="D")
    columns = set(fundamental_series.fundamental_series_build_table({"facts": {}}, days, pandas.Series(1.0, index=days)).columns)
    assert set(live_indicators.EDGAR_INDICATOR_NAME_LIST) <= columns
