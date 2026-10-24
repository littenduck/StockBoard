# Plan: bilingual interface (English default, Chinese with English underneath)

Branch: `feature/bilingual`. One commit per step. Quality bar: the page must still score at least 4.5 on the strict Apple review used so far.
The previous plan (UI and API v1) is finished; it stays in git history (commit `216d1e5`).

---

## 0. Requirements

### 0.1 From the user

| ID | Requirement |
|---|---|
| L1 | Two languages: English and Chinese. |
| L2 | English is the default. |
| L3 | In Chinese mode, Chinese is the main text and the English text is shown too, in small gray type underneath. |
| L4 | Every strategy, gate, rule and help text gets an English version; the Chinese version is kept. |
| L5 | Language code: `zh` (not CH, which is Switzerland, nor CN, which is China as a country). |
| L6 | Keep the 4.5 design standard. |

### 0.2 Decisions (made for the user, explained)

| ID | Decision | Why |
|---|---|---|
| D1 | Two modes, not three: **English** (English only) and **中文** (Chinese plus English underneath). | Matches L2 and L3 exactly. A Chinese-only mode is not requested. |
| D2 | Codes `en` and `zh`; the page sets `<html lang="en">` or `<html lang="zh-Hans">`; every English line shown in Chinese mode carries `lang="en"`. | Standard BCP 47; screen readers switch voice correctly. |
| D3 | Switch = segmented control `EN | 中文` in the sidebar header, between the title and the theme button. Choice stored in `localStorage` key `stockboard-language` (try/catch). Same control on the rules page. | One place, same as the theme switch; no reload needed. |
| D4 | Localized text in data is an object `{en: "...", zh: "..."}` under the existing field name. Both keys are required. | One field, two languages; a SwiftUI client reads the same object. |
| D5 | Snapshot and API `schema_version` goes from 2 to 3 because field types change from string to object. | The API contract says type changes bump the version. |
| D6 | Where the English line appears (Chinese mode), see section 2.3. Status words, numbers, prices, times, buttons and the status bar are never doubled. | Doubling every word would make rows unreadable; icons and numbers are already language-neutral. |
| D7 | Long help paragraphs: the English paragraph follows its Chinese paragraph in `--text-secondary` color at body size (15px), not 12px. | 12px is too small for paragraphs of running text; it stays gray so the hierarchy is clear. |
| D8 | `<select>` options show the active language only. | Native `<select>` cannot show two lines; the selected strategy's English name appears in the main header. |

---

## 1. Glossary (fixed translations; every step must use these)

| 中文 | English |
|---|---|
| 策略 | Strategy |
| 市场指标 | Market |
| 标的 | Symbols |
| 结论 | Verdict |
| 分数 | Score |
| 通过 / 未通过 / 否决 / 未知 / 不适用 | Pass / Fail / Veto / Unknown / N/A |
| 数据缺失权重 X%（未知规则不计入分数） | Missing-data weight X% (unknown rules are left out of the score) |
| 数据不足 | Insufficient data |
| 到期窗口 X 天（最佳） · 本层分数 Y | Expiration X days (best) · Gate score Y |
| 备选到期窗口 | Alternative expiration |
| 开盘中 · 更新于 N 分钟前 | Market open · Updated N min ago |
| 休市 · 最后更新 | Market closed · Last update |
| 数据已过期 | Data is stale |
| 连接断开，正在重试 | Disconnected, retrying |
| 正在获取数据… | Loading data… |
| 获取失败 | Unavailable |
| 规则目录 | Rule catalog |
| 编号 / 说明 / 默认权重 / 数据状态 / 使用它的策略 | ID / Rule / Weight / Availability / Used by |
| 自动计算 / 缺少数据源 / 需要账户数据 / 需要你回答 / 交易计划项 / 尚未实现 | Automatic / No data source / Needs account data / Needs your answer / Trade plan / Not built yet |
| 是 / 否 | Yes / No |
| 宽松档 / 严格档 | loose tier / strict tier |
| GATE, VIX, SPX, DTE, IV, RV30, FGI, HY, bp, Delta | unchanged in both languages |

---

## 2. Design (add to `docs/design.md` as a "Language" section)

### 2.1 Tokens

| Class | Style | Use |
|---|---|---|
| `.translation` | `display:block; font-size:12px; line-height:16px; color:var(--text-secondary); font-weight:400;` | English line under Chinese text |
| `.translation-inline` | `font-size:12px; color:var(--text-secondary); margin-left:var(--space-1);` | English after a 12px caption label on the same line |
| `.translation-paragraph` | `color:var(--text-secondary);` (15px body) | English help paragraph (D7) |

### 2.2 Segmented control `language-switch`

Two buttons inside a 1px `--separator` rounded container (radius 8px), each at least 44px tall. Selected button: `--fill` background, `--text` color, `aria-pressed="true"`. Labels `EN` and `中文`. Width budget: title 110px + switch 88px + theme button 44px + gaps 16px + padding 32px = 290px, under the 300px sidebar.

### 2.3 Where the English line appears in Chinese mode

