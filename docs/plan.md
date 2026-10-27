# Plan V1.3.x

Current version: `VERSION` = 1.3.0 on `main`. This plan covers the 1.3.x line: fixes, then one feature, a fundamentals strategy that is tested before it is trusted.

This file is the only plan in `docs/`. It replaces the earlier `docs/plan.md` (type system, executed) and `docs/plan_indicator_registry.md` (indicator registry, executed); both are in git history.

How an agent runs this file:

- Each to-do item has an ID (for example T1.3.5), its files, its steps, its acceptance check and what it depends on. Run items in dependency order, one commit per item.
- Before every commit run `.venv/bin/python -m pytest -q`. It must pass (190 tests at 1.3.0).
- Every text a person reads is `{en, zh}`, and both are required (`docs/language.md`). Paragraphs pair up.
- No new Python packages. `requirements.txt` has pandas and numpy; write statistics by hand.
- A rule, indicator or strategy changes only in its config file. Code never hard-codes a threshold.
- Do not commit or push unless the user says so.

## Status after the first execution run

| Item | Status | Note |
|---|---|---|
| T1.3.1 default panel | done, not committed | `config/settings.yaml` default, tests |
| T1.3.2 help text | done | matches the rules in use; the veto is the audit rule |
| T1.3.3 browser check | done | 375px: no horizontal scroll; Fundamentals is the selected panel. A 500 on the snapshot was a stored snapshot without this strategy, fixed by a refresh (see note under T1.3.3) |
| T1.3.4 remove old plans | done | |
| T1.3.5 forward returns | done | `forward_returns.py`, `tests/test_forward_returns.py` |
| T1.3.6 statistics | done | `factor_statistics.py`; Spearman is Pearson on ranks (no scipy) |
| T1.3.7 cost settings | done | `config/settings.yaml` |
| T1.3.8 column mapping | done as a gap report | the company table already names columns after indicators; see gap list below |
| T1.3.9 accounting indicators | done | I-123, I-124, I-125; R-ACC-01 to R-ACC-03 in an ACC group at the end of `rules.yaml` (ids must rise along rule order) |
| T1.3.10 live versus rebuilt | script written, not run | needs `EDGAR_CONTACT` |
| T1.3.11 restatement rule | already existed | `R-MGT-06 no_audit_red_flags` (covers 4.01, 4.02, NT 10-K/10-Q); now the veto |
| T1.3.12 industry not applicable | not done | Yahoo's `assetProfile` has `industry`, but the rule would need the value passed through the live pipeline. Banks keep "unknown" on gross margin, as before |
| T1.3.13 rewrite strategy | done | six gates: five themes plus the veto gate. Three-year PEG not built (needs a live indicator) |
| T1.3.14 baselines | done | `backtest.py`: low P/E, Piotroski, quality factor, 100 random repeats |
| T1.3.15 score per date | done | scored on month-end rebalance dates, not every day (speed) |
| T1.3.16 decision gate | written, not run | written in `fundamentals.yaml` before the run; the run needs `EDGAR_CONTACT` |
| T1.3.17 report and failure cases | script written, not run; failure cases not done | the failure list needs verified EDGAR data for each name |
| T1.3.18 docs | done for docs; strategy page status not done | no report file to read yet |
| T1.3.19 to T1.3.25 | not started | need a data decision first, as planned |

Two things found while running, both fixed or to fix:

- The live EDGAR values (interest coverage, three-year growth, ROIC, the audit flag and now the accounting indicators) come from SEC. Without `EDGAR_CONTACT` SEC answers 403 and the page shows them as unknown. The app itself needs that variable set.
- The stored snapshot (`data/latest_snapshot.json`) does not refresh outside market hours. A new strategy is missing from it until the next refresh, and the page returned 500 meanwhile. Run `python -m stock_benchmark_backend.refresh_scheduler --once` after adding a strategy.

