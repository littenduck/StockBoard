# Plan: indicator registry, config layout, fetch schedule and fewer Yahoo requests

Branch `refactor/indicator-registry`, one PR, small commits. Not deployed by this plan.

## Requirements (what was asked)

1. Strategies are YAML files, not Python (`strategies/*.yaml`, loaded by `strategy_loader.py`). Move them under `config/strategies/` and fix every path that uses them.
2. The config folder then holds three catalogs plus settings: `config/indicators.yaml` (new), `config/rules.yaml`, `config/strategies/*.yaml`, `config/settings.yaml`.
3. An **indicator** is the measured quantity (one number or flag, with a source and a way of getting it). A **rule** is a judgment on one indicator (operator and line). A **strategy** weights rules. Facts about an indicator live once, in `indicators.yaml`, not repeated on every rule or in a code constant.
4. Every indicator carries two new fields that today are constants in code: `fetch_every` (how often to ask the source) and `max_age` (how old its newest observation may be before it reads unknown). A value that is not due is not fetched again.
5. After the market closes, slow indicators are still fetched when due (for example once a night), so data published overnight is fresh before the next open.
6. The five sidebar market indicators (display name, "higher is riskier") move from `settings.yaml` into `indicators.yaml`; `settings.yaml` keeps only which ids to show.
7. Cut outgoing Yahoo requests: reuse the `Ticker` and the expiration list, fetch price history once a day plus one batched quote for the latest price, and take all company data in one `quoteSummary` request per symbol. Cboe options are out of scope.
8. Tidy `requirements.txt`.
9. The plan is checked independently (a reviewer that did not write it) before the work starts; the claim "fewer requests, lower risk of being blocked" is measured, not assumed.

## Measured baseline (current `main`, `scripts/count_requests.py --twice`)

| | Cold start | Next refresh right after |
|---|---|---|
| Total requests | 371 | 218 |
| Yahoo option chains and expirations (`/v7/finance/options`) | 168 | 168 |
| Yahoo `quoteSummary` | 77 | 14 (the earnings date, asked again every refresh) |
| Yahoo price (`/v8/finance/chart`, one per symbol) | 34 | 34 |
| Yahoo `quote` and `fundamentals-timeseries` | 28 | 0 |
| FRED, DoltHub, FINRA, Internet Archive, others | 66 | 2 |

Twelve option requests per symbol: a fresh `Ticker` re-requests the expiration list, each `option_chain` asks for it again, and the covered call asks a second time.

Targets (revised after the review, see the end): one intraday tick during market hours with options and the quote due, about 75 to 85 requests (from 218), 99 at the top of the hour when the 14 `quoteSummary` requests are due too; cold start about 200 (from 371); per trading day about 3,500 (from about 8,500 at 39 ticks of 218); zero requests for indicators that are not due. Measured with the clock faked to market hours, because a refresh straight after another with a cache makes almost no requests and says nothing.

## 1. Config layout and the strategy move

- `git mv strategies config/strategies` (history kept).
- Paths to change: `refresh_scheduler.py`, `web_server.py`, `tests/test_rule_catalog.py` (two places), `scripts/count_requests.py` (already looks in both), `README.md`, `docs/strategy.md`, `docs/language.md`, the header of `config/rules.yaml`, `.claude/skills/stock-benchmark-strategy/SKILL.md`. A final `git grep "strategies/"` must show only `config/strategies/`.
- One constant `config_directory` (`PROJECT_DIRECTORY/config`) used by all loaders.

## 2. `config/indicators.yaml`

One entry per indicator id (all ids that rules use plus the ones the code makes without a rule, such as `last_price`):

```yaml
indicator_list:
  - indicator_id: treasury_ten_year_yield
    scope: market            # market | symbol | window (per option expiration window)
    method: api_fetch        # api_fetch | scrape | computed | ai_search
    quantifiable: "yes"
    backtestable: "yes"
    history_source: "fred:DGS10"
    history_start: "1962-01-02"
    status: built            # built | todo
    fetch_group: fred        # indicators that come from one request share a group
    fetch_every: 1d          # 10m | 30m | 1h | 6h | 1d | 7d ...
    max_age: 10d             # age of the newest observation, past this it reads unknown
    market_hours_only: false # true for prices and option quotes
    display_name: {en: "10Y", zh: "10Y"}   # only the sidebar ones
    is_higher_value_risky: true            # only the sidebar ones
```

