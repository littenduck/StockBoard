import pandas

from stockboard_backend.indicator_calculation import (
    indicator_calculation_calculate_change_over_trading_days,
    indicator_calculation_calculate_fifty_two_week_range_percentile,
    indicator_calculation_calculate_is_price_above_two_hundred_day_average,
    indicator_calculation_calculate_latest_change_basis_points,
    indicator_calculation_calculate_realized_volatility_annualized_percent,
    indicator_calculation_calculate_relative_strength_index,
    indicator_calculation_calculate_simple_moving_average,
)


def test_simple_moving_average():
    average_series = indicator_calculation_calculate_simple_moving_average(pandas.Series([1, 2, 3, 4]), 2)
    assert list(average_series.dropna()) == [1.5, 2.5, 3.5]


def test_relative_strength_index_rising_series_is_high():
    rising_series = pandas.Series(range(1, 60), dtype=float)
    assert indicator_calculation_calculate_relative_strength_index(rising_series, 14).iloc[-1] > 99


def test_fifty_two_week_range_percentile():
    assert indicator_calculation_calculate_fifty_two_week_range_percentile(pandas.Series([10.0, 20.0, 15.0])) == 50.0
    assert indicator_calculation_calculate_fifty_two_week_range_percentile(pandas.Series([5.0, 5.0, 5.0])) is None


def test_price_above_two_hundred_day_average_needs_history():
    assert indicator_calculation_calculate_is_price_above_two_hundred_day_average(pandas.Series([1.0] * 50)) is None
    assert indicator_calculation_calculate_is_price_above_two_hundred_day_average(
        pandas.Series([float(n) for n in range(1, 251)])) is True


def test_realized_volatility_needs_enough_rows_and_flat_series_is_zero():
    assert indicator_calculation_calculate_realized_volatility_annualized_percent(pandas.Series([1.0] * 5), 30) is None
    assert indicator_calculation_calculate_realized_volatility_annualized_percent(pandas.Series([100.0] * 40), 30) == 0.0


def test_change_over_trading_days():
    value_series = pandas.Series([1.0, 2.0, 4.0])
    assert indicator_calculation_calculate_change_over_trading_days(value_series, 2) == 3.0
    assert indicator_calculation_calculate_change_over_trading_days(value_series, 3) is None


def test_latest_change_basis_points():
    assert indicator_calculation_calculate_latest_change_basis_points(pandas.Series([4.10, 4.13])) == 3.0
    assert indicator_calculation_calculate_latest_change_basis_points(pandas.Series([4.1])) is None
