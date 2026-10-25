# Language

The interface has two languages, English (`en`, default) and Chinese (`zh`, shown as `zh-Hans`).
In Chinese mode Chinese is the main text and the English appears underneath in small gray type (see `docs/design.md`, Language).

## Writing both languages

- Every text in `config/rules.yaml`, `config/indicators.yaml`, `config/strategies/*.yaml` and `config/settings.yaml` that a person reads is an object `{en: "...", zh: "..."}`. Both are required and non-empty; the app refuses to start otherwise. A rule has a `description` (its pass sentence) and an indicator has a `description` (what it measures, how it is read, where the value comes from, typical values), both `{en, zh}`; they spell out every abbreviation (FOMC, CPI, IV and so on) and name the data source. A `rule_name` and an `indicator_name` are identifiers in lower case with underscores, English only, like a variable name; so is the `quantifiable` field.
- English must not contain Chinese characters. Use the glossary below; do not invent variants.
- Technical terms stay English in both languages: GATE, VIX, SPX, DTE, IV, RV30, FGI, HY, bp, Delta, Put, Call.
- Interface strings live in `static/language.js` (`UI_TEXT`), with the same rule.
- **The one English rule (no exceptions):** in Chinese mode the English text is `<small lang="en">`, always on its own line directly under the Chinese line it translates, always 12px gray, including every help paragraph. Do not use any other English style.

## Glossary

| 中文 | English |
|---|---|
| 权重 | weight |
| 一票否决 | veto |
| 分档 | tier |
| 阈值 | threshold |
| 通过 | pass |
| 不通过 | fail |
| 未知 | unknown |
| 低于 | below |
| 不高于 | at most |
| 高于 | above |
| 不低于 | at least |
| 介于 … 之间 | between |
| 国债 | Treasury |
| 消费者价格指数 | Consumer Price Index (CPI) |
| 净资产收益率 | return on equity (ROE) |
| 首次申请失业救济人数 | initial jobless claims |
| 平值 | at the money (ATM) |
| 最近 12 个月 | the last 12 months (TTM) |
| pp（stays English; percentage points） | pp |
| X% 以内 | within X% |
| 增加不超过 X% | at most X% more |
| Put、Call、Covered Call | put, call, covered call (stay in English) |
| 规则 | rule |
| 策略 | strategy |
