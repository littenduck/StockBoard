# Plan: UI to Editor's Choice level (web) + platform-neutral API

Target: front-end score from 2.0 to at least 4.5 (strict Apple review standard), with very little code and no new dependencies.
Executor: read this whole file, then `docs/design.md`, `docs/strategy.md`, `docs/indicator.md`. Work on branch `feature/strategy-dashboard`. Do the steps in order; each step ends with its own check.

---

## 0. Confirmed requirements

### 0.1 Fixed (do not change)

| ID | Requirement |
|---|---|
| F1 | Web only for now. No Liquid Glass, no iOS-specific layout. A native SwiftUI client may come later, so the API must not depend on the web page. |
| F2 | Layout: narrow left sidebar (lists: strategy, market indicators, symbols), main area on the right is the strategy tree. |
| F3 | Two independent results per symbol: pass (weight 5 veto) and score (0 to 100). |
| F4 | Strategy tree shows gates 0, 1, 2; each rule row shows id, status, description, measured value. |
| F5 | Single HTML file, vanilla JS and CSS, no framework, no chart library, no CDN, no web font. |
| F6 | Python naming `module_verb_object`, no abbreviations. JS uses camelCase, also no abbreviations. |
| F7 | Light and dark mode. **Light is the default**; the user can switch to dark. |
| F8 | No new runtime dependency. (FastAPI's bundled CORS middleware is allowed; it ships with FastAPI.) |

### 0.2 Answers from the user

| Question | Answer |
|---|---|
| Q1 colors | Claude app style (warm ivory, terracotta accent). Colors only. |
| Q2 up/down | US convention: green up, red down. |
| Q3 theme | Light default; dark selectable. |
| Q4 Liquid Glass | Not on web. |
| Q5 fonts | System font only (`-apple-system, system-ui`). |
| Q6 motion | Yes, about 10 lines of CSS. |
| Q7 stale | Data older than 60 minutes counts as stale. Fetch every 10 minutes (already the setting). |
| Q8 time zone | Exchange time, America/New_York, labelled `ET`. |
| Q9 phone | Responsive web (same page works on phone and desktop). No iOS navigation pattern. |
| Q10 labels | Chinese: 通过 / 否决 / 未知. |
| Q11 language | Chinese UI, but symbols and technical terms stay English (VIX, DTE, IV, RV30, GATE, SPX, bp). |
| Q12 sparkline | Yes: the symbol's **price** trend. |
| Q13 packaging | Not decided; out of scope. |
| Q14 backend fixes | Include V6, V7, V8; executor decides details as written below. |

### 0.3 Decisions made on the user's behalf (user said "decide freely")

| ID | Decision | Why |
|---|---|---|
| D1 | Rule rows use four labels: 通过 / 未通过 / 未知 / 不适用. The symbol and gate summary use the user's three: 通过 / 否决 / 未知. | A single failed weight 2 rule is not a veto; calling it 否决 would be wrong. |
| D2 | Score is always an integer on screen (sidebar and main). | Removes the 91 vs 90.9 mismatch. Raw value stays in the API. |
| D3 | Sparkline = last 60 trading days of daily close, no axes, colored by 60 day change. | Enough shape, tiny payload. |
| D4 | Theme switch = one button in the sidebar header (sun/moon icon), choice stored in `localStorage` (wrapped in try/catch). | Light default plus manual dark, minimal code. |
| D5 | Selected symbol is kept in the URL hash (`#AAPL`). | Survives reload, shareable, no storage needed. |
| D6 | API moves to `/api/v1/...` with a documented JSON contract (`docs/api.md`). Old `/api/...` routes are removed (only our own page uses them). | Lets a future SwiftUI or iOS client rely on a stable contract. |
| D7 | US market holidays are NOT handled in this plan. | Needs a holiday table; out of scope. Listed in section 4. |
| D8 | No new test dependency: API tests call the endpoint functions directly instead of FastAPI `TestClient` (which needs `httpx`). | Keeps F8. |

---

## 1. Verified problems this plan must fix

| ID | Problem | Status |
|---|---|---|
| U1 | Font sizes out of control (12/15/28/30px found; 30px is the unstyled `h1`); spacing inconsistent | verified in browser |
| U2 | Emoji used for status (✅❌❓➖), glued to numbers (`✅91`) | verified |
| U3 | Update time only `10-23 15:52` in 12px; no date context, time zone, age; stale data looks fresh | verified |
| V1 | Fetch failure shows nothing on the page | verified (simulated) |
| V2 | Each 60 s refresh collapses opened `<details>` | verified |
| V3 | Symbol rows are `div` with `tabIndex -1`, no role | verified |
| V4 | Light mode contrast: `#00C805` ~2.3:1, `#D9A400` ~2.3:1, `#FF5000` ~3.3:1 (need 4.5:1 for text) | computed |
| V5 | Score 91 in sidebar vs 90.9 in main | verified |
| V6 | 10Y and HY show relative percent change; should be basis point change | verified |
| V7 | Market open/closed not shown | code reading |
| V8 | Symbols that failed to fetch silently disappear | code reading |
| V9 | Fast clicking can show an older response | code reading |
| V10 | No loading state during the first ~45 s | code reading |
| V11 | Selection lost on reload | code reading |
| V12 | "Data insufficient" shown only by gray color | verified |

---

## 2. To-do list (in execution order)

Each item names the requirement it serves. Line budgets are hard limits.

### Step 1. Design spec first — `docs/design.md` (serves Q1–Q11, U1, U2, V4)

Rewrite `docs/design.md` completely with the tokens below. Every later step must use only these tokens.

1.1 Colors (CSS custom properties on `:root`, dark values on `:root[data-theme="dark"]`). Claude-inspired, verified contrast against `--background`:

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | `#FAF9F5` | `#262624` | page |
| `--surface` | `#FFFFFF` | `#30302E` | sidebar, hover, selected row |
| `--text` | `#141413` | `#F5F4EE` | primary text |
| `--text-secondary` | `#6B6A64` | `#A8A69D` | captions (must be at least 4.5:1) |
| `--separator` | `#E8E6DC` | `#3D3D3A` | 1px lines |
| `--accent` | `#C96442` | `#D97757` | selection bar, focus ring, theme button (not used for body text) |
| `--positive` | `#17803D` | `#4ADE80` | up, 通过 (light ~4.8:1) |
| `--negative` | `#B42318` | `#F87171` | down, 否决 / 未通过 (light ~6.2:1) |
| `--caution` | `#8A5A00` | `#FBBF24` | score 60 to 74, stale warning (light ~5.6:1) |
| `--unknown` | `--text-secondary` | same | 未知, 不适用 |

Executor must re-check each text color pair with the WCAG formula and adjust the value (not the rule) if any pair is below 4.5:1.

1.2 Type scale, system font, `font-variant-numeric: tabular-nums` on all numbers:

| Token | Size / weight / line height | Use |
|---|---|---|
| `--font-caption` | 12px / 400 / 16px | labels, timestamps |
| `--font-body` | 15px / 400 / 20px | rows, rule text |
| `--font-title` | 20px / 600 / 24px | symbol name in main, section titles |
| `--font-display` | 34px / 600 / 40px, letter-spacing -0.02em | score and pass result in main |

No other sizes. Every heading element gets an explicit size (fixes the 30px `h1`).

1.3 Spacing: only 4, 8, 12, 16, 24, 32px (`--space-1` … `--space-6`). Radius: 8px rows, 12px containers. No shadows.

1.4 Status components (replace all emoji):

| Status | Icon (inline SVG, 16px, `currentColor`) | Text | Color |
|---|---|---|---|
| rule pass | filled circle + check | 通过 | `--positive` |
| rule fail | filled circle + cross | 未通过 | `--negative` |
| summary veto | filled circle + cross | 否决 | `--negative` |
| unknown | outline circle + "?" | 未知 | `--unknown` |
| not applicable | short dash | 不适用 | `--unknown`, row opacity 0.45 |

Icon and text always together in summaries (sidebar may show icon only but with `aria-label`). Gap between icon and text: 4px.

1.5 Motion (whole budget about 10 CSS lines):
- row hover/selected background: `transition: background-color 120ms ease`
- main panel on symbol change: fade in + 4px rise, 160ms (`@keyframes` `panel-enter`)
- refresh indicator dot: 1 s opacity pulse while a request is in flight
- `@media (prefers-reduced-motion: reduce)` turns all of it off.

1.6 Layout:
- Desktop (>= 900px): grid `300px 1fr`; sidebar sticky, own scroll, `--surface` background, 1px right separator; main max width 880px, padding 32px.
- Phone (< 900px): one column. Sidebar order: header, status bar, indicators as a horizontal scroll strip (chips), symbol list; main below. Selecting a symbol smooth-scrolls to main; main has a small "↑ 列表" link at top.
- Components (only these): `status-bar`, `indicator-item`, `symbol-item`, `status-badge`, `sparkline`, `strategy-gate`, `strategy-rule-row`.

1.7 Language: Chinese UI; symbols and terms in English (Q11). Status words from 1.4.

Check: `docs/design.md` contains every token above and nothing says "Robinhood".

### Step 2. Backend: snapshot data the new UI needs (serves V6, V7, V8, Q8, Q12)

2.1 `stockboard_backend/refresh_scheduler.py`
- Replace `"updated": time.strftime(...)` with `"generated_at"`: ISO 8601 in America/New_York with offset, e.g. `2026-10-23T15:52:19-04:00` (use `market_data.NEW_YORK_TIME_ZONE`).
- Add `"schema_version": 2` to the snapshot.
- Rename `"error_list"` to `"failed_symbol_list"` (V8). Also add to it any symbol whose per-symbol evaluation raised (wrap the executor call per symbol; today one exception would abort the whole snapshot).
- In each symbol result add `"sparkline_close_price_list"`: last 60 daily closes, rounded to 2 decimals (Q12, D3).

2.2 `stockboard_backend/indicator_calculation.py` (V6)
- New function `indicator_calculation_calculate_latest_change_basis_points(value_series) -> Optional[float]`: `(last - previous) * 100`, rounded to 1 decimal. Input series is in percent points (FRED DGS10 and BAMLH0A0HYM2 both are).
- In `strategy_evaluation.py`, rename `IndicatorValue.change_percent` to `change_value` and add `change_unit: Optional[str] = None` (`"percent"` or `"basis_points"`). Update every caller and test.
- 10Y and HY use basis points; VIX, VXN, VVIX, prices use percent.

2.3 Market card list (built in `refresh_scheduler_build_dashboard_snapshot`): each card has `indicator_id, display_name, is_higher_value_risky, value, change_value, change_unit`.

2.4 Old snapshot files: `web_server` must treat a snapshot whose `schema_version` is not 2 as missing (return the empty snapshot and let the refresher rebuild). `refresh_scheduler_determine_whether_refresh_is_due` returns True when the file's `schema_version` is not 2.

Check: `python -m stockboard_backend.refresh_scheduler --once` prints `generated_at` with `-04:00` or `-05:00`; the JSON has `sparkline_close_price_list` of length 60 for each symbol and `change_unit: "basis_points"` for 10Y and HY.

### Step 3. Backend: platform-neutral API v1 (serves F1, D6, V7)

3.1 `stockboard_backend/web_server.py`
- Replace `@app.on_event("startup")` with a FastAPI `lifespan` context manager (`web_server_run_application_lifespan`).
- Routes (all JSON, snake_case, `null` for unknown, enums as lower-case strings, times ISO 8601 with offset):

| Method and path | Function | Returns |
|---|---|---|
| `GET /` | `web_server_get_index_page` | the HTML file |
| `GET /api/v1/strategies` | `web_server_get_strategy_list` | `{default_strategy_id, strategy_list:[{strategy_id, display_name}]}` |
| `GET /api/v1/snapshot?strategy_id=` | `web_server_get_dashboard_snapshot` | see 3.2 |
| `GET /api/v1/evaluations/{strategy_id}/{symbol}` | `web_server_get_strategy_evaluation_for_symbol` | the evaluation dict (unchanged shape) |

3.2 Snapshot response adds a `status` object computed at request time (V7):

```json
"status": {
  "server_time": "2026-10-24T10:01:00-04:00",
  "generated_at": "2026-10-23T15:52:19-04:00",
  "market_is_open": false,
  "refresh_interval_minutes": 10,
  "stale_after_minutes": 60
}
```

plus `schema_version`, `strategy_id`, `max_unknown_weight_ratio`, `market_indicator_card_list`, `symbol_card_list` (each: `symbol, price, change_value, change_unit, is_pass, score_percent, unknown_weight_ratio, sparkline_close_price_list`), `failed_symbol_list`.
`stale_after_minutes` comes from a new setting `stale_after_minutes: 60` in `config/settings.yaml` (add field to `ApplicationSettings`).

3.3 CORS: new setting `allowed_origin_list: []` in `config/settings.yaml`; when non-empty, add FastAPI's built-in `CORSMiddleware` with those origins, GET only. Empty means no CORS (same-origin page and native apps do not need it).

3.4 New `docs/api.md`: one example response per endpoint, field table, the rule "fields are only added within a schema version; renames or removals bump `schema_version`".

3.5 Tests `tests/test_web_server.py` (D8): build a fake snapshot dict on disk in a temp directory (monkeypatch `refresh_scheduler.SNAPSHOT_FILE_PATH`), call the endpoint functions directly, assert: unknown strategy raises `HTTPException` 404; old `schema_version` returns the empty snapshot; `status.market_is_open` is a bool; `symbol_card_list` keeps watchlist order.

Check: `pytest` all green; `curl localhost:8000/api/v1/snapshot` shows `status`.

### Step 4. Front end rewrite — `static/index.html` (serves U1–U3, V1–V5, V9–V12, Q6, Q10, Q12)

Hard budget: at most 320 lines including CSS and the SVG sprite. Rebuild from scratch following `docs/design.md`; reuse the existing fetch flow only.

4.1 Structure

```
<svg hidden> <symbol id="icon-pass"/> <symbol id="icon-fail"/> <symbol id="icon-unknown"/> <symbol id="icon-not-applicable"/> <symbol id="icon-theme"/> </svg>
<div class="layout">
  <aside>
    <header> StockBoard  [theme button] </header>
    <div class="status-bar" role="status" aria-live="polite"></div>
    <select id="strategy-select"></select>
    <section> 市场指标  <ul id="indicator-list"></ul></section>
    <section> 标的      <ul id="symbol-list"></ul></section>
  </aside>
  <main id="strategy-panel" tabindex="-1"></main>
</div>
```

4.2 JS functions (each does one thing):

| Function | Job |
|---|---|
| `loadStrategyList()` | fetch `/api/v1/strategies`, fill select |
| `loadDashboardSnapshot()` | fetch snapshot; on success render; on failure set connection error state (V1); always update status bar |
| `renderStatusBar(status, connectionError)` | see 4.3 |
| `renderIndicatorList(list)` | rows: name, value, change (`+3.0 bp` or `+1.23%`, Unicode minus `−`) colored with risk inversion |
| `renderSymbolList(list, failedSymbolList)` | `<li><button class="symbol-item">`: symbol, sparkline, status icon, integer score, price, change; failed symbols as disabled rows "获取失败" (V8) |
| `renderSparkline(closePriceList)` | returns `<svg viewBox="0 0 64 20">` with one `<polyline>`, stroke 1.5, color by first vs last value; empty string when fewer than 2 points |
| `renderStatusBadge(status, isSummary)` | icon + text from design 1.4 |
| `loadStrategyEvaluationForSymbol(symbol)` | fetch with a request counter; ignore any response whose counter is not the latest (V9) |
| `renderStrategyTree(symbol, evaluation)` | header (symbol at title size), two display results 通过/否决/未知 and integer score, "数据不足" text tag when unknown ratio is above the threshold (V12), then gates |
| `formatNumber(value)`, `formatChange(value, unit)`, `formatRelativeTime(isoText, serverTimeIsoText)`, `formatExchangeTime(isoText)` | formatting only, `Intl.NumberFormat("en-US")`, booleans as 是/否 |
| `selectSymbol(symbol)` | set `location.hash`, update `aria-current`, load evaluation, on phone scroll main into view |
| `handleSymbolListKeydown(event)` | ArrowUp/ArrowDown move focus and selection |
| `applyTheme(themeName)` | set `data-theme` on `<html>`, store in localStorage inside try/catch |

4.3 Status bar states (U3, V1, V7, Q7, Q8). Age = server_time − generated_at (do not trust the client clock), re-rendered every 30 s locally:

| Condition | Text | Color |
|---|---|---|
| no snapshot yet | 正在获取数据… (pulse dot) | `--text-secondary` |
| fetch failed | 连接断开，正在重试 | `--negative` |
| market open, age ≤ 60 min | 开盘中 · 更新于 N 分钟前 | `--text-secondary`, green dot |
| market open, age > 60 min | 数据已过期 · 最后更新 HH:MM ET | `--caution` |
| market closed | 休市 · 最后更新 MM/DD HH:MM ET | `--text-secondary` |

`title` attribute on the bar shows the full time, e.g. `2026-10-23 15:52:19 ET`.

4.4 Refresh without disruption (V2): before re-rendering the main panel, remember which `<details>` (by window label) are open and the scroll position; restore them after. Skip re-rendering entirely when the evaluation JSON string is unchanged.

4.5 Initial symbol: `location.hash` if it is in the list, else the first symbol (V11).

4.6 Loading and empty states (V10): sidebar shows three placeholder rows in `--separator` color while the first snapshot is missing; main shows "选择左侧的标的查看策略树".

4.7 Accessibility: every icon-only element has `aria-label`; `:focus-visible` ring 2px `--accent` with 2px offset; symbol list is `role="listbox"`-free plain list of buttons with `aria-current="true"` on the selected one; main has `aria-live="polite"` off (only status bar is live).

Check: see section 3.

### Step 5. Docs and cleanup

5.1 Update `docs/indicator.md`: 10Y and HY change is in basis points.
5.2 Update `README.md`: API is `/api/v1`, link `docs/api.md`, mention theme switch.
5.3 Update `.claude/skills/stockboard-design/SKILL.md` description: "Claude-style warm palette" instead of "Robinhood-style".
5.4 Delete the old `data/latest_snapshot.json` once so the new schema is generated.

---

## 3. Verification (executor must do all of these and report results)

1. `.venv/bin/python -m pytest tests -q` all pass (existing 18 plus new).
2. `.venv/bin/python -m stockboard_backend.refresh_scheduler --once` succeeds; inspect JSON fields from Step 2.
3. Start the server: `.venv/bin/python -m uvicorn stockboard_backend.web_server:app --port 8000`. Note: the app's Browser pane preview uses a stale launch config from the old scratch folder; start the server from Bash and navigate the pane to `http://localhost:8000/?v=N` (bump N to beat the cache).
4. In the browser at 1280×800 and 375×812, light and dark:
   - only 12/15/20/34px font sizes exist (run `[...new Set([...document.querySelectorAll('body *')].map(e=>getComputedStyle(e).fontSize))]`)
   - no emoji anywhere in `document.body.innerText`
   - status bar shows 休市 or 开盘中 with ET time
   - sparkline visible on every symbol row
   - Tab reaches symbol rows; ArrowDown changes selection; reload keeps the selected symbol (hash)
   - open an "其他窗口" panel, call `loadDashboardSnapshot()` from the console, panel stays open
   - override `window.fetch` to reject, call `loadDashboardSnapshot()`, status bar shows 连接断开
   - `prefers-reduced-motion` emulation removes the animations
5. Contrast: compute every text color pair from `docs/design.md` with the WCAG formula; all at least 4.5:1 (captions included).
6. `wc -l static/index.html` at most 320.
7. Commit on `feature/strategy-dashboard` with a message per step; do not push without the user's OK.

---

## 4. Out of scope (recorded so nobody adds it)

- Liquid Glass, blur, iOS navigation stack, SwiftUI client, App Store packaging.
- US market holiday calendar (refresher may run on holidays; harmless).
- Login protection (needed before any public deployment).
- Fear and Greed data source (A08/A09 stay unknown).
- Charts beyond the sparkline.

## 5. Expected score after this plan

| Area | Now | Target |
|---|---|---|
| Information architecture | 3.0 | 4.5 |
| Typography and spacing | 2.0 | 4.5 |
| Color and contrast | 1.5 | 4.5 |
| Status communication | 1.5 | 5.0 |
| Data trust (freshness, errors) | 1.0 | 5.0 |
| Interaction and accessibility | 1.5 | 4.5 |
| Platform consistency | 2.0 | 4.0 (web ceiling; native client needed for 5) |
| **Overall** | **2.0** | **4.5** |
