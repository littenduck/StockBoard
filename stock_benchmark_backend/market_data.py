"""Fetch prices and calendar dates from yfinance."""
import datetime
from typing import Dict, FrozenSet, List, Optional, Tuple
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


YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
QUOTE_SYMBOLS_PER_REQUEST = 40
QUOTE_PREVIOUS_CLOSE_TOLERANCE = 0.001


def market_data_fetch_latest_quote_by_symbol(symbol_list: List[str]) -> Dict[str, dict]:
    """The latest regular-session quote of many symbols, a few dozen per request (the same endpoint yfinance uses for one symbol).
    Only the symbols Yahoo answered are returned."""
    quote_by_symbol: Dict[str, dict] = {}
    yahoo_data = yfinance.data.YfData()
    for start in range(0, len(symbol_list), QUOTE_SYMBOLS_PER_REQUEST):
        answer = yahoo_data.get_raw_json(YAHOO_QUOTE_URL, params={
            "symbols": ",".join(symbol_list[start:start + QUOTE_SYMBOLS_PER_REQUEST]), "formatted": "false"})
        for quote in answer["quoteResponse"]["result"]:
            if quote.get("regularMarketPrice") is not None and quote.get("regularMarketTime") is not None:
                quote_by_symbol[quote["symbol"]] = quote
    return quote_by_symbol


def market_data_merge_quote_into_history(price_history: pandas.DataFrame, quote: dict) -> Tuple[pandas.DataFrame, bool]:
    """Put the latest quote into the daily history as today's bar, which is what a download made during the day gives.
    Returns (history, needs_reload). The bar is replaced when the quote is from the same trading day as the last bar and appended when
    it is from a later weekday (the exchange's own date). needs_reload is True when the quote's previous close does not match the history's
    (a split, or a dividend that the adjusted history has not caught up with): the history must then be loaded again."""
    zone = ZoneInfo(quote.get("exchangeTimezoneName") or "America/New_York")
    quote_day = datetime.datetime.fromtimestamp(quote["regularMarketTime"], zone).date()
    last_day = price_history.index[-1].date()
    if quote_day < last_day or quote_day.weekday() >= 5:
        return price_history, False  # an older quote, or a weekend session of a futures contract: the history stands
    row = {"Open": quote.get("regularMarketOpen"), "High": quote.get("regularMarketDayHigh"), "Low": quote.get("regularMarketDayLow"),
           "Close": quote["regularMarketPrice"], "Volume": quote.get("regularMarketVolume")}
    merged = price_history.copy()
    if quote_day == last_day:
        previous_close_in_history = price_history["Close"].iloc[-2] if len(price_history) > 1 else None
        for column, value in row.items():
            if column in merged.columns and value is not None:
                merged.loc[merged.index[-1], column] = value
    else:
        previous_close_in_history = price_history["Close"].iloc[-1]
        new_row = pandas.DataFrame([{column: (row.get(column) if row.get(column) is not None else row["Close"] if column != "Volume" else 0)
                                     for column in merged.columns}], index=pandas.DatetimeIndex([pandas.Timestamp(quote_day)]))
        merged = pandas.concat([merged, new_row])
    previous_close = quote.get("regularMarketPreviousClose")
    can_split_or_pay = quote.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")  # futures, indexes and currencies have neither
    needs_reload = bool(can_split_or_pay and previous_close and previous_close_in_history and
                        abs(previous_close / previous_close_in_history - 1) > QUOTE_PREVIOUS_CLOSE_TOLERANCE)
    return merged, needs_reload


def market_data_find_next_earnings_date_in_calendar(calendar: Optional[dict], today: datetime.date) -> Optional[datetime.date]:
    """The calendar yfinance gives for a symbol; None means no upcoming earnings date is listed (for example an index fund)."""
    upcoming_date_list = [d for d in (calendar or {}).get("Earnings Date", []) if d >= today]
    return min(upcoming_date_list) if upcoming_date_list else None


def market_data_fetch_next_earnings_date_by_symbol(symbol: str) -> Optional[datetime.date]:
    return market_data_find_next_earnings_date_in_calendar(yfinance.Ticker(symbol).calendar, datetime.date.today())


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
