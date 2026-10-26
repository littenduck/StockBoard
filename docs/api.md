# API

JSON over HTTP, read only, served by `stockboard_backend/web_server.py`. Any client can use it: the web page, a future SwiftUI app, scripts.

## Conventions

- Field names are `snake_case`. Unknown values are `null`. Enumerations are lower-case strings.
- Times are ISO 8601 in exchange time (America/New_York) with offset, for example `2026-10-23T15:52:19-04:00`.
- `schema_version` (currently `3`): within one version fields may only be added. Renaming, removing or changing the type of a field bumps the version (3 made text fields objects).
- Text a person reads is an object `{"en": "...", "zh": "..."}`: strategy `display_name`, `summary`, `help_text`, `source`; gate `display_name`; rule `name`, `description` and `note`; group `display_name` and `description`; indicator `display_name`. Clients pick the language; `default_language` tells them which to start with.
- Errors: HTTP 404 with `{"detail": "..."}` for an unknown strategy or symbol.
- CORS is off unless `allowed_origin_list` in `config/settings.yaml` lists origins. Native apps do not need it.

## GET /api/v1/rules

Every rule from `config/rules.yaml`, grouped by category (`MAC`, `TRD`, ...) and, inside a category, by topic (`topic_list` of the group, `topic` of the rule), with the strategies that use it. A rule has no weight: the weight and the `veto` flag are per strategy and appear in `used_by`. `indicator_description` is the bilingual text of the rule's indicator and `indicator_line_list` every line of that measure (`{"rule_id": "R-MAC-03", "line": "< 4.5"}`), so a client needs no second request to explain a rule.

```json
{"default_language": "en",
 "group_list": [{"group_id": "EVT", "display_name": {"en": "EVT · Events", "zh": "EVT · 事件"},
  "description": {"en": "...", "zh": "..."}, "aspect": {"en": "Events", "zh": "事件面"},
  "topic_list": [{"topic_id": "company_events", "display_name": {"en": "Company events", "zh": "公司事件"}}],
  "rule_list": [{"rule_id": "R-EVT-01", "rule_name": "no_earnings_within_45_days", "topic": "company_events",
                 "description": {"en": "Passes when there is no earnings report before the option expires. ...", "zh": "..."},
                 "method": "api_fetch", "quantifiable": "yes", "backtestable": "yes", "history_source": "edgar:submissions", "history_start": "2004", "status": "built", "indicator_id": "I-082", "indicator": "no_earnings_before_expiration",
                 "indicator_description": {"en": "True when the stock's next earnings date is later than ...", "zh": "..."},
                 "indicator_line_list": [{"rule_id": "R-EVT-01", "line": {"en": "yes", "zh": "是"}}], "fetch_group": "yahoo_company", "fetch_every": "1h", "max_age": "3d",
                 "operator": "is_true", "value": null, "band_of": null, "legacy_id": ["A22", "F05"], "note": null,
                 "used_by": [{"strategy_id": "sell_put_four_in_one", "display_name": {"en": "Sell Put 4-in-1", "zh": "Sell Put 四合一"}, "weight": 5, "veto": true}]}]}]}
```

`status`: `built`, `todo`, `no_data`. A rule with an `indicator` gets `method`, `quantifiable`, `backtestable`, `history_source`, `history_start`, `status`, `fetch_group`, `fetch_every` (how often the source is asked) and `max_age` (how old the newest value may be before the rule reads unknown) from that indicator in `config/indicators.yaml`; a manual rule has them from `config/rules.yaml` and no fetch fields. `method`: `api_fetch`, `scrape`, `computed`, `ai_search`, `manual`. `quantifiable`: `yes`, `part`, `no`. `backtestable`: `yes` or `no`, whether free historical data can rebuild what the rule would have said on a past date; a `yes` rule also has `history_source` (for example `fred:DGS10`) and `history_start` (a year, month or day). Rules retired from the catalog are listed in `retired_rule_list` of `config/rules.yaml`, never in this response. `band_of` names the main rule when this rule is another line of the same measure (for example `R-SEN-04`, VIX below 25, points to `R-SEN-01`).

