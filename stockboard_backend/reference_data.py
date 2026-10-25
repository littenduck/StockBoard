"""Three slow market gauges: the Shiller CAPE (from multpl.com), Damodaran's implied equity risk premium and the Geopolitical Risk index.

All three are monthly or weekly figures, so a day's delay does not matter. The CAPE page is a third party copy of Robert Shiller's
series with the newest month filled in daily, so it is the stopgap for the Yale file, which stopped in 2023.
"""
import html
import io
import re
import urllib.request
from typing import Optional

import pandas

BROWSER_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
MULTPL_CAPE_TABLE_URL = "https://www.multpl.com/shiller-pe/table/by-month"
DAMODARAN_ERP_URL = "https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx"
GPR_DAILY_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
DAMODARAN_ERP_COLUMN_NAME = "ERP (T12m)"
GPR_THIRTY_DAY_AVERAGE_COLUMN = "GPRD_MA30"
GPR_PERCENTILE_WINDOW_DAYS = 5 * 365
TIMEOUT_SECONDS = 60


def reference_data_download(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": BROWSER_USER_AGENT}), timeout=TIMEOUT_SECONDS).read()


def reference_data_parse_multpl_cape_table(page_html: str) -> pandas.Series:
    """Rows read 'Oct 23, 2026 &#x2002; 40.36': the first row is the latest reading, the rest are month starts."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", page_html))
    value_by_day = {}
    for month_day_year, value in re.findall(r"([A-Z][a-z]{2} \d{1,2}, \d{4})\s+\W?\s*(\d+\.\d+)", text):
        value_by_day[pandas.to_datetime(month_day_year, format="%b %d, %Y")] = float(value)
    return pandas.Series(value_by_day, dtype=float).sort_index()


def reference_data_fetch_shiller_cape_series() -> pandas.Series:
    return reference_data_parse_multpl_cape_table(reference_data_download(MULTPL_CAPE_TABLE_URL).decode("utf8", "ignore"))


def reference_data_parse_damodaran_sheet(sheet: pandas.DataFrame) -> pandas.Series:
    """The header row names the columns; the premium is a fraction, returned here in percent. Rows without a value are dropped."""
    header = [str(cell).strip() for cell in sheet.iloc[0]]
    column = header.index(DAMODARAN_ERP_COLUMN_NAME)
    table = sheet.iloc[1:]
    days = pandas.to_datetime(table.iloc[:, 0], errors="coerce")
    values = pandas.to_numeric(table.iloc[:, column], errors="coerce") * 100
    series = pandas.Series(values.values, index=pandas.DatetimeIndex(days)).dropna()
    return series[~series.index.isna()].sort_index()


def reference_data_fetch_damodaran_implied_premium_series() -> pandas.Series:
    return reference_data_parse_damodaran_sheet(pandas.read_excel(io.BytesIO(reference_data_download(DAMODARAN_ERP_URL)), header=None))


def reference_data_parse_gpr_percentile_series(table: pandas.DataFrame) -> pandas.Series:
    """The 30 day average of the daily index, as a percentile of the five years before each day (0 to 100)."""
    average = pandas.Series(table[GPR_THIRTY_DAY_AVERAGE_COLUMN].values, index=pandas.to_datetime(table["date"])).dropna().sort_index()
    window = GPR_PERCENTILE_WINDOW_DAYS

    def rank(values) -> float:
        return float((values[:-1] < values[-1]).mean() * 100)

    return average.rolling(window, min_periods=window // 2).apply(rank, raw=True).dropna()


def reference_data_fetch_geopolitical_risk_percentile_series() -> pandas.Series:
    return reference_data_parse_gpr_percentile_series(pandas.read_excel(io.BytesIO(reference_data_download(GPR_DAILY_URL))))
