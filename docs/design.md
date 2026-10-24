# Design

Claude-style warm palette, Apple-level clarity. Two pages (`static/index.html` dashboard, `static/rules.html` rule catalog) sharing `static/base.css` for tokens and type; vanilla JS and CSS, no framework, no chart library, no web font, no CDN.
Light theme is the default; the user can switch to dark with the button in the sidebar header.

## Colors

CSS custom properties on `:root` (light) and `:root[data-theme="dark"]`. Every text pair below is at least 4.5:1 on `--background`, `--surface` and `--fill` (checked with the WCAG formula).

| Token | Light | Dark | Use |
|---|---|---|---|
| `--background` | `#FAF9F5` | `#262624` | page, main area |
| `--surface` | `#FFFFFF` | `#30302E` | sidebar |
| `--fill` | `#F0EEE6` | `#3A3A37` | hover and selected row |
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

Spacing only 4, 8, 12, 16, 24, 32px (`--space-1` to `--space-6`). Radius 8px for rows, 12px for containers. No shadows.

Touch targets are at least 44px tall. The one spacing exception: a 16px-line element that must reach 44px uses 14px vertical padding.
Font weights: 400 and 600 only.

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

## Components (only these)

| Class | Shows |
|---|---|
| `status-bar` | market open or closed, data age, stale or connection warning, full ET time on hover |
| `indicator-item` | name, value, change (`+1.23%` or `+3.0 bp`) |
| `symbol-item` | symbol, sparkline, status icon, integer score, price, change. A `<button>` |
| `status-badge` | icon plus text from the Status table |
| `sparkline` | 64 by 20 SVG polyline of the last 60 closes, colored by first vs last |
| `strategy-gate` | gate title, summary badge, rule rows |
| `strategy-rule-row` | rule id, status badge, description, measured value |
| `rule-row` (rules page) | rule id, description and note, default weight, availability, strategies that use it; the row named in the URL hash is highlighted |
| `help-popover` | native `popover` opened by the question mark next to the strategy name; title, summary, help paragraphs, source; closes with the close button, Esc or a click outside |

## Language

Chinese UI. Symbols and technical terms stay English: VIX, SPX, DTE, IV, RV30, GATE, bp. Times are exchange time, labelled `ET`.

## Language

English is the default; Chinese mode shows Chinese with the English underneath. Glossary and writing rules: `docs/language.md`.

| Class | Style | Use |
|---|---|---|
| `.translation` | block, 12px / 16px, `--text-secondary`, weight 400 | English line under Chinese text |
| `.translation-inline` | 12px, `--text-secondary`, 4px left margin | English after a 12px caption on the same line |
| `.translation-paragraph` | 15px body, `--text-secondary` | English help paragraph after its Chinese paragraph |
| `.icon-button` | 44px square, radius 8px, `--text-secondary` icon, `--fill` on hover; used for the theme button (half-filled circle) and the language button (globe). The language button toggles English and Chinese; its aria-label and tooltip say what a click does (Switch to Chinese / 切换到英文) | sidebar header, rules page header |

English appears under: sidebar section captions, strategy name, gate titles, rule descriptions and notes, rule group titles, help title, summary and paragraphs, result captions, expiration window lines, the rules page explanation.
Never doubled: status words, numbers, prices, percentages, times, symbols, the status bar, buttons, select options, aria-labels.
`<html lang>` is `en` or `zh-Hans`; every English line in Chinese mode carries `lang="en"`.
