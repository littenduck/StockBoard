"""Fetch FINRA's twice-a-month consolidated short interest (free, no key), one symbol at a time.

The API refuses sorting unless every partition key is an EQUAL filter, so the rows are sorted here. History starts 2017-12-29.
"""
import json
import urllib.request
from typing import List

import pandas

FINRA_SHORT_INTEREST_URL = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
FINRA_PAGE_LIMIT = 5000
FINRA_TIMEOUT_SECONDS = 60


def finra_data_convert_symbol_to_finra_symbol(symbol: str) -> str:
    """FINRA writes a share class without the separator: Yahoo's BRK-B is BRKB there."""
    return symbol.upper().replace("-", "").replace(".", "")


def finra_data_build_short_interest_request_body(symbol: str, offset: int = 0) -> bytes:
    return json.dumps({
        "limit": FINRA_PAGE_LIMIT, "offset": offset,
        "compareFilters": [{"compareType": "EQUAL", "fieldName": "symbolCode", "fieldValue": finra_data_convert_symbol_to_finra_symbol(symbol)}],
    }).encode()


def finra_data_parse_short_interest_rows(row_list: List[dict]) -> pandas.DataFrame:
    """Columns: short_shares, average_daily_volume, days_to_cover; indexed by settlement date."""
    if not row_list:
        return pandas.DataFrame(columns=["short_shares", "average_daily_volume", "days_to_cover"],
                                index=pandas.DatetimeIndex([]), dtype=float)
    table = pandas.DataFrame(row_list)
    result = pandas.DataFrame({
        "short_shares": pandas.to_numeric(table["currentShortPositionQuantity"], errors="coerce"),
        "average_daily_volume": pandas.to_numeric(table["averageDailyVolumeQuantity"], errors="coerce"),
        "days_to_cover": pandas.to_numeric(table["daysToCoverQuantity"], errors="coerce"),
    })
    result.index = pandas.DatetimeIndex(pandas.to_datetime(table["settlementDate"]))
    result = result.dropna(subset=["short_shares"])
    return result[~result.index.duplicated(keep="last")].sort_index()


def finra_data_fetch_short_interest_table(symbol: str) -> pandas.DataFrame:
    request = urllib.request.Request(
        FINRA_SHORT_INTEREST_URL, data=finra_data_build_short_interest_request_body(symbol),
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Accept": "application/json"})
    row_list = json.loads(urllib.request.urlopen(request, timeout=FINRA_TIMEOUT_SECONDS).read())
    return finra_data_parse_short_interest_rows(row_list)


def finra_data_calculate_short_interest_percent_of_shares(short_interest: pandas.DataFrame, shares_outstanding: pandas.Series) -> pandas.Series:
    """Short shares divided by the shares outstanding last reported on or before each settlement date, in percent."""
    if short_interest.empty or shares_outstanding.empty:
        return pandas.Series(dtype=float)
    shares = shares_outstanding.sort_index().reindex(short_interest.index, method="ffill")
    return (short_interest["short_shares"] / shares * 100).dropna()


if __name__ == "__main__":
    table = finra_data_fetch_short_interest_table("AAPL")
    print(f"AAPL {len(table)} rows, {table.index[0].date()} to {table.index[-1].date()}, last short shares {table['short_shares'].iloc[-1]:.0f}")
