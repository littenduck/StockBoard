"""Pure indicator math on price history. No network, no files."""
import datetime
import math
from typing import Dict, Optional

import numpy
import pandas

from stockboard_backend.strategy_evaluation import IndicatorValue

TRADING_DAYS_PER_YEAR = 252


def indicator_calculation_calculate_simple_moving_average(
    close_price_series: pandas.Series, window_length: int,
) -> pandas.Series:
    return close_price_series.rolling(window_length).mean()


def indicator_calculation_calculate_relative_strength_index(
    close_price_series: pandas.Series, window_length: int,
) -> pandas.Series:
    price_change = close_price_series.diff()
    average_gain = price_change.clip(lower=0).ewm(alpha=1 / window_length, adjust=False).mean()
    average_loss = (-price_change.clip(upper=0)).ewm(alpha=1 / window_length, adjust=False).mean()
    return 100 - 100 / (1 + average_gain / average_loss)


def indicator_calculation_calculate_realized_volatility_annualized_percent(
    close_price_series: pandas.Series, window_length: int,
) -> Optional[float]:
    daily_return_series = close_price_series.pct_change().dropna().iloc[-window_length:]
    if len(daily_return_series) < window_length:
        return None
    return float(daily_return_series.std() * numpy.sqrt(TRADING_DAYS_PER_YEAR) * 100)


def indicator_calculation_calculate_fifty_two_week_range_percentile(
    close_price_series: pandas.Series,
) -> Optional[float]:
    """0 means at the 52 week low, 100 means at the 52 week high."""
    recent_close_series = close_price_series.iloc[-TRADING_DAYS_PER_YEAR:]
    price_range = recent_close_series.max() - recent_close_series.min()
    if len(recent_close_series) < 2 or price_range == 0:
        return None
    return float((recent_close_series.iloc[-1] - recent_close_series.min()) / price_range * 100)


def indicator_calculation_calculate_is_price_above_two_hundred_day_average(
    close_price_series: pandas.Series,
) -> Optional[bool]:
    average_series = indicator_calculation_calculate_simple_moving_average(close_price_series, 200)
    if len(close_price_series) < 200:
        return None
    return bool(close_price_series.iloc[-1] > average_series.iloc[-1])


def indicator_calculation_calculate_change_over_trading_days(
    value_series: pandas.Series, trading_day_count: int,
) -> Optional[float]:
    """Difference between the latest value and the value trading_day_count rows earlier."""
    clean_series = value_series.dropna()
    if len(clean_series) <= trading_day_count:
        return None
    return float(clean_series.iloc[-1] - clean_series.iloc[-1 - trading_day_count])


def indicator_calculation_calculate_latest_value_or_none(value_series: pandas.Series, minimum_length: int) -> Optional[float]:
    """Last value of a rolling series, or None when the history is too short for it to be meaningful."""
    if len(value_series.dropna()) == 0 or len(value_series) < minimum_length:
        return None
    return round(float(value_series.iloc[-1]), 2)


def indicator_calculation_calculate_distance_from_fifty_two_week_high_percent(
    close_price_series: pandas.Series,
) -> Optional[float]:
    """How far the last close is below the 52 week high, in percent (0 means at the high)."""
    recent_close_series = close_price_series.iloc[-TRADING_DAYS_PER_YEAR:]
    if len(recent_close_series) < 2:
        return None
    return round(float((1 - recent_close_series.iloc[-1] / recent_close_series.max()) * 100), 2)


def indicator_calculation_calculate_volume_ratio_to_average(volume_series: pandas.Series, window_length: int) -> Optional[float]:
    """Last day's volume divided by the average of the window_length days before it."""
    previous_volume_series = volume_series.iloc[-window_length - 1:-1]
    if len(previous_volume_series) < window_length or previous_volume_series.mean() == 0:
        return None
    return round(float(volume_series.iloc[-1] / previous_volume_series.mean()), 2)


