# Indicator

Three levels, three kinds of file:

| Level | What it is | Where it is written |
|---|---|---|
| **Indicator** | one measured quantity (a number or a yes/no), with where it comes from and how often it is fetched | `config/indicators.yaml` |
| **Rule** | a judgment on one indicator: an operator and a line (`MAC-03`: the 10-year yield is below 4.5). Several rules can share an indicator | `config/rules.yaml` |
| **Strategy** | which rules, with what weight and veto | `config/strategies/*.yaml` |

A rule refers to an indicator by its `indicator_id`. A value that cannot be fetched, or is older than the indicator's `max_age`, is `unknown` (shown as ❓, left out of the score).

### The indicator file

Each indicator has `scope` (market, symbol, or window for one option expiration window), `method`, `status`, the backtest facts (`backtestable`, `history_source`, `history_start`) and the schedule:

- `fetch_group`: the family of requests it comes from. Indicators of one group are fetched together, so a group is asked as often as its most frequent indicator needs (the shortest `fetch_every`).
- `fetch_every`: how often the source is asked again (`10m`, `1h`, `1d`). A value that is not due is not fetched again.
- `max_age`: how old the newest observation may be. Past it the value reads unknown. Monthly series are dated the first of the month and published a month or two later, so their limit is long; prices get 4 days so a weekend does not blank them.
- The group list at the top sets `market_hours_only` (prices and option quotes are asked only while the market is open) and `fetch_at` (New York times at which the group is also asked once: prices at 16:20 after the close, slow data at 06:00 before the open).

Rules take `method`, `backtestable`, `history_*` and `status` from their indicator, so these facts are written once. A manual rule has no indicator and keeps them itself. The code lists the indicators it makes in `PRODUCED_INDICATOR_ID_SET`; a test fails if that list and the built indicators of the YAML differ.

How a refresh works: the background loop wakes every minute; a refresh is due when the market is open and the snapshot is older than `refresh_interval_minutes`, or when any fetched answer is due again (also after the close, at the `fetch_at` times). A refresh rebuilds the snapshot from the cache and asks only the groups that are due. A failed fetch keeps the old value and waits 15 minutes before trying again. `scripts/count_requests.py --ticks 3` shows the requests per refresh.

## Volatility (market, same for every symbol)

| indicator_id | Meaning | Source |
|---|---|---|
| `vix_level` | VIX close | yfinance `^VIX` |
| `vxn_level` | VXN close | yfinance `^VXN` |
| `vvix_level` | VVIX close | yfinance `^VVIX` |
| `vix_term_structure_is_contango` | `^VIX` below `^VIX3M` | yfinance |

## Rates and credit (market)

Daily change of these indicators is reported in basis points (`change_unit: basis_points`); volatility indices and prices report percent change.

| indicator_id | Meaning | Source |
|---|---|---|
| `treasury_ten_year_yield` | 10Y yield, percent | FRED `DGS10` (public CSV, no key) |
| `treasury_ten_year_yield_twenty_day_change_basis_points` | 20 trading day change | FRED `DGS10` |
| `high_yield_credit_spread_basis_points` | HY option adjusted spread | FRED `BAMLH0A0HYM2` |

## Market trend and sentiment

| indicator_id | Meaning | Source |
|---|---|---|
| `spx_above_two_hundred_day_average` | `^GSPC` close above its 200 day average | yfinance |
| `fear_greed_index` | CNN Fear and Greed | no free stable source, always unknown for now |

## Symbol technicals

| indicator_id | Meaning | Source |
|---|---|---|
| `last_price` | latest close | yfinance |
| `fifty_two_week_range_percentile` | position in 52 week range, 0 to 100 | yfinance daily history |
| `price_above_two_hundred_day_average` | close above 200 day average | yfinance daily history |
| `realized_volatility_thirty_day` | annualized, percent | yfinance daily history |
| `no_earnings_before_expiration` | no earnings date within the longest day count of the first (standard) expiration window | yfinance calendar |

## Symbol trend and momentum

