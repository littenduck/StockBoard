# Strategy

A strategy is one YAML file in `strategies/`. The app loads every file in that folder at startup and refuses to start if a rule refers to an unknown indicator.

## File format

```yaml
strategy_id: sell_put_four_in_one        # unique, snake_case
display_name: Sell Put 四合一
source: "where this strategy came from"
thresholds: {max_unknown_weight_ratio: 0.20}
summary: "one sentence shown at the top of the help popover"
help: |
  Longer explanation. Blank lines separate paragraphs.
  Shown when the user clicks the question mark next to the strategy name.
gates:                                    # evaluated in order, top to bottom
  - gate_id: gate_0_macro
    display_name: "GATE 0 宏观/情绪开关"
    rules:
      - {rule_id: A07, weight: 2, variant_group: ten_year_level}
      - {rule_id: A02, weight: 4, variant_group: ten_year_level}
```

A strategy only references rules. Every rule is defined once in `config/rules.yaml` (description, indicator, operator, threshold, default weight, availability). A strategy entry has `rule_id`, an optional `weight` (1 to 5, defaults to the catalog's `default_weight`) and an optional `variant_group`. Only rules with `availability: automatic` can be used; the loader refuses copies (`alias_of`) and rules without an indicator.

## Rule ids

Id = group letter + two digits. A to F and Z come from the Notion scorecard: A #1 five-layer framework, B #2 CSP parameters, C #3 SPMO rotation, D #4 directional buying, E #5 Wheel, F #6 wheel stock selection, Z common layer. T (trend), R (pullback) and M (momentum) were added with the stock strategies. The same id means the same rule in every strategy. A strategy uses only the rules it needs and that can be computed, so ids inside one gate are not consecutive. The full list, with the reason each unused rule is not automated, is on the 规则目录 page (`/rules`).

Operators: `less_than`, `less_or_equal`, `greater_than`, `greater_or_equal`, `between` (value is `[low, high]`, inclusive), `is_true`.

## Rule status

`pass` ✅, `fail` ❌, `unknown` ❓ (indicator missing), `not_applicable` ➖.

## Two independent results per symbol

- **Pass** (`is_pass`): any weight 5 rule failing makes it `false` (veto). All weight 5 rules passing makes it `true`. Weight 5 rules unknown with none failing makes it unknown.
- **Score** (`score_percent`): `sum(weight x pass) / sum(weight x (pass + fail)) x 100`. Unknown and not applicable rules are left out. All rules count, including weight 5.

A high score can still fail the veto, and a low score can still pass.
`unknown_weight_ratio` is the weight share of unknown rules; above `max_unknown_weight_ratio` the page greys the score as "data insufficient".

## Variant groups

Rules sharing a `variant_group` are loose and strict versions of one test (for example VIX at least 13 and at least 15). Only the strictest passing rule counts as pass; the looser ones become `not_applicable`. If none pass, only the loosest counts as fail. Order rules from loose to strict inside the file.

## Expiration windows

A gate with `per_expiration_window: true` is evaluated once per window in `option_expiration_window_list` (`config/settings.yaml`). The symbol's result for that gate is the window with the highest score; the other windows are shown as alternatives. Rule `B07` (DTE 30 to 45) is fixed, so the standard window normally wins.

## Converting to other formats

The YAML is `indicator + operator + threshold`, which maps to other tools:

| Format | What converts | What does not |
|---|---|---|
| JSON + JSON Schema | everything (one to one) | nothing |
| QuantConnect LEAN | technical rules as conditions in `OnData` | macro and option chain rules need extra data feeds |
| TradingView Pine Script v5 | moving average, 52 week position, volatility rules | macro and option rules |
| vectorbt or backtrader | technical rules as boolean signals for backtests | macro and option rules |
