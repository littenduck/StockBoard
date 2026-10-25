import datetime

import pandas
import pytest

from stockboard_backend import company_indicators as C

INFO = {"marketCap": 200e9, "enterpriseValue": 210e9, "ebitda": 14e9, "freeCashflow": 10e9, "forwardPE": 18.0, "trailingPE": 20.0,
        "trailingEps": 5.0, "revenueGrowth": 0.12, "grossMargins": 0.45, "returnOnEquity": 0.2, "totalDebt": 30e9, "totalCash": 10e9,
        "operatingCashflow": 12e9, "netIncomeToCommon": 8e9, "dividendRate": 2.0, "sharesOutstanding": 1e9}


def test_info_fields_become_rule_values():
    value = C.company_indicators_build_info_indicator_value_by_name(INFO)
    assert value["market_capitalization_billion_usd"] == 200
    assert value["free_cash_flow_yield_percent"] == pytest.approx(5.0)
    assert value["enterprise_value_to_ebitda"] == pytest.approx(15.0)
    assert value["net_debt_to_ebitda"] == pytest.approx(20 / 14, abs=1e-3)
    assert value["forward_pe_to_trailing_pe_ratio"] == pytest.approx(0.9)
    assert value["operating_cash_flow_to_net_income_ratio"] == pytest.approx(1.5)
    assert value["dividend_to_free_cash_flow_ratio"] == pytest.approx(0.2)
    assert value["gross_margin_percent"] == pytest.approx(45.0) and value["revenue_year_over_year_percent"] == pytest.approx(12.0)


def test_missing_zero_or_negative_inputs_leave_the_value_out():
    value = C.company_indicators_build_info_indicator_value_by_name({**INFO, "ebitda": -1e9, "grossMargins": 0.0, "netIncomeToCommon": -1.0})
    for key in ("enterprise_value_to_ebitda", "net_debt_to_ebitda", "gross_margin_percent", "operating_cash_flow_to_net_income_ratio"):
        assert key not in value
    assert C.company_indicators_build_info_indicator_value_by_name({}) == {}


def test_a_company_without_a_dividend_has_a_zero_ratio_but_a_fund_has_none():
    assert C.company_indicators_build_info_indicator_value_by_name({"trailingEps": 3.0})["dividend_to_free_cash_flow_ratio"] == 0.0
    assert "dividend_to_free_cash_flow_ratio" not in C.company_indicators_build_info_indicator_value_by_name({"totalAssets": 5})


def test_estimates_change_peg_and_buy_share():
    eps_trend = pandas.DataFrame({"current": [10.0, 11.0], "30daysAgo": [10.0, 10.0]}, index=["0y", "+1y"])
    summary = pandas.DataFrame([{"strongBuy": 6, "buy": 4, "hold": 8, "sell": 1, "strongSell": 1}])
    value = C.company_indicators_build_estimate_indicator_value_by_name(eps_trend, summary, 20.0)
    assert value["eps_estimate_next_year_four_week_change_percent"] == pytest.approx(10.0)
    assert value["peg_ratio"] == pytest.approx(2.0)  # forward PE 20 over growth of 10%
    assert value["buy_rating_share_percent"] == pytest.approx(50.0)
    assert C.company_indicators_build_estimate_indicator_value_by_name(None, None, None) == {}


def test_insider_sales_and_purchases_are_told_apart_by_text_and_window():
    table = pandas.DataFrame({
        "Shares": [1000, 200, 5000, 300, 400],
        "Text": ["Sale at price 10 per share.", "Purchase at price 9 per share.", "Stock Gift at price 0.00 per share.",
                 "Sale at price 10 per share.", "Purchase at price 8 per share."],
        "Start Date": ["2026-10-01", "2026-10-10", "2026-10-12", "2026-01-01", "2026-04-01"]})
    value = C.company_indicators_build_insider_indicator_value_by_name(table, 100_000.0, datetime.date(2026, 10, 25))
    assert value["insider_net_open_market_selling_percent_of_shares_180_days"] == pytest.approx((1000 - 200) / 100_000 * 100, abs=1e-3)  # the January sale and the April purchase are outside 180 days
    assert value["insider_open_market_purchase_count_90_days"] == 1
    assert C.company_indicators_build_insider_indicator_value_by_name(None, 1.0, datetime.date(2026, 10, 25)) == {}


def test_sector_name_maps_to_its_etf():
    assert C.company_indicators_find_sector_etf_symbol({"sector": "Technology"}) == "XLK"
    assert C.company_indicators_find_sector_etf_symbol({}) is None