| indicator_id | Meaning | Source |
|---|---|---|
| `relative_strength_index_two_day` | RSI over 2 days, 0 to 100 (Connors pullback) | yfinance daily history |
| `relative_strength_index_fourteen_day` | RSI over 14 days, 0 to 100 | yfinance daily history |
| `price_above_fifty_day_average` | close above 50 day average | yfinance daily history |
| `fifty_day_average_above_two_hundred_day_average` | 50 day average above 200 day average (golden cross state) | yfinance daily history |
| `price_below_five_day_average` | close below 5 day average (short-term pullback) | yfinance daily history |
| `distance_from_fifty_two_week_high_percent` | percent below the 52 week high (0 = at the high) | yfinance daily history |
| `volume_ratio_to_twenty_day_average` | last volume divided by the previous 20 day average | yfinance daily history |
| `return_six_month_percent` | price change over 126 trading days, percent | yfinance daily history |

## Symbol option contract (per expiration window)

Computed for the representative put of each expiration window.

| indicator_id | Meaning | Source |
|---|---|---|
| `selected_put_absolute_delta` | Black-Scholes delta, absolute value | computed from yfinance chain |
| `selected_put_days_to_expiration` | days to expiration | yfinance chain |
| `selected_put_annualized_return_percent` | bid divided by strike, annualized | yfinance chain |
| `selected_put_implied_volatility_exceeds_realized` | implied volatility above realized | yfinance chain |

## History series (FRED and Cboe)

`stockboard_backend/history_series.py` rebuilds these indicators as a date-indexed series from free history, so a backtest and the live dashboard can share one definition. `python -m stockboard_backend.history_series` fetches every one and prints its first and last date, row count and latest value next to the start date in the rule catalog (the first date is later than the catalog start when a rolling window needs warm-up). The daily put/call cache is built once with `python -m stockboard_backend.cboe_data` (about 1,900 small requests, then only new days).

| indicator_id | Built from |
|---|---|
| `federal_funds_target_rate_not_raised_in_182_days` | FRED DFEDTAR (1982 to 2008-12-15) joined to DFEDTARU; true when the rate is not above its level 182 calendar days earlier |
| `six_month_treasury_bill_yield_minus_federal_funds_rate` | FRED DGS6MO minus DFF |
| `treasury_ten_year_yield` | FRED DGS10 |
| `treasury_ten_year_yield_twenty_day_change_basis_points` | FRED DGS10, change over 20 observations times 100 |
| `high_yield_credit_spread_basis_points` | FRED BAMLH0A0HYM2 times 100 (FRED keeps about 3 years) |
| `high_yield_credit_spread_twenty_day_change_basis_points` | FRED BAMLH0A0HYM2, change over 20 observations times 100 |
| `moodys_baa_minus_ten_year_treasury_spread` | FRED BAA10Y |
| `treasury_ten_year_minus_two_year_spread` | FRED T10Y2Y |
| `treasury_ten_year_minus_three_month_spread` | FRED T10Y3M |
| `consumer_price_index_year_over_year_percent` | FRED CPIAUCSL, 12 month percent change of the latest values (the point-in-time version uses ALFRED vintages) |
| `core_pce_price_index_year_over_year_percent` | FRED PCEPILFE, 12 month percent change |
| `sahm_rule_recession_indicator` | FRED SAHMREALTIME |
| `initial_jobless_claims_four_week_average` | FRED ICSA, 4 week mean |
| `chicago_fed_national_activity_index_three_month_average` | FRED CFNAIMA3 |
| `wti_crude_oil_price` | FRED DCOILWTICO |
| `wti_crude_oil_one_month_change_percent` | FRED DCOILWTICO, change over 21 observations |
| `m2_money_supply_year_over_year_percent` | FRED M2SL, 12 month percent change |
| `federal_reserve_total_assets_thirteen_week_change_percent` | FRED WALCL, change over 13 weeks |
| `market_value_to_gdp_percent` | FRED NCBEILQ027S (millions) divided by 1,000 and by GDP (billions) |
| `trade_policy_uncertainty_ten_year_percentile` | FRED EPUTRADE, percentile of the last 120 months |
| `us_epu_thirty_day_average_percentile_five_year` | FRED USEPUINDXD, 30 day mean, percentile of the last 5 years |
| `vix_level` | Cboe VIX_History.csv, close |
| `vix_term_structure_is_contango` | Cboe VIX below VIX3M (from 2009-09-18) |
| `vxn_to_vix_ratio` | Cboe VXN divided by VIX (from 2009-09-14) |
| `vix_to_twenty_day_average_ratio` | Cboe VIX divided by its 20 day mean |
| `put_call_ratio_total_five_day_average` | Cboe total put/call: old CSV 2006-11-01 to 2019-10-04, then the daily files kept in `data/cache/cboe_total_put_call.csv`; 5 day mean |