| Element | English shown? | How |
|---|---|---|
| Sidebar section captions (策略, 市场指标, 标的) | yes | `.translation-inline` |
| Strategy name in main header | yes | `.translation` under it |
| Gate titles | yes | `.translation` under the title |
| Rule descriptions (dashboard and rules page) | yes | `.translation` under the description |
| Rule notes (rules page) | yes | `.translation` |
| Rule group titles and descriptions (rules page) | yes | `.translation` / `.translation-inline` |
| Help popover: title, summary | yes | `.translation` |
| Help popover: paragraphs | yes | `.translation-paragraph` after each paragraph |
| Result captions 结论 / 分数 | yes | `.translation-inline` |
| Expiration window lines | yes | `.translation-inline` |
| Explanation box on the rules page | yes | `.translation-paragraph` |
| Status words, numbers, prices, percentages, times, symbols | no | language-neutral or too frequent |
| Status bar, buttons, select options, aria-labels | no | one line only; aria in the active language |

In English mode no `.translation` element is rendered at all.

### 2.4 Layout checks forced by longer English

- Rule row status column: from 72px to 88px ("Unknown" with icon).
- Strategy tree rule rows grow from 1 line to 2 lines in Chinese mode; accepted (it is the requested feature).
- Indicator rows: English names already used (VIX…); `HY bp` becomes `HY spread` in both languages.

---

## 3. Data and backend

### 3.1 Data format

```yaml
# config/rules.yaml
rule_group_list:
  - {group_id: A, display_name: {en: "A · #1 Sell Put five-layer framework", zh: "A · #1 Sell Put 五层决策框架"},
     description: {en: "...", zh: "..."}}
rule_list:
  - {rule_id: A22, description: {en: "No earnings before expiration", zh: "到期前无财报"}, default_weight: 5, ...}
  - {rule_id: A04, ..., note: {en: "...", zh: "..."}}
# strategies/*.yaml
display_name: {en: "Sell Put 4-in-1", zh: "Sell Put 四合一"}
summary: {en: "...", zh: "..."}
help: {en: "paragraphs\n\nseparated by blank lines", zh: "..."}
gates: [{gate_id: gate_0_macro, display_name: {en: "GATE 0 Macro and sentiment", zh: "GATE 0 宏观/情绪开关"}, ...}]
# config/settings.yaml
market_indicator_list: [{indicator_id: vix_level, display_name: {en: VIX, zh: VIX}, ...}]
default_language: en
```

### 3.2 Code

| File | Change |
|---|---|
| `stockboard_backend/localized_text.py` (new) | `LocalizedText` dataclass (`en`, `zh`); `localized_text_build_from_raw_value(raw_value, field_name) -> LocalizedText` raises `ValueError` naming the field when a language is missing or empty. |
| `rule_catalog.py` | `description`, `note`, group `display_name`, `description` become `LocalizedText`. |
| `strategy_evaluation.py` | `RuleDefinition.description`, `GateDefinition.display_name`, `StrategyDefinition.display_name/summary/help_text`, `RuleEvaluationResult.description`, `GateEvaluationResult.display_name` typed `LocalizedText` (dataclasses.asdict turns them into `{en, zh}`). |
| `strategy_loader.py`, `settings_loader.py` | build `LocalizedText` for those fields; settings gains `default_language` (must be `en` or `zh`). |
| `refresh_scheduler.py` | `SNAPSHOT_SCHEMA_VERSION = 3`; market card `display_name` is `{en, zh}`. |
| `web_server.py` | strategies, rules and snapshot responses carry `{en, zh}` objects and `default_language`; old snapshots (v2) count as missing and are rebuilt. |

### 3.3 Tests (new or changed)

- `tests/test_localized_text.py`: missing `zh`, empty `en`, non-dict value each raise with the field name in the message.
- `tests/test_rule_catalog.py`, **completeness and quality test** over every group, rule, note, strategy name, summary, help and gate in the project:
  - both `en` and `zh` are present and non-empty;
  - `en` contains no CJK character (`[\u3400-\u9fff]`), so no untranslated Chinese leaks into English;
  - `en` uses the glossary spellings: none of the off-glossary variants `loose grade`, `strict grade`, `loose level`, `strict level`, `Not applicable`, `not applicable` appears (forbidden-words list in the test; extend it when the glossary grows).
- `tests/test_web_server.py`: strategies response has `{en, zh}`; `default_language == "en"`; a schema v2 snapshot counts as missing.
- Existing tests updated for the new types; all must pass.

---

## 4. Front end

### 4.1 Shared: `static/language.js` (served at `/language.js`; logic at most 50 lines, plus the `UI_TEXT` table) and `static/base.css`

