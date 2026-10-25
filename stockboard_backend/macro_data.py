"""Fetch rate, credit and macro series from the public FRED and ALFRED CSV downloads (no key needed)."""
import datetime
import io
import urllib.request
from typing import Dict, Iterable, List

import pandas

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
ALFRED_CSV_URL = "https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={series_id}&vintage_date={vintage_date}"
FRED_TIMEOUT_SECONDS = 15

# One download per series for the life of the process: several indicators are built from the same series (DGS10, DFF ...).
fred_series_cache: Dict[str, pandas.Series] = {}


def macro_data_parse_fred_csv_bytes(csv_bytes: bytes) -> pandas.Series:
    """The first column is the date, the second the value; missing values are written as a dot."""
    table = pandas.read_csv(io.BytesIO(csv_bytes), na_values=["."])
    return pandas.Series(table.iloc[:, 1].values, index=pandas.to_datetime(table.iloc[:, 0])).dropna()


def macro_data_fetch_fred_series_by_series_id(series_id: str) -> pandas.Series:
    """Values in the series' own frequency, oldest first, missing days dropped. Raises on network failure."""
    # FRED stalls requests that carry a custom User-Agent, so keep urllib's default headers.
    csv_bytes = urllib.request.urlopen(FRED_CSV_URL + series_id, timeout=FRED_TIMEOUT_SECONDS).read()
    return macro_data_parse_fred_csv_bytes(csv_bytes)


def macro_data_fetch_fred_series_cached(series_id: str) -> pandas.Series:
    if series_id not in fred_series_cache:
        fred_series_cache[series_id] = macro_data_fetch_fred_series_by_series_id(series_id)
    return fred_series_cache[series_id].copy()


def macro_data_fetch_alfred_series_as_of_date(series_id: str, as_of_date: datetime.date) -> pandas.Series:
    """The series as it stood on that date, with the revisions known then (ALFRED keeps every vintage)."""
    csv_bytes = urllib.request.urlopen(
        ALFRED_CSV_URL.format(series_id=series_id, vintage_date=as_of_date.isoformat()), timeout=FRED_TIMEOUT_SECONDS).read()
    return macro_data_parse_fred_csv_bytes(csv_bytes)


def macro_data_build_point_in_time_year_over_year_series(
    series_id: str, as_of_date_list: Iterable[datetime.date], periods_per_year: int = 12,
    fetch_as_of=macro_data_fetch_alfred_series_as_of_date,
) -> pandas.Series:
    """For each date: the year over year percent change of the newest observation known on that date.
    This is what a backtest may use, because later revisions are not allowed to leak back."""
    value_by_date = {}
    for as_of_date in as_of_date_list:
        vintage = fetch_as_of(series_id, as_of_date)
        if len(vintage) > periods_per_year:
            value_by_date[pandas.Timestamp(as_of_date)] = (vintage.iloc[-1] / vintage.iloc[-1 - periods_per_year] - 1) * 100
    return pandas.Series(value_by_date, dtype=float)


def macro_data_fetch_treasury_ten_year_yield_series() -> pandas.Series:
    return macro_data_fetch_fred_series_by_series_id("DGS10")


def macro_data_fetch_high_yield_credit_spread_series() -> pandas.Series:
    """Option adjusted spread in percent points; multiply by 100 for basis points."""
    return macro_data_fetch_fred_series_by_series_id("BAMLH0A0HYM2")


def macro_data_get_upcoming_macro_event_list_from_calendar(
    macro_event_calendar: list, window_end_date: datetime.date,
) -> List[dict]:
    today = datetime.date.today()
    return [event for event in macro_event_calendar
            if today <= datetime.date.fromisoformat(str(event["event_date"])) <= window_end_date]
