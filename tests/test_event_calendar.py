import datetime

import pytest
import yaml

from stockboard_backend import event_calendar, settings_loader
from stockboard_backend.settings_loader import PROJECT_DIRECTORY

CALENDAR = [
    {"event_name": "FOMC", "event_date": "2026-10-27", "event_end_date": "2026-10-28"},
    {"event_name": "CPI", "event_date": "2026-11-10"},
    {"event_name": "PCE", "event_date": "2026-10-29"},
    {"event_name": "JOBS", "event_date": "2026-11-06"},
]
COVERED = {"FOMC": datetime.date(2027, 12, 31), "CPI": datetime.date(2027, 12, 31), "PCE": datetime.date(2026, 12, 31),
           "JOBS": datetime.date(2027, 12, 31)}


def test_third_friday_and_election_day():
    assert event_calendar.event_calendar_find_third_friday(2026, 10) == datetime.date(2026, 10, 16)
    assert event_calendar.event_calendar_find_election_day(2026) == datetime.date(2026, 11, 3)
    assert event_calendar.event_calendar_find_election_day(2027) is None
    assert event_calendar.event_calendar_determine_whether_election_day_is_inside(datetime.date(2026, 10, 25), datetime.date(2026, 11, 20))
    assert not event_calendar.event_calendar_determine_whether_election_day_is_inside(datetime.date(2026, 11, 4), datetime.date(2027, 3, 1))


def test_quadruple_witching_looks_five_trading_days_ahead():
    assert event_calendar.event_calendar_determine_whether_quadruple_witching_is_within_trading_days(datetime.date(2026, 9, 14))  # Friday 18th
    assert not event_calendar.event_calendar_determine_whether_quadruple_witching_is_within_trading_days(datetime.date(2026, 9, 1))
    assert not event_calendar.event_calendar_determine_whether_quadruple_witching_is_within_trading_days(datetime.date(2026, 10, 12))  # October is no witching month


def test_a_meeting_of_two_days_counts_when_the_window_touches_either_day():
    inside = lambda start, end: event_calendar.event_calendar_determine_whether_event_is_inside(CALENDAR, COVERED, ["FOMC"], start, end)
    assert inside(datetime.date(2026, 10, 28), datetime.date(2026, 11, 20)) is True
    assert inside(datetime.date(2026, 10, 29), datetime.date(2026, 11, 20)) is False


def test_an_answer_past_the_end_of_the_calendar_is_unknown():
    life = event_calendar.event_calendar_build_option_life_indicator_value_by_id(
        CALENDAR, COVERED, datetime.date(2026, 12, 20), datetime.date(2027, 1, 20))
    assert life["no_cpi_or_pce_release_inside_option_life"] is None  # PCE dates stop at 2026-12-31
    assert life["no_fomc_meeting_inside_option_life"] is True


def test_jobs_report_within_one_day():
    near = lambda day: event_calendar.event_calendar_determine_whether_jobs_report_is_within_one_day(CALENDAR, COVERED, day)
    assert near(datetime.date(2026, 11, 5)) is True and near(datetime.date(2026, 11, 4)) is False


def test_ex_dividend_dates_are_projected_every_quarter():
    projected = event_calendar.event_calendar_project_next_ex_dividend_date_list(
        datetime.date(2026, 8, 10), datetime.date(2026, 10, 25), datetime.date(2026, 11, 20))
    assert projected == [datetime.date(2026, 11, 9)]
    assert event_calendar.event_calendar_project_next_ex_dividend_date_list(None, datetime.date(2026, 10, 25), datetime.date(2026, 11, 20)) == []


def test_the_release_calendar_in_settings_is_well_formed():
    settings = settings_loader.settings_loader_load_settings_from_yaml_file(f"{PROJECT_DIRECTORY}/config/settings.yaml")
    covered = event_calendar.event_calendar_build_covered_until_by_event_name(settings.macro_event_covered_until)
    assert set(covered) == {"FOMC", "CPI", "JOBS", "PCE"}
    for event in settings.macro_event_calendar:
        day = datetime.date.fromisoformat(str(event["event_date"]))
        assert day <= covered[event["event_name"]]
        assert event["event_name"] == "FOMC" or day.weekday() < 5, event  # data releases come out on weekdays
