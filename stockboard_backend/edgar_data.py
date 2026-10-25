"""Fetch SEC EDGAR company facts (free, no key) and turn them into point-in-time series stamped with the filing date.

SEC asks every client to identify itself: set the environment variable EDGAR_CONTACT (for example an email address).
Each value is stamped with the date the filing reached EDGAR, so a backtest never sees a number before it was public.
"""
import json
import os
import urllib.request
from typing import Dict, List, Optional

import pandas

EDGAR_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
EDGAR_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
EDGAR_TIMEOUT_SECONDS = 60
ANNUAL_DAY_RANGE = (350, 380)
YEAR_TO_DATE_MAXIMUM_DAYS = 300
DATE_MATCH_TOLERANCE_DAYS = 10
REPORT_FORM_SET = {"10-K", "10-Q"}
ticker_cik_cache: Dict[str, str] = {}
company_facts_cache: Dict[str, dict] = {}


def edgar_data_build_user_agent() -> str:
    return "StockBoard research " + os.environ.get("EDGAR_CONTACT", "unset-contact")


def edgar_data_fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": edgar_data_build_user_agent()})
    return json.loads(urllib.request.urlopen(request, timeout=EDGAR_TIMEOUT_SECONDS).read())


def edgar_data_fetch_cik_by_ticker(ticker: str) -> str:
    """Ten-digit CIK as EDGAR's URLs want it."""
    if not ticker_cik_cache:
        for company in edgar_data_fetch_json(EDGAR_TICKER_URL).values():
            ticker_cik_cache[company["ticker"].upper()] = str(company["cik_str"]).zfill(10)
    return ticker_cik_cache[ticker.upper()]


def edgar_data_fetch_company_facts(ticker: str) -> dict:
    cik = edgar_data_fetch_cik_by_ticker(ticker)
    if cik not in company_facts_cache:
        company_facts_cache[cik] = edgar_data_fetch_json(EDGAR_COMPANY_FACTS_URL.format(cik=cik))
    return company_facts_cache[cik]


def edgar_data_fetch_submissions(ticker: str) -> dict:
    return edgar_data_fetch_json(EDGAR_SUBMISSIONS_URL.format(cik=edgar_data_fetch_cik_by_ticker(ticker)))


def edgar_data_extract_fact_table(
        company_facts: dict, concept_name_list: List[str], unit: str = "USD", taxonomy: str = "us-gaap") -> pandas.DataFrame:
    """Rows of one measure. Companies change concept names over the years, so every name is read and each period keeps
    the version that was filed first. Columns: start (NaT for balance sheet items), end, val, filed, form."""
    column_list = ["start", "end", "val", "filed", "form"]
    row_list = []
    for concept_name in concept_name_list:
        concept = company_facts.get("facts", {}).get(taxonomy, {}).get(concept_name)
        for fact in (concept or {}).get("units", {}).get(unit, []):
            row_list.append({"start": fact.get("start"), "end": fact["end"], "val": fact["val"], "filed": fact["filed"],
                             "form": fact.get("form"), "rank": concept_name_list.index(concept_name)})
    if not row_list:
        return pandas.DataFrame(columns=column_list)
    table = pandas.DataFrame(row_list)
    for column in ("start", "end", "filed"):
        table[column] = pandas.to_datetime(table[column])
    table = table[table["form"].isin(REPORT_FORM_SET)].sort_values(["filed", "rank"])
    # the earliest filing of a period wins (what was public first), and among equals the earlier concept name
    table = table.drop_duplicates(subset=["start", "end"], keep="first") if table["start"].notna().any() \
        else table.drop_duplicates(subset=["end"], keep="first")
    return table[column_list].reset_index(drop=True)


def edgar_data_build_instant_series(fact_table: pandas.DataFrame) -> pandas.Series:
    """Balance sheet items and share counts, indexed by the day the filing was made public."""
    if fact_table.empty:
        return pandas.Series(dtype=float)
    series = pandas.Series(fact_table["val"].astype(float).values, index=pandas.DatetimeIndex(fact_table["filed"]))
    return series[~series.index.duplicated(keep="last")].sort_index()


def edgar_data_build_trailing_twelve_month_series(fact_table: pandas.DataFrame) -> pandas.Series:
    """Twelve month totals of a flow measure, indexed by filing date.

    A 10-K gives the fiscal year itself. A 10-Q gives the year to date, so the total is the last fiscal year plus this year to date
    minus the same stretch of the year before (found in the same filing)."""
    if fact_table.empty:
        return pandas.Series(dtype=float)
    table = fact_table.dropna(subset=["start"]).copy()
    table["days"] = (table["end"] - table["start"]).dt.days
    annual = table[table["days"].between(*ANNUAL_DAY_RANGE)]
    year_to_date = table[table["days"] <= YEAR_TO_DATE_MAXIMUM_DAYS]
    tolerance = pandas.Timedelta(days=DATE_MATCH_TOLERANCE_DAYS)
    total_by_filing_date: Dict[pandas.Timestamp, float] = {}
    for _, row in annual[annual["form"] == "10-K"].iterrows():
        total_by_filing_date[row["filed"]] = float(row["val"])
    # a 10-Q also carries the single quarter; its longest period is the year to date, which is the one used
    latest_year_to_date = year_to_date[year_to_date["form"] == "10-Q"].sort_values("days").groupby(["filed", "end"]).tail(1)
    for _, row in latest_year_to_date.iterrows():
        last_year = annual[(annual["end"] - (row["start"] - pandas.Timedelta(days=1))).abs() <= tolerance]
        same_stretch = year_to_date[((year_to_date["start"] - (row["start"] - pandas.Timedelta(days=365))).abs() <= tolerance)
                                    & ((year_to_date["end"] - (row["end"] - pandas.Timedelta(days=365))).abs() <= tolerance)]
        if last_year.empty or same_stretch.empty:
            continue
        total_by_filing_date[row["filed"]] = float(last_year["val"].iloc[0] + row["val"] - same_stretch["val"].iloc[0])
    series = pandas.Series(total_by_filing_date, dtype=float).sort_index()
    return series[~series.index.duplicated(keep="last")]


def edgar_data_pick_latest_known(series: pandas.Series, day: pandas.Timestamp, days_back: int = 0) -> Optional[float]:
    """The last value filed on or before day minus days_back."""
    known = series[series.index <= day - pandas.Timedelta(days=days_back)]
    return None if known.empty else float(known.iloc[-1])
