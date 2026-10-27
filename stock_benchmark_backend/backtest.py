"""Backtest of a strategy's score: score every symbol on each rebalance date using only the company table as it was that day, then
measure how the score ranked the forward returns. Baselines are scored the same way.

Scores use the company table (point in time, built from EDGAR), so a rule that needs live Yahoo data is unknown on past dates. The
report shows how much of each score was unknown; a score that is mostly unknown is not evidence for anything.
"""
import random
from typing import Dict, List, Optional

import numpy
import pandas

from stock_benchmark_backend import factor_statistics, strategy_evaluation

BASELINE_RANDOM_REPEAT_COUNT = 100
RANDOM_SEED = 1
BASELINE_QUALITY_INPUT_NAME_LIST = ["return_on_invested_capital_percent", "gross_margin_percent", "accruals_percent_of_average_total_assets"]
ACCRUALS_NAME = "accruals_percent_of_average_total_assets"
EVIDENCE_SOURCE = "edgar:companyfacts"


def backtest_rebalance_dates(calendar: pandas.DatetimeIndex) -> pandas.DatetimeIndex:
    """The last trading day of each month in the calendar."""
    return pandas.DatetimeIndex(pandas.Series(calendar).groupby(calendar.to_period("M")).max().values)


def backtest_build_score_table(strategy_definition: strategy_evaluation.StrategyDefinition,
                               company_table_by_symbol: Dict[str, pandas.DataFrame],
                               date_index: pandas.DatetimeIndex) -> Dict[str, pandas.DataFrame]:
    """Strategy score and pass per symbol and date. Returns two tables (rows dates, columns symbols): score_percent and unknown_weight_ratio."""
    score_by_symbol, unknown_by_symbol = {}, {}
    for symbol, company_table in company_table_by_symbol.items():
        score_list, unknown_list = [], []
        for date in date_index:
            row = company_table.loc[date] if date in company_table.index else None
            indicator_value_by_name = {}
            if row is not None:
                for name, value in row.items():
                    if pandas.notna(value):
                        indicator_value_by_name[name] = strategy_evaluation.IndicatorValue(
                            indicator_name=name, value=float(value), source=EVIDENCE_SOURCE)
            result = strategy_evaluation.strategy_evaluation_evaluate_strategy_for_symbol(
                strategy_definition, symbol, indicator_value_by_name, {})
            score_list.append(result.score_percent if result.score_percent is not None else numpy.nan)
            unknown_list.append(result.unknown_weight_ratio)
        score_by_symbol[symbol] = pandas.Series(score_list, index=date_index)
        unknown_by_symbol[symbol] = pandas.Series(unknown_list, index=date_index)
    return {"score": pandas.DataFrame(score_by_symbol, index=date_index),
            "unknown_weight_ratio": pandas.DataFrame(unknown_by_symbol, index=date_index)}


def backtest_build_baseline_score_tables(company_table_by_symbol: Dict[str, pandas.DataFrame], price_by_symbol: Dict[str, pandas.Series],
                                         date_index: pandas.DatetimeIndex) -> Dict[str, pandas.DataFrame]:
    """Four baselines on the same dates: low P/E, Piotroski alone, a quality factor, and random (one table per repeat)."""
    symbol_list = list(company_table_by_symbol)
    column_by = lambda name: pandas.DataFrame({s: company_table_by_symbol[s][name].reindex(date_index) for s in symbol_list}, index=date_index)
    eps = column_by("trailing_twelve_month_eps")
    price = pandas.DataFrame({s: price_by_symbol[s].reindex(date_index, method="ffill") if s in price_by_symbol else numpy.nan
                              for s in symbol_list}, index=date_index)
    price_earnings = (price / eps).where(eps > 0)
    quality_z_score_list = []
    for name in BASELINE_QUALITY_INPUT_NAME_LIST:
        table = column_by(name)
        if name == ACCRUALS_NAME:
            table = -table  # lower accruals are better
        quality_z_score_list.append(table.sub(table.mean(axis=1), axis=0).div(table.std(axis=1), axis=0))
    quality = sum(quality_z_score_list) / len(quality_z_score_list)
    tables = {"low_price_earnings": -price_earnings, "piotroski_only": column_by("piotroski_f_score"), "quality_factor": quality}
    rng = random.Random(RANDOM_SEED)
    for repeat in range(BASELINE_RANDOM_REPEAT_COUNT):
        tables["random_{:03d}".format(repeat)] = pandas.DataFrame(
            {s: [rng.random() for _ in date_index] for s in symbol_list}, index=date_index)
    return tables


def backtest_apply_cost_to_spread(spread_series: pandas.Series, cost_basis_points_per_trade: float) -> pandas.Series:
    """Charge a monthly rebalance the cost of buying and selling the top bucket: two trades at the cost per trade, as a fraction."""
    return spread_series - 2 * cost_basis_points_per_trade / 10000


def backtest_summarize_factor(score_table: pandas.DataFrame, return_table: pandas.DataFrame, cost_basis_points_per_trade: float,
                              newey_west_lag_count: int) -> dict:
    """Rank IC and decile spread of one score against forward returns, with and without costs."""
    rank_ic = factor_statistics.factor_statistics_rank_ic_by_date(score_table, return_table, minimum_symbol_count=5)
    spread = factor_statistics.factor_statistics_decile_spread_by_date(score_table, return_table, minimum_symbol_count=10)
    summary = factor_statistics.factor_statistics_summarize(rank_ic, spread, newey_west_lag_count)
    summary["decile_spread_after_costs_mean"] = None if spread.dropna().empty else float(
        backtest_apply_cost_to_spread(spread, cost_basis_points_per_trade).mean())
    return summary


def backtest_unknown_share(unknown_weight_ratio_table: pandas.DataFrame) -> float:
    """Average share of the score's weight that was unknown, over all symbols and dates."""
    values = unknown_weight_ratio_table.to_numpy(dtype=float)
    return float(numpy.nanmean(values)) if values.size else float("nan")


def backtest_sector_etf_lookup(sector_by_symbol: Dict[str, Optional[str]], etf_by_sector: Dict[str, str]) -> Dict[str, str]:
    return {symbol: etf_by_sector[sector] for symbol, sector in sector_by_symbol.items() if sector in etf_by_sector}


def backtest_random_band(summary_list: List[dict], key: str) -> tuple:
    """The 5th and 95th percentile of a statistic across the random baseline's repeats."""
    values = [summary[key] for summary in summary_list if summary.get(key) is not None]
    if not values:
        return (None, None)
    return (float(numpy.percentile(values, 5)), float(numpy.percentile(values, 95)))
