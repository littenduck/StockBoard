"""Fetch prices and calendar dates from yfinance."""
import datetime
from typing import Dict, FrozenSet, List, Optional
from zoneinfo import ZoneInfo

import pandas
import yfinance

NEW_YORK_TIME_ZONE = ZoneInfo("America/New_York")


def market_data_fetch_daily_price_history_for_symbol_list(
    symbol_list: List[str], history_period: str,
) -> Dict[str, pandas.DataFrame]:
    """Returns only the symbols that came back with data."""
    raw_table = yfinance.download(symbol_list, period=history_period, interval="1d", group_by="ticker",
                                  auto_adjust=True, progress=False, threads=True)
    price_history_by_symbol = {}
    for symbol in symbol_list:
        try:
            price_history = raw_table[symbol].dropna(subset=["Close"])
        except KeyError:
            continue
        if len(price_history):
            price_history_by_symbol[symbol] = price_history
    return price_history_by_symbol


def market_data_fetch_next_earnings_date_by_symbol(symbol: str) -> Optional[datetime.date]:
    """None means no upcoming earnings date is listed (for example an index fund)."""
    calendar = yfinance.Ticker(symbol).calendar or {}
    today = datetime.date.today()
    upcoming_date_list = [d for d in calendar.get("Earnings Date", []) if d >= today]
    return min(upcoming_date_list) if upcoming_date_list else None


def market_data_determine_whether_us_market_is_open(
    current_time: datetime.datetime,
    holiday_date_set: FrozenSet[datetime.date] = frozenset(),
    early_close_date_set: FrozenSet[datetime.date] = frozenset(),
) -> bool:
    """Regular hours Monday to Friday, 9:30 to 16:00 New York time; closed on holidays,
    13:00 close on early close days. Both sets come from config/settings.yaml."""
    new_york_time = current_time.astimezone(NEW_YORK_TIME_ZONE)
    if new_york_time.weekday() >= 5 or new_york_time.date() in holiday_date_set:
        return False
    closing_time = datetime.time(13, 0) if new_york_time.date() in early_close_date_set else datetime.time(16, 0)
    return datetime.time(9, 30) <= new_york_time.time() <= closing_time
