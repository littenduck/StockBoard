"""Pure indicator math on price history. No network, no files."""
import datetime
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


KNOWN_INDICATOR_ID_SET = {
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
    if is_earnings_date_known:
        add_value("no_earnings_before_expiration",
                  next_earnings_date is None or (next_earnings_date - today).days > earnings_check_days)
    return value_by_id


def indicator_calculation_build_option_indicator_value_by_id(
    selected_put_contract, realized_volatility_percent: Optional[float],
) -> Dict[str, IndicatorValue]:
    """Indicators for one expiration window. Empty when no put contract could be picked."""
    if selected_put_contract is None:
        return {}
    value_by_id = {
        "selected_put_absolute_delta": selected_put_contract.absolute_delta,
        "selected_put_days_to_expiration": selected_put_contract.days_to_expiration,
        "selected_put_annualized_return_percent": selected_put_contract.annualized_return_percent,
    }
    if realized_volatility_percent is not None:
        value_by_id["selected_put_implied_volatility_exceeds_realized"] = (
            selected_put_contract.implied_volatility * 100 > realized_volatility_percent)
    return {key: IndicatorValue(key, value, "yfinance option chain") for key, value in value_by_id.items()}
