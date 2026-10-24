# Design

Claude-style warm palette, Apple-level clarity. Two pages (`static/index.html` dashboard, `static/rules.html` rule catalog) sharing `static/base.css` for tokens and type; vanilla JS and CSS, no framework, no chart library, no web font, no CDN.
Light theme is the default; the user can switch to dark with the button in the sidebar header.

## Colors

CSS custom properties on `:root` (light) and `:root[data-theme="dark"]`. Every text pair below is at least 4.5:1 on `--background`, `--surface` and `--fill` (checked with the WCAG formula).

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | `#FAF9F5` | `#262624` | page, main area |
| `--surface` | `#FFFFFF` | `#30302E` | sidebar |
| `--fill` | `#F0EEE6` | `#3A3A37` | hover and selected row (selected adds the accent bar) |
| `--separator` | `#E8E6DC` | `#3D3D3A` | 1px lines, placeholder rows |
| `--text` | `#141413` | `#F5F4EE` | primary text |
| `--text-secondary` | `#6B6A64` | `#A8A69D` | captions, unknown, not applicable |
| `--accent` | `#C96442` | `#D97757` | selection bar, focus ring, theme button. Never body text |
| `--positive` | `#146C35` | `#4ADE80` | up, 通过 |
| `--negative` | `#B42318` | `#FF8A8A` | down, 否决, 未通过 |
| `--caution` | `#8A5A00` | `#FBBF24` | score 60 to 74, stale data |

US convention: green up, red down. Indicators marked `is_higher_value_risky` (VIX, rates, spreads) invert the color.
Score color: 75 or more `--positive`, 60 to 74 `--caution`, below 60 `--negative`, unknown `--text-secondary`.

## Type

System font only: `-apple-system, BlinkMacSystemFont, system-ui, sans-serif`. All numbers use `font-variant-numeric: tabular-nums`.

| Token | Size / weight / line height | Use |
|---|---|---|
| `--font-caption` | 12px / 400 / 16px | labels, timestamps, section titles |
| `--font-body` | 15px / 400 / 20px | rows, rule text |
| `--font-title` | 20px / 600 / 24px | symbol name in main, gate titles |
| `--font-display` | 34px / 600 / 40px, letter-spacing -0.02em | pass result and score in main |

No other sizes. Every heading element has an explicit size.

## Space and shape

Spacing only 4, 8, 12, 16, 24, 32px (`--space-1` to `--space-6`). Radius tokens: `--radius-control` 8px (everything clickable, plus chips), `--radius-panel` 12px (boxes). Hit size token: `--hit-size` 44px. No shadows except the 3px accent bar on a selected row. Font weights: 400 and 600 only.

## Status

No emoji anywhere. Status = icon (16px, `currentColor`) plus text. All icons are Tabler Icons 3.49.0 (MIT), taken unchanged from the official npm package and bundled into `static/icons.svg` by `scripts/build_icons.py`. Pages reference them as `/icons.svg#icon-name`. Outline icons render at 1.5px. Never hand-draw an icon: if a needed icon is missing from Tabler, pick the closest Tabler icon.

| Status | Icon | Text | Color |
|---|---|---|---|
| rule pass | filled circle with check | 通过 | `--positive` |
| rule fail | filled circle with cross | 未通过 | `--negative` |
| summary veto (symbol, gate) | filled circle with cross | 否决 | `--negative` |
| unknown | outline circle with "?" | 未知 | `--text-secondary` |
| not applicable | short dash | 不适用 | `--text-secondary` for the whole row (no opacity: it would break contrast) |

Summaries (symbol, gate) use only 通过 / 否决 / 未知. Icon-only places carry `aria-label`. Icon to text gap 4px.

## Motion (about 10 CSS lines)

- Row hover and selection: `transition: background-color 120ms ease`.
- Main panel on symbol change: fade in plus 4px rise, 160ms (`@keyframes panel-enter`).
- Status dot pulses while a request is in flight.
- `@media (prefers-reduced-motion: reduce)` disables all of it.

## Layout

