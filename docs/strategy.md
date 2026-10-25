# Strategy

A strategy is one YAML file in `strategies/`. The app loads every file in that folder at startup and refuses to start if a rule refers to an unknown indicator.

> **Status (branch `refactor/rule-catalog-by-theme`):** the catalog, the four strategy files, the loader, the evaluator, the API (`schema_version` 4) and the two pages all use the new design: theme-based ids, one rule per tier line, weights and veto flags in the strategy files.

## File format

```yaml
strategy_id: sell_put_four_in_one        # unique, snake_case
display_name: {en: "Sell Put 4-in-1", zh: "Sell Put 四合一"}
source: "where this strategy came from"
thresholds: {max_unknown_weight_ratio: 0.20}
summary: {en: "one sentence shown at the top of the help popover", zh: "..."}
help:
  en: |
    Longer explanation. Blank lines separate paragraphs.
    Shown when the user clicks the question mark next to the strategy name.
  zh: |
    中文说明，段落数必须和英文一样。
gates:                                    # evaluated in order, top to bottom
  - gate_id: gate_0_macro
    display_name: {en: "GATE 0 Macro and sentiment", zh: "GATE 0 宏观/情绪开关"}
    rules:
      - {rule_id: SEN-10, weight: 1}              # VIX at least 12
      - {rule_id: SEN-01, weight: 2}              # VIX at least 15
      - {rule_id: EVT-01, weight: 5, veto: true}  # no earnings before expiration
```

A strategy only references rules. Every rule is defined once in `config/rules.yaml` (name, description, method, quantifiable, backtestable, history_source, history_start, status, indicator, operator and value, band_of, old ids). `name` is a short title; `description` explains the rule in plain words, spells out abbreviations, gives typical values and update frequency, and names the data source. A strategy entry has `rule_id`, a required `weight` (integer 1 to 5: how much this strategy cares about the rule) and an optional `veto: true`. The catalog has no weight, so the same rule can weigh 4 in one strategy and 1 in another. Any rule can be listed. A rule the app has no data for, including every `method: manual` rule, evaluates to unknown ❓ and is left out of the score. The loader refuses a `veto` on a manual rule, a missing or out-of-range `weight`, and the retired `variant_group`.

## Languages

Every text a person reads (`display_name`, `source`, `summary`, `help`, gate `display_name`, and rule text in `config/rules.yaml`) is `{en, zh}`. Both are required, English must not contain Chinese characters, and help paragraphs must pair up. The app refuses to start otherwise; `pytest` checks it too. Glossary: `docs/language.md`.

## Rule ids

Id = category code + two digits, for example `TRD-03`. The same id means the same rule in every strategy, and ids are never reused. Categories run from macro down to detail, grouped into six aspects:

| Aspect | Categories |
|---|---|
| Fundamentals | `MAC` macro, `IND` industry, `QUA` company quality, `MGT` management and governance, `VAL` valuation |
| Sentiment and flows | `SEN` sentiment and positioning |
| Technicals | `TRD` trend and momentum |
| Events | `EVT` events |
| Options | `LIQ` liquidity, `VOL` volatility, `CTR` contract selection, `RET` return and payoff |
| Risk | `POS` position, account and portfolio, `THS` thesis and discipline, `EXT` management and exit |

Each rule lists the old ids it replaces in `legacy_id` (A01 to Z20 plus T, R, M). Old alias rules were merged away, and every tiered measure was split into one rule per line (see Tiers). Three old rules are not rules any more because they are strategy choices (B12, D15, C06); see the comment at the end of `config/rules.yaml`. Rules removed after they were first added (VAL-02, LIQ-02, EVT-09) stay in `retired_rule_list` with the reason, and a retired id is never reused. The full list is on the 规则目录 page (`/rules`).

`method` says how a rule's value is obtained: `api_fetch` (stable API or CSV such as FRED and yfinance), `scrape` (web page, unofficial endpoint, spreadsheet), `computed` (calculated from fetched prices, series or option chains), `ai_search` (an AI reads web pages and records the result with its source), or `manual` (no data in the app: your own input, your trade plan or your brokerage account; a manual rule can still sit in a strategy, where it always shows unknown).