def indicator_calculation_calculate_return_over_trading_days_percent(
    close_price_series: pandas.Series, trading_day_count: int,
) -> Optional[float]:
    if len(close_price_series) <= trading_day_count:
        return None
    return round(float(close_price_series.iloc[-1] / close_price_series.iloc[-1 - trading_day_count] - 1) * 100, 2)


def indicator_calculation_calculate_distance_above_recent_low_close_percent(
    close_price_series: pandas.Series, window_length: int,
) -> Optional[float]:
    recent_close_series = close_price_series.iloc[-window_length:]
    if len(recent_close_series) < window_length or recent_close_series.min() <= 0:
        return None
    return round(float((recent_close_series.iloc[-1] / recent_close_series.min() - 1) * 100), 2)


def indicator_calculation_calculate_average_true_range_percent(price_history: pandas.DataFrame, window_length: int) -> Optional[float]:
    if len(price_history) <= window_length or not {"High", "Low", "Close"} <= set(price_history.columns):
        return None
    previous_close = price_history["Close"].shift(1)
    true_range = pandas.concat([price_history["High"] - price_history["Low"],
                                (price_history["High"] - previous_close).abs(),
                                (price_history["Low"] - previous_close).abs()], axis=1).max(axis=1)
    return round(float(true_range.iloc[-window_length:].mean() / price_history["Close"].iloc[-1] * 100), 2)


