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
| `--text-secondary` | `#6B6A64` | `#A8A69D` | small text, English companions, unknown, not applicable |
| `--accent` | `#C96442` | `#D97757` | selection bar, focus ring, theme button. Never body text |
| `--positive` | `#146C35` | `#4ADE80` | up, 通过 |
| `--negative` | `#B42318` | `#FF8A8A` | down, 否决, 未通过 |
| `--caution` | `#8A5A00` | `#FBBF24` | score 60 to 74, stale data |

US convention: green up, red down. Indicators marked `is_higher_value_risky` (VIX, rates, spreads) invert the color.
Score color: 75 or more `--positive`, 60 to 74 `--caution`, below 60 `--negative`, unknown `--text-secondary`.

## Type

Markdown-like. Plain HTML tags, no text classes: the tag decides the look.

System font only: `-apple-system, BlinkMacSystemFont, system-ui, sans-serif`. All numbers use `font-variant-numeric: tabular-nums`.

| Markdown | HTML tag | Size / weight / line | Used for |
|---|---|---|---|
| `#` H1 | `h1` | 28 / 600 / 32, letter-spacing -0.02em | symbol name, page title, the big verdict and score figures |
| `##` H2 | `h2` | 20 / 600 / 24 | app name, popover title, rule group titles |
| `###` H3 | `h3` | 15 / 600 / 20 | gate titles, strategy name, the summary sentence |
| body | `p`, `li` | 15 / 400 / 20 | everything else that is read |
| small | `small` | 12 / 400 / 16, `--text-secondary` | labels, timestamps, notes, every English companion |
| bold | `strong` | weight 600, same size as its parent | emphasis inside a line |
| link | `a` | see Links below | all links |

Sizes in use: **28, 20, 15, 12**. Weights: **400 and 600**. No other sizes.

**Links:** gray `--text-secondary`, no underline. Hover and keyboard focus turn the text `--text` and underline it. Inside a paragraph, list item or small line (`p a`, `li a`, `small a`) a link is always `--text` and underlined, like Markdown. Every `a` has a 44px hit area built in (`::after`), so no separate hit class is needed. Inside a `.row` the hit area is `--hit-size` minus 8px (`.row a::after`), so links in dense rows do not overlap the rows above and below.

**Vertical rhythm** (inside any `.box`, the popover and the explanation box included):
- `.box > * + * { margin-top: 12px }`
- `.box > h2 + * { margin-top: 8px }`
- `small[lang="en"] { margin-top: 4px }`, so an English companion hugs the Chinese line it translates.

## Space and shape

Spacing only 4, 8, 12, 16, 24, 32px (`--space-1` to `--space-6`). Radius: one token, `--radius` 8px, for everything (controls, rows, boxes, small tags). The only other curves are the 2px accent pill and the round gate icon. Hit size token: `--hit-size` 44px. No shadows, except the one soft shadow under the rule hover card, which floats over the page.

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
| Interactive elements | radius `--radius`; min height `--hit-size`; no negative margins anywhere (the gate icon is offset with `position:absolute`) |
| Hover | background `--fill`; text becomes `--text`. Same for icon button, interactive row, link |
| Keyboard focus | 2px `--accent` outline, offset 2px, follows the element's own radius (`:focus-visible` never sets a radius); rows use `outline-offset: -2px` so the ring is not clipped |
| Selected | `aria-current="true"` (sidebar) or `.is-target` (rules page, the row named by the URL hash): `--fill` plus a straight accent pill, 3px wide and 16px tall, centered on the row's left edge (`::before`). It is a separate shape, not an inset shadow, so it never bends with the row's rounded corner. A darker fill is not used: secondary text would fall below 4.5:1 |
| Disabled or failed | no opacity (contrast); text becomes `--text-secondary` |
| Field (`select`) | a `span.field` wraps the `select` and a Tabler chevron: 1px `--separator` border, `--surface` background on every page, radius control, 44px tall. The browser's own arrow is turned off; the chevron sits 12px from the right edge. Keyboard focus rings the whole field |
| Row | margin `0 var(--space-2)`, padding `var(--space-2)`, radius control |
| Box (`.box`) | radius control, `--surface`, 1px `--separator` border. Padding `--space-4` `--space-5` for the popover and explanation box; `0 var(--space-2)` for small tags (`small.box`), whose height comes from the line height, never fixed |
| Link hit area (`a`) | `position: relative` plus an `::after` that extends the clickable area to `--hit-size` without changing layout; replaces every negative-margin hack |
| Circles | only non-clickable marks: `status-dot`, sparkline |

