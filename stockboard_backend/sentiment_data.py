"""Fetch the free sentiment histories: CNN Fear and Greed, the AAII survey and the NAAIM Exposure Index.

CNN serves its history as JSON when the request looks like it comes from cnn.com. AAII blocks scripts with a bot check, so its
spreadsheet is read from the Internet Archive copy; the NAAIM spreadsheet is a dated upload, also found through the archive.
Both archive copies can be a few weeks behind the live sites, which is fine for a backtest and wrong for a live reading.
"""
import datetime
import io
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

import pandas

BROWSER_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
CNN_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{first_day}"
CNN_FEAR_GREED_FIRST_DAY = datetime.date(2021, 1, 4)
AAII_SURVEY_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
NAAIM_UPLOAD_PREFIX = "naaim.org/wp-content/uploads/*"
NAAIM_FILE_PATTERN = ".*USE_Data.*xlsx"
WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx?"
WAYBACK_RAW_URL = "https://web.archive.org/web/{timestamp}id_/{original}"
AAII_MINIMUM_FILE_BYTES = 100_000  # the bot-check page the archive may hold instead of the sheet is about 6 KB
TIMEOUT_SECONDS = 90
RETRY_STATUS_CODE_SET = {429, 502, 503, 504}
RETRY_PAUSE_SECONDS = (10, 30, 60)
WAYBACK_PAUSE_SECONDS = 3
aaii_table_cache: Dict[str, pandas.DataFrame] = {}
aaii_download_lock = threading.Lock()


def sentiment_data_open_url(url: str, header_by_name: Optional[dict] = None) -> bytes:
    """The Internet Archive answers 429 when asked too fast; wait and ask again a few times."""
    request = urllib.request.Request(url, headers={"User-Agent": BROWSER_USER_AGENT, **(header_by_name or {})})
    for pause in RETRY_PAUSE_SECONDS:
        try:
            return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS).read()
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_STATUS_CODE_SET:
                raise
            time.sleep(pause)
    return urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS).read()


# ---- CNN Fear and Greed ------------------------------------------------------------------------------------------------------

def sentiment_data_parse_cnn_fear_greed_json(json_text: str) -> pandas.Series:
    """Daily score 0 to 100; x is a UTC millisecond timestamp."""
    point_list = json.loads(json_text)["fear_and_greed_historical"]["data"]
    days = pandas.to_datetime([point["x"] for point in point_list], unit="ms").normalize()
    series = pandas.Series([float(point["y"]) for point in point_list], index=days, name="fear_greed_index")
    return series[~series.index.duplicated(keep="last")].sort_index()


def sentiment_data_fetch_cnn_fear_greed_series() -> pandas.Series:
    body = sentiment_data_open_url(
        CNN_FEAR_GREED_URL.format(first_day=CNN_FEAR_GREED_FIRST_DAY.isoformat()),
        {"Referer": "https://www.cnn.com/", "Origin": "https://www.cnn.com", "Accept": "application/json"})
    return sentiment_data_parse_cnn_fear_greed_json(body.decode("utf8"))


# ---- Internet Archive --------------------------------------------------------------------------------------------------------

def sentiment_data_parse_wayback_capture_lines(cdx_text: str, minimum_bytes: int = 0) -> Optional[Tuple[str, str]]:
    """Lines are 'timestamp original length'. Returns (timestamp, original) of the newest capture that is large enough."""
    capture_list = []
    for line in cdx_text.splitlines():
        parts = line.split()
        if len(parts) == 3 and int(parts[2]) >= minimum_bytes:
            capture_list.append((parts[0], parts[1]))
    return max(capture_list) if capture_list else None


def sentiment_data_find_latest_wayback_capture(
        url: str, original_filter: Optional[str] = None, minimum_bytes: int = 0) -> Tuple[str, str]:
    query = {"url": url, "output": "txt", "fl": "timestamp,original,length", "filter": ["statuscode:200"], "collapse": "digest"}
    if original_filter:
        query["filter"].append("original:" + original_filter)
    query["matchType"] = "exact" if "*" not in url else "prefix"
    query["url"] = url.rstrip("*")
    time.sleep(WAYBACK_PAUSE_SECONDS)
    cdx_text = sentiment_data_open_url(WAYBACK_CDX_URL + urllib.parse.urlencode(query, doseq=True)).decode("utf8")
    capture = sentiment_data_parse_wayback_capture_lines(cdx_text, minimum_bytes)
    if capture is None:
        raise LookupError(f"no usable Internet Archive capture of {url}")
    return capture