- Values are chosen from each source's real update cadence (daily FRED series 1d and 10d, weekly AAII 1d and 16d, monthly CPI 1d and 100d, prices 10m and 1d, EDGAR 1d, DoltHub 6h, company data 1h).
- A **fetch group** is one request or one family of requests (`yahoo_price`, `yahoo_options`, `yahoo_company`, `fred`, `cboe_putcall`, `cnn`, `aaii`, `edgar`, `dolthub_iv`, `finra`, `reference_files`, `calendar`). The interval of a group is the shortest `fetch_every` among its indicators; each indicator keeps its own `max_age`.
- Fields that leave `rules.yaml` for rules that have an indicator: `method`, `quantifiable`, `backtestable`, `history_source`, `history_start`, `status`. Before moving, a check lists every indicator whose rules disagree on these values; any disagreement is resolved by hand and listed in the commit message.
- `KNOWN_INDICATOR_ID_SET` in code and the per-indicator constants in `live_indicators.py` (`MAX_AGE_DAYS_BY_SERIES_INDICATOR_ID`, cache seconds) are deleted; the registry is the only list.

## 3. `config/rules.yaml`

A rule keeps `rule_id`, `name`, `description`, `indicator`, `operator`, `value`, `band_of`, `legacy_id`, `note`. The 34 manual rules have no indicator and keep their own `method: manual`, `status: no_data`, `quantifiable`, `backtestable` and history fields (there is nothing to share). The loader gives each rule the fields of its indicator, so `/api/v1/rules`, the rule catalog page and the hover card keep working unchanged; the API also gains `fetch_every` and `max_age`, shown as two more fields on the rule catalog page.

Validation (at startup and in tests): a rule's indicator exists; `status: built` rules point at a `built` indicator; every sidebar id has `display_name`; `fetch_every` and `max_age` parse; `max_age >= fetch_every`; a retired rule id is not reused (as today).

## 4. `settings.yaml`

`market_indicator_list` becomes a list of ids only. `refresh_interval_minutes` stays as the tick for intraday groups.

## 5. Fetch schedule

- New `fetch_cache.py`: `fetch_cache_get_or_fetch(group, every_seconds, fetch_function)` keeps the last result and the time it was fetched in memory (thread safe, one in-flight fetch per group so two indicators asking at once make one request). A failed fetch keeps the old result, retried after a short back-off (15 minutes), and the old value ages out through `max_age`.
- Every `IndicatorValue` gets `observed_at`. After a refresh builds all values, `indicator_registry_drop_stale` removes any value older than its indicator's `max_age`, so one rule decides unknown the same way for FRED, Yahoo and everything else.
- The background loop ticks every 60 seconds. A refresh is due when an intraday group is due and the market is open, or when any group that is not `market_hours_only` is due (also after the close). A due refresh rebuilds the snapshot from cached values and fetches only the groups that are due.
- A first start after a deploy is cold (cache is in memory); the deploy note says the first refresh makes about 250 requests.

## 6. Fewer Yahoo requests

1. **One `Ticker` and one expiration list per symbol per refresh**; one `option_chain` call serves puts and calls for that expiry; the covered call reuses the chain of a window that has the same expiry. Option groups run only while the market is open.
2. **Price history once a day, latest price from one batched request.** `v7/finance/quote?symbols=A,B,C` returns price, day high and low, volume and time for many symbols in one request (tested: 8 symbols, one request). The daily history (34 symbols, 1d) is cached; each intraday refresh replaces today's bar with the quote, which is what the current download gives. If the batched request fails, fall back to the per-symbol download.
3. **One `quoteSummary` request per symbol with all modules** (`financialData, defaultKeyStatistics, summaryDetail, price, assetProfile, quoteType, earningsTrend, recommendationTrend, calendarEvents, insiderTransactions`; tested for MSFT: one request returned everything the code reads). It replaces `info` (3 requests), `eps_trend`, `recommendations_summary`, `calendar` and `insider_transactions`, and also serves the next earnings date (the 14 requests every refresh today). Parsers read the raw JSON shape; a test compares them against the old `yfinance` objects on recorded data.
4. Funds (`quoteType == ETF`) skip the modules they do not have, which removes the 404 noise.

