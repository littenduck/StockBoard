# Fundamentals strategy backtest

Generated 2026-10-26 from the stocks in `config/symbols.yaml` that have SEC company facts.

**Survivorship warning:** the stock list is today's list. Companies that failed or left the index are not in it, so every result here is biased upward.

Scores use only the company table as it was on each rebalance date (EDGAR filings by acceptance date). Rules that need live Yahoo data (estimates, insider buying, PEG, EV/EBITDA when price is needed) are unknown on past dates and do not count.

## Coverage

- Stocks tested: 35 (AAOI, AAPL, ALAB, AMD, AMZN, ARM, ASML, ASTS, AVGO, BE, BEAM, BRK-B, CBRS, COHR, COIN, CRCL, GOOGL, HOOD, INTC, LITE, LUNR, META, MRVL, MSFT, MU, NFLX, NVDA, PLTR, QCOM, RKLB, SKHY, SNDK, SPCX, TSLA, TSM)
- Stocks skipped: DRAM (no SEC company facts (KeyError)); MUU (no SEC company facts (KeyError)); QQQ (no SEC company facts (KeyError)); RAM (no SEC company facts (KeyError)); SMH (no SEC company facts (KeyError)); SNXX (no SEC company facts (KeyError)); SOXL (no SEC company facts (KeyError)); SOXX (no SEC company facts (KeyError)); SPMO (no SEC company facts (KeyError)); SPXL (no SEC company facts (KeyError)); SPY (no SEC company facts (HTTPStatusError)); TQQQ (no SEC company facts (KeyError)); UFO (no SEC company facts (KeyError)); VGT (no SEC company facts (KeyError)); VOO (no SEC company facts (KeyError))
- Rebalance dates: 176 from 2011-01-31 to 2025-08-29
- Average unknown share of the fundamentals score: 0.70
- Cost assumption: 10 bp per trade, two trades per monthly rebalance.

## Sector-neutral excess return, 3 months ahead

| Score | Dates | Rank IC mean | IC t | Top-minus-bottom decile after costs | Spread t | IC > 0 |
|---|---|---|---|---|---|---|
| fundamentals | 176 | 0.026 | 0.73 | -0.0865 | -1.50 | yes |
| low_price_earnings | 176 | 0.087 | 2.37 | -0.0678 | -1.01 | yes |
| piotroski_only | 112 | -0.049 | -0.69 | -0.0972 | -1.38 | no |
| quality_factor | 131 | -0.012 | -0.15 | -0.0583 | -0.65 | no |

Random baseline rank IC, 5th to 95th percentile over 100 repeats: -0.028 to 0.031.

## Sector-neutral excess return, 6 months ahead

| Score | Dates | Rank IC mean | IC t | Top-minus-bottom decile after costs | Spread t | IC > 0 |
|---|---|---|---|---|---|---|
| fundamentals | 176 | -0.002 | -0.03 | -0.2639 | -1.92 | no |
| low_price_earnings | 176 | 0.128 | 2.74 | -0.1064 | -0.75 | yes |
| piotroski_only | 112 | -0.055 | -0.59 | -0.1445 | -1.18 | no |
| quality_factor | 131 | -0.015 | -0.16 | -0.1107 | -0.68 | no |

Random baseline rank IC, 5th to 95th percentile over 100 repeats: -0.025 to 0.035.

## Sector-neutral excess return, 12 months ahead

| Score | Dates | Rank IC mean | IC t | Top-minus-bottom decile after costs | Spread t | IC > 0 |
|---|---|---|---|---|---|---|
| fundamentals | 176 | -0.029 | -0.51 | -0.8656 | -1.95 | no |
| low_price_earnings | 176 | 0.158 | 2.61 | -0.2875 | -0.91 | yes |
| piotroski_only | 112 | -0.046 | -0.49 | -0.6580 | -1.40 | no |
| quality_factor | 131 | -0.028 | -0.29 | -0.3391 | -0.95 | no |

Random baseline rank IC, 5th to 95th percentile over 100 repeats: -0.028 to 0.031.

## Decision gate (12 months, out of sample from 2019)

- out-of-sample rank IC mean above 0: FAIL
- out-of-sample Newey-West t above 2: FAIL
- decile spread after costs above 0: FAIL
- same sign in sample (2011 to 2018) and out of sample: FAIL
- rank IC above the random baseline's 95th percentile: FAIL

**Verdict: the fundamentals score is not validated.**