Gap list from T1.3.8, indicators the backtest cannot rebuild from filings (unknown on past dates): PEG (`I-049`), estimate revisions (`I-034`), forward versus trailing P/E (`I-047`), insider purchases and selling (`I-036`, `I-037`), buy-rating share (`I-035`), and the audit flag (`I-040`, so the veto never fails in a backtest).

---

## Part A: fixes before the feature

### T1.3.1 Commit the default fundamentals panel

Status: done in the working tree, not committed. Files: `config/strategies/fundamentals.yaml` (new), `config/settings.yaml` (`default_strategy_id: fundamentals`), `tests/test_web_server.py` (two tests point at `sell_put_four_in_one` through `SELL_PUT_STRATEGY_ID`; one new test checks the default is first).

Acceptance: `pytest` 190 passed. The strategy list returns `fundamentals` first, with gates `gate_1_earnings_and_cash` to `gate_5_price_and_holders`.

Depends on: nothing. Commit message: `Add the fundamentals strategy as the default panel`.

### T1.3.2 Correct the fundamentals help text

File: `config/strategies/fundamentals.yaml`, `help` and `summary`.

Problems: the text says the five gates "run in order". The evaluator does not stop at a failed gate; only rules marked `veto` decide pass or fail, and gates are just groups. The English "Gate 1 is a veto" sentence should say the veto is on one rule, `R-QUA-01`. The Chinese FCF sentence ("3% 到 5% 以上") reads badly.

Steps: rewrite the two paragraphs in English and Chinese, keep the paragraph count equal, and state that gates group rules and only the veto rule removes a company.

Acceptance: `pytest` passes (the loader checks paired paragraphs). The help popover reads correctly in both languages.

Depends on: T1.3.1.

### T1.3.3 Browser check of the default panel

Run the app (`preview_start`), open `/`, check the strategy list shows 基本面 first in Chinese and English, the popover reads, and at 375px width there is no horizontal scroll. Save one screenshot for the user.

Acceptance: no console errors; first strategy is 基本面; no horizontal overflow at 375px.

Depends on: T1.3.1, T1.3.2.

### T1.3.4 Remove the executed plan file

Done with this file: `docs/plan_indicator_registry.md` is deleted (last version in git at commit `e141456`); `docs/plan.md` is rewritten. Nothing in the repo links to either file (checked with `grep`).

Depends on: nothing. Commit message: `Replace the executed plans with one plan`.

---

## 增加一个基本面 strategy

### What the task is

Build a fundamentals score that is tested before anyone trusts it:

- For every symbol and any past date T, use only information that was public at T (SEC acceptance date for filings; the date a value was known for other sources).
- Score every symbol with the same rules. Banks, insurers, REITs and utilities get rules that fit them, and a rule that does not apply is `not_applicable`, not `fail`.
- Show whether the score predicts the sector-neutral excess return over the next 3, 6 and 12 months, out of sample, after costs. If it does not, the page says so.
- Compare against simple baselines: random selection, low P/E within the universe, Piotroski F-score, a quality factor.

### What already exists (checked in the code)

