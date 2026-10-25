import datetime
from zoneinfo import ZoneInfo

import pandas

from stockboard_backend import market_data
from stockboard_backend.market_data import NEW_YORK_TIME_ZONE, market_data_determine_whether_us_market_is_open


def build_new_york_time(year, month, day, hour, minute):
    return datetime.datetime(year, month, day, hour, minute, tzinfo=NEW_YORK_TIME_ZONE)


def test_regular_day_hours():
    assert market_data_determine_whether_us_market_is_open(build_new_york_time(2026, 10, 23, 10, 0)) is True
    assert market_data_determine_whether_us_market_is_open(build_new_york_time(2026, 10, 23, 9, 0)) is False
    assert market_data_determine_whether_us_market_is_open(build_new_york_time(2026, 10, 24, 12, 0)) is False


def test_holiday_and_early_close():
    thanksgiving = datetime.date(2026, 11, 26)
    day_after = datetime.date(2026, 11, 27)
    assert market_data_determine_whether_us_market_is_open(
        build_new_york_time(2026, 11, 26, 11, 0), frozenset({thanksgiving})) is False
    assert market_data_determine_whether_us_market_is_open(
        build_new_york_time(2026, 11, 27, 12, 30), frozenset(), frozenset({day_after})) is True
    assert market_data_determine_whether_us_market_is_open(
        build_new_york_time(2026, 11, 27, 14, 0), frozenset(), frozenset({day_after})) is False


def build_history(days, closes):
    return pandas.DataFrame({"Open": closes, "High": [c + 1 for c in closes], "Low": [c - 1 for c in closes], "Close": closes,
                             "Volume": [1000.0] * len(closes)}, index=pandas.DatetimeIndex(days))


def quote_at(day_text, price, **fields):
    zone = ZoneInfo("America/New_York")
    moment = datetime.datetime.fromisoformat(day_text).replace(tzinfo=zone)
    return {"symbol": "X", "regularMarketPrice": price, "regularMarketTime": int(moment.timestamp()), "regularMarketOpen": price - 0.5,
            "regularMarketDayHigh": price + 2, "regularMarketDayLow": price - 2, "regularMarketVolume": 5000,
            "regularMarketPreviousClose": fields.pop("previous_close", 100.0), "exchangeTimezoneName": "America/New_York",
            "quoteType": fields.pop("quote_type", "EQUITY"), **fields}


def test_a_quote_from_the_same_day_replaces_the_last_bar():
    history = build_history(["2026-10-21", "2026-10-22"], [100.0, 101.0])
    merged, needs_reload = market_data.market_data_merge_quote_into_history(history, quote_at("2026-10-22T11:00", 103.0, previous_close=100.0))
    assert len(merged) == 2 and merged["Close"].iloc[-1] == 103.0 and merged["High"].iloc[-1] == 105.0 and merged["Volume"].iloc[-1] == 5000
    assert merged["Close"].iloc[0] == 100.0 and needs_reload is False
    assert history["Close"].iloc[-1] == 101.0  # the cached history is not changed


def test_a_quote_from_a_new_day_adds_a_bar_and_an_old_or_weekend_quote_changes_nothing():
    history = build_history(["2026-10-21", "2026-10-22"], [100.0, 101.0])
    merged, needs_reload = market_data.market_data_merge_quote_into_history(history, quote_at("2026-10-23T10:00", 102.0, previous_close=101.0))
    assert len(merged) == 3 and merged.index[-1] == pandas.Timestamp("2026-10-23") and merged["Close"].iloc[-1] == 102.0 and needs_reload is False
    assert market_data.market_data_merge_quote_into_history(history, quote_at("2026-10-21T10:00", 99.0))[0] is history
    assert market_data.market_data_merge_quote_into_history(history, quote_at("2026-10-25T19:00", 99.0, quote_type="FUTURE"))[0] is history  # a Sunday


def test_a_previous_close_that_does_not_match_asks_for_a_reload_except_for_futures_and_indexes():
    history = build_history(["2026-10-21", "2026-10-22"], [100.0, 101.0])
    split = quote_at("2026-10-22T11:00", 51.0, previous_close=50.0)  # a 2 for 1 split: history still says 100
    assert market_data.market_data_merge_quote_into_history(history, split)[1] is True
    assert market_data.market_data_merge_quote_into_history(history, {**split, "quoteType": "FUTURE"})[1] is False
    close_enough = quote_at("2026-10-22T11:00", 103.0, previous_close=100.05)  # 0.05% apart
    assert market_data.market_data_merge_quote_into_history(history, close_enough)[1] is False