### Sentiment sources

| indicator_id | Built from |
|---|---|
| `fear_greed_index` | CNN `graphdata` JSON from 2021-01-04 (needs a cnn.com Referer and Origin header) |
| `aaii_bullish_percent`, `aaii_bullish_minus_bearish_percent` | AAII `sentiment.xls`, which blocks scripts, so the newest Internet Archive copy is read |
| `naaim_exposure_index` | NAAIM `USE_Data-since-Inception_*.xlsx`, the newest copy the Internet Archive holds |

The archive copies can be weeks behind the live sites and the archive answers 429 when asked too fast (the fetcher waits and retries). `python -m stockboard_backend.sentiment_data` prints the row count and date range of each.

### Company indicators (SEC EDGAR and FINRA)

`history_series_build_company_indicator_table(ticker, price_series)` returns one row per day with one column per company indicator id. Set the environment variable `EDGAR_CONTACT` (for example an email address) first: SEC asks every client to identify itself.

- **Point in time**: each filed figure is used from the day its filing reached EDGAR, and the earliest filing of a period wins over later restatements.
- **Trailing twelve months** come from a 10-K (the fiscal year) or a 10-Q (last fiscal year plus this year to date minus the same stretch a year earlier).
- **Columns without a price**: `trailing_twelve_month_eps`, revenue growth (1 year, 3 year CAGR), `eps_three_year_cagr_percent`, `return_on_equity_percent`, `return_on_invested_capital_percent` (approximate: operating income taxed at 21% over equity plus debt minus cash), `gross_margin_percent`, free cash flow and its yearly change, `net_debt_to_ebitda`, `interest_coverage_ratio`, `operating_cash_flow_to_net_income_ratio`, `shares_outstanding_year_over_year_percent`, `dividend_to_free_cash_flow_ratio`.
- **Columns that need a daily close**: `market_capitalization_billion_usd`, `free_cash_flow_yield_percent`, `enterprise_value_to_ebitda`, `price_earnings_ttm_to_five_year_median_ratio`.
- **FINRA**: `short_interest_percent_of_shares_outstanding` is the twice-monthly short position divided by the latest share count on file (history from 2017-12-29).
- **Not built yet**: the insider rules (`edgar:form345`) and the filing-based rules (`edgar:submissions`: audit problems, earnings dates).

`python -m stockboard_backend.fundamental_series AAPL` prints a sample of the table for one ticker.

## Live indicators on the dashboard

Each refresh adds these to the indicators above, asking each source only when it is due (see the schedule above and `config/indicators.yaml`; the Kept for column shows the usual interval). A source that fails or is too old only turns its own rules to Unknown.

| What | Source | Kept for | Newest value counts for |
|---|---|---|---|
| FRED series (rates, spreads, inflation, jobs, money, EPU), Cboe put/call, CNN Fear and Greed, AAII | the history series builders; the newest observation is the live value | 30 minutes | daily series 10 days, weekly 16, monthly 100, quarterly 270, put/call 7, Fear and Greed 5 |
| Oil, dollar index, RSP versus SPY, VXN/VIX, VIX versus its 20-day average, sector ETF versus SPY | yfinance price history | each refresh | the last close |
| 60-day low, ATR, 52-week low, 200-day distance, trading value, relative strength | yfinance price history of the symbol | each refresh | the last close |
| Market cap, EV/EBITDA, free cash flow, margins, ROE, forward PE, dividend cover | yfinance `info` | 1 hour | now |
| EPS estimate change (4 weeks), PEG, buy share of ratings | yfinance `eps_trend`, `recommendations_summary` | 1 hour | now (PEG is forward PE over the growth of next-year over this-year EPS) |
| Insider net selling (180 days) and purchase count (90 days) | yfinance `insider_transactions`, told apart by the text "Sale" and "Purchase" | 1 hour | now |
| Short interest, percent of shares | FINRA with yfinance shares outstanding | 1 hour | 45 days |
| 3-year growth, ROIC, interest coverage, FCF change, share count change | SEC EDGAR (needs `EDGAR_CONTACT`, else unknown) | 1 day | the latest filing |
| FOMC, CPI, PCE and jobs report dates | the release calendar in `config/settings.yaml` (`macro_event_calendar`), kept by hand; unknown past `macro_event_covered_until` | file | the window of the option |
| Election day, quadruple witching, SPMO rebalance (the months March and September) | the calendar | none | today |
| Option quotes (spread, open interest, volume, strike, premium, expected move, skew) | yfinance option chain; the implied volatility is solved from the mid of a live bid and ask (Black-Scholes), not read from Yahoo's own column | each refresh | only for contracts with a live bid and ask |
| Covered call (about 30 days out, strike about 10% above the price) | yfinance call chain; strikes need no live quote | each refresh | now |
| IV percentile over a year and IV against a month ago | DoltHub `volatility_history` (whole-chain 30 day IV, one or two days behind) | 6 hours | 7 days |
| Shiller CAPE, Damodaran implied equity risk premium, Geopolitical Risk percentile | multpl.com table, Damodaran's `ERPbymonth.xlsx`, the GPR daily file | 30 minutes | 45, 75 and 14 days |
| Equity risk premium (earnings yield of SPY minus the 10-year yield) | yfinance SPY trailing PE and FRED DGS10 | each refresh | now |
| SPMO holding rank | yfinance top 10 holdings of SPMO; a stock outside the ten has no rank and reads unknown | 6 hours | now |
| Audit changes and late filings (8-K items 4.01 and 4.02, NT 10-K, NT 10-Q) and PE against its own 5-year median | SEC EDGAR submissions and company facts plus six years of yfinance prices (needs `EDGAR_CONTACT`) | 1 day | the last 365 days |