| Piece | Where | State |
|---|---|---|
| Point-in-time SEC data, stamped by filing date | `stock_benchmark_backend/edgar_data.py` (`edgar_data_extract_fact_table`, `edgar_data_build_instant_series`, `edgar_data_build_trailing_twelve_month_series`) | built |
| Daily company table since 2010 (QUA, MGT, VAL, LIQ columns) | `history_series.py` `history_series_build_company_indicator_table`; `fundamental_series.py` `fundamental_series_build_table` | built |
| Auditor change (4.01), restatement (4.02), late filing (NT 10-K, NT 10-Q) in the last 365 days | `edgar_data.py` `edgar_data_find_audit_or_late_filing_problem`; indicator I-040 | built. An earlier draft said 4.02 was missing; it is not |
| Insider buys and sells from Form 3, 4, 5 (2006 on) | I-036, I-037 (`edgar:form345`) | built |
| Analyst estimate history | I-034, I-047, I-049 (`dolthub:earnings`, from 2017-10-26) | built, short window |
| Daily price history | `market_data.py` `market_data_fetch_daily_price_history_for_symbol_list` (yfinance) | built |
| Sector ETF per sector | `company_indicators.py` `SECTOR_ETF_BY_SECTOR_NAME` (11 sectors; "Financial Services" covers banks and insurers together) | built, coarse |
| Universe | `config/symbols.yaml`, 50 US-listed symbols | fixed list, not historical |
| Strategy engine | `strategy_evaluation.py` `strategy_evaluation_evaluate_strategy_for_symbol`; statuses pass, fail, unknown, not_applicable | built |
| Strategy files and rules | `config/strategies/*.yaml`, `config/rules.yaml` (R-QUA, R-MGT, R-VAL) | built |
| Snapshots kept over time | `snapshot_storage.py` | built, not yet used for validation |
| Backtest code | none. A search of `stock_benchmark_backend`, `scripts` and `tests` finds no forward-return, rank IC, decile or t-statistic code | **missing** |

Mismatch to fix: several fundamentals indicators read Yahoo's current snapshot (for example ROE I-027, gross margin I-028, net debt/EBITDA I-032, PEG I-049). Their history is rebuilt from EDGAR in the company table, but the live value still comes from Yahoo. Before a rule is used in a backtest, the live and rebuilt values must agree within a tolerance (T1.3.10).

### Order

Items T1.3.5 to T1.3.8 come first; nothing user-visible changes. Then T1.3.9 to T1.3.12, which change the rules. Then T1.3.13 to T1.3.16, which test them. T1.3.17 and T1.3.18 come last.

### To-do items

#### T1.3.5 Forward return table

New file: `stock_benchmark_backend/forward_returns.py`.

- `forward_returns_build_table(price_by_symbol: Dict[str, pandas.Series], horizon_trading_days: List[int]) -> pandas.DataFrame`: for each date and symbol, the total return over the next N trading days, from adjusted closes. The return starts the day after the score date (no lookahead).
- `forward_returns_build_sector_neutral(return_table, sector_by_symbol, sector_etf_return_table)`: subtracts the matching sector ETF's return over the same window.

Steps: use `pandas` shift with a negative index; drop the last N rows per symbol. Sector comes from yfinance `info['sector']` (a current value; the report says so, since it is a bias).

Tests: `tests/test_forward_returns.py`, with a synthetic path where the answer is known (a constant 1% daily rise gives 1.01^N − 1). A missing day must not produce a return that spans it.

Depends on: nothing.

#### T1.3.6 Statistics: rank IC, decile spread, Newey-West t

New file: `stock_benchmark_backend/factor_statistics.py`.

- `factor_statistics_rank_ic_by_date(score_table, return_table)`: Spearman correlation per date between score and forward return across symbols.
- `factor_statistics_decile_spread_by_date(score_table, return_table, bucket_count=10)`: mean return of the top bucket minus the bottom bucket, per date.
- `factor_statistics_newey_west_t(series, lags)`: t-statistic of the mean with Newey-West standard errors (Bartlett weights), written with numpy.

Tests: a score that rises with the return gives rank IC 1.0 on every date; a constant series returns `None`, not an error; with lags = 0 the Newey-West t equals the plain t.

Depends on: nothing.

#### T1.3.7 Cost model

In `config/settings.yaml`: `backtest_cost_basis_points_per_trade` (default 10) and `backtest_rebalance` (monthly). Read in `backtest.py`; do not hard-code. Document both in the settings file's comments.

Depends on: nothing.

#### T1.3.8 Map company table columns to indicator names

Problem: `history_series_build_company_indicator_table` returns named columns, but rules refer to `indicator_name` values in `config/indicators.yaml`, and some names differ.