def sentiment_data_fetch_wayback_file(timestamp: str, original: str) -> bytes:
    time.sleep(WAYBACK_PAUSE_SECONDS)
    return sentiment_data_open_url(WAYBACK_RAW_URL.format(timestamp=timestamp, original=original))


# ---- AAII --------------------------------------------------------------------------------------------------------------------

def sentiment_data_parse_aaii_sheet(sheet: pandas.DataFrame) -> pandas.DataFrame:
    """Rows whose first cell is a date: Bullish, Neutral, Bearish as fractions in the sheet, returned here in percent."""
    dated = sheet[sheet.iloc[:, 0].map(lambda cell: isinstance(cell, (datetime.datetime, pandas.Timestamp)))]
    table = dated.iloc[:, 1:4].apply(pandas.to_numeric, errors="coerce")
    table.columns = ["bullish_percent", "neutral_percent", "bearish_percent"]
    table.index = pandas.DatetimeIndex(dated.iloc[:, 0]).normalize()
    table = table.dropna() * 100
    table["bullish_minus_bearish_percent"] = table["bullish_percent"] - table["bearish_percent"]
    return table[~table.index.duplicated(keep="last")].sort_index()


def sentiment_data_fetch_aaii_survey_table() -> pandas.DataFrame:
    """Downloaded once per process: two indicators read it."""
    with aaii_download_lock:  # two indicators ask at once; the second waits and reuses the first download
        if "table" not in aaii_table_cache:
            aaii_table_cache["table"] = sentiment_data_download_aaii_survey_table()
        return aaii_table_cache["table"].copy()


def sentiment_data_download_aaii_survey_table() -> pandas.DataFrame:
    timestamp, original = sentiment_data_find_latest_wayback_capture(
        AAII_SURVEY_URL.split("://", 1)[1], minimum_bytes=AAII_MINIMUM_FILE_BYTES)
    raw = sentiment_data_fetch_wayback_file(timestamp, original)
    return sentiment_data_parse_aaii_sheet(pandas.read_excel(io.BytesIO(raw), sheet_name="SENTIMENT", header=None))


# ---- NAAIM -------------------------------------------------------------------------------------------------------------------

def sentiment_data_parse_naaim_sheet(sheet: pandas.DataFrame) -> pandas.Series:
    """Header row has 'Date' and 'Mean/Average'. The sheet lists the newest week first and repeats the first week."""
    table = sheet.iloc[1:, :2].copy()
    table.columns = ["date", "value"]
    table["date"] = pandas.to_datetime(table["date"], errors="coerce")
    table["value"] = pandas.to_numeric(table["value"], errors="coerce")
    table = table.dropna()
    series = pandas.Series(table["value"].values, index=pandas.DatetimeIndex(table["date"]).normalize(), name="naaim_exposure_index")
    return series[~series.index.duplicated(keep="first")].sort_index()


def sentiment_data_fetch_naaim_exposure_series() -> pandas.Series:
    timestamp, original = sentiment_data_find_latest_wayback_capture(
        NAAIM_UPLOAD_PREFIX, original_filter=NAAIM_FILE_PATTERN)
    raw = sentiment_data_fetch_wayback_file(timestamp, original)
    return sentiment_data_parse_naaim_sheet(pandas.read_excel(io.BytesIO(raw), header=None))


if __name__ == "__main__":
    fear_greed = sentiment_data_fetch_cnn_fear_greed_series()
    aaii = sentiment_data_fetch_aaii_survey_table()
    naaim = sentiment_data_fetch_naaim_exposure_series()
    for name, data in (("cnn fear and greed", fear_greed), ("aaii", aaii), ("naaim", naaim)):
        print(f"{name:20s} {len(data):6d} rows, {data.index[0].date()} to {data.index[-1].date()}")
