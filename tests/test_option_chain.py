import datetime

import pandas

from stockboard_backend.option_chain import (
    option_chain_calculate_black_scholes_put_delta,
    option_chain_determine_expiration_within_day_window,
    option_chain_determine_representative_put_contract_from_table,
)


def test_black_scholes_put_delta_at_the_money():
    delta = option_chain_calculate_black_scholes_put_delta(100, 100, 365, 0.2, 0.0)
    assert abs(delta - (-0.4602)) < 0.001


def test_black_scholes_put_delta_far_out_of_the_money_is_near_zero():
    assert abs(option_chain_calculate_black_scholes_put_delta(100, 50, 30, 0.2, 4.0)) < 0.001


def test_expiration_window_prefers_monthly_expiration():
    today = datetime.date(2026, 10, 15)
    expiration_list = [datetime.date(2026, 11, 13), datetime.date(2026, 11, 20), datetime.date(2026, 11, 27)]
    assert option_chain_determine_expiration_within_day_window(expiration_list, 30, 45, today) == datetime.date(2026, 11, 20)
    assert option_chain_determine_expiration_within_day_window(expiration_list, 100, 120, today) is None


def test_representative_contract_needs_live_quotes_and_targets_delta():
    today = datetime.date(2026, 10, 1)
    expiration_date = datetime.date(2026, 11, 6)
    table = pandas.DataFrame({
        "strike": [80.0, 90.0, 95.0, 105.0], "bid": [0.1, 1.0, 2.0, 6.0], "ask": [0.2, 1.2, 2.2, 6.4],
        "lastPrice": [0.0] * 4, "impliedVolatility": [0.3, 0.3, 0.3, 0.3]})
    contract = option_chain_determine_representative_put_contract_from_table(
        table, 100.0, expiration_date, today, 0.25, 4.0)
    assert contract is not None and contract.strike_price in (90.0, 95.0)
    assert option_chain_determine_representative_put_contract_from_table(
        table.assign(bid=0.0, ask=0.0), 100.0, expiration_date, today, 0.25, 4.0) is None
