"""Forward returns for a backtest: what each stock did over the next N trading days after a score date, and the same minus its sector ETF.

The return of a score date starts at that day's close and ends N trading days later, so a score is only ever compared with what came
after it. Every symbol is put on one shared trading calendar (the union of all the price histories). A return is left out when the
symbol has no price on any day of its window, so a missing day never silently shortens or stretches a return.
"""
from typing import Dict, List

import pandas


def forward_returns_build_table(price_by_symbol: Dict[str, pandas.Series], horizon_trading_days: List[int]) -> Dict[int, pandas.DataFrame]:
    """One table per horizon: rows are score dates, columns are symbols, values are the total return over the next N trading days."""
    calendar = pandas.DatetimeIndex(sorted(set().union(*[set(price.index) for price in price_by_symbol.values()])))
    table_by_horizon: Dict[int, Dict[str, pandas.Series]] = {horizon: {} for horizon in horizon_trading_days}
    for symbol, price in price_by_symbol.items():
        price = price.dropna().sort_index().reindex(calendar)
        has_price = price.notna().astype(int)
        for horizon in horizon_trading_days:
            window_complete = has_price.rolling(horizon + 1).sum().shift(-horizon) == horizon + 1
            table_by_horizon[horizon][symbol] = (price.shift(-horizon) / price - 1).where(window_complete)
    return {horizon: pandas.DataFrame(column_by_symbol, index=calendar) for horizon, column_by_symbol in table_by_horizon.items()}


def forward_returns_subtract_sector_etf(return_table: pandas.DataFrame, etf_symbol_by_symbol: Dict[str, str],
                                        etf_return_table: pandas.DataFrame) -> pandas.DataFrame:
    """Each stock's return minus its sector ETF's return over the same window. A stock with no ETF mapping is left out."""
    excess = {}
    for symbol in return_table.columns:
        etf_symbol = etf_symbol_by_symbol.get(symbol)
        if etf_symbol is None or etf_symbol not in etf_return_table.columns:
            continue
        excess[symbol] = return_table[symbol] - etf_return_table[etf_symbol].reindex(return_table.index)
    return pandas.DataFrame(excess, index=return_table.index)