Steps: write a mapping in `history_series.py` from indicator name to column name. Add a test that lists every QUA, MGT and VAL indicator with `backtestable: yes`, its column, and its source (EDGAR, Yahoo, DoltHub). Indicators with no column are listed as gaps for T1.3.10.

Depends on: nothing.

#### T1.3.9 Accounting quality indicators

New indicators in `config/indicators.yaml` (ids continue from the last one; check first), built from EDGAR facts:

- Accruals ratio: (net income − operating cash flow) / average total assets. Lower is better.
- SBC-adjusted free cash flow: free cash flow minus `ShareBasedCompensation`.
- Piotroski F-score: nine yes/no tests (positive ROA, positive operating cash flow, ROA rising, cash flow above net income, leverage falling, current ratio rising, no new shares, gross margin rising, asset turnover rising).

Concept names go into `CONCEPT_NAME_LIST_BY_MEASURE` in `fundamental_series.py`. Each indicator: `fetch_group: edgar`, `fetch_every: 1d`, `max_age: 400d`, `backtestable: yes`, `history_source: edgar:companyfacts`, `history_start: 2009`. Rules go in `config/rules.yaml`, appended to the `QUA` group with the next unbroken numbers (the file header rules apply).

Tests: a fake companyfacts dictionary with known numbers gives the expected accruals ratio and F-score. `tests/test_rule_catalog.py` still passes.

Depends on: T1.3.8.

#### T1.3.10 Live versus rebuilt agreement

New script `scripts/check_live_against_rebuilt.py`. For each symbol in `config/symbols.yaml`, compare the live value (current cache) with the rebuilt value on the latest date, for the indicators in T1.3.8. Flag a relative difference above 5%, or an absolute difference above 0.05 for ratios.

Acceptance: a printed table for all 50 symbols. Each disagreeing indicator is either fixed (the rebuilt value is used for both) or excluded from backtests with a note in the config. The result goes in the PR description, not in this file.

Depends on: T1.3.8.

#### T1.3.11 Restatement rule

I-040 already sees 4.02 and NT 10-K/10-Q. Add a rule in the `MGT` group, appended, that passes when I-040 is false. It may be a veto in the fundamentals strategy.

Acceptance: a submissions dictionary with a 4.02 filing 100 days ago gives the rule `fail`.

Depends on: nothing.

#### T1.3.12 Sector applicability (not_applicable)

Problem: gross margin, net debt/EBITDA and EV/EBITDA do not fit banks and insurers. Today a bank with a zero gross margin gets `unknown`, which is left out of the score, so the score depends on which rules happened to be known.

Steps:

1. In `config/rules.yaml`, add an optional field `not_applicable_industry_list` (Yahoo `industry` names). Document it in the file header.
2. In `strategy_loader.py`, read the field into the rule definition.
3. In `strategy_evaluation.py`, `strategy_evaluation_evaluate_rule_against_indicator_values` returns `STATUS_NOT_APPLICABLE` when the symbol's industry is in the list. That status already exists and is already left out of the score.
4. The industry comes from yfinance `info['industry']`. First check that the field is in the snapshot `yahoo_company.py` builds; if not, add it to `yahoo_company_build_info`.

Acceptance: a test with a bank industry gives `not_applicable` for gross margin and leaves the score as it would be without that rule.

Depends on: nothing.

#### T1.3.13 Rebuild the fundamentals strategy file

Rewrite `config/strategies/fundamentals.yaml`. The veto and weights below are proposals; the user confirms them before the rewrite is committed.

