import datetime

import pandas
import pytest

from stock_benchmark_backend import edgar_data, option_chain, reference_data


def test_multpl_table_rows_become_a_series():
    page = ("<table><tr><td>Oct 23, 2026</td><td>&#x2002; 40.36</td></tr><tr><td>Oct 1, 2026</td><td>&#x2002; 40.81</td></tr>"
            "<tr><td>Sep 1, 2026</td><td>&#x2002; 40.42</td></tr></table>")
    series = reference_data.reference_data_parse_multpl_cape_table(page)
    assert series.index[-1] == pandas.Timestamp("2026-10-23") and series.iloc[-1] == 40.36 and len(series) == 3


def test_damodaran_sheet_uses_the_named_column_and_converts_to_percent():
    sheet = pandas.DataFrame([
        ["Start of month", "S&P 500", "ERP (T12m)"], [datetime.datetime(2026, 9, 1), 7686.0, 0.0409],
        [datetime.datetime(2026, 10, 1), 7652.0, None], ["note", None, None]])
    series = reference_data.reference_data_parse_damodaran_sheet(sheet)
    assert series.tolist() == pytest.approx([4.09]) and series.index[0] == pandas.Timestamp("2026-09-01")


def test_gpr_percentile_ranks_the_thirty_day_average_against_five_years():
    days = pandas.date_range("2018-01-01", periods=2200, freq="D")
    table = pandas.DataFrame({"date": days, "GPRD_MA30": [100 + index * 0.1 for index in range(2200)]})
    series = reference_data.reference_data_parse_gpr_percentile_series(table)
    assert series.iloc[-1] == 100.0 and series.index[-1] == days[-1]


def submissions(*filings):
    return {"filings": {"recent": {"form": [f[0] for f in filings], "items": [f[1] for f in filings], "filingDate": [f[2] for f in filings]}}}


def test_audit_and_late_filing_problems_in_the_last_year():
    today = datetime.date(2026, 10, 25)
    check = lambda *filings: edgar_data.edgar_data_find_audit_or_late_filing_problem(submissions(*filings), today)
    assert check(("8-K", "2.02,9.01", "2026-08-01")) is False
    assert check(("8-K", "4.01,9.01", "2026-08-01")) is True
    assert check(("8-K", "4.02", "2026-03-01")) is True
    assert check(("NT 10-Q", "", "2026-05-20")) is True
    assert check(("8-K", "4.01", "2025-06-01")) is False  # older than 365 days
    assert edgar_data.edgar_data_find_audit_or_late_filing_problem({}, today) is False


def test_covered_call_strike_is_the_listed_strike_closest_to_ten_percent_above():
    table = pandas.DataFrame({"strike": [95.0, 105.0, 108.0, 110.0, 115.0, 120.0]})
    assert option_chain.option_chain_determine_covered_call_strike_premium_percent(table, 100.0) == 10.0
    assert option_chain.option_chain_determine_covered_call_strike_premium_percent(table.iloc[:1], 100.0) is None
