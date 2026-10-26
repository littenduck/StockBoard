"""One Yahoo request per symbol for all company data, shaped like the yfinance objects the indicator code already reads.

yfinance asks for the modules of Yahoo's quoteSummary one request at a time (info alone is three requests). The endpoint accepts a list of
modules, so one request returns everything: key statistics, financial data, analyst estimates and ratings, calendar and insider trades.
"""
import datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import pandas
import yfinance

QUOTE_SUMMARY_URL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
MODULE_LIST = ["price", "summaryDetail", "defaultKeyStatistics", "financialData", "assetProfile", "quoteType", "earningsTrend",
               "recommendationTrend", "calendarEvents", "insiderTransactions"]
INFO_MODULE_LIST = ["price", "summaryDetail", "defaultKeyStatistics", "financialData", "assetProfile", "quoteType"]  # later ones win
NEW_YORK_TIME_ZONE = ZoneInfo("America/New_York")
# Fields of the live quote (one batched request for every symbol) that are fresher than the hourly company data.
QUOTE_FIELD_BY_INFO_FIELD = {"marketCap": "marketCap", "trailingPE": "trailingPE", "forwardPE": "forwardPE", "sharesOutstanding": "sharesOutstanding"}


def yahoo_company_unwrap(value: Any) -> Any:
    """A plain number or text; None for the empty {} Yahoo sends for a missing value and for lists and nested objects."""
    if isinstance(value, dict):
        return value.get("raw") if "raw" in value else None
    return None if isinstance(value, list) else value


def yahoo_company_epoch_to_new_york_date(value: Any) -> Optional[datetime.date]:
    seconds = yahoo_company_unwrap(value)
    return None if seconds is None else datetime.datetime.fromtimestamp(seconds, NEW_YORK_TIME_ZONE).date()


def yahoo_company_build_info(result: dict) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    for module_name in INFO_MODULE_LIST:
        for key, value in (result.get(module_name) or {}).items():
            plain = yahoo_company_unwrap(value)
            if plain is not None and plain != "":
                info[key] = plain
    return info


def yahoo_company_build_eps_trend(result: dict) -> Optional[pandas.DataFrame]:
    row_by_period = {}
    for trend in (result.get("earningsTrend") or {}).get("trend", []):
        eps_trend = trend.get("epsTrend") or {}
        row_by_period[trend["period"]] = {name: yahoo_company_unwrap(value) for name, value in eps_trend.items() if name != "maxAge"}
    return pandas.DataFrame.from_dict(row_by_period, orient="index") if row_by_period else None


def yahoo_company_build_recommendations_summary(result: dict) -> Optional[pandas.DataFrame]:
    trend_list = (result.get("recommendationTrend") or {}).get("trend", [])
    return pandas.DataFrame([{key: value for key, value in trend.items() if key != "maxAge"} for trend in trend_list]) if trend_list else None


def yahoo_company_build_insider_transactions(result: dict) -> Optional[pandas.DataFrame]:
    row_list = []
    for transaction in (result.get("insiderTransactions") or {}).get("transactions", []):
        start_day = yahoo_company_epoch_to_new_york_date(transaction.get("startDate"))
        if start_day is not None:
            row_list.append({"Shares": yahoo_company_unwrap(transaction.get("shares")) or 0,
                             "Text": transaction.get("transactionText", ""), "Start Date": start_day})
    return pandas.DataFrame(row_list) if row_list else None


def yahoo_company_build_calendar(result: dict) -> Optional[dict]:
    events = result.get("calendarEvents")
    if not events:
        return None
    calendar: Dict[str, Any] = {}
    earnings_day_list = [yahoo_company_epoch_to_new_york_date(value) for value in (events.get("earnings") or {}).get("earningsDate", [])]
    if earnings_day_list:
        calendar["Earnings Date"] = earnings_day_list
    if yahoo_company_epoch_to_new_york_date(events.get("exDividendDate")):
        calendar["Ex-Dividend Date"] = yahoo_company_epoch_to_new_york_date(events.get("exDividendDate"))
    return calendar


def yahoo_company_parse_quote_summary(result: dict) -> dict:
    """The snapshot the indicator code reads: info (a flat dictionary), eps_trend, recommendations_summary, insider_transactions, calendar."""
    return {"info": yahoo_company_build_info(result), "eps_trend": yahoo_company_build_eps_trend(result),
            "recommendations_summary": yahoo_company_build_recommendations_summary(result),
            "insider_transactions": yahoo_company_build_insider_transactions(result), "calendar": yahoo_company_build_calendar(result)}


def yahoo_company_fetch_snapshot(symbol: str) -> dict:
    answer = yfinance.data.YfData().get_raw_json(
        QUOTE_SUMMARY_URL.format(symbol=symbol), params={"modules": ",".join(MODULE_LIST), "formatted": "false"})
    return yahoo_company_parse_quote_summary(answer["quoteSummary"]["result"][0])


def yahoo_company_overlay_quote(snapshot: dict, quote: Optional[dict]) -> dict:
    """Put the live market cap, price earnings ratios and share count of the latest quote over the hourly figures."""
    if not quote or not isinstance(snapshot.get("info"), dict):
        return snapshot
    info = dict(snapshot["info"])
    for info_field, quote_field in QUOTE_FIELD_BY_INFO_FIELD.items():
        if quote.get(quote_field) is not None:
            info[info_field] = quote[quote_field]
    if "trailingEps" not in info and quote.get("epsTrailingTwelveMonths") is not None:
        info["trailingEps"] = quote["epsTrailingTwelveMonths"]
    return {**snapshot, "info": info}
