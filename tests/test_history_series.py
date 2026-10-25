import os

import pandas
import pytest

from stockboard_backend import history_series
from stockboard_backend.rule_catalog import rule_catalog_load_rule_catalog_from_yaml_file
from stockboard_backend.settings_loader import PROJECT_DIRECTORY


def daily(values, start="2020-01-01"):
    return pandas.Series(values, index=pandas.date_range(start, periods=len(values), freq="D"), dtype=float)


def test_difference_and_ratio_use_only_the_dates_both_series_have():
    first, second = daily([5, 6, 7]), daily([1, 2], "2020-01-02")
    assert history_series.history_series_calculate_difference(first, second).tolist() == [5.0, 5.0]
    assert history_series.history_series_calculate_ratio(first, second).tolist() == [6.0, 3.5]


def test_change_and_percent_change_look_back_a_number_of_observations():
    series = daily([100, 110, 121])
    assert history_series.history_series_calculate_change(series, 1, 100).tolist() == pytest.approx([1000.0, 1100.0])
    assert history_series.history_series_calculate_percent_change(series, 2).tolist() == pytest.approx([21.0])


def test_rolling_mean_waits_for_a_full_window():
    assert history_series.history_series_calculate_rolling_mean(daily([1, 2, 3, 4]), 3).tolist() == [2.0, 3.0]


def test_percentile_rank_counts_the_earlier_values_below_the_current_one():
    ranks = history_series.history_series_calculate_rolling_percentile_rank(daily([5, 1, 2, 3, 4, 9, 0]), 5)
    # windows: [5,1,2,3,4] -> 4 is above 3 of 4 earlier values = 75; [1,2,3,4,9] -> 100; [2,3,4,9,0] -> 0
    assert ranks.tolist() == [75.0, 100.0, 0.0]


def test_not_raised_compares_with_the_rate_a_number_of_calendar_days_earlier():
    rate = pandas.Series([1.0, 1.0, 2.0], index=pandas.to_datetime(["2020-01-01", "2020-01-03", "2020-01-05"]))
    result = history_series.history_series_calculate_not_raised(rate, 2)
    assert result.index[0] == pandas.Timestamp("2020-01-03")
    assert result.tolist() == [True, True, False]  # Jan 3 (1 vs 1), Jan 4 (1 vs 1), Jan 5 (2 vs 1)


def test_market_value_to_gdp_converts_millions_to_billions():
    equities = pandas.Series([83_050_847.0], index=pandas.to_datetime(["2026-04-01"]))
    gdp = pandas.Series([32_563.03], index=pandas.to_datetime(["2026-04-01"]))
    assert history_series.history_series_calculate_market_value_to_gdp_percent(equities, gdp).iloc[0] == pytest.approx(255.05, abs=0.01)


def test_every_builder_returns_a_series_when_the_sources_are_available(monkeypatch):
    base = pandas.Series(range(1, 4001), index=pandas.date_range("2005-01-01", periods=4000, freq="D"), dtype=float)
    monkeypatch.setattr(history_series, "fred", lambda series_id: base.copy())
    monkeypatch.setattr(history_series, "cboe", lambda index_name: base.copy())
    monkeypatch.setattr(history_series, "history_series_build_total_put_call_ratio", lambda: base.copy())
    for indicator_id, builder in history_series.HISTORY_SERIES_BUILDER_BY_INDICATOR_ID.items():
        series = builder()
        assert isinstance(series, pandas.Series) and not series.empty, indicator_id


def test_every_builder_serves_an_indicator_of_a_backtestable_rule():
    catalog = rule_catalog_load_rule_catalog_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml"))
    backtestable_indicator_set = {entry.indicator for entry in catalog.rule_entry_by_id.values() if entry.backtestable == "yes"}
    assert set(history_series.HISTORY_SERIES_BUILDER_BY_INDICATOR_ID) <= backtestable_indicator_set