- Gate 一 earnings and cash: `R-QUA-08` (free cash flow positive), `R-QUA-10` (operating cash flow at least net income), the accruals rule from T1.3.9. No veto: a loss-making company fails the earnings rule, and a loss-based veto is added only if the backtest shows it is needed.
- Gate 二 balance sheet: `R-QUA-12`, `R-QUA-13`, `R-QUA-14`.
- Gate 三 growth: `R-QUA-02`, `R-QUA-03`, `R-QUA-04`.
- Gate 四 return and quality: `R-QUA-05`, `R-QUA-06`, `R-QUA-07` (non-financials only), Piotroski score.
- Gate 五 price and holders: one-year PEG (`R-VAL-10`, renamed "one-year PEG" in the display), a three-year PEG (P/E divided by the three-year EPS CAGR, I-025; new indicator), FCF yield 5% (`R-VAL-11`), `R-MGT-03`, `R-QUA-15`, `R-MGT-02`.
- Drop the duplicates: `R-QUA-11` (80% cash conversion) and `R-QUA-09` (FCF growing) repeat other rules; keep them only if the backtest favours them.
- Veto: the restatement rule (T1.3.11) only.

Acceptance: `pytest` passes; the strategy loads; gate ids follow the naming in the file.

Depends on: T1.3.9, T1.3.11, T1.3.12.

#### T1.3.14 Baselines

In `backtest.py`, four baseline score functions evaluated on the same dates and universe:

1. Random: seeded (seed 1), repeated 100 times for the spread.
2. Low P/E: negative trailing P/E from the company table.
3. Piotroski F-score alone (T1.3.9).
4. Quality factor: average of z-scores of ROIC, gross margin and negative accruals.

Acceptance: each baseline gives a rank IC series and a decile spread. The random baseline's mean rank IC over the 100 repeats is within 0.02 of zero, or there is a bug in the engine.

Depends on: T1.3.6, T1.3.9, T1.3.15.

#### T1.3.15 Historical score per date

New function `backtest_build_score_table(strategy_definition, company_table_by_symbol, price_by_symbol, date_index)` in `stock_benchmark_backend/backtest.py`.

For each symbol and date, build `shared_indicator_value_by_name` from the company table (values as of that date only), call `strategy_evaluation_evaluate_strategy_for_symbol` with empty option dictionaries, keep `score_percent` and `is_pass`. No calls to Yahoo for historical dates.

Tests: a fake company table with two symbols and three dates; the score on the date where a rule flips is the expected number. A filing with an acceptance date after T must not change the value on T.

Acceptance: a run over the 50 symbols from 2012 to 2025 finishes in under 5 minutes on the dev machine; record the time in the PR description.

Depends on: T1.3.5, T1.3.8.

#### T1.3.16 Decision gate, written before any run

Write the thresholds into `config/strategies/fundamentals.yaml` comments, with the date, before the backtest runs. Proposed (the user confirms):

- Rank IC mean for the 12-month sector-neutral excess return: above 0.
- Newey-West t of that mean: above 2.
- Decile spread after costs (T1.3.7): above 0.
- Out of sample: thresholds are set on 2010 to 2018; 2019 onwards is tested once, and the signs must match.
- The score beats the random baseline at the 95th percentile of its own distribution.

If any fails, the strategy stays in the list with a warning that the score is not validated, and it is not the default. The result is reported whichever way it goes.

Depends on: T1.3.13, T1.3.14.

#### T1.3.17 Backtest report and failure cases

- `scripts/backtest_fundamentals.py` writes `docs/reports/fundamentals_backtest.md` (new folder) and prints the same numbers.
- `config/failure_cases.yaml`: known accounting or price collapses for companies that filed 10-K or 10-Q (candidates include Enron, WorldCom, Sears Holdings). Each entry has ticker, dates, a short description and a source link. Before a name is added, check that its EDGAR companyfacts still exist. A company with no companyfacts is listed as "not testable", not dropped.

Acceptance: the report has the decision-gate numbers, the baselines, the cost assumption, a survivorship warning (the universe is current), and the failure case table with a column "score in the four quarters before the collapse".

Depends on: T1.3.16.

#### T1.3.18 Docs and the page

- `docs/strategy.md`: a section on validated and unvalidated strategies.
- `docs/indicator.md`: the new indicators.
- `docs/language.md`: the rule for the new text.
- Strategy page: show the validation status from the report, reusing the backtest status that the rule catalog page already shows (commit `04a2403`).

