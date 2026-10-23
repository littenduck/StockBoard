"""Fetch rate and credit series from the public FRED CSV download (no key needed)."""
import datetime
import io
import urllib.request
from typing import List

import pandas

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
FRED_TIMEOUT_SECONDS = 15


def macro_data_fetch_fred_series_by_series_id(series_id: str) -> pandas.Series:
    """Daily values, oldest first, missing days dropped. Raises on network failure."""
    # FRED stalls requests that carry a custom User-Agent, so keep urllib's default headers.
    csv_bytes = urllib.request.urlopen(FRED_CSV_URL + series_id, timeout=FRED_TIMEOUT_SECONDS).read()
    table = pandas.read_csv(io.BytesIO(csv_bytes), na_values=["."])
    return pandas.Series(table.iloc[:, 1].values, index=pandas.to_datetime(table.iloc[:, 0])).dropna()


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