- Desktop (900px or wider): grid `300px 1fr`. Sidebar sticky, scrolls by itself, `--surface` background, 1px right separator. Main max width 880px, padding 32px, centered in the remaining space so the white space is even on both sides.
- Main header: symbol and price on the left, 结论 and 分数 on the right, both big values on one bottom line; the missing-data note sits under them; a 1px separator closes the header. On phones the results wrap under the symbol.
- Sidebar order: header (title, theme button), status bar, strategy select, 市场指标 list, 标的 list.
- Phone (below 900px): one column. Indicators become a horizontal scroll strip. Selecting a symbol scrolls to main; main has a "↑ 列表" link.

## Shape and states

One shape language. Everything the user can click shares one radius, one hover and one focus ring.

| Rule | Value |
|---|---|
| Interactive elements | radius `--radius-control`; min height `--hit-size`; no negative margins anywhere |
| Hover | background `--fill`; text becomes `--text`. Same for icon button, interactive row, link hit area |
| Keyboard focus | 2px `--accent` outline, offset 2px, follows the element's own radius (`:focus-visible` never sets a radius); rows use `outline-offset: -2px` so the ring is not clipped |
| Selected | `aria-current="true"` (sidebar) or `.is-target` (rules page, from the URL hash): `--fill` plus `box-shadow: inset 3px 0 var(--accent)`. A darker fill is not used: secondary text would fall below 4.5:1 |
| Disabled or failed | no opacity (contrast); text becomes `--text-secondary` |
| Field (`select`) | 1px `--separator` border, `--surface` background on every page, radius control, padding `--space-3` |
| Row | margin `0 var(--space-2)`, padding `var(--space-2)`, radius control |
| Panel | radius panel, `--surface`, 1px `--separator` border, padding `--space-4` or `--space-5` |
| Chip | radius control, 1px `--separator` border, padding `0 var(--space-2)`, caption type; height comes from line height, never fixed |
| Hit area (`.hit`) | `position: relative` plus an `::after` that extends the clickable area to `--hit-size` without changing layout; replaces every negative-margin hack |
| Circles | only non-clickable marks: `status-dot`, `gate-marker`, sparkline |

## Elements (five families)

| Family | Classes | Used for |
|---|---|---|
| Text | `caption` `title` `display` `strong`, colors `positive` `negative` `caution` `muted`, `link`, `link-emphasis` | all text and every link (hover underline; `link-emphasis` is always underlined) |
| Control | `icon-button`, `field` | theme, language, help and close buttons; strategy and filter selects |
| Row | `row` (a `button` or `a` row is interactive; `aria-current` or `.is-target` marks selected) | symbol, indicator and rule rows, sidebar footer link, loading placeholders |
| Surface | `panel`, `chip` | popover, explanation box; tag, usage chips, phone indicator strip |
| Mark | `status-badge`, `status-dot`, `sparkline`, `gate-marker` | pass, fail and unknown badges, market dot, price trend, gate icon |

Layout-only containers (not elements): sidebar, main, `detail-header`, `result-row`, `strategy-gate`, `status-bar`, dividers. Do not add a new element class; compose these.

## Language

English is the default; Chinese mode shows Chinese with the English underneath. Glossary and writing rules: `docs/language.md`.

| Class | Style | Use |
|---|---|---|
| `.translation` | block, 12px / 16px, `--text-secondary`, weight 400 | English line under Chinese text |
| `.translation-inline` | 12px, `--text-secondary`, 4px left margin | English after a 12px caption on the same line |
| `.translation-paragraph` | 15px body, `--text-secondary` | English help paragraph after its Chinese paragraph |

English appears under: sidebar section captions, strategy name, gate titles, rule descriptions and notes, rule group titles, help title, summary and paragraphs, result captions, expiration window lines, the rules page explanation.
Never doubled: status words, numbers, prices, percentages, times, symbols, the status bar, buttons, select options, aria-labels.
`<html lang>` is `en` or `zh-Hans`; every English line in Chinese mode carries `lang="en"`.

The language button (Tabler `language` icon) is an `icon-button`; one click toggles English and Chinese, and its aria-label and tooltip say what a click does. Technical terms stay English in both languages: VIX, SPX, DTE, IV, RV30, GATE, bp. Times are exchange time, labelled `ET`.
