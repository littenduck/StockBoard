# Strategy

A strategy is one YAML file in `strategies/`. The app loads every file in that folder at startup and refuses to start if a rule refers to an unknown indicator.

> **Status (branch `refactor/rule-catalog-by-theme`):** `config/rules.yaml` has been redesigned (new ids, `kind`, `acquisition`, `bands`, `explanation`, `review`). The files in `strategies/`, the loader and the evaluator still use the old ids and rules, so they do not load against the new catalog until they are migrated. Sections below describe the new catalog; the "Variant groups" section describes what the evaluator does today.

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
      - {rule_id: MAC-03, weight: 4}
      - {rule_id: SEN-01, weight: 5}
```

A strategy only references rules. Every rule is defined once in `config/rules.yaml` (description, explanation, importance, kind, acquisition, availability, indicator with operator and threshold or with bands, old ids, review notes). A strategy entry has `rule_id`, an optional `weight` (1 to 5, defaults to the catalog's `default_weight`) and an optional `variant_group`. Any rule can be listed. A rule the app has no data for, including every `kind: manual` rule, evaluates to unknown ❓ and is left out of the score (target behaviour; the current loader still refuses rules without an indicator).

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

Each rule lists the old ids it replaces in `legacy_id` (A01 to Z20 plus T, R, M). Old alias rules were merged away, and loose and strict tiers of one test became one rule with `bands`. Three old rules are not rules any more because they are strategy choices (B12, D15, C06); see the comment at the end of `config/rules.yaml`. The full list is on the 规则目录 page (`/rules`).

Every rule has a `kind`. `script` means the app gets the value with code; `manual` means it would come from you, your trade plan or your brokerage account. `acquisition` says how a script rule is obtained: `api_fetch` (stable API or CSV such as FRED and yfinance), `scrape` (web page, unofficial endpoint, spreadsheet), `computed` (calculated from fetched prices, series or option chains), `ai_search` (an AI reads web pages and records the result with its source), or `manual`.

`default_weight` is the importance score from 1 to 5. A rule with `bands` gives partial credit: the first matching band wins and no match means credit 0. Credits are a first draft. A weight 5 manual rule in a strategy keeps the pass result unknown, because the veto can never be checked.

Operators: `less_than`, `less_or_equal`, `greater_than`, `greater_or_equal`, `between` (value is `[low, high]`, inclusive), `is_true`.

## Rule status

`pass` ✅, `fail` ❌, `unknown` ❓ (no data: indicator missing, or a manual rule), `not_applicable` ➖.

## Two independent results per symbol

- **Pass** (`is_pass`): any weight 5 rule failing makes it `false` (veto). All weight 5 rules passing makes it `true`. Weight 5 rules unknown with none failing makes it unknown.
- **Score** (`score_percent`): `sum(weight x pass) / sum(weight x (pass + fail)) x 100`. Unknown and not applicable rules are left out. All rules count, including weight 5.

A high score can still fail the veto, and a low score can still pass.
`unknown_weight_ratio` is the weight share of unknown rules; above `max_unknown_weight_ratio` the page greys the score as "data insufficient".

## Variant groups

Rules sharing a `variant_group` are loose and strict versions of one test (for example VIX at least 13 and at least 15). Only the strictest passing rule counts as pass; the looser ones become `not_applicable`. If none pass, only the loosest counts as fail. Order rules from loose to strict inside the file. The new catalog replaces most variant groups with `bands` on a single rule; the evaluator does not read `bands` yet.

## Expiration windows

A gate with `per_expiration_window: true` is evaluated once per window in `option_expiration_window_list` (`config/settings.yaml`). The symbol's result for that gate is the window with the highest score; the other windows are shown as alternatives. Rule `CTR-02` (DTE 30 to 45 is full credit; old id `B07`) is fixed, so the standard window normally wins.

## Converting to other formats

The YAML is `indicator + operator + threshold`, which maps to other tools:

| Format | What converts | What does not |
|---|---|---|
| JSON + JSON Schema | everything (one to one) | nothing |
| QuantConnect LEAN | technical rules as conditions in `OnData` | macro and option chain rules need extra data feeds |
| TradingView Pine Script v5 | moving average, 52 week position, volatility rules | macro and option rules |
| vectorbt or backtrader | technical rules as boolean signals for backtests | macro and option rules |
