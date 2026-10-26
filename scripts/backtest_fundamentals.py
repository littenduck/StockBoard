"""Backtest the fundamentals strategy on the stocks in config/symbols.yaml and write docs/reports/fundamentals_backtest.md.

Run from the project folder with the project's Python:

    EDGAR_CONTACT=you@example.com .venv/bin/python scripts/backtest_fundamentals.py

It needs internet: SEC EDGAR for company facts and Yahoo (yfinance) for prices, sectors and the sector ETFs. ETFs in the symbol list have
no company facts and are left out. The decision gate is the one written in config/strategies/fundamentals.yaml before this was run.
"""
import datetime
import os
import sys

import pandas
import yaml

PROJECT_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIRECTORY)

from stock_benchmark_backend import (  # noqa: E402
    backtest, company_indicators, edgar_data, forward_returns, factor_statistics, history_series, market_data, rule_catalog,
    strategy_loader,
)

REPORT_PATH = os.path.join(PROJECT_DIRECTORY, "docs", "reports", "fundamentals_backtest.md")
HORIZON_NAME_BY_TRADING_DAYS = {63: "3 months", 126: "6 months", 252: "12 months"}
IN_SAMPLE_END = pandas.Timestamp("2018-12-31")
FIRST_SCORE_DATE = pandas.Timestamp("2011-01-01")
PRICE_HISTORY_PERIOD = "max"


def load_symbol_list():
    with open(os.path.join(PROJECT_DIRECTORY, "config", "symbols.yaml"), encoding="utf8") as symbol_file:
        return yaml.safe_load(symbol_file)["symbol_list"]


def load_fundamentals_strategy():
    catalog = rule_catalog.rule_catalog_load_rule_catalog_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml"))
    strategy_by_id = strategy_loader.strategy_loader_load_all_strategy_definitions_from_directory(
        os.path.join(PROJECT_DIRECTORY, "config", "strategies"), catalog)
    return strategy_by_id["fundamentals"]


def load_settings():
    with open(os.path.join(PROJECT_DIRECTORY, "config", "settings.yaml"), encoding="utf8") as settings_file:
        return yaml.safe_load(settings_file)


def fetch_stock_company_tables(symbol_list, price_by_symbol):
    """Company table per stock that has SEC company facts; the sector from Yahoo's profile."""
    import yfinance
    company_table_by_symbol, sector_by_symbol, skipped = {}, {}, {}
    for symbol in symbol_list:
        if symbol not in price_by_symbol:
            skipped[symbol] = "no price history"
            continue
        try:
            company_table_by_symbol[symbol] = history_series.history_series_build_company_indicator_table(
                symbol, price_by_symbol[symbol]["Close"])
        except Exception as error:  # one stock failing (SEC 403 or 5xx after retries) must not stop the whole run
            skipped[symbol] = "no SEC company facts ({})".format(type(error).__name__)
            continue
        sector_by_symbol[symbol] = yfinance.Ticker(symbol).info.get("sector")
    return company_table_by_symbol, sector_by_symbol, skipped


def run_family_summaries(score_by_family, return_table_by_horizon, horizon, lag_count, cost_bps):
    result = {}
    for family, score_table in score_by_family.items():
        result[family] = backtest.backtest_summarize_factor(score_table, return_table_by_horizon[horizon], cost_bps, lag_count)
    return result


def format_number(value, digits=3):
    return "n/a" if value is None or pandas.isna(value) else "{:.{}f}".format(value, digits)


def table_row(name, summary):
    return "| {} | {} | {} | {} | {} | {} | {} |".format(
        name, summary["date_count"], format_number(summary["rank_ic_mean"]), format_number(summary["rank_ic_t"], 2),
        format_number(summary["decile_spread_after_costs_mean"], 4), format_number(summary["decile_spread_t"], 2),
        "yes" if (summary["rank_ic_mean"] or 0) > 0 else "no")