Funds (SPY, QQQ) have no company figures, so their company rules read Unknown.

## Planned indicators (not built yet)

Every rule in `config/rules.yaml` names the indicator that will give its value. These indicators do not exist in the code yet (those the dashboard computes now are listed in the live section above); the rule that uses each one, and where its free history comes from, is listed here. The meaning of each is in the rule's description.

| indicator_id | Rules | History source |
|---|---|---|
| `sector_next_year_eps_estimate_four_week_change_median_percent` | `IND-02` | `dolthub:earnings` |
| `no_audit_or_late_filing_problem_in_last_365_days` | `MGT-04` | `edgar:submissions` |
| `sp500_forward_pe` | `VAL-01` | `wayback:sp-dji-eps` |
| `equity_risk_premium_simple_percent` | `VAL-03` | `shiller:ie_data` |
| `shiller_cape` | `VAL-11` | `shiller:ie_data` |
| `damodaran_implied_equity_risk_premium_percent` | `VAL-12` | `damodaran:implied-erp` |
| `price_earnings_ttm_to_five_year_median_ratio` | `VAL-05` | `edgar:companyfacts` |
| `naaim_exposure_index` | `SEN-06`, `SEN-21` | `naaim:exposure-index` |
| `no_mega_ipo_in_last_30_trading_days` | `SEN-08` | `ritter:ipo-data` |
| `sp500_share_above_two_hundred_day_average_percent` | `TRD-02`, `TRD-21` | `fja05680:sp500-components` |
| `spmo_holding_rank` | `TRD-16`, `TRD-25` | `sec:n-port` |
| `geopolitical_risk_index_thirty_day_average_percentile_five_year` | `EVT-08` | `gpr:daily` |
| `industry_leader_has_no_earnings_inside_option_life` | `EVT-10` | `edgar:submissions` |
| `customers_and_suppliers_have_no_earnings_inside_option_life` | `EVT-11` | `edgar:submissions` |
| `implied_volatility_percentile` | `VOL-01`, `VOL-06`, `VOL-07` | `dolthub:volatility_history` |
| `implied_volatility_to_one_month_ago_ratio` | `VOL-08` | `dolthub:options` |
| `selected_call_strike_premium_percent` | `CTR-08` | `dolthub:options` |
| `selected_call_days_to_expiration` | `CTR-09` | `dolthub:options` |
| `selected_option_implied_leverage` | `RET-03` | `dolthub:options` |

## Not built yet

Account values (net value, cash, positions) and the strategy gates that need them (capital structure, position limits). The release calendar in `config/settings.yaml` ends in 2027 (PCE in 2026); add the next year's dates before then. Rules still unknown: IND-02, VAL-01, TRD-02 and TRD-21 are marked difficulty 5 in their notes and are not planned (they need hundreds of requests per refresh or a PDF read by hand); NAAIM (SEN-06/21, the archive copy is months old); the mega IPO list (SEN-08) and the industry, customer and supplier earnings dates (EVT-10/11), which need a list kept by hand; implied leverage of the option you buy (RET-03), whose definition is not settled.