def indicator_calculation_calculate_has_no_new_low_in_recent_days(
    close_price_series: pandas.Series, recent_day_count: int, look_back_day_count: int = TRADING_DAYS_PER_YEAR,
) -> Optional[bool]:
    """True when none of the last recent_day_count closes was lower than every close in the look_back_day_count days before it."""
    if len(close_price_series) < look_back_day_count // 2 + recent_day_count:
        return None
    earlier_low_series = close_price_series.shift(1).rolling(look_back_day_count, min_periods=look_back_day_count // 2).min()
    return bool(not (close_price_series.iloc[-recent_day_count:] < earlier_low_series.iloc[-recent_day_count:]).any())


def indicator_calculation_calculate_absolute_distance_from_average_percent(close_price_series: pandas.Series, window_length: int) -> Optional[float]:
    if len(close_price_series) < window_length:
        return None
    average = close_price_series.iloc[-window_length:].mean()
    return round(float(abs(close_price_series.iloc[-1] / average - 1) * 100), 2)


def indicator_calculation_calculate_average_trading_value(price_history: pandas.DataFrame, window_length: int) -> Optional[float]:
    if "Volume" not in price_history or len(price_history) < window_length:
        return None
    return round(float((price_history["Close"] * price_history["Volume"]).iloc[-window_length:].mean()), 0)


KNOWN_INDICATOR_ID_SET = {
    "short_interest_percent_of_shares_outstanding",
    "vix_level", "vxn_level", "vvix_level", "vix_term_structure_is_contango",
    "treasury_ten_year_yield", "treasury_ten_year_yield_twenty_day_change_basis_points",
    "high_yield_credit_spread_basis_points", "spx_above_two_hundred_day_average", "fear_greed_index",
    "last_price", "fifty_two_week_range_percentile", "price_above_two_hundred_day_average",
    "realized_volatility_thirty_day", "no_earnings_before_expiration",
    "selected_put_absolute_delta", "selected_put_days_to_expiration",
    "selected_put_annualized_return_percent", "selected_put_implied_volatility_exceeds_realized",
    "relative_strength_index_two_day", "relative_strength_index_fourteen_day", "price_above_fifty_day_average",
    "fifty_day_average_above_two_hundred_day_average", "price_below_five_day_average",
    "distance_from_fifty_two_week_high_percent", "volume_ratio_to_twenty_day_average", "return_six_month_percent",
    "aaii_bullish_minus_bearish_percent", "aaii_bullish_percent", "absolute_distance_from_two_hundred_day_average_percent",
    "average_daily_trading_value_twenty_day_usd", "average_true_range_fourteen_day_percent", "buy_rating_share_percent",
    "chicago_fed_national_activity_index_three_month_average", "consumer_price_index_year_over_year_percent",
    "core_pce_price_index_year_over_year_percent", "distance_above_sixty_day_low_close_percent",
    "dividend_to_free_cash_flow_ratio", "enterprise_value_to_ebitda", "eps_estimate_next_year_four_week_change_percent",
    "eps_three_year_cagr_percent", "federal_funds_target_rate_not_raised_in_182_days",
    "federal_reserve_total_assets_thirteen_week_change_percent", "forward_pe_to_trailing_pe_ratio",
    "free_cash_flow_year_over_year_change", "free_cash_flow_yield_percent", "gross_margin_percent",
    "high_yield_credit_spread_twenty_day_change_basis_points", "initial_jobless_claims_four_week_average",
    "insider_net_open_market_selling_percent_of_shares_180_days", "insider_open_market_purchase_count_90_days",
    "interest_coverage_ratio", "is_spmo_rebalance_window", "m2_money_supply_year_over_year_percent",
    "market_capitalization_billion_usd", "market_value_to_gdp_percent", "moodys_baa_minus_ten_year_treasury_spread",
    "net_debt_to_ebitda", "no_cpi_or_pce_release_inside_option_life", "no_election_day_inside_option_life",
    "no_ex_dividend_date_inside_option_life", "no_fomc_meeting_inside_option_life", "no_jobs_report_within_one_day",
    "no_new_fifty_two_week_low_in_last_20_days", "no_quadruple_witching_in_next_five_trading_days",
    "one_sigma_expected_move_thirty_day_percent", "operating_cash_flow_to_net_income_ratio", "peg_ratio",
    "put_call_ratio_total_five_day_average", "put_skew_ten_percent_otm_minus_atm_iv_points", "return_on_equity_percent",
    "return_on_invested_capital_percent", "return_one_hundred_twenty_six_day_minus_spy_percent",
    "revenue_three_year_cagr_percent", "revenue_year_over_year_percent", "rsp_to_spy_ratio_above_two_hundred_day_average",
    "sahm_rule_recession_indicator", "sector_etf_return_minus_spy_return_one_hundred_twenty_six_day",
    "selected_expiration_is_third_friday", "selected_option_days_to_expiration", "selected_put_bid_ask_spread_percent_of_mid",
    "selected_put_breakeven_discount_percent", "selected_put_monthly_premium_percent", "selected_put_open_interest",
    "selected_put_probability_of_profit", "selected_put_strike_below_support", "selected_put_strike_discount_percent",
    "selected_put_strike_outside_one_sigma_move", "selected_put_volume", "selected_strike_is_multiple_of_five",
    "shares_outstanding_year_over_year_percent", "six_month_treasury_bill_yield_minus_federal_funds_rate",
    "trade_policy_uncertainty_ten_year_percentile", "trailing_twelve_month_eps", "trailing_twelve_month_free_cash_flow",
    "treasury_ten_year_minus_three_month_spread", "treasury_ten_year_minus_two_year_spread",
    "us_dollar_index_twenty_day_change_percent", "us_epu_thirty_day_average_percentile_five_year",
    "vix_to_twenty_day_average_ratio", "vxn_to_vix_ratio", "wti_crude_oil_one_month_change_percent", "wti_crude_oil_price",
}


def indicator_calculation_calculate_latest_change_percent(value_series: pandas.Series) -> Optional[float]:
    clean_series = value_series.dropna()
    if len(clean_series) < 2 or clean_series.iloc[-2] == 0:
        return None
    return round(float(clean_series.iloc[-1] / clean_series.iloc[-2] - 1) * 100, 2)


def indicator_calculation_calculate_latest_change_basis_points(value_series: pandas.Series) -> Optional[float]:
    """For series quoted in percent points (FRED DGS10, BAMLH0A0HYM2): one percent point is 100 bp."""
    clean_series = value_series.dropna()
    if len(clean_series) < 2:
        return None
    return round(float(clean_series.iloc[-1] - clean_series.iloc[-2]) * 100, 1)


def indicator_calculation_build_market_indicator_value_by_id(
    price_history_by_symbol: Dict[str, pandas.DataFrame],
    ten_year_yield_series: Optional[pandas.Series],
    credit_spread_series: Optional[pandas.Series],
) -> Dict[str, IndicatorValue]:
    """Indicators shared by every symbol. A source that failed is simply left out (the rules read unknown)."""
    value_by_id: Dict[str, IndicatorValue] = {}

    def add_value(indicator_id: str, value, source: str, change_value: Optional[float] = None,
                  change_unit: Optional[str] = None) -> None:
        value_by_id[indicator_id] = IndicatorValue(indicator_id, value, source, change_value, change_unit)

    close_series_by_symbol = {symbol: history["Close"] for symbol, history in price_history_by_symbol.items()}
    for symbol, indicator_id in (("^VIX", "vix_level"), ("^VXN", "vxn_level"), ("^VVIX", "vvix_level")):
        if symbol in close_series_by_symbol:
            series = close_series_by_symbol[symbol]
            add_value(indicator_id, round(float(series.iloc[-1]), 2), "yfinance " + symbol,
                      indicator_calculation_calculate_latest_change_percent(series), "percent")
    if "^VIX" in close_series_by_symbol and "^VIX3M" in close_series_by_symbol:
        add_value("vix_term_structure_is_contango",
                  bool(close_series_by_symbol["^VIX"].iloc[-1] < close_series_by_symbol["^VIX3M"].iloc[-1]),
                  "yfinance ^VIX ^VIX3M")
    if "^GSPC" in close_series_by_symbol:
        above_average = indicator_calculation_calculate_is_price_above_two_hundred_day_average(
            close_series_by_symbol["^GSPC"])
        if above_average is not None:
            add_value("spx_above_two_hundred_day_average", above_average, "yfinance ^GSPC")
    if "^VXN" in close_series_by_symbol and "^VIX" in close_series_by_symbol:
        add_value("vxn_to_vix_ratio", round(float(close_series_by_symbol["^VXN"].iloc[-1] / close_series_by_symbol["^VIX"].iloc[-1]), 3), "yfinance ^VXN ^VIX")
    if "^VIX" in close_series_by_symbol and len(close_series_by_symbol["^VIX"]) >= 20:
        vix_series = close_series_by_symbol["^VIX"]
        add_value("vix_to_twenty_day_average_ratio", round(float(vix_series.iloc[-1] / vix_series.iloc[-20:].mean()), 3), "yfinance ^VIX")
    if "CL=F" in close_series_by_symbol:
        oil_series = close_series_by_symbol["CL=F"]
        add_value("wti_crude_oil_price", round(float(oil_series.iloc[-1]), 2), "yfinance CL=F")
        oil_change = indicator_calculation_calculate_return_over_trading_days_percent(oil_series, 21)
        if oil_change is not None:
            add_value("wti_crude_oil_one_month_change_percent", oil_change, "yfinance CL=F")
    if "DX-Y.NYB" in close_series_by_symbol:
        dollar_change = indicator_calculation_calculate_return_over_trading_days_percent(close_series_by_symbol["DX-Y.NYB"], 20)
        if dollar_change is not None:
            add_value("us_dollar_index_twenty_day_change_percent", dollar_change, "yfinance DX-Y.NYB")
    if "RSP" in close_series_by_symbol and "SPY" in close_series_by_symbol:
        ratio_series = (close_series_by_symbol["RSP"] / close_series_by_symbol["SPY"]).dropna()
        above_average = indicator_calculation_calculate_is_price_above_two_hundred_day_average(ratio_series)
        if above_average is not None:
            add_value("rsp_to_spy_ratio_above_two_hundred_day_average", above_average, "yfinance RSP SPY")
    if ten_year_yield_series is not None and len(ten_year_yield_series):
        add_value("treasury_ten_year_yield", round(float(ten_year_yield_series.iloc[-1]), 2), "FRED DGS10",
                  indicator_calculation_calculate_latest_change_basis_points(ten_year_yield_series), "basis_points")
        change = indicator_calculation_calculate_change_over_trading_days(ten_year_yield_series, 20)
        if change is not None:
            add_value("treasury_ten_year_yield_twenty_day_change_basis_points", round(change * 100, 1), "FRED DGS10")
    if credit_spread_series is not None and len(credit_spread_series):
        add_value("high_yield_credit_spread_basis_points", round(float(credit_spread_series.iloc[-1]) * 100),
                  "FRED BAMLH0A0HYM2",
                  indicator_calculation_calculate_latest_change_basis_points(credit_spread_series), "basis_points")
    return value_by_id


def indicator_calculation_build_symbol_indicator_value_by_id(
    price_history: pandas.DataFrame,
    is_earnings_date_known: bool,
    next_earnings_date: Optional[datetime.date],
    earnings_check_days: int,
    today: datetime.date,
    spy_close_series: Optional[pandas.Series] = None,
    sector_etf_close_series: Optional[pandas.Series] = None,
) -> Dict[str, IndicatorValue]:
    close_series = price_history["Close"]
    value_by_id: Dict[str, IndicatorValue] = {}

    def add_value(indicator_id: str, value, change_value: Optional[float] = None,
                  change_unit: Optional[str] = None) -> None:
        if value is not None:
            value_by_id[indicator_id] = IndicatorValue(indicator_id, value, "yfinance", change_value, change_unit)

    add_value("last_price", round(float(close_series.iloc[-1]), 2),
              indicator_calculation_calculate_latest_change_percent(close_series), "percent")
    add_value("fifty_two_week_range_percentile",
              indicator_calculation_calculate_fifty_two_week_range_percentile(close_series))
    add_value("price_above_two_hundred_day_average",
              indicator_calculation_calculate_is_price_above_two_hundred_day_average(close_series))
    add_value("realized_volatility_thirty_day",
              indicator_calculation_calculate_realized_volatility_annualized_percent(close_series, 30))
    fifty_day_average = indicator_calculation_calculate_latest_value_or_none(
        indicator_calculation_calculate_simple_moving_average(close_series, 50), 50)
    two_hundred_day_average = indicator_calculation_calculate_latest_value_or_none(
        indicator_calculation_calculate_simple_moving_average(close_series, 200), 200)
    five_day_average = indicator_calculation_calculate_latest_value_or_none(
        indicator_calculation_calculate_simple_moving_average(close_series, 5), 5)
    last_close = float(close_series.iloc[-1])
    add_value("relative_strength_index_two_day", indicator_calculation_calculate_latest_value_or_none(
        indicator_calculation_calculate_relative_strength_index(close_series, 2), 3))
    add_value("relative_strength_index_fourteen_day", indicator_calculation_calculate_latest_value_or_none(
        indicator_calculation_calculate_relative_strength_index(close_series, 14), 15))
    add_value("price_above_fifty_day_average", None if fifty_day_average is None else last_close > fifty_day_average)
    add_value("fifty_day_average_above_two_hundred_day_average",
              None if fifty_day_average is None or two_hundred_day_average is None
              else fifty_day_average > two_hundred_day_average)
    add_value("price_below_five_day_average", None if five_day_average is None else last_close < five_day_average)
    add_value("distance_from_fifty_two_week_high_percent",
              indicator_calculation_calculate_distance_from_fifty_two_week_high_percent(close_series))
    if "Volume" in price_history:
        add_value("volume_ratio_to_twenty_day_average",
                  indicator_calculation_calculate_volume_ratio_to_average(price_history["Volume"], 20))
    add_value("return_six_month_percent", indicator_calculation_calculate_return_over_trading_days_percent(close_series, 126))
    add_value("distance_above_sixty_day_low_close_percent",
              indicator_calculation_calculate_distance_above_recent_low_close_percent(close_series, 60))
    add_value("average_true_range_fourteen_day_percent",
              indicator_calculation_calculate_average_true_range_percent(price_history, 14))
    add_value("no_new_fifty_two_week_low_in_last_20_days",
              indicator_calculation_calculate_has_no_new_low_in_recent_days(close_series, 20))
    add_value("absolute_distance_from_two_hundred_day_average_percent",
              indicator_calculation_calculate_absolute_distance_from_average_percent(close_series, 200))
    add_value("average_daily_trading_value_twenty_day_usd", indicator_calculation_calculate_average_trading_value(price_history, 20))
    stock_return = indicator_calculation_calculate_return_over_trading_days_percent(close_series, 126)
    if stock_return is not None and spy_close_series is not None:
        spy_return = indicator_calculation_calculate_return_over_trading_days_percent(spy_close_series, 126)
        add_value("return_one_hundred_twenty_six_day_minus_spy_percent", None if spy_return is None else round(stock_return - spy_return, 2))
    if sector_etf_close_series is not None and spy_close_series is not None:
        etf_return = indicator_calculation_calculate_return_over_trading_days_percent(sector_etf_close_series, 126)
        spy_return = indicator_calculation_calculate_return_over_trading_days_percent(spy_close_series, 126)
        if etf_return is not None and spy_return is not None:
            add_value("sector_etf_return_minus_spy_return_one_hundred_twenty_six_day", round(etf_return - spy_return, 2))
    if is_earnings_date_known:
        add_value("no_earnings_before_expiration",
                  next_earnings_date is None or (next_earnings_date - today).days > earnings_check_days)
    return value_by_id


def indicator_calculation_build_option_indicator_value_by_id(
    selected_put_contract, realized_volatility_percent: Optional[float],
    underlying_price: Optional[float] = None, support_price: Optional[float] = None, put_skew_points: Optional[float] = None,
) -> Dict[str, IndicatorValue]:
    """Indicators for one expiration window. Empty when no put contract could be picked."""
    if selected_put_contract is None:
        return {}
    contract = selected_put_contract
    value_by_id = {
        "selected_put_absolute_delta": contract.absolute_delta,
        "selected_put_days_to_expiration": contract.days_to_expiration,
        "selected_option_days_to_expiration": contract.days_to_expiration,
        "selected_put_annualized_return_percent": contract.annualized_return_percent,
        "selected_expiration_is_third_friday": contract.expiration_date.weekday() == 4 and 15 <= contract.expiration_date.day <= 21,
        "selected_strike_is_multiple_of_five": contract.strike_price % 5 == 0,
        "selected_put_probability_of_profit": round(1 - contract.absolute_delta, 3),
        "one_sigma_expected_move_thirty_day_percent": round(
            contract.implied_volatility * math.sqrt(contract.days_to_expiration / 365) * 100, 2),
        "selected_put_monthly_premium_percent": round(contract.premium / contract.strike_price * 30 / contract.days_to_expiration * 100, 2),
    }
    if contract.bid + contract.ask > 0:
        value_by_id["selected_put_bid_ask_spread_percent_of_mid"] = round((contract.ask - contract.bid) / ((contract.ask + contract.bid) / 2) * 100, 2)
    if contract.open_interest is not None:
        value_by_id["selected_put_open_interest"] = contract.open_interest
    if contract.volume is not None:
        value_by_id["selected_put_volume"] = contract.volume
    if realized_volatility_percent is not None:
        value_by_id["selected_put_implied_volatility_exceeds_realized"] = contract.implied_volatility * 100 > realized_volatility_percent
    if underlying_price:
        value_by_id["selected_put_strike_discount_percent"] = round((underlying_price - contract.strike_price) / underlying_price * 100, 2)
        value_by_id["selected_put_breakeven_discount_percent"] = round(
            (underlying_price - (contract.strike_price - contract.premium)) / underlying_price * 100, 2)
        one_sigma_move = underlying_price * contract.implied_volatility * math.sqrt(contract.days_to_expiration / 365)
        value_by_id["selected_put_strike_outside_one_sigma_move"] = contract.strike_price < underlying_price - one_sigma_move
    if support_price:
        value_by_id["selected_put_strike_below_support"] = contract.strike_price < support_price
    if put_skew_points is not None:
        value_by_id["put_skew_ten_percent_otm_minus_atm_iv_points"] = put_skew_points
    return {key: IndicatorValue(key, value, "yfinance option chain") for key, value in value_by_id.items()}