| Function | Job |
|---|---|
| `UI_TEXT` | object `{key: {en, zh}}` holding every fixed string: glossary terms, aria-labels, error messages, page titles |
| `languageGetActive()` | stored choice (`localStorage`, try/catch) if valid, else `document.documentElement.dataset.defaultLanguage`, else `en` |
| `languageApply(languageCode, onChange)` | sets `<html lang>` (`en` / `zh-Hans`), `document.title`, stores the choice, updates the switch's `aria-pressed`, calls `onChange` |
| `languageText(key)` | fixed string in the active language |
| `languageRenderText(localizedText)` | escaped primary text; in Chinese mode adds `<span class="translation" lang="en">` with the English |
| `languageRenderInline(localizedText)` | same, with `.translation-inline` |
| `languageRenderParagraphs(localizedText)` | splits on blank lines; Chinese mode pairs each Chinese paragraph with its English paragraph (`.translation-paragraph`) |
| `languageRenderSwitch()` | markup of the `EN | 中文` segmented control |

Precedence: a stored user choice beats `default_language` from settings, which beats `en`.
Numbers, prices and percentages keep `Intl.NumberFormat("en-US")` in both languages (US market data). Times keep `ET`.

### 4.2 Dashboard (`static/index.html`, at most 380 lines)

- Replace every hard-coded Chinese string with `languageText(key)` or a render helper; nothing in Chinese stays in the HTML except inside `UI_TEXT`.
- Add the switch to the sidebar header.
- On language change: re-render sidebar lists, status bar, main panel and the help popover **from data already in memory** (no fetch); keep selected symbol, scroll position and whether the popover is open.
- `renderedEvaluationKey` includes the active language, so the "skip identical re-render" shortcut cannot keep the old language on screen.
- `formatAge`, `formatMeasuredValue` (Yes/No) and the window labels use the active language.

### 4.3 Rules page (`static/rules.html`, at most 140 lines)

Same switch and helpers; availability labels, legend, column headers, filter options, explanation box, summary line, error message and `<title>` from `UI_TEXT`; group, rule and note text via the render helpers.

---

## 5. Steps and commits

Each commit leaves the tests green. The page may show `[object Object]` between steps 3 and 6; the branch is only merged after step 8.

1. Docs: `docs/language.md` (glossary, section 1 moves there; rules for writing both languages) and the Language section of `docs/design.md`. Commit.
2. `stockboard_backend/localized_text.py` and its tests (not used yet). Commit.
3. Rule catalog: convert `config/rules.yaml` to `{en, zh}` **with the English written in the same commit**, update `rule_catalog.py` and catalog tests. Commit.
4. Strategies and settings: convert the 4 strategy files (names, summaries, help, gates) and `config/settings.yaml` with English in the same commit; update `strategy_evaluation.py`, loaders, `refresh_scheduler.py` (schema 3), `web_server.py`; completeness test. Commit.
5. `static/language.js` and the `base.css` language styles; route `/language.js`. Commit.
6. Dashboard. Commit.
7. Rules page. Commit.
8. Docs: `docs/api.md` (objects, schema 3, `default_language`), `docs/strategy.md` (both languages required), `.claude/skills/stockboard-strategy/SKILL.md` (both languages required, link to `docs/language.md`), `README.md`. Commit.
9. Verification (section 6), independent review, score. Fix commits if needed.

---

## 6. Verification

1. `pytest` all pass, including the completeness and quality test.
2. English mode, both pages: no CJK character in `document.body.innerText` except the switch label `中文`.
3. Chinese mode: every element marked "yes" in 2.3 has a `.translation`, `.translation-inline` or `.translation-paragraph` with `lang="en"`, and the English matches the data (spot-check 10 rules against `config/rules.yaml`).
4. Contrast audit in both themes, both languages, both pages: every text element at least 4.5:1.
5. Font sizes 12/15/20/34, weights 400/600, tap targets at least 44px, no horizontal overflow at 375, 1024 and 1512px, in both languages.
6. Switching language: no network request (checked in the network log), selected symbol, scroll position and open popover kept, `<html lang>` and `document.title` change.
7. Reload keeps the choice; a fresh browser (storage cleared) starts in English.
8. Line budgets: `index.html` at most 380, `rules.html` at most 140, `language.js` logic at most 50 (the `UI_TEXT` table, one string pair per line, is not counted).

Execution note: the first budget of 70 lines for all of `language.js` counted the text table as code; with about 55 string pairs it could not hold. Moving the table to a JSON file would add an async load and a flash of English, so the budget was split instead.

---

## 7. Plan review

| Version | Score | Deductions |
|---|---|---|
| Draft | 4.0 | P1 step order broke the build between commits; P2 no translation quality check; P3 language switch did not cover the open popover and the render cache; P4 page title, error messages, number format and default precedence unspecified; P5 future strategy authors not told to write both languages; P6 no code size limits |
| Revised (this file) | 5.0 | P1 data and English land in the same commit per file group (steps 3, 4); P2 completeness plus no-CJK-in-English plus forbidden-words test; P3 explicit in 4.2; P4 in 4.1 and 4.3; P5 step 8 updates the authoring guide and the skill; P6 line budgets in 4.2, 4.3, 4.1 and section 6 |

Residual risks (not deductions, accepted): rule rows are taller in Chinese mode (requested feature); translations are mine and should get a read-through from the user after merge.
