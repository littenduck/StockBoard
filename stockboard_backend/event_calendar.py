"""Calendar facts for the event rules: Fed meetings, inflation and jobs releases, election day, option expiration days.
Pure date logic. The release dates come from config/settings.yaml (macro_event_calendar), kept by hand from the official schedules."""
import datetime
from typing import Dict, List, Optional

FOMC = "FOMC"
INFLATION_EVENT_NAME_LIST = ["CPI", "PCE"]
JOBS = "JOBS"
ELECTION_MONTH = 11
QUADRUPLE_WITCHING_MONTH_SET = {3, 6, 9, 12}
SPMO_REBALANCE_MONTH_SET = {3, 9}


def event_calendar_find_third_friday(year: int, month: int) -> datetime.date:
    first_day = datetime.date(year, month, 1)
    first_friday = first_day + datetime.timedelta(days=(4 - first_day.weekday()) % 7)
    return first_friday + datetime.timedelta(days=14)


def event_calendar_determine_whether_date_is_third_friday(day: datetime.date) -> bool:
    return day == event_calendar_find_third_friday(day.year, day.month)


def event_calendar_find_election_day(year: int) -> Optional[datetime.date]:
    """The Tuesday after the first Monday in November of an even year (US federal election day)."""
    if year % 2:
        return None
    first_day = datetime.date(year, ELECTION_MONTH, 1)
    first_monday = first_day + datetime.timedelta(days=(0 - first_day.weekday()) % 7)
    return first_monday + datetime.timedelta(days=1)


def event_calendar_determine_whether_election_day_is_inside(start_day: datetime.date, end_day: datetime.date) -> bool:
    return any(election_day is not None and start_day <= election_day <= end_day
               for election_day in (event_calendar_find_election_day(year) for year in range(start_day.year, end_day.year + 1)))


def event_calendar_determine_whether_quadruple_witching_is_within_trading_days(
    today: datetime.date, trading_day_count: int = 5,
) -> bool:
    """Counts weekdays only (market holidays are ignored: a holiday can only move the day by one)."""
    day, counted = today, 0
    while counted <= trading_day_count:
        if day.weekday() < 5:
            if day.month in QUADRUPLE_WITCHING_MONTH_SET and event_calendar_determine_whether_date_is_third_friday(day):
                return True
            counted += 1
        day += datetime.timedelta(days=1)
    return False


def event_calendar_determine_whether_spmo_rebalance_month(today: datetime.date) -> bool:
    return today.month in SPMO_REBALANCE_MONTH_SET


def event_calendar_build_covered_until_by_event_name(raw_value: Optional[dict]) -> Dict[str, datetime.date]:
    return {name: datetime.date.fromisoformat(str(day)) for name, day in (raw_value or {}).items()}


def event_calendar_determine_whether_event_is_inside(
    macro_event_calendar: List[dict], covered_until_by_event_name: Dict[str, datetime.date],
    event_name_list: List[str], start_day: datetime.date, end_day: datetime.date,
) -> Optional[bool]:
    """True when an event of one of these names falls in [start_day, end_day]; None when the calendar does not reach end_day
    (the answer would be a guess). An event may last several days (event_end_date)."""
    if any(covered_until_by_event_name.get(name, datetime.date.min) < end_day for name in event_name_list):
        return None
    for event in macro_event_calendar:
        if event["event_name"] not in event_name_list:
            continue
        first = datetime.date.fromisoformat(str(event["event_date"]))
        last = datetime.date.fromisoformat(str(event.get("event_end_date", event["event_date"])))
        if first <= end_day and last >= start_day:
            return True
    return False


def event_calendar_build_option_life_indicator_value_by_id(
    macro_event_calendar: List[dict], covered_until_by_event_name: Dict[str, datetime.date],
    today: datetime.date, expiration_date: datetime.date,
) -> Dict[str, Optional[bool]]:
    """The 'no event inside the option's life' answers for one expiration. A value of None means unknown."""
    def no_event(event_name_list: List[str]) -> Optional[bool]:
        inside = event_calendar_determine_whether_event_is_inside(
            macro_event_calendar, covered_until_by_event_name, event_name_list, today, expiration_date)
        return None if inside is None else not inside
    return {
        "no_fomc_meeting_inside_option_life": no_event([FOMC]),
        "no_cpi_or_pce_release_inside_option_life": no_event(INFLATION_EVENT_NAME_LIST),
        "no_election_day_inside_option_life": not event_calendar_determine_whether_election_day_is_inside(today, expiration_date),
    }


def event_calendar_determine_whether_jobs_report_is_within_one_day(
    macro_event_calendar: List[dict], covered_until_by_event_name: Dict[str, datetime.date], today: datetime.date,
) -> Optional[bool]:
    """True when the jobs report is released yesterday, today or tomorrow."""
    return event_calendar_determine_whether_event_is_inside(
        macro_event_calendar, covered_until_by_event_name, [JOBS],
        today - datetime.timedelta(days=1), today + datetime.timedelta(days=1))


def event_calendar_project_next_ex_dividend_date_list(
    last_ex_dividend_date: Optional[datetime.date], today: datetime.date, end_day: datetime.date, days_between: int = 91,
) -> List[datetime.date]:
    """Quarterly dividends repeat about every 91 days after the last known ex-dividend date."""
    if last_ex_dividend_date is None:
        return []
    projected, day = [], last_ex_dividend_date
    while day <= end_day:
        if day >= today:
            projected.append(day)
        day += datetime.timedelta(days=days_between)
    return projected