## 7. How the claims are checked

- `scripts/count_requests.py` (already in the branch) counts outgoing requests by host and Yahoo endpoint for a cold refresh and a second refresh; the table above is the "before", the PR description carries the "after".
- A unit test with a fake clock: an indicator with `fetch_every: 1h` is fetched once in 59 minutes of 10-minute ticks and again at 61; a closed market fetches only the groups that are not `market_hours_only`; a failed fetch is retried after the back-off; a value older than `max_age` is dropped.
- Parser tests for the raw `quoteSummary` and `quote` shapes, including a symbol with missing modules.
- All existing 124 tests still pass; the dashboard and the rule catalog page are opened in the browser after the change and compared with the snapshot before it (same rules built, same pass and fail on every symbol, within market moves).
- Risk of being blocked is judged from the request count, not measured directly: fewer requests, fewer distinct endpoints per symbol, and the same cadence per symbol as before is the argument, stated as such in the PR.

## 8. Docs

`docs/indicator.md` explains the three levels and the new file; `docs/strategy.md`, `docs/api.md` (new fields), `docs/deployment.md` (new paths, `git pull` then restart; nothing else changes on the server), `README.md`, the strategy skill.

## Order of commits (revised)

1. Yahoo: one `Ticker` and one expiration list per symbol (independent, low risk, about 100 fewer requests, measured alone).
2. Move strategies to `config/strategies/` and fix paths.
3. Add `indicators.yaml`, the loader and validation; slim `rules.yaml`; move the sidebar fields from `settings.yaml`; API and rule catalog page get the new fields.
4. `fetch_cache`, `observed_at`, stale gate, tick loop and after-hours schedule driven by the YAML fields.
5. Yahoo: batched quote and daily history, then the single `quoteSummary`.
6. Tidy `requirements.txt` (pin `yfinance`), docs, measurement table, PR.

## Revisions after the independent review (these override the text above)

The reviewer (a separate agent that read the code and ran read-only experiments) confirmed the baseline explanation (12 option requests per symbol: a fresh `Ticker` re-requests the expiration list, 1 list + 2 per window x 4 + 3 for the covered call) and the 77 and 14 `quoteSummary` counts, and found only two rules that disagree on a field (both on `method`: `naaim_exposure_index`, `market_capitalization_billion_usd`). It asked for these changes, all accepted:

