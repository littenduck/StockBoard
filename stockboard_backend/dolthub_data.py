"""Implied volatility history from the community DoltHub database post-no-preference/options (free, no key).

volatility_history has one row per symbol and day with iv_current, the 30 day implied volatility of the whole option chain.
It lags the market by a day or two, which is fine for a percentile over a year.
"""
import datetime
import json
import re
import time
import urllib.parse
import urllib.request
from typing import Dict, List

import pandas

DOLTHUB_QUERY_URL = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q="
DOLTHUB_TIMEOUT_SECONDS = 60
SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z.\-]{0,5}$")
HISTORY_DAY_COUNT = 400
PERCENTILE_WINDOW = 252
MINIMUM_PERCENTILE_DAY_COUNT = 120
MAX_AGE_DAYS = 7
ATTEMPT_COUNT = 3
RETRY_PAUSE_SECONDS = 3
ONE_MONTH_DAYS = 30


def dolthub_data_build_history_query(symbol: str, today: datetime.date) -> str:
    """The symbol is checked against a pattern first because it goes into the query text."""
    if not SYMBOL_PATTERN.match(symbol):
        raise ValueError("not a plain ticker symbol: " + symbol)
    first_day = today - datetime.timedelta(days=HISTORY_DAY_COUNT)
    return f"SELECT date, iv_current FROM volatility_history WHERE act_symbol='{symbol}' AND date >= '{first_day.isoformat()}' ORDER BY date"


def dolthub_data_parse_history_rows(row_list: List[Dict[str, str]]) -> pandas.Series:
    values = {pandas.Timestamp(row["date"]): float(row["iv_current"]) for row in row_list if row.get("iv_current") not in (None, "")}
    return pandas.Series(values, dtype=float).sort_index()


def dolthub_data_fetch_implied_volatility_series(symbol: str, today: datetime.date) -> pandas.Series:
    url = DOLTHUB_QUERY_URL + urllib.parse.quote(dolthub_data_build_history_query(symbol, today))
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(ATTEMPT_COUNT):  # the free server sometimes answers "context deadline exceeded" and then works
        answer = json.loads(urllib.request.urlopen(request, timeout=DOLTHUB_TIMEOUT_SECONDS).read())
        if answer.get("query_execution_status") == "Success":
            return dolthub_data_parse_history_rows(answer["rows"])
        time.sleep(RETRY_PAUSE_SECONDS)
    raise RuntimeError("DoltHub query failed: " + str(answer.get("query_execution_message")))


def dolthub_data_build_indicator_value_by_id(iv_series: pandas.Series, today: datetime.date) -> Dict[str, float]:
    """implied_volatility_percentile: share of the last year's days with a lower implied volatility than the newest one, 0 to 100.
    implied_volatility_to_one_month_ago_ratio: the newest value over the value on or before 30 days earlier."""
    if iv_series.empty or (today - iv_series.index[-1].date()).days > MAX_AGE_DAYS:
        return {}
    latest_day, latest = iv_series.index[-1], float(iv_series.iloc[-1])
    value_by_id: Dict[str, float] = {}
    window = iv_series.iloc[-PERCENTILE_WINDOW:]
    if len(window) >= MINIMUM_PERCENTILE_DAY_COUNT:
        value_by_id["implied_volatility_percentile"] = round(float((window.iloc[:-1] < latest).mean() * 100), 1)
    month_ago = iv_series[iv_series.index <= latest_day - pandas.Timedelta(days=ONE_MONTH_DAYS)]
    if len(month_ago) and month_ago.iloc[-1] > 0 and (latest_day - month_ago.index[-1]).days <= ONE_MONTH_DAYS + 7:
        value_by_id["implied_volatility_to_one_month_ago_ratio"] = round(latest / float(month_ago.iloc[-1]), 3)
    return value_by_id
