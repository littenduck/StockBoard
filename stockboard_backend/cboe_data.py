"""Fetch the free Cboe files: index history (VIX family, SKEW, VVIX) and the total put/call ratio.

Index history: one CSV per index. Put/call: an old CSV covers 2006-11-01 to 2019-10-04, and from 2019-10-07 there is one small
JSON file per trading day, which this module collects into a local cache file so each day is requested only once.
"""
import datetime
import io
import json
import os
import time
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional

import pandas

CBOE_INDEX_HISTORY_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{index_name}_History.csv"
CBOE_PUT_CALL_CSV_URL = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv"
CBOE_DAILY_STATISTICS_URL = "https://cdn.cboe.com/data/us/options/market_statistics/daily/{day}_daily_options"
CBOE_DAILY_STATISTICS_FIRST_DAY = datetime.date(2019, 10, 7)
CBOE_TIMEOUT_SECONDS = 30
TOTAL_PUT_CALL_RATIO_NAME = "TOTAL PUT/CALL RATIO"
PUT_CALL_CACHE_FILE_NAME = "cboe_total_put_call.csv"
index_history_cache: Dict[str, pandas.Series] = {}


def cboe_data_parse_index_history_csv(csv_text: str) -> pandas.Series:
    """DATE is month/day/year. Indexes with prices have OPEN, HIGH, LOW and CLOSE; SKEW and VVIX have one value column."""
    table = pandas.read_csv(io.StringIO(csv_text))
    value_column = "CLOSE" if "CLOSE" in table.columns else table.columns[1]
    dates = pandas.to_datetime(table["DATE"], format="%m/%d/%Y")
    return pandas.Series(table[value_column].values, index=dates, name=value_column).dropna().astype(float)


def cboe_data_fetch_index_history_series(index_name: str) -> pandas.Series:
    """For example VIX, VIX3M, VXN, VIX9D (closing values), SKEW, VVIX. The URL redirects, urllib follows it."""
    csv_bytes = urllib.request.urlopen(CBOE_INDEX_HISTORY_URL.format(index_name=index_name), timeout=CBOE_TIMEOUT_SECONDS).read()
    return cboe_data_parse_index_history_csv(csv_bytes.decode("utf8", "ignore"))


def cboe_data_fetch_index_history_series_cached(index_name: str) -> pandas.Series:
    """One download per index for the life of the process; several indicators use the VIX."""
    if index_name not in index_history_cache:
        index_history_cache[index_name] = cboe_data_fetch_index_history_series(index_name)
    return index_history_cache[index_name].copy()


def cboe_data_parse_old_put_call_csv(csv_text: str) -> pandas.Series:
    """Skips the notice lines above the header. Values have stray spaces after the commas."""
    lines = csv_text.splitlines()
    header_position = next(position for position, line in enumerate(lines) if line.strip().upper().startswith("DATE,"))
    table = pandas.read_csv(io.StringIO("\n".join(lines[header_position:])), skipinitialspace=True)
    dates = pandas.to_datetime(table.iloc[:, 0], format="%m/%d/%Y")
    return pandas.Series(table["P/C Ratio"].values, index=dates, name=TOTAL_PUT_CALL_RATIO_NAME).dropna().astype(float)


def cboe_data_fetch_old_total_put_call_ratio_series() -> pandas.Series:
    csv_bytes = urllib.request.urlopen(CBOE_PUT_CALL_CSV_URL, timeout=CBOE_TIMEOUT_SECONDS).read()
    return cboe_data_parse_old_put_call_csv(csv_bytes.decode("utf8", "ignore"))


def cboe_data_parse_daily_statistics_json(json_text: str) -> Optional[float]:
    for ratio in json.loads(json_text).get("ratios", []):
        if ratio.get("name") == TOTAL_PUT_CALL_RATIO_NAME:
            return float(ratio["value"])
    return None


def cboe_data_fetch_daily_total_put_call_ratio(day: datetime.date) -> Optional[float]:
    """None when Cboe has no file for the day (weekend, holiday: the CDN answers 403 or 404). Other errors are raised."""
    try:
        body = urllib.request.urlopen(CBOE_DAILY_STATISTICS_URL.format(day=day.isoformat()), timeout=CBOE_TIMEOUT_SECONDS).read()
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            return None
        raise
    return cboe_data_parse_daily_statistics_json(body.decode("utf8", "ignore"))


def cboe_data_load_put_call_cache(cache_file_path: str) -> pandas.Series:
    if not os.path.exists(cache_file_path):
        return pandas.Series(dtype=float, index=pandas.DatetimeIndex([]), name=TOTAL_PUT_CALL_RATIO_NAME)
    table = pandas.read_csv(cache_file_path, parse_dates=["date"])
    return pandas.Series(table["ratio"].values, index=pandas.DatetimeIndex(table["date"]), name=TOTAL_PUT_CALL_RATIO_NAME)


def cboe_data_save_put_call_cache(series: pandas.Series, cache_file_path: str) -> None:
    os.makedirs(os.path.dirname(cache_file_path), exist_ok=True)
    temporary_file_path = cache_file_path + ".tmp"
    pandas.DataFrame({"date": series.index.strftime("%Y-%m-%d"), "ratio": series.values}).to_csv(temporary_file_path, index=False)
    os.replace(temporary_file_path, cache_file_path)


def cboe_data_update_total_put_call_cache(
    cache_file_path: str, end_day: Optional[datetime.date] = None, request_pause_seconds: float = 0.2,
    fetch_day: Callable[[datetime.date], Optional[float]] = cboe_data_fetch_daily_total_put_call_ratio,
) -> pandas.Series:
    """Request every weekday after the last cached day, up to end_day. Progress is saved even if a request fails."""
    cached = cboe_data_load_put_call_cache(cache_file_path)
    end_day = end_day or datetime.date.today()
    day = CBOE_DAILY_STATISTICS_FIRST_DAY if cached.empty else cached.index[-1].date() + datetime.timedelta(days=1)
    collected = {}
    try:
        while day <= end_day:
            if day.weekday() < 5:
                ratio = fetch_day(day)
                if ratio is not None:
                    collected[pandas.Timestamp(day)] = ratio
                time.sleep(request_pause_seconds)
            day += datetime.timedelta(days=1)
    finally:
        if collected:
            cached = pandas.concat([cached, pandas.Series(collected, name=TOTAL_PUT_CALL_RATIO_NAME)]).sort_index()
            cboe_data_save_put_call_cache(cached, cache_file_path)
    return cached


def cboe_data_build_total_put_call_ratio_series(cache_file_path: str, old_series: Optional[pandas.Series] = None) -> pandas.Series:
    """2006-11-01 to 2019-10-04 from the old CSV, then the cached daily files (2019-10-07 onward)."""
    old_series = cboe_data_fetch_old_total_put_call_ratio_series() if old_series is None else old_series
    cached = cboe_data_load_put_call_cache(cache_file_path)
    combined = pandas.concat([old_series, cached[cached.index > old_series.index[-1]]])
    return combined[~combined.index.duplicated(keep="last")].sort_index()


if __name__ == "__main__":
    from stockboard_backend.settings_loader import PROJECT_DIRECTORY
    cache_path = os.path.join(PROJECT_DIRECTORY, "data", "cache", PUT_CALL_CACHE_FILE_NAME)
    series = cboe_data_update_total_put_call_cache(cache_path)
    print(f"{len(series)} days cached, {series.index[0].date()} to {series.index[-1].date()}, file {cache_path}")
