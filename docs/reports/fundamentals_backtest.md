# Fundamentals strategy backtest

Generated 2026-10-26 from the stocks in `config/symbols.yaml` that have SEC company facts.

**Survivorship warning:** the stock list is today's list. Companies that failed or left the index are not in it, so every result here is biased upward.

Scores use only the company table as it was on each rebalance date (EDGAR filings by acceptance date). Rules that need live Yahoo data (estimates, insider buying, PEG, EV/EBITDA when price is needed) are unknown on past dates and do not count.

## Coverage

- Stocks tested: 35 (AAOI, AAPL, ALAB, AMD, AMZN, ARM, ASML, ASTS, AVGO, BE, BEAM, BRK-B, CBRS, COHR, COIN, CRCL, GOOGL, HOOD, INTC, LITE, LUNR, META, MRVL, MSFT, MU, NFLX, NVDA, PLTR, QCOM, RKLB, SKHY, SNDK, SPCX, TSLA, TSM)
- Stocks skipped: DRAM (no SEC company facts (KeyError)); MUU (no SEC company facts (KeyError)); QQQ (no SEC company facts (KeyError)); RAM (no SEC company facts (KeyError)); SMH (no SEC company facts (KeyError)); SNXX (no SEC company facts (KeyError)); SOXL (no SEC company facts (KeyError)); SOXX (no SEC company facts (KeyError)); SPMO (no SEC company facts (KeyError)); SPXL (no SEC company facts (KeyError)); SPY (no SEC company facts (HTTPStatusError)); TQQQ (no SEC company facts (KeyError)); UFO (no SEC company facts (KeyError)); VGT (no SEC company facts (KeyError)); VOO (no SEC company facts (KeyError))
- Rebalance dates: 176 from 2011-01-31 to 2025-08-29
- Average unknown share of the fundamentals score: 0.67
- Cost assumption: 10 bp per trade, two trades per monthly rebalance.

## Sector-neutral excess return, 3 months ahead

| Score | Dates | Rank IC mean | IC t | Top-minus-bottom decile after costs | Spread t | IC > 0 |
|---|---|---|---|---|---|---|
| fundamentals | 176 | 0.020 | 0.49 | -0.0810 | -1.75 | yes |
| low_price_earnings | 176 | 0.083 | 2.28 | -0.0678 | -1.01 | yes |
| piotroski_only | 157 | -0.014 | -0.26 | -0.0432 | -0.69 | no |
| quality_factor | 157 | -0.007 | -0.14 | -0.0439 | -0.64 | no |

Random baseline rank IC, 5th to 95th percentile over 100 repeats: -0.028 to 0.031.

## Sector-neutral excess return, 6 months ahead

| Score | Dates | Rank IC mean | IC t | Top-minus-bottom decile after costs | Spread t | IC > 0 |
|---|---|---|---|---|---|---|
| fundamentals | 176 | 0.008 | 0.14 | -0.2070 | -1.93 | yes |
| low_price_earnings | 176 | 0.122 | 2.64 | -0.1064 | -0.75 | yes |
| piotroski_only | 157 | -0.030 | -0.45 | -0.0711 | -0.59 | no |
| quality_factor | 157 | 0.015 | 0.26 | -0.0884 | -0.66 | yes |

Random baseline rank IC, 5th to 95th percentile over 100 repeats: -0.025 to 0.035.

## Sector-neutral excess return, 12 months ahead

| Score | Dates | Rank IC mean | IC t | Top-minus-bottom decile after costs | Spread t | IC > 0 |
|---|---|---|---|---|---|---|
| fundamentals | 176 | -0.022 | -0.34 | -0.8273 | -1.78 | no |
| low_price_earnings | 176 | 0.154 | 2.58 | -0.2875 | -0.91 | yes |
| piotroski_only | 157 | -0.064 | -0.89 | -0.4195 | -1.09 | no |
| quality_factor | 157 | -0.032 | -0.48 | -0.5243 | -1.39 | no |

Random baseline rank IC, 5th to 95th percentile over 100 repeats: -0.028 to 0.031.

## Decision gate (12 months, out of sample from 2019)

- out-of-sample rank IC mean above 0: FAIL
- out-of-sample Newey-West t above 2: FAIL
- decile spread after costs above 0: FAIL
- same sign in sample (2011 to 2018) and out of sample: FAIL
- rank IC above the random baseline's 95th percentile: FAIL

**Verdict: the fundamentals score is not validated.**

