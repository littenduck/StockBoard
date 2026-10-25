import datetime
import json

import pandas
import pytest

from stockboard_backend import sentiment_data


def test_cnn_json_becomes_a_daily_score_series():
    text = json.dumps({"fear_and_greed_historical": {"data": [
        {"x": 1609804800000.0, "y": 50.0, "rating": "neutral"}, {"x": 1609718400000.0, "y": 40.5, "rating": "fear"},
        {"x": 1609804800000.0, "y": 55.0, "rating": "neutral"}]}})
    series = sentiment_data.sentiment_data_parse_cnn_fear_greed_json(text)
    assert series.index.strftime("%Y-%m-%d").tolist() == ["2021-01-04", "2021-01-05"]
    assert series.tolist() == [40.5, 55.0]


def test_wayback_capture_choice_takes_the_newest_large_enough_file():
    lines = "20260101000000 http://x/a.xls 6000\n20260301000000 http://x/a.xls 500000\n20260401000000 http://x/a.xls 7000\n"
    assert sentiment_data.sentiment_data_parse_wayback_capture_lines(lines, 100_000) == ("20260301000000", "http://x/a.xls")
    assert sentiment_data.sentiment_data_parse_wayback_capture_lines(lines, 900_000) is None


def test_aaii_sheet_keeps_dated_rows_and_converts_to_percent():
    sheet = pandas.DataFrame([
        [None, None, None, None], ["Reported", None, None, None], ["Date", "Bullish", "Neutral", "Bearish"],
        [datetime.datetime(1987, 7, 24), 0.36, 0.5, 0.14], [datetime.datetime(1987, 7, 31), 0.26, 0.48, 0.26],
        [datetime.datetime(1987, 8, 7), None, None, None], ["Average", 0.38, 0.31, 0.30]])
    table = sentiment_data.sentiment_data_parse_aaii_sheet(sheet)
    assert table["bullish_percent"].tolist() == pytest.approx([36.0, 26.0])
    assert table["bullish_minus_bearish_percent"].tolist() == pytest.approx([22.0, 0.0])


def test_naaim_sheet_uses_the_mean_column_and_drops_the_repeated_week():
    sheet = pandas.DataFrame([["Date", "Mean/Average"], [datetime.datetime(2006, 7, 12), 31.2],
                              [datetime.datetime(2006, 7, 5), 19.444444], [datetime.datetime(2006, 7, 5), 19.44]])
    series = sentiment_data.sentiment_data_parse_naaim_sheet(sheet)
    assert series.index.strftime("%Y-%m-%d").tolist() == ["2006-07-05", "2006-07-12"]
    assert series.iloc[0] == pytest.approx(19.444444)
