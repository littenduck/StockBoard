import json

import pandas
import pytest

from stock_benchmark_backend import finra_data


def row(day, short):
    return {"settlementDate": day, "currentShortPositionQuantity": short, "averageDailyVolumeQuantity": 1000, "daysToCoverQuantity": 2.5}


def test_request_filters_on_the_symbol_and_does_not_ask_for_sorting():
    body = json.loads(finra_data.finra_data_build_short_interest_request_body("aapl"))
    assert body["compareFilters"][0]["fieldValue"] == "AAPL" and "sortFields" not in body


def test_rows_are_sorted_by_settlement_date_and_deduplicated():
    table = finra_data.finra_data_parse_short_interest_rows([row("2026-09-30", 3), row("2026-09-15", 2), row("2026-09-15", 4)])
    assert table.index.strftime("%Y-%m-%d").tolist() == ["2026-09-15", "2026-09-30"]
    assert table["short_shares"].tolist() == [4, 3]


def test_no_rows_gives_an_empty_table():
    assert finra_data.finra_data_parse_short_interest_rows([]).empty


def test_short_percent_uses_the_latest_share_count_filed_before_each_date():
    short = finra_data.finra_data_parse_short_interest_rows([row("2026-09-15", 50), row("2026-09-30", 60)])
    shares = pandas.Series([1000.0, 500.0], index=pandas.to_datetime(["2026-08-01", "2026-09-20"]))
    assert finra_data.finra_data_calculate_short_interest_percent_of_shares(short, shares).tolist() == pytest.approx([5.0, 12.0])


def test_a_share_class_is_written_without_a_separator_for_finra():
    assert finra_data.finra_data_convert_symbol_to_finra_symbol("BRK-B") == "BRKB"
    assert finra_data.finra_data_convert_symbol_to_finra_symbol("bf.b") == "BFB"
    assert json.loads(finra_data.finra_data_build_short_interest_request_body("BRK-B"))["compareFilters"][0]["fieldValue"] == "BRKB"
