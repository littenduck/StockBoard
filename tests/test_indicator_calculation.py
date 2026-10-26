import datetime

import pandas

from stock_benchmark_backend.indicator_calculation import (
    indicator_calculation_build_symbol_indicator_value_by_name,
    indicator_calculation_calculate_change_over_trading_days,
    indicator_calculation_calculate_distance_from_fifty_two_week_high_percent,
    indicator_calculation_calculate_fifty_two_week_range_percentile,
    indicator_calculation_calculate_is_price_above_two_hundred_day_average,
    indicator_calculation_calculate_latest_change_basis_points,
    indicator_calculation_calculate_realized_volatility_annualized_percent,
    indicator_calculation_calculate_relative_strength_index,
    indicator_calculation_calculate_return_over_trading_days_percent,
    indicator_calculation_calculate_simple_moving_average,
    indicator_calculation_calculate_volume_ratio_to_average,
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


def test_distance_from_fifty_two_week_high_and_return():
    close_series = pandas.Series([100.0, 120.0, 90.0])
    assert indicator_calculation_calculate_distance_from_fifty_two_week_high_percent(close_series) == 25.0
    assert indicator_calculation_calculate_return_over_trading_days_percent(close_series, 2) == -10.0
    assert indicator_calculation_calculate_return_over_trading_days_percent(close_series, 3) is None


def test_volume_ratio_to_average():
    volume_series = pandas.Series([100.0] * 20 + [250.0])
    assert indicator_calculation_calculate_volume_ratio_to_average(volume_series, 20) == 2.5
    assert indicator_calculation_calculate_volume_ratio_to_average(pandas.Series([1.0, 2.0]), 20) is None


def test_symbol_indicator_values_include_trend_fields():
    rising_close = pandas.Series([float(n) for n in range(1, 261)])
    history = pandas.DataFrame({"Close": rising_close, "Volume": [1000.0] * 260})
    value_by_name = indicator_calculation_build_symbol_indicator_value_by_name(
        history, True, None, 45, datetime.date(2026, 10, 1))
    assert value_by_name["fifty_day_average_above_two_hundred_day_average"].value is True
    assert value_by_name["price_above_fifty_day_average"].value is True
    assert value_by_name["price_below_five_day_average"].value is False
    assert value_by_name["distance_from_fifty_two_week_high_percent"].value == 0.0
    assert value_by_name["relative_strength_index_two_day"].value > 90