`backtestable` is `yes` only when free historical data can rebuild what the rule would have said on a past date, using only what was known then. A `yes` rule names its `history_source` (for example `fred:DGS10` or `dolthub:options`) and its `history_start` (a year, a month or a day; for per-symbol price rules it is the oldest symbol on the watchlist). Rules that need your own answer or your account are always `no`, and so are the two option volume rules LIQ-05 and LIQ-09 until the app has recorded its own history. How far back each source goes is in the rule descriptions; the indicators that are not built yet are listed in `docs/indicator.md`.

## Tiers: one rule per line

A measure with several lines (VIX, Delta, DTE, RSI ...) is one rule per line, for example `SEN-10` VIX at least 12, `SEN-01` VIX at least 15, `SEN-11` VIX below 20, `SEN-12` VIX below 25, `SEN-13` VIX below 30, `SEN-14` VIX at least 30, `SEN-15` VIX at least 40. A rule only says pass, fail or unknown. The main rule (`SEN-01`) carries the full description; the other lines name it in `band_of`, which is for display only. A strategy lists the lines it wants and gives each its own weight.

Two ways to use the lines:

- **Nested lines give partial credit.** The score is passed weight divided by passed plus failed weight, so listing `MAC-13` (10Y below 5.0%, weight 2) and `MAC-03` (10Y below 4.5%, weight 2) gives 100% at 4.3%, 50% at 4.7% and 0% at 5.2%. Each line the value passes adds its weight.
- **Lines that point opposite ways serve different strategies.** A seller wants fear and uses the floors (`SEN-10`, `SEN-01`); a trend or momentum strategy avoids panic and uses a cap (`SEN-12`); a contrarian buyer uses `SEN-14`. Because the weight lives in the strategy, each one picks its own.

Do not list lines that exclude each other, such as `SEN-11` (below 20) together with `SEN-14` (at least 30): the one that cannot pass always counts as a fail.

Operators: `less_than`, `less_or_equal`, `greater_than`, `greater_or_equal`, `between` (value is `[low, high]`, inclusive), `is_true`.

## Rule status

`pass` ✅, `fail` ❌, `unknown` ❓ (no data: indicator missing, or a manual rule), `not_applicable` ➖.

## Two independent results per symbol

- **Pass** (`is_pass`): any rule marked `veto: true` that fails makes it `false`. All veto rules passing makes it `true`. A veto rule that is unknown with none failing makes it unknown. A manual rule cannot be a veto, because it is always unknown.
- **Score** (`score_percent`): `sum(weight x pass) / sum(weight x (pass + fail)) x 100`. Unknown and not applicable rules are left out. All rules count, including veto rules.

A high score can still fail the veto, and a low score can still pass.
`unknown_weight_ratio` is the weight share of unknown rules (manual rules are not counted, otherwise one manual rule would grey every score); above `max_unknown_weight_ratio` the page greys the score as "data insufficient".

## Variant groups

Retired. The old evaluator let rules sharing a `variant_group` act as loose and strict versions of one test (only the strictest passing rule counted). In the new catalog every tier is its own rule and nested lines give partial credit, so strategy entries have no `variant_group` and the loader refuses it.

## Expiration windows

A gate with `per_expiration_window: true` is evaluated once per window in `option_expiration_window_list` (`config/settings.yaml`). The symbol's result for that gate is the window with the highest score; the other windows are shown as alternatives. Rule `CTR-02` (DTE 30 to 45; old id `B07`) is fixed, so the standard window normally wins.

## Converting to other formats

The YAML is `indicator + operator + threshold`, which maps to other tools:

| Format | What converts | What does not |
|---|---|---|
| JSON + JSON Schema | everything (one to one) | nothing |
| QuantConnect LEAN | technical rules as conditions in `OnData` | macro and option chain rules need extra data feeds |
| TradingView Pine Script v5 | moving average, 52 week position, volatility rules | macro and option rules |
| vectorbt or backtrader | technical rules as boolean signals for backtests | macro and option rules |
