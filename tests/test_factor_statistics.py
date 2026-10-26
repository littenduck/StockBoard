import numpy
import pandas

from stock_benchmark_backend import factor_statistics

DATE_INDEX = pandas.bdate_range("2024-01-01", periods=5)
SYMBOL_LIST = ["S{:02d}".format(number) for number in range(12)]


def one_date_table(values, symbol_list):
    return pandas.DataFrame([values], index=DATE_INDEX[:1], columns=symbol_list, dtype=float)


def test_rank_ic_is_one_when_the_score_orders_the_returns_exactly():
    scores = one_date_table(numpy.arange(12.0), SYMBOL_LIST)
    ic = factor_statistics.factor_statistics_rank_ic_by_date(scores, scores * 0.01)
    assert numpy.isclose(ic.iloc[0], 1.0)


def test_decile_spread_is_top_minus_bottom_bucket_mean():
    scores = one_date_table(numpy.arange(10.0), SYMBOL_LIST[:10])
    spread = factor_statistics.factor_statistics_decile_spread_by_date(scores, scores * 0.01, bucket_count=10, minimum_symbol_count=10)
    assert numpy.isclose(spread.iloc[0], 0.09)


def test_dates_with_too_few_symbols_are_skipped():
    scores = one_date_table(numpy.arange(3.0), SYMBOL_LIST[:3])
    assert factor_statistics.factor_statistics_rank_ic_by_date(scores, scores).empty


def test_newey_west_with_zero_lags_matches_population_standard_deviation():
    values = pandas.Series([0.01, 0.03, -0.02, 0.04, 0.00])
    expected = values.mean() / (values.std(ddof=0) / numpy.sqrt(len(values)))
    assert numpy.isclose(factor_statistics.factor_statistics_newey_west_t(values, lags=0), expected)


def test_newey_west_is_none_for_constant_or_single_values():
    assert factor_statistics.factor_statistics_newey_west_t(pandas.Series([0.02, 0.02, 0.02]), lags=2) is None
    assert factor_statistics.factor_statistics_newey_west_t(pandas.Series([0.02]), lags=2) is None


def test_summary_reports_means_and_counts():
    ic = pandas.Series([0.1, 0.2, 0.3, 0.2, 0.2])
    spread = pandas.Series([0.01, 0.02, 0.0, 0.01, 0.02])
    summary = factor_statistics.factor_statistics_summarize(ic, spread, lags=1)
    assert summary["date_count"] == 5 and numpy.isclose(summary["rank_ic_mean"], 0.2)
    assert summary["rank_ic_t"] is not None and summary["decile_spread_t"] is not None