## GET /api/v1/strategies

```json
{"default_strategy_id": "sell_put_four_in_one",
 "default_language": "en",
 "strategy_list": [{"strategy_id": "sell_put_four_in_one", "display_name": {"en": "Sell Put 4-in-1", "zh": "Sell Put 四合一"},
                    "summary": {"en": "...", "zh": "..."}, "help_text": {"en": "paragraphs separated by blank lines", "zh": "..."},
                    "source": "where the strategy came from"}]}
```

## GET /api/v1/snapshot?strategy_id=sell_put_four_in_one

`strategy_id` is optional (default strategy).

```json
{
  "schema_version": 4,
  "status": {
    "server_time": "2026-10-24T10:01:00-04:00",
    "generated_at": "2026-10-23T15:52:19-04:00",
    "market_is_open": true,
    "refresh_interval_minutes": 10,
    "stale_after_minutes": 60
  },
  "strategy_id": "sell_put_four_in_one",
  "max_unknown_weight_ratio": 0.2,
  "market_indicator_card_list": [
    {"indicator_name": "vix_level", "display_name": {"en": "VIX", "zh": "VIX"}, "is_higher_value_risky": true,
     "value": 19.78, "change_value": 2.21, "change_unit": "percent"},
    {"indicator_name": "treasury_ten_year_yield", "display_name": {"en": "10Y", "zh": "10Y"}, "is_higher_value_risky": true,
     "value": 4.96, "change_value": -17.0, "change_unit": "basis_points"}
  ],
  "symbol_card_list": [
    {"symbol": "SPY", "price": 759.84, "change_value": -0.54, "change_unit": "percent",
     "is_pass": true, "score_percent": 95.5, "unknown_weight_ratio": 0.043,
     "sparkline_close_price_list": [741.2, 745.0, 759.84]}
  ],
  "failed_symbol_list": []
}
```

| Field | Meaning |
|---|---|
| `status.generated_at` | when the data was computed; `null` before the first snapshot |
| `status.server_time` | server clock now; compute data age as `server_time - generated_at` |
| `status.market_is_open` | US regular hours, Monday to Friday 9:30 to 16:00 ET; closed on `market_holiday_list` days, 13:00 close on `market_early_close_list` days (`config/settings.yaml`) |
| `status.stale_after_minutes` | while the market is open, older data should be shown as stale |
| `change_unit` | `percent` (relative change) or `basis_points` (absolute change of a rate) |
| `is_pass` | `true` passed, `false` vetoed by a rule marked `veto`, `null` unknown |
| `score_percent` | 0 to 100, `null` when no rule could be judged |
| `unknown_weight_ratio` | share of rule weight with missing data; above `max_unknown_weight_ratio` means data insufficient |
| `sparkline_close_price_list` | last 60 daily closes, oldest first |
| `failed_symbol_list` | watchlist symbols whose data could not be fetched or evaluated |

## GET /api/v1/evaluations/{strategy_id}/{symbol}

The strategy tree for one symbol.

```json
{
  "strategy_id": "sell_put_four_in_one", "symbol": "SPY",
  "is_pass": true, "score_percent": 95.5, "unknown_weight_ratio": 0.043,
  "gate_result_list": [
    {"gate_id": "gate_0_macro", "display_name": {"en": "GATE 0 Macro and sentiment", "zh": "GATE 0 宏观/情绪开关"}, "is_pass": true,
     "expiration_window_label": null, "alternative_window_result_list": [],
     "rule_result_list": [
       {"rule_id": "R-MAC-03", "rule_name": "ten_year_below_4_5pct", "status": "fail",
        "measured_value": 4.96, "weight": 2, "veto": false, "method": "api_fetch"}
     ]}
  ]
}
```

Rule `status`: `pass`, `fail`, `unknown`, `not_applicable`. A gate with `expiration_window_label` was evaluated per option expiration window; the other windows are in `alternative_window_result_list` with the same shape.