1. **Targets and measurement** as in the paragraph above; `count_requests.py` gets a faked clock (`--market-open`, ticks 10 minutes apart) and prints per tick and per day.
2. **Group split**: `yahoo_history` (1d) and `yahoo_quote` (10m) are separate groups. Validation: every indicator of a group agrees on `scope` and `market_hours_only`.
3. **Cache key** is (group, symbol or none) with one lock per key and no lock held during a network call; the old module caches (`series_cache`, `company_cache`, `edgar_cache`, `fred_series_cache`, cache seconds in `live_indicators.py`) are replaced by `fetch_cache`, not kept next to it.
4. **`max_age` and `observed_at`**: price indicators get `max_age: 4d` (weekends and holidays must not read unknown). `observed_at` is the bar date for values computed from prices, the date of the newest observation for series, the fetch time for company data, today for calendar values.
5. **Anchored times**: a group may set `fetch_at` (New York time, for example `["16:20"]`) besides `fetch_every`; it is due when the last fetch is older than `fetch_every` or older than the latest `fetch_at`. Prices and history load once after the close, slow groups before the open.
6. **Batched quote guards**: use only `regularMarket*` fields; choose replace or append by the exchange date of `regularMarketTime`; if `regularMarketPreviousClose` differs from the cached last close by more than 0.1% (a split or an ex-dividend day with adjusted history), reload the history.
7. **`quoteSummary` shape**: flatten the modules into the `info` dictionary the code expects, drop empty `{}`, unwrap `{raw}` values, convert epoch dates in New York time, and fill quote-only fields (`sharesOutstanding` and `dividendYield` of funds) from the batched quote; call the endpoints through `YfData` (cookie and crumb); pin `yfinance` in `requirements.txt`.
8. **Evidence about blocking**: the request count is a proxy. `YfData` retries a failed request once with a fresh cookie and crumb, so errors cost double and the script undercounts them; bursts (`yf.download` with threads) and the datacenter IP matter at least as much. Add counters for rate-limit errors, 4xx and crumb refreshes, logged hourly, and a global cap of 2 concurrent Yahoo requests; the PR says the effect on blocking is compared over a week of the counters, not claimed.
9. **Producer map**: keep a map in code (fetch group, fetch function, the ids it makes) and a test that every `built` indicator in the YAML has a producer, so a typo is caught.
10. **Missed places**: `history_series.py` reads `history_start` from `rules.yaml`; `static/rules.html` (`RECORD_FIELD_LIST`) and `static/language.js` get the two fields with en and zh labels; `tests/test_live_indicators.py` and `tests/test_history_series.py` use the old constants; `docs/indicator.md` is updated, not created; `docs/deployment.md` says to run `pip install -r requirements.txt` after pulling; `SNAPSHOT_SCHEMA_VERSION` goes up if `observed_at` or `prices_as_of` enter the snapshot.
11. **After hours**: the snapshot gets `prices_as_of` so the status bar shows when prices were taken, not when the snapshot was rebuilt; option values from the last session are kept in the cache overnight, and a restart at night leaves option rules unknown until the open.
12. **More cuts**: the expiration list is cached for a day; the 7-year chart request per symbol (EDGAR price median) is counted and cached for a day.

Kept as asked: one branch and one PR (the reviewer suggested two); the commit order above keeps each step measurable.

## Out of scope

Cboe option quotes, persisting the fetch cache across restarts, the remaining todo rules, deployment.

## Open risks

- `v7/finance/quote` and `quoteSummary` multi-module are undocumented Yahoo endpoints (the same ones yfinance calls); a change on their side breaks them, as it would break yfinance. The fallback keeps the old per-symbol path.
- Rules that share an indicator may disagree today on method, source or status; fixing that by hand may change a displayed value on the rule catalog page.
- Splitting "market hours only" from "any time" changes when a snapshot is rebuilt; after-hours snapshots show the last intraday values with the daily ones refreshed.

## Result (measured with `scripts/count_requests.py`, market hours simulated, ten minutes between refreshes)

| | Before (main) | After |
|---|---|---|
| Cold start (first refresh after a restart) | 371 requests | 177 |
| A refresh ten minutes later | 218 | 71 |
| Option chains and expirations | 168 per refresh | 70 |
| Prices (`/v8/finance/chart`) | 34 per refresh | 33 once a day, plus 1 batched quote per refresh |
| Company data (`quoteSummary`, `quote`, `fundamentals-timeseries`) | 91 cold, 14 per refresh | 14 cold, 0 per refresh (1 request per symbol per hour) |
| FRED, DoltHub, FINRA, Cboe, CNN, archive, reference files | all asked again on a 30 minute cache | each asked when its own group is due (one request per source per day for most) |
| Per trading day (39 refreshes) | about 8,500 | about 2,800, 67% fewer |

What is not claimed: that this lowers the chance of being blocked by a measured amount. It lowers the request rate to about a third and the simultaneous requests to two, and it logs counts of rate-limit and error answers every hour (`yahoo_gate.py`); compare a week of those lines before and after deploying. The option chains (70 of the 71) are now almost all of the traffic; Cboe's delayed quotes (one file per symbol) are the next step if that is still too much.

Done as planned, with these differences from the text above: the commit order starts with the option session; a fetch group with no indicator (`yahoo_history`) takes its own `fetch_every`; the code keeps `PRODUCED_INDICATOR_ID_SET` as a test guard instead of deleting it; `yfinance` is pinned as a range (`>=1.2,<2`) because the server has 1.7.0 and this machine 1.2.0, and the new Yahoo code was smoke-tested on both; the expiration list is not cached for a day (yfinance needs it on its own `Ticker` before it will fetch a chain).