def main():
    if not os.environ.get("EDGAR_CONTACT"):
        sys.exit("Set EDGAR_CONTACT to a contact address first; SEC returns 403 to anonymous clients.")
    settings = load_settings()
    strategy = load_fundamentals_strategy()
    lag_count = settings["backtest_newey_west_lag_count"]
    cost_bps = settings["backtest_cost_basis_points_per_trade"]
    symbol_list = load_symbol_list()

    price_history_by_symbol = market_data.market_data_fetch_daily_price_history_for_symbol_list(symbol_list, PRICE_HISTORY_PERIOD)
    price_by_symbol = {symbol: history for symbol, history in price_history_by_symbol.items()}
    close_by_symbol = {symbol: history["Close"] for symbol, history in price_by_symbol.items()}
    calendar = pandas.DatetimeIndex(sorted(set().union(*[set(close.index) for close in close_by_symbol.values()])))
    rebalance_dates = backtest.backtest_rebalance_dates(calendar)
    rebalance_dates = rebalance_dates[(rebalance_dates >= FIRST_SCORE_DATE) & (rebalance_dates <= calendar[-1] - pandas.Timedelta(days=400))]

    company_table_by_symbol, sector_by_symbol, skipped = fetch_stock_company_tables(symbol_list, price_by_symbol)
    stock_list = sorted(company_table_by_symbol)
    stock_close_by_symbol = {symbol: close_by_symbol[symbol] for symbol in stock_list}

    score_tables = backtest.backtest_build_score_table(strategy, company_table_by_symbol, rebalance_dates)
    baseline_tables = backtest.backtest_build_baseline_score_tables(company_table_by_symbol, stock_close_by_symbol, rebalance_dates)
    score_by_family = {"fundamentals": score_tables["score"], **{k: v for k, v in baseline_tables.items() if not k.startswith("random_")}}
    random_table_list = [v for k, v in baseline_tables.items() if k.startswith("random_")]

    return_table_by_horizon = forward_returns.forward_returns_build_table(stock_close_by_symbol, list(HORIZON_NAME_BY_TRADING_DAYS))
    sector_etf_by_sector = company_indicators.SECTOR_ETF_BY_SECTOR_NAME
    etf_symbol_by_symbol = backtest.backtest_sector_etf_lookup(sector_by_symbol, sector_etf_by_sector)
    # The sector ETFs are not in symbols.yaml, so fetch their prices too; without them every excess return is missing.
    etf_history_by_symbol = market_data.market_data_fetch_daily_price_history_for_symbol_list(
        sorted(set(sector_etf_by_sector.values()) | {"SPY"}), PRICE_HISTORY_PERIOD)
    etf_price_by_symbol = {symbol: history["Close"] for symbol, history in etf_history_by_symbol.items()}
    etf_return_by_horizon = forward_returns.forward_returns_build_table(etf_price_by_symbol, list(HORIZON_NAME_BY_TRADING_DAYS))
    excess_by_horizon = {}
    for horizon in HORIZON_NAME_BY_TRADING_DAYS:
        excess_by_horizon[horizon] = forward_returns.forward_returns_subtract_sector_etf(
            return_table_by_horizon[horizon].reindex(rebalance_dates), etf_symbol_by_symbol,
            etf_return_by_horizon[horizon].reindex(rebalance_dates))

    report_lines = ["# Fundamentals strategy backtest", "",
                    "Generated {} from the stocks in `config/symbols.yaml` that have SEC company facts.".format(datetime.date.today()), "",
                    "**Survivorship warning:** the stock list is today's list. Companies that failed or left the index are not in it, so every result here is biased upward.", "",
                    "Scores use only the company table as it was on each rebalance date (EDGAR filings by acceptance date). Rules that need live Yahoo data (estimates, insider buying, PEG, EV/EBITDA when price is needed) are unknown on past dates and do not count.", ""]
    report_lines += ["## Coverage", "", "- Stocks tested: {} ({})".format(len(stock_list), ", ".join(stock_list)),
                     "- Stocks skipped: {}".format("; ".join("{} ({})".format(s, r) for s, r in sorted(skipped.items())) or "none"),
                     "- Rebalance dates: {} from {} to {}".format(len(rebalance_dates), rebalance_dates[0].date(), rebalance_dates[-1].date()),
                     "- Average unknown share of the fundamentals score: {}".format(format_number(backtest.backtest_unknown_share(score_tables["unknown_weight_ratio"]), 2)),
                     "- Cost assumption: {} bp per trade, two trades per monthly rebalance.".format(cost_bps), ""]
    for horizon, name in HORIZON_NAME_BY_TRADING_DAYS.items():
        report_lines += ["## Sector-neutral excess return, {} ahead".format(name), "",
                         "| Score | Dates | Rank IC mean | IC t | Top-minus-bottom decile after costs | Spread t | IC > 0 |", "|---|---|---|---|---|---|---|"]
        summaries = run_family_summaries(score_by_family, excess_by_horizon, horizon, lag_count, cost_bps)
        for family, summary in summaries.items():
            report_lines.append(table_row(family, summary))
        random_summary_list = [backtest.backtest_summarize_factor(table, excess_by_horizon[horizon], cost_bps, lag_count) for table in random_table_list]
        low, high = backtest.backtest_random_band(random_summary_list, "rank_ic_mean")
        report_lines += ["", "Random baseline rank IC, 5th to 95th percentile over {} repeats: {} to {}.".format(
            len(random_summary_list), format_number(low), format_number(high)), ""]

    twelve = excess_by_horizon[252]
    in_sample = backtest.backtest_summarize_factor(score_tables["score"][score_tables["score"].index <= IN_SAMPLE_END],
                                                   twelve[twelve.index <= IN_SAMPLE_END], cost_bps, lag_count)
    out_sample_index = score_tables["score"].index[score_tables["score"].index > IN_SAMPLE_END]
    out_sample = backtest.backtest_summarize_factor(score_tables["score"].loc[out_sample_index], twelve.loc[out_sample_index], cost_bps, lag_count)
    random_out_sample = [backtest.backtest_summarize_factor(t.loc[out_sample_index], twelve.loc[out_sample_index], cost_bps, lag_count)
                         for t in random_table_list]
    _, random_high = backtest.backtest_random_band(random_out_sample, "rank_ic_mean")
    gate_checks = {
        "out-of-sample rank IC mean above 0": (out_sample["rank_ic_mean"] or 0) > 0,
        "out-of-sample Newey-West t above 2": (out_sample["rank_ic_t"] or 0) > 2,
        "decile spread after costs above 0": (out_sample["decile_spread_after_costs_mean"] or 0) > 0,
        "same sign in sample (2011 to 2018) and out of sample": (in_sample["rank_ic_mean"] or 0) > 0 and (out_sample["rank_ic_mean"] or 0) > 0,
        "rank IC above the random baseline's 95th percentile": out_sample["rank_ic_mean"] is not None and random_high is not None and out_sample["rank_ic_mean"] > random_high,
    }
    report_lines += ["## Decision gate (12 months, out of sample from 2019)", ""]
    report_lines += ["- {}: {}".format(check, "pass" if passed else "FAIL") for check, passed in gate_checks.items()]
    verdict = "validated" if all(gate_checks.values()) else "not validated"
    report_lines += ["", "**Verdict: the fundamentals score is {}.**".format(verdict), ""]

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf8") as report_file:
        report_file.write("\n".join(report_lines) + "\n")
    print("\n".join(report_lines))


if __name__ == "__main__":
    main()
