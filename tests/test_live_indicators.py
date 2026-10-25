import datetime

import pandas
import pytest

from stockboard_backend import indicator_calculation as I
from stockboard_backend import live_indicators, history_series, option_chain


def test_a_series_is_used_only_while_its_newest_value_is_recent():
    series = pandas.Series([1.0, 2.5], index=pandas.to_datetime(["2026-10-01", "2026-10-20"]))
    today = datetime.date(2026, 10, 25)
    assert live_indicators.live_indicators_extract_latest_value(series, 10, today) == 2.5
    assert live_indicators.live_indicators_extract_latest_value(series, 3, today) is None
    assert live_indicators.live_indicators_extract_latest_value(pandas.Series(dtype=float), 10, today) is None
    flags = pandas.Series([True, False], index=series.index)
    assert live_indicators.live_indicators_extract_latest_value(flags, 10, today) is False


def test_every_live_series_indicator_has_a_builder_and_is_known():
    for indicator_id in live_indicators.MAX_AGE_DAYS_BY_SERIES_INDICATOR_ID:
        assert indicator_id in history_series.HISTORY_SERIES_BUILDER_BY_INDICATOR_ID
        assert indicator_id in I.KNOWN_INDICATOR_ID_SET
    for indicator_id in live_indicators.EDGAR_INDICATOR_ID_LIST:
        assert indicator_id in I.KNOWN_INDICATOR_ID_SET


def test_short_interest_percent_uses_the_latest_filing_and_ignores_an_old_one():
    table = pandas.DataFrame({"short_shares": [5_000_000.0]}, index=pandas.to_datetime(["2026-10-15"]))
    fresh = live_indicators.live_indicators_build_short_interest_indicator_value_by_id(table, 1_000_000_000, datetime.date(2026, 10, 25))
    assert fresh["short_interest_percent_of_shares_outstanding"] == pytest.approx(0.5)
    assert live_indicators.live_indicators_build_short_interest_indicator_value_by_id(table, 1e9, datetime.date(2027, 1, 25)) == {}


def price_history(count=300, step=0.1):
    close = pandas.Series([100 + step * day for day in range(count)])
    return pandas.DataFrame({"Close": close, "High": close + 1, "Low": close - 1, "Volume": 1_000_000.0})


def test_price_derived_indicators():
    history = price_history()
    close = history["Close"]
    assert I.indicator_calculation_calculate_distance_above_recent_low_close_percent(close, 60) == pytest.approx(
        (close.iloc[-1] / close.iloc[-60] - 1) * 100, abs=0.01)
    assert I.indicator_calculation_calculate_average_true_range_percent(history, 14) == pytest.approx(2.0 / close.iloc[-1] * 100, abs=0.01)  # high minus low is 2 on every day
    assert I.indicator_calculation_calculate_has_no_new_low_in_recent_days(close, 20) is True
    assert I.indicator_calculation_calculate_has_no_new_low_in_recent_days(close.iloc[::-1].reset_index(drop=True), 20) is False
    assert I.indicator_calculation_calculate_has_no_new_low_in_recent_days(close.iloc[:50], 20) is None
    assert I.indicator_calculation_calculate_average_trading_value(history, 20) == pytest.approx(close.iloc[-20:].mean() * 1_000_000, rel=1e-6)
    assert I.indicator_calculation_calculate_absolute_distance_from_average_percent(close, 200) > 0


def test_relative_returns_need_the_spy_series():
    history = price_history()
    spy = pandas.Series([100 + 0.05 * day for day in range(300)])
    value = I.indicator_calculation_build_symbol_indicator_value_by_id(
        history, True, None, 45, datetime.date(2026, 10, 25), spy, spy)
    assert value["return_one_hundred_twenty_six_day_minus_spy_percent"].value > 0
    assert value["sector_etf_return_minus_spy_return_one_hundred_twenty_six_day"].value == 0
    assert "return_one_hundred_twenty_six_day_minus_spy_percent" not in I.indicator_calculation_build_symbol_indicator_value_by_id(
        history, True, None, 45, datetime.date(2026, 10, 25))


def test_market_indicators_from_yfinance_histories():
    def frame(start, step, count=260):
        return pandas.DataFrame({"Close": pandas.Series([start + step * day for day in range(count)])})
    histories = {"^VIX": frame(20, 0), "^VXN": frame(30, 0), "CL=F": frame(80, 0.1), "DX-Y.NYB": frame(100, 0.01),
                 "RSP": frame(50, 0.05), "SPY": frame(100, 0.05)}
    value = I.indicator_calculation_build_market_indicator_value_by_id(histories, None, None)
    assert value["vxn_to_vix_ratio"].value == 1.5 and value["vix_to_twenty_day_average_ratio"].value == 1.0
    assert value["wti_crude_oil_price"].value == pytest.approx(80 + 0.1 * 259, abs=0.01)
    assert value["wti_crude_oil_one_month_change_percent"].value > 0
    assert value["us_dollar_index_twenty_day_change_percent"].value > 0
    assert value["rsp_to_spy_ratio_above_two_hundred_day_average"].value in (True, False)


def test_option_indicators_from_one_selected_put():
    contract = option_chain.SelectedPutContract(
        expiration_date=datetime.date(2026, 11, 20), strike_price=90.0, absolute_delta=0.25, implied_volatility=0.30, premium=2.0,
        days_to_expiration=26, annualized_return_percent=31.2, bid=1.9, ask=2.1, open_interest=800.0, volume=120.0)
    value = {key: indicator.value for key, indicator in I.indicator_calculation_build_option_indicator_value_by_id(
        contract, 25.0, 100.0, 85.0, 3.5).items()}
    assert value["selected_put_bid_ask_spread_percent_of_mid"] == pytest.approx(10.0)
    assert value["selected_expiration_is_third_friday"] is True and value["selected_strike_is_multiple_of_five"] is True
    assert value["selected_put_strike_discount_percent"] == pytest.approx(10.0)
    assert value["selected_put_breakeven_discount_percent"] == pytest.approx(12.0)
    assert value["selected_put_probability_of_profit"] == pytest.approx(0.75)
    assert value["selected_put_strike_below_support"] is False and value["selected_put_open_interest"] == 800.0
    assert value["selected_put_strike_outside_one_sigma_move"] is True  # the one-sigma move is 100 * 0.30 * sqrt(26/365) = 8.0, so 92 is the edge and 90 is outside
    assert value["put_skew_ten_percent_otm_minus_atm_iv_points"] == 3.5
    assert value["selected_put_implied_volatility_exceeds_realized"] is True
    assert I.indicator_calculation_build_option_indicator_value_by_id(None, 25.0) == {}


def test_put_skew_compares_the_ten_percent_otm_put_with_the_money_put():
    table = pandas.DataFrame({"strike": [85.0, 90.0, 95.0, 100.0], "bid": [0.5, 1.0, 2.0, 4.0], "impliedVolatility": [0.40, 0.34, 0.30, 0.28]})
    assert option_chain.option_chain_calculate_put_skew_points(table, 100.0) == pytest.approx(6.0)
    assert option_chain.option_chain_calculate_put_skew_points(table.assign(bid=0.0), 100.0) is None
