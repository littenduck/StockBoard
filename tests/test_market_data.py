import datetime

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
