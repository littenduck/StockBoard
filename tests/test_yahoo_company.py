import datetime

import pandas
import pytest

from stockboard_backend import company_indicators, yahoo_company

RAW = {
    "price": {"marketCap": {"raw": 5e12, "fmt": "5T"}, "symbol": "AAPL", "longName": "Apple"},
    "summaryDetail": {"trailingPE": 39.9, "forwardPE": 36.0, "dividendRate": 1.04, "exDividendDate": 1786320000, "bid": {}, "volume": {"raw": 5}},
    "defaultKeyStatistics": {"trailingEps": 8.72, "sharesOutstanding": {"raw": 1.4e7}, "enterpriseValue": 5.1e12, "netIncomeToCommon": 1.1e11},
    "financialData": {"ebitda": 1.68e11, "freeCashflow": 1.08e11, "revenueGrowth": 0.164, "grossMargins": 0.4865, "returnOnEquity": 1.49,
                      "totalDebt": 9e10, "totalCash": 7e10, "operatingCashflow": 1.25e11, "targetMeanPrice": {}},
    "quoteType": {"quoteType": "EQUITY"}, "assetProfile": {"sector": "Technology", "companyOfficers": [{"name": "x"}]},
    "earningsTrend": {"trend": [
        {"period": "0y", "epsTrend": {"current": {"raw": 8.8}, "30daysAgo": {"raw": 8.7}, "maxAge": 1}},
        {"period": "+1y", "epsTrend": {"current": {"raw": 9.6}, "30daysAgo": {"raw": 9.5}}}]},
    "recommendationTrend": {"trend": [{"period": "0m", "strongBuy": 6, "buy": 18, "hold": 14, "sell": 3, "strongSell": 3, "maxAge": 1}]},
    "calendarEvents": {"earnings": {"earningsDate": [1793649600]}, "exDividendDate": 1786320000},
    "insiderTransactions": {"transactions": [
        {"shares": {"raw": 2399}, "transactionText": "Sale at price 339.62 per share.", "startDate": {"raw": 1792454400}},
        {"shares": {}, "transactionText": "Stock Gift", "startDate": {"raw": 1792454400}}]},
}


def test_the_modules_are_flattened_into_one_info_dictionary():
    info = yahoo_company.yahoo_company_build_info(RAW)
    assert info["marketCap"] == 5e12 and info["trailingEps"] == 8.72 and info["sharesOutstanding"] == 1.4e7 and info["sector"] == "Technology"
    assert "bid" not in info and "targetMeanPrice" not in info and "companyOfficers" not in info  # empty values and lists are dropped


def test_the_snapshot_feeds_the_same_indicator_code_as_yfinance_did():
    snapshot = yahoo_company.yahoo_company_parse_quote_summary(RAW)
    assert list(snapshot["eps_trend"].columns) == ["current", "30daysAgo"] and list(snapshot["eps_trend"].index) == ["0y", "+1y"]
    assert snapshot["recommendations_summary"].iloc[0]["strongBuy"] == 6
    assert snapshot["calendar"]["Earnings Date"] == [datetime.date(2026, 11, 2)]
    value = company_indicators.company_indicators_build_info_indicator_value_by_name(snapshot["info"])
    value.update(company_indicators.company_indicators_build_estimate_indicator_value_by_name(
        snapshot["eps_trend"], snapshot["recommendations_summary"], snapshot["info"]["forwardPE"]))
    value.update(company_indicators.company_indicators_build_insider_indicator_value_by_name(
        snapshot["insider_transactions"], snapshot["info"]["sharesOutstanding"], datetime.date(2026, 10, 25)))
    assert value["free_cash_flow_yield_percent"] == pytest.approx(2.16, abs=0.01) and value["buy_rating_share_percent"] == pytest.approx(54.5, abs=0.1)
    assert value["eps_estimate_next_year_four_week_change_percent"] == pytest.approx((9.6 / 9.5 - 1) * 100, abs=0.01)
    assert value["insider_net_open_market_selling_percent_of_shares_180_days"] > 0


def test_a_fund_has_only_the_modules_it_has():
    snapshot = yahoo_company.yahoo_company_parse_quote_summary({"quoteType": {"quoteType": "ETF"}, "summaryDetail": {"trailingPE": 24.1}})
    assert snapshot["info"]["quoteType"] == "ETF" and snapshot["eps_trend"] is None and snapshot["insider_transactions"] is None
    assert snapshot["calendar"] is None


def test_the_live_quote_overrides_the_hourly_market_cap_and_ratios():
    snapshot = {"info": {"marketCap": 1.0, "trailingPE": 20.0, "trailingEps": 5.0}, "fetched_at": 1}
    merged = yahoo_company.yahoo_company_overlay_quote(snapshot, {"marketCap": 2.0, "trailingPE": 21.0, "sharesOutstanding": 7.0})
    assert merged["info"]["marketCap"] == 2.0 and merged["info"]["trailingPE"] == 21.0 and merged["info"]["sharesOutstanding"] == 7.0
    assert snapshot["info"]["marketCap"] == 1.0 and merged["fetched_at"] == 1
    assert yahoo_company.yahoo_company_overlay_quote(snapshot, None) is snapshot
