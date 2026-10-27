"""Compare each live Yahoo value with the value rebuilt from SEC filings for the same stock on the latest date.

A backtest uses the rebuilt value, the live page uses the Yahoo value. Where they disagree, the backtest and the page show different
numbers for the same rule. This prints one row per stock and indicator that both sources provide, and flags a relative difference above
5% (or an absolute difference above 0.05 for a ratio).

Run from the project folder, with internet and a contact for SEC:

    EDGAR_CONTACT=you@example.com .venv/bin/python scripts/check_live_against_rebuilt.py
"""
import os
import sys

import pandas
import yaml

PROJECT_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIRECTORY)

from stock_benchmark_backend import company_indicators, history_series, market_data, yahoo_company  # noqa: E402

RELATIVE_TOLERANCE = 0.05
ABSOLUTE_TOLERANCE_FOR_RATIO = 0.05


def check_live_against_rebuilt_is_disagreement(live: float, rebuilt: float) -> bool:
    if live == rebuilt:
        return False
    scale = max(abs(live), abs(rebuilt))
    if scale < 1:  # a ratio or a small number: use the absolute tolerance
        return abs(live - rebuilt) > ABSOLUTE_TOLERANCE_FOR_RATIO
    return abs(live - rebuilt) / scale > RELATIVE_TOLERANCE


def main():
    if not os.environ.get("EDGAR_CONTACT"):
        sys.exit("Set EDGAR_CONTACT to a contact address first; SEC returns 403 to anonymous clients.")
    with open(os.path.join(PROJECT_DIRECTORY, "config", "symbols.yaml"), encoding="utf8") as symbol_file:
        symbol_list = yaml.safe_load(symbol_file)["symbol_list"]
    price_by_symbol = market_data.market_data_fetch_daily_price_history_for_symbol_list(symbol_list, "5y")
    rows = []
    for symbol in symbol_list:
        if symbol not in price_by_symbol:
            continue
        try:
            table = history_series.history_series_build_company_indicator_table(symbol, price_by_symbol[symbol]["Close"])
            snapshot = yahoo_company.yahoo_company_fetch_snapshot(symbol)
        except Exception:  # ETFs and stocks without SEC facts (SEC answers 404), or one failing request: skip it, keep going
            continue
        live_by_name = company_indicators.company_indicators_build_info_indicator_value_by_name(snapshot["info"])
        known_rows = table.dropna(how="all")
        if known_rows.empty:  # no SEC figures for this stock
            continue
        latest = known_rows.iloc[-1]
        for name, live in live_by_name.items():
            if name in latest.index and pandas.notna(latest[name]):
                rebuilt = float(latest[name])
                rows.append((symbol, name, live, rebuilt, check_live_against_rebuilt_is_disagreement(live, rebuilt)))
    disagreeing = [row for row in rows if row[4]]
    print("| Symbol | Indicator | Live | Rebuilt | Disagrees |")
    print("|---|---|---|---|---|")
    for symbol, name, live, rebuilt, flag in rows:
        print("| {} | {} | {:.4g} | {:.4g} | {} |".format(symbol, name, live, rebuilt, "yes" if flag else "no"))
    print("\n{} comparisons, {} disagree.".format(len(rows), len(disagreeing)))


if __name__ == "__main__":
    main()
