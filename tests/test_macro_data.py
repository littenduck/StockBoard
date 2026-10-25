import datetime

import pandas
import pytest

from stockboard_backend import macro_data


@pytest.fixture(autouse=True)
def empty_cache():
    macro_data.fred_series_cache.clear()
    yield
    macro_data.fred_series_cache.clear()


def test_fred_csv_drops_the_dots_that_mark_missing_days():
    series = macro_data.macro_data_parse_fred_csv_bytes(b"observation_date,DGS10\n2026-10-20,4.9\n2026-10-21,.\n2026-10-22,4.96\n")
    assert list(series.values) == [4.9, 4.96] and series.index[-1] == pandas.Timestamp("2026-10-22")


def test_cached_fetch_downloads_once_and_hands_out_copies(monkeypatch):
    calls = []

    def fetch(series_id):
        calls.append(series_id)
        return pandas.Series([1.0, 2.0], index=pandas.to_datetime(["2026-01-01", "2026-01-02"]))

    monkeypatch.setattr(macro_data, "macro_data_fetch_fred_series_by_series_id", fetch)
    first = macro_data.macro_data_fetch_fred_series_cached("DGS10")
    first.iloc[0] = 99.0
    second = macro_data.macro_data_fetch_fred_series_cached("DGS10")
    assert calls == ["DGS10"] and second.iloc[0] == 1.0


def test_point_in_time_year_over_year_uses_only_what_was_known_on_each_date():
    def fetch_as_of(series_id, as_of_date):
        # a vintage with 13 monthly values; the newest observation is higher in the later vintage
        newest = 110.0 if as_of_date.month == 1 else 121.0
        return pandas.Series([100.0] * 12 + [newest], index=pandas.date_range("2019-01-01", periods=13, freq="MS"))

    series = macro_data.macro_data_build_point_in_time_year_over_year_series(
        "CPIAUCSL", [datetime.date(2020, 1, 15), datetime.date(2020, 2, 15)], 12, fetch_as_of)
    assert series.loc["2020-01-15"] == pytest.approx(10.0) and series.loc["2020-02-15"] == pytest.approx(21.0)


def test_point_in_time_year_over_year_skips_a_vintage_that_is_too_short():
    def fetch_as_of(series_id, as_of_date):
        return pandas.Series([100.0, 101.0], index=pandas.date_range("2019-01-01", periods=2, freq="MS"))

    assert macro_data.macro_data_build_point_in_time_year_over_year_series(
        "CPIAUCSL", [datetime.date(2020, 1, 15)], 12, fetch_as_of).empty
