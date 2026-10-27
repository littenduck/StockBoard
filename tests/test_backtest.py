import os

import numpy
import pandas

from stock_benchmark_backend import backtest, factor_statistics, rule_catalog, strategy_loader
from stock_benchmark_backend.web_server import PROJECT_DIRECTORY


def load_fundamentals_strategy():
    catalog = rule_catalog.rule_catalog_load_rule_catalog_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml"))
    strategy_by_id = strategy_loader.strategy_loader_load_all_strategy_definitions_from_directory(
        os.path.join(PROJECT_DIRECTORY, "config", "strategies"), catalog)
    return strategy_by_id["fundamentals"]


def test_rebalance_dates_are_the_last_trading_day_of_each_month():
    calendar = pandas.DatetimeIndex(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-29"])
    assert list(backtest.backtest_rebalance_dates(calendar)) == [pandas.Timestamp("2024-01-31"), pandas.Timestamp("2024-02-29")]


def test_cost_is_two_trades_at_the_basis_point_cost():
    spread = pandas.Series([0.01, 0.02])
    assert numpy.allclose(backtest.backtest_apply_cost_to_spread(spread, 10).to_numpy(), [0.01 - 0.002, 0.02 - 0.002])


def test_unknown_share_is_the_average_over_symbols_and_dates():
    table = pandas.DataFrame({"A": [0.0, 0.5], "B": [1.0, numpy.nan]})
    assert numpy.isclose(backtest.backtest_unknown_share(table), 0.5)


def test_random_band_is_the_5th_and_95th_percentile():
    summary_list = [{"rank_ic_mean": value} for value in numpy.linspace(-0.1, 0.1, 101)]
    low, high = backtest.backtest_random_band(summary_list, "rank_ic_mean")
    assert numpy.isclose(low, -0.09) and numpy.isclose(high, 0.09)


def test_summary_of_a_perfect_score_has_rank_ic_one_and_costs_reduce_the_spread():
    symbol_list = ["S{:02d}".format(number) for number in range(12)]
    date_index = pandas.bdate_range("2024-01-01", periods=4)
    score = pandas.DataFrame([list(range(12))] * len(date_index), index=date_index, columns=symbol_list, dtype=float)
    returns = score * 0.001
    summary = backtest.backtest_summarize_factor(score, returns, cost_basis_points_per_trade=10, newey_west_lag_count=1)
    assert numpy.isclose(summary["rank_ic_mean"], 1.0)
    assert summary["decile_spread_after_costs_mean"] < summary["decile_spread_mean"]


def test_score_table_uses_only_the_values_known_on_each_date():
    strategy = load_fundamentals_strategy()
    date_index = pandas.DatetimeIndex(["2024-01-31", "2024-02-29"])
    company_table = pandas.DataFrame({"piotroski_f_score": [8.0, 2.0], "return_on_equity_percent": [20.0, 20.0],
                                      "return_on_invested_capital_percent": [20.0, 20.0], "gross_margin_percent": [50.0, 50.0],
                                      "free_cash_flow_after_stock_compensation": [1.0, 1.0],
                                      "accruals_percent_of_average_total_assets": [1.0, 1.0],
                                      "net_debt_to_ebitda": [1.0, 1.0]}, index=date_index)
    tables = backtest.backtest_build_score_table(strategy, {"AAA": company_table}, date_index)
    assert tables["score"]["AAA"].iloc[1] < tables["score"]["AAA"].iloc[0]  # Piotroski fell, so the score fell
    assert (tables["unknown_weight_ratio"]["AAA"] < 1).all()


def test_baseline_tables_have_the_four_families_and_one_table_per_random_repeat():
    date_index = pandas.bdate_range("2024-01-01", periods=3)
    company_table = pandas.DataFrame({name: [1.0, 2.0, 3.0] for name in backtest.BASELINE_QUALITY_INPUT_NAME_LIST + [
        "piotroski_f_score", "trailing_twelve_month_eps"]}, index=date_index)
    prices = {"AAA": pandas.Series([10.0, 10.0, 10.0], index=date_index)}
    tables = backtest.backtest_build_baseline_score_tables({"AAA": company_table}, prices, date_index)
    families = [name for name in tables if not name.startswith("random_")]
    assert set(families) == {"low_price_earnings", "piotroski_only", "quality_factor"}
    assert len([name for name in tables if name.startswith("random_")]) == backtest.BASELINE_RANDOM_REPEAT_COUNT


def test_factor_statistics_summary_keys_are_stable():
    score = pandas.DataFrame(numpy.arange(12.0)[None, :], index=pandas.bdate_range("2024-01-01", periods=1),
                             columns=["S{:02d}".format(n) for n in range(12)])
    summary = factor_statistics.factor_statistics_summarize(
        factor_statistics.factor_statistics_rank_ic_by_date(score, score), factor_statistics.factor_statistics_decile_spread_by_date(score, score), 0)
    assert {"date_count", "rank_ic_mean", "rank_ic_t", "decile_spread_mean", "decile_spread_t"} <= set(summary)
