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

Targets, measured again with the same script after the work: next refresh right after at most 100 requests (from 218), cold start at most 250 (from 371), Yahoo `/v8/finance/chart` at most 2 outside the daily history load, `quoteSummary` at most 14 per hour (one per symbol), and zero requests for indicators that are not due.

## 1. Config layout and the strategy move

- `git mv strategies config/strategies` (history kept).
- Paths to change: `refresh_scheduler.py`, `web_server.py`, `tests/test_rule_catalog.py` (two places), `scripts/count_requests.py` (already looks in both), `README.md`, `docs/strategy.md`, `docs/language.md`, the header of `config/rules.yaml`, `.claude/skills/stockboard-strategy/SKILL.md`. A final `git grep "strategies/"` must show only `config/strategies/`.
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

## Order of commits

1. Move strategies to `config/strategies/` and fix paths.
2. Add `indicators.yaml`, the loader and validation; slim `rules.yaml`; API and rule catalog page unchanged except two new fields.
3. Move the sidebar indicator fields from `settings.yaml`.
4. `fetch_cache`, `observed_at`, stale gate, tick loop and after-hours schedule driven by the YAML fields.
5. Yahoo: Ticker and expiration reuse, then the batched quote and daily history, then the single `quoteSummary`.
6. Tidy `requirements.txt`, docs, measurement table, PR.

## Out of scope

Cboe option quotes, persisting the fetch cache across restarts, the remaining todo rules, deployment.

## Open risks

- `v7/finance/quote` and `quoteSummary` multi-module are undocumented Yahoo endpoints (the same ones yfinance calls); a change on their side breaks them, as it would break yfinance. The fallback keeps the old per-symbol path.
- Rules that share an indicator may disagree today on method, source or status; fixing that by hand may change a displayed value on the rule catalog page.
- Splitting "market hours only" from "any time" changes when a snapshot is rebuilt; after-hours snapshots show the last intraday values with the daily ones refreshed.
