# Indicator

Three levels, three kinds of file:

| Level | What it is | Where it is written |
|---|---|---|
| **Indicator** | one measured quantity (a number or a yes/no), with where it comes from and how often it is fetched | `config/indicators.yaml` |
| **Rule** | a judgment on one indicator: an operator and a line (`R-MAC-03`: the 10-year yield is below 4.5). Several rules can share an indicator | `config/rules.yaml` |
| **Strategy** | which rules, with what weight and veto | `config/strategies/*.yaml` |

A rule refers to an indicator by its short id (`indicator: I-003`), and the loader looks up its long name. A value that cannot be fetched, or is older than the indicator's `max_age`, is `unknown` (shown as ❓, left out of the score).

### Ids and names

An indicator has a short `indicator_id` (`I-001` to `I-122`) and a long `indicator_name` (`treasury_ten_year_yield`). The id is what people and the rule file write; the name is what the code keys on (the history builders, `PRODUCED_INDICATOR_NAME_SET`, the fetch functions). Ids follow the order of the rule catalog: the first indicator is the one the first rule uses, and so on, with the sidebar-only and internal ones at the end. An id is never reused.

A rule has `rule_id` (`R-MAC-03`) and a short `rule_name` (`ten_year_below_4_5pct`) written the same way as an indicator name.

### The indicator file

The meaning of every indicator, how it is read, where the live value and the history come from and what values are typical is the bilingual `description` of that indicator in `config/indicators.yaml`; the rule catalog page and the hover card show it under each rule, together with every line of the measure. This file does not repeat it. A new indicator needs a description in both languages (a test checks).

Each indicator has `scope` (market, symbol, or window for one option expiration window), `method`, `status`, the backtest facts (`backtestable`, `history_source`, `history_start`) and the schedule:

- `fetch_group`: the family of requests it comes from. Indicators of one group are fetched together, so a group is asked as often as its most frequent indicator needs (the shortest `fetch_every`).
- `fetch_every`: how often the source is asked again (`10m`, `1h`, `1d`). A value that is not due is not fetched again.
- `max_age`: how old the newest observation may be. Past it the value reads unknown. Monthly series are dated the first of the month and published a month or two later, so their limit is long; prices get 4 days so a weekend does not blank them.
- The group list at the top sets `market_hours_only` (prices and option quotes are asked only while the market is open) and `fetch_at` (New York times at which the group is also asked once: prices at 16:20 after the close, slow data at 06:00 before the open).

Rules take `method`, `backtestable`, `history_*` and `status` from their indicator, so these facts are written once. A manual rule has no indicator and keeps them itself. The code lists the indicators it makes in `PRODUCED_INDICATOR_NAME_SET`; a test fails if that list and the built indicators of the YAML differ.

How a refresh works: the background loop wakes every minute; a refresh is due when the market is open and the snapshot is older than `refresh_interval_minutes`, or when any fetched answer is due again (also after the close, at the `fetch_at` times). A refresh rebuilds the snapshot from the cache and asks only the groups that are due. A failed fetch keeps the old value and waits 15 minutes before trying again. `scripts/count_requests.py --ticks 3` shows the requests per refresh.


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

## Not built yet

Account values (net value, cash, positions) and the strategy gates that need them (capital structure, position limits). The release calendar in `config/settings.yaml` ends in 2027 (PCE in 2026); add the next year's dates before then. Rules still unknown: R-IND-02, R-VAL-01, R-TRD-02 and R-TRD-03 are marked difficulty 5 in their notes and are not planned (they need hundreds of requests per refresh or a PDF read by hand); NAAIM (R-SEN-16/21, the archive copy is months old); the mega IPO list (R-SEN-22) and the industry, customer and supplier earnings dates (R-EVT-03/11), which need a list kept by hand; implied leverage of the option you buy (R-RET-07), whose definition is not settled.
