"""Statistics that say whether a score predicts returns: rank IC per date, the spread between the top and bottom buckets, and a
Newey-West t-statistic for the mean. Written with pandas and numpy only (no new package).

Each date is one cross-section: the score and the forward return of every symbol on that date. A missing value drops that symbol.
"""
import math
from typing import Dict, Optional

import numpy
import pandas

MINIMUM_SYMBOL_COUNT_PER_DATE = 10
BUCKET_COUNT = 10


def factor_statistics_rank_ic_by_date(score_table: pandas.DataFrame, return_table: pandas.DataFrame,
                                      minimum_symbol_count: int = MINIMUM_SYMBOL_COUNT_PER_DATE) -> pandas.Series:
    """Spearman correlation between score and forward return across the symbols of each date. NaN where it is not defined."""
    result: Dict[pandas.Timestamp, float] = {}
    for date in score_table.index.intersection(return_table.index):
        pair = pandas.DataFrame({"score": score_table.loc[date], "return": return_table.loc[date]}).dropna()
        if len(pair) < minimum_symbol_count:
            continue
        result[date] = pair["score"].rank().corr(pair["return"].rank())  # Spearman: Pearson on ranks (no scipy here)
    return pandas.Series(result, dtype=float).sort_index()


def factor_statistics_decile_spread_by_date(score_table: pandas.DataFrame, return_table: pandas.DataFrame,
                                            bucket_count: int = BUCKET_COUNT,
                                            minimum_symbol_count: int = MINIMUM_SYMBOL_COUNT_PER_DATE) -> pandas.Series:
    """Mean forward return of the top-score bucket minus the bottom-score bucket, per date."""
    result: Dict[pandas.Timestamp, float] = {}
    for date in score_table.index.intersection(return_table.index):
        pair = pandas.DataFrame({"score": score_table.loc[date], "return": return_table.loc[date]}).dropna()
        if len(pair) < minimum_symbol_count:
            continue
        bucket = pandas.qcut(pair["score"].rank(method="first"), bucket_count, labels=False)
        result[date] = pair.loc[bucket == bucket.max(), "return"].mean() - pair.loc[bucket == bucket.min(), "return"].mean()
    return pandas.Series(result, dtype=float).sort_index()


def factor_statistics_newey_west_t(series: pandas.Series, lags: int) -> Optional[float]:
    """t-statistic of the mean with Newey-West (Bartlett) standard errors. None when there are fewer than two values or no variance.
    With lags = 0 it is the mean over the population standard deviation divided by the square root of the count."""
    values = series.dropna().to_numpy(dtype=float)
    count = len(values)
    if count < 2:
        return None
    demeaned = values - values.mean()
    long_run_variance = demeaned @ demeaned / count
    for lag in range(1, lags + 1):
        weight = 1 - lag / (lags + 1)
        autocovariance = demeaned[lag:] @ demeaned[:-lag] / count
        long_run_variance += 2 * weight * autocovariance
    variance_of_mean = long_run_variance / count
    if not numpy.isfinite(variance_of_mean) or variance_of_mean <= 0:
        return None
    return float(values.mean() / math.sqrt(variance_of_mean))


def factor_statistics_summarize(rank_ic_series: pandas.Series, spread_series: pandas.Series, lags: int) -> dict:
    """The numbers the decision gate reads: means, Newey-West t-statistics and how many dates were used."""
    return {
        "date_count": int(rank_ic_series.dropna().size),
        "rank_ic_mean": None if rank_ic_series.dropna().empty else float(rank_ic_series.mean()),
        "rank_ic_t": factor_statistics_newey_west_t(rank_ic_series, lags),
        "decile_spread_mean": None if spread_series.dropna().empty else float(spread_series.mean()),
        "decile_spread_t": factor_statistics_newey_west_t(spread_series, lags),
    }