## Elements

Text is done by tags. There are 7 element classes (6 styled in `base.css` plus `.sparkline`, which has no CSS of its own), 3 helper classes (plus the page-local `.panel-enter`) and one radius (8px). Do not add a new element class; compose these.

| Family | What exists | Used for |
|---|---|---|
| Text | tags only: `h1` `h2` `h3` `p` `li` `small` `strong` `a`, plus four color modifiers `.positive` `.negative` `.caution` `.muted` | all text and every link |
| Control | `.icon-button` (theme, language, help, close), `.field` (select with chevron) | buttons and strategy and filter selects |
| List row | `.row` (a `button` or `a` row is interactive; `aria-current` or `.is-target` marks selected) | symbol, indicator and rule rows, sidebar footer link, loading placeholders |
| Box | `.box`: bordered, radius 8px, `--surface` | popover, explanation box, and `small.box` for tags, usage chips and the phone indicator strip |
| Mark | `.status-badge` (icon plus word), `.status-dot` (8px dot, `currentColor`), `.sparkline` (inline SVG drawn by the page script, no CSS of its own; the dashboard only uses the class to place it in the row grid) | pass, fail and unknown badges, market dot, price trend |
| Helper | `.icon` (16px svg, `flex:none`), `.placeholder` (loading row, `--separator` fill), `.is-target` (row named by the URL hash), `.panel-enter` (fade-in animation, page-local in `index.html`) | icons, loading rows, rule row from the hash, main panel on symbol change |

Layout-only containers (not elements, styled by the page only for layout): page grid (`.layout`), `aside`, `main`, `#strategy-help` (the popover, a `.box`), `.detail-header`, `.result-row`, `.strategy-gate`, `.status-bar`, `.strategy-line`, `.symbol-header`, `.top-row`, `.page-header`, `.filter-row`, `.rule-group`, `.usage`, `.rule-meta`, dividers.

## Rule hover card

Each rule row on the dashboard has a small help icon (a link) after its id. Hovering it for one second, or focusing it with the keyboard, opens `#rule-card`, a `.box` popover with the rule's id (`small`), name (`h3`) and description (`p`), each with its English companion in Chinese mode. It closes the moment the pointer leaves, on blur and on Escape, and never takes the pointer itself (`pointer-events: none`). The full record of every field is on the rule catalog page, where each rule row shows its name and description, then a grid of every other field in `config/rules.yaml` order (a `small` field name above a `p` value, a gray dash when empty, `band_of` as a link, identifiers breaking at underscores) and a last line for `note` and `used_by` (strategy chips with weight and veto). The grid fills as many columns as fit, two on a phone. Built by `static/rule-card.js` from `/api/v1/rules`.

## Language

English is the default; Chinese mode shows Chinese with the English underneath. Glossary and writing rules: `docs/language.md`.

**The one English rule (no exceptions):** in Chinese mode the English text is `<small lang="en">`, always on its own line directly under the Chinese line it translates, always 12px gray. That covers titles, labels, rule descriptions and every help paragraph. There are no `translation*` classes.

English appears under: sidebar section labels, strategy name, gate titles, rule descriptions and notes, rule group titles, help title, summary and paragraphs, result labels, expiration window lines, the rules page explanation.
Never doubled: status words, numbers, prices, percentages, times, symbols, the status bar, buttons, select options, aria-labels.
`<html lang>` is `en` or `zh-Hans`; every English line in Chinese mode carries `lang="en"`.

The language button (Tabler `language` icon) is an `icon-button`; one click toggles English and Chinese, and its aria-label and tooltip say what a click does. Technical terms stay English in both languages: VIX, SPX, DTE, IV, RV30, GATE, bp. Times are exchange time, labelled `ET`.