Acceptance: `pytest` passes; the status appears in both languages.

Depends on: T1.3.17.

### Needs a data decision first (not started)

These are part of this feature but cannot be built with the data in the repo. Each needs a decision written here before code.

- **T1.3.19 Historical universe.** A source for past S&P 500 membership. No free source in the repo. Until it exists, the results carry the survivorship warning. Acceptance: `config/universe_history.yaml` with dated membership, used by `backtest.py` so each date uses only members on that date.
- **T1.3.20 Sector-specific rules.** Banks (CET1 ratio, net interest margin, efficiency ratio), insurers (combined ratio, book value growth), REITs (funds from operations, which is in 8-K releases and needs parsing), utilities (allowed return on equity, from rate-case filings). Each family gets its own decision gate.
- **T1.3.21 Text-based inputs.** Critical audit matters from the auditor's report (text parsing); customer and supplier concentration (10-K notes, or XBRL `ConcentrationRiskPercentage` if coverage is good); industry raw data (units, prices, orders), which has no free source yet. Each is a rule with a tested parser, or dropped with a note.
- **T1.3.22 Beneish M-score.** Needs receivables, SG&A, depreciation, PP&E, long-term debt and current liabilities from EDGAR; add concepts and an indicator. Test on a known manipulator from the failure cases.
- **T1.3.23 Beta and reverse DCF.** Beta from 252 days of daily returns against SPY (computed, no external source). Reverse DCF: the growth rate implied by the price, using free cash flow, beta-based cost of capital and the 10-year yield (`fred:DGS10`, already built). Shown on the page, not scored, until the backtest validates it.
- **T1.3.24 Live forward validation.** Use `snapshot_storage.py` to store a dated score for every symbol every month from the day this feature ships. After 12 months, compute the T1.3.6 statistics on those real out-of-sample scores. Script: `scripts/forward_validation.py`, run monthly.
- **T1.3.25 Analyst estimates before 2017.** The estimate history starts in 2017 (`dolthub:earnings`). Find another source; if none is free, rules that use estimates are marked "validated from 2017 only" in the report.

---

## Gap list (everything still missing)

| Gap | Blocks | Item |
|---|---|---|
| No backtest engine (forward returns, IC, t-statistic, costs) | any validation | T1.3.5 to T1.3.7, T1.3.16 |
| Universe is current, not historical | honest backtest | T1.3.19 (warning until then) |
| Yahoo live values not checked against EDGAR rebuild | rule accuracy | T1.3.8, T1.3.10 |
| No accounting quality indicators | Piotroski, quality factor | T1.3.9 |
| No way to mark a rule not applicable to an industry | banks, insurers, REITs | T1.3.12 |
| Sector is coarse (11 ETFs; financials lumped) | sector-neutral returns | T1.3.12 (industry field), T1.3.20 |
| Analyst estimates only from 2017 | analyst rule history | T1.3.25 |
| Critical audit matters, customer concentration, industry data | rules that need them | T1.3.21 |
| Beneish M-score concepts not mapped | manipulation check | T1.3.22 |
| No beta, no reverse DCF | valuation beyond multiples | T1.3.23 |
| No failure case set | sanity check | T1.3.17 |
| No out-of-sample period that was not used to fit | proof | T1.3.16 (split history), T1.3.24 (real time) |

---

## What counts as proof (and what does not)

A reading of the score alone proves nothing. Accepted evidence, strongest first:

1. Out-of-sample prediction on data that was available at the time (point in time), with costs, against baselines (T1.3.14, T1.3.16).
2. Live forward results over 12 months or more (T1.3.24).
3. Consistency across periods, sectors and market caps (T1.3.17 report).
4. Failure cases flagged before the collapse (T1.3.17).

Not proof: that the rules look sensible, that one chart rises, or that the score is high for a stock someone already likes.
