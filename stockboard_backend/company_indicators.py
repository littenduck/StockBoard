"""Company indicators worked out from the yfinance info dictionary, the analyst tables and the insider table.
Pure functions: the caller fetches the data. A figure that is missing or cannot be worked out is left out (the rule reads unknown)."""
import datetime
import math
from typing import Dict, Optional

import pandas

INSIDER_SELLING_WINDOW_DAYS = 180
INSIDER_BUYING_WINDOW_DAYS = 90
SECTOR_ETF_BY_SECTOR_NAME = {
    "Technology": "XLK", "Financial Services": "XLF", "Healthcare": "XLV", "Energy": "XLE", "Industrials": "XLI",
    "Consumer Cyclical": "XLY", "Consumer Defensive": "XLP", "Utilities": "XLU", "Basic Materials": "XLB",
    "Real Estate": "XLRE", "Communication Services": "XLC",
}


def company_indicators_get_number(info: dict, key: str) -> Optional[float]:
    value = info.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(value):
        return None
    return float(value)


def company_indicators_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def company_indicators_build_info_indicator_value_by_id(info: dict) -> Dict[str, float]:
    number = lambda key: company_indicators_get_number(info, key)
    market_cap, ebitda, free_cash_flow = number("marketCap"), number("ebitda"), number("freeCashflow")
    forward_pe, trailing_pe = number("forwardPE"), number("trailingPE")
    total_debt, total_cash = number("totalDebt"), number("totalCash")
    shares, dividend_rate = number("sharesOutstanding"), number("dividendRate")
    value_by_id: Dict[str, Optional[float]] = {
        "market_capitalization_billion_usd": None if market_cap is None else market_cap / 1e9,
        "trailing_twelve_month_eps": number("trailingEps"),
        "trailing_twelve_month_free_cash_flow": free_cash_flow,
        "revenue_year_over_year_percent": None if number("revenueGrowth") is None else number("revenueGrowth") * 100,
        "gross_margin_percent": number("grossMargins") * 100 if number("grossMargins") else None,  # banks report 0: no gross margin
        "return_on_equity_percent": None if number("returnOnEquity") is None else number("returnOnEquity") * 100,
        "forward_pe_to_trailing_pe_ratio": company_indicators_divide(forward_pe, trailing_pe) if (forward_pe or 0) > 0 and (trailing_pe or 0) > 0 else None,
        "enterprise_value_to_ebitda": company_indicators_divide(number("enterpriseValue"), ebitda) if (ebitda or 0) > 0 else None,
        "free_cash_flow_yield_percent": None if company_indicators_divide(free_cash_flow, market_cap) is None else free_cash_flow / market_cap * 100,
        "net_debt_to_ebitda": None if total_debt is None or total_cash is None or (ebitda or 0) <= 0 else (total_debt - total_cash) / ebitda,
        "operating_cash_flow_to_net_income_ratio": company_indicators_divide(number("operatingCashflow"), number("netIncomeToCommon"))
        if (number("netIncomeToCommon") or 0) > 0 else None,
    }
    if not dividend_rate:
        if "trailingEps" in info:  # a company that pays no dividend passes; a fund has no such ratio
            value_by_id["dividend_to_free_cash_flow_ratio"] = 0.0
    elif shares is not None and (free_cash_flow or 0) > 0:
        value_by_id["dividend_to_free_cash_flow_ratio"] = dividend_rate * shares / free_cash_flow
    return {key: round(value, 4) for key, value in value_by_id.items() if value is not None}


def company_indicators_build_estimate_indicator_value_by_id(
    eps_trend: Optional[pandas.DataFrame], recommendations_summary: Optional[pandas.DataFrame], forward_pe: Optional[float],
) -> Dict[str, float]:
    """eps_trend has rows 0y and +1y with columns current and 30daysAgo; recommendations_summary has the row 0m."""
    value_by_id: Dict[str, float] = {}
    if eps_trend is not None and "+1y" in eps_trend.index and "0y" in eps_trend.index:
        next_year_now, next_year_before = eps_trend.loc["+1y", "current"], eps_trend.loc["+1y", "30daysAgo"]
        this_year_now = eps_trend.loc["0y", "current"]
        if next_year_before and next_year_before > 0 and not math.isnan(next_year_now):
            value_by_id["eps_estimate_next_year_four_week_change_percent"] = (next_year_now / next_year_before - 1) * 100
        if this_year_now and this_year_now > 0 and next_year_now > this_year_now and forward_pe and forward_pe > 0:
            value_by_id["peg_ratio"] = forward_pe / ((next_year_now / this_year_now - 1) * 100)
    if recommendations_summary is not None and len(recommendations_summary):
        current = recommendations_summary.iloc[0]
        total = sum(current[column] for column in ("strongBuy", "buy", "hold", "sell", "strongSell"))
        if total > 0:
            value_by_id["buy_rating_share_percent"] = (current["strongBuy"] + current["buy"]) / total * 100
    return {key: round(float(value), 4) for key, value in value_by_id.items()}


def company_indicators_build_insider_indicator_value_by_id(
    insider_transactions: Optional[pandas.DataFrame], shares_outstanding: Optional[float], today: datetime.date,
) -> Dict[str, float]:
    """Open-market sales and purchases are told apart by the text yfinance gives ('Sale at price ...', 'Purchase at price ...');
    gifts, awards and option exercises are not trades the insider chose to make with money."""
    if insider_transactions is None or not len(insider_transactions) or not shares_outstanding:
        return {}
    table = insider_transactions.copy()
    table["day"] = pandas.to_datetime(table["Start Date"]).dt.date
    text = table["Text"].fillna("").str.lower()
    sold = table[text.str.startswith("sale") & (table["day"] > today - datetime.timedelta(days=INSIDER_SELLING_WINDOW_DAYS))]["Shares"].sum()
    bought_in_selling_window = table[text.str.startswith("purchase") & (table["day"] > today - datetime.timedelta(days=INSIDER_SELLING_WINDOW_DAYS))]["Shares"].sum()
    purchase_count = int((text.str.startswith("purchase") & (table["day"] > today - datetime.timedelta(days=INSIDER_BUYING_WINDOW_DAYS))).sum())
    return {
        "insider_net_open_market_selling_percent_of_shares_180_days": round(float(sold - bought_in_selling_window) / shares_outstanding * 100, 4),
        "insider_open_market_purchase_count_90_days": purchase_count,
    }


def company_indicators_find_sector_etf_symbol(info: dict) -> Optional[str]:
    return SECTOR_ETF_BY_SECTOR_NAME.get(info.get("sector"))
