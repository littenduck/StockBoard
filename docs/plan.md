# Plan: one shape language for every control, row and surface

Branch: `feature/ui-consistency` (from `main` at `e8b09cd`). One commit per step. Quality bar: the page must keep scoring at least 4.5 on the strict Apple review, and the audit in section 7 must pass.
Previous plans (UI and API v1, bilingual interface) are in git history.

---

## 1. The problem, verified

The user reported: small buttons, the dropdown, the market indicator box and the highlighted symbol row do not share a style (some rounded, some square), and the help circle next to the strategy is round on hover while everything else is square. All measured in the running page (dark theme, 1512px wide):

| Claim | Verdict | Evidence (computed style) |
|---|---|---|
| Help button is round, other buttons are square | **True** | `.help-button` radius `50%`; `.icon-button` (theme, language) radius `8px`. Same size (44px), same job, same hover color, two shapes |
| Dropdown differs from the rest | **True** | `select`: 8px radius **with** a 1px border; icon buttons: 8px radius **no** border, no background until hover |
| Selected symbol row differs | **True** | Selected row: radius `0px`, full width (299px, touches the sidebar edge), accent bar made with `box-shadow: inset 3px 0`. Rules page highlighted row (same meaning): radius `8px` + same bar. Same state, two shapes |
| Market indicator box differs | **True** | Desktop: plain rows, no background, radius `0px`. Phone (`max-width: 899px`): bordered chips with radius `12px`. The same element has two shapes, and the chip radius (12) matches no other chip (tag and usage chips use 8) |
| Colors differ | **Partly true** | Select background is `--background` on the dashboard (`rgb(38,38,36)`) but `--surface` on the rules page (`rgb(48,48,46)`). Hover and selected rows share the same fill, so a hovered row looks selected |

**Additional faults found while auditing (the user did not mention them):**

| # | Fault | How it was found |
|---|---|---|
| F1 | `:focus-visible { border-radius: 8px }` in `base.css` changes the shape of any element whose own class sets no radius (symbol rows are `0px`, so they become rounded only while keyboard-focused) | Code reading. Could **not** be reproduced in the browser tool: script focus does not enter the keyboard-focus state |
| F2 | Five different hacks to reach a 44px tap area: negative margins on `.help-button`, `.back-link`, `.rule-link`, `.catalog-link`, alias links, plus `padding: 14px/15px` | CSS |
| F3 | Five link styles: `.rule-link` (no underline, underline on hover), `.catalog-link` (always underlined), `.back-link` (gray), `.sidebar-footer-link` (gray with top border), alias link (small gray) | CSS |
| F4 | `.strategy-gate > header .icon` masks the vertical line with `background` + `border-radius: 50%` (a hack) | CSS |
| F5 | `.strategy-name` re-implements `.strong` (15px/600) as its own class | CSS |
| F6 | 42 distinct CSS classes on one dashboard render, many one-off | `distinctClasses` = 42 |
| F7 | Magic numbers outside the token scale: 14px, 15px, 36px, -24px, 22px chip height | CSS |
| F8 | Placeholder rows are 8px rounded while the rows they stand in for are square | CSS |

---

## 2. Three style options

All keep the Claude palette, system font and the 4-size type scale. They differ in shape rules.

### Option 1: one control radius, inset rounded rows (recommended) — 4.7 / 5

- Every clickable thing shares **one radius (8px)**: icon buttons (including help and close), select, list rows, links' hover area.
- List rows are **inset** (8px side margin) with 8px corners; hover = `--fill`; selected = `--fill` + the 3px accent bar (the rules page already looks like this).
- Panels (popover, explanation box) use 12px; chips use 8px.
- Circles only for things that are not clickable: status dot, gate marker, sparkline end.
- Matches Apple's current sidebar look (inset rounded selection) and the Claude app. Fewest rules.

| Criterion (1 to 5) | Score |
|---|---|
| Looks unified | 5.0 |
| Fits Claude and Apple | 4.8 |
| Code simplicity (fewest rules) | 4.8 |
| Accessibility (44px targets, focus ring follows the shape) | 4.7 |
| Migration effort and risk (rows lose 16px width) | 4.2 |
| **Overall** | **4.7** |

### Option 2: role-based shapes (circle for icon-only, rounded rectangle for text) — 4.0 / 5

- Icon-only buttons are circles (like an iOS toolbar), selects and rows 8px, panels 12px.
- Principled, but the user's complaint is exactly "some round, some square"; this keeps two shapes on screen. Three radii plus a circle rule to remember.

| Criterion | Score |
|---|---|
| Looks unified | 3.2 |
| Fits Claude and Apple | 4.3 |
| Code simplicity | 4.0 |
| Accessibility | 4.5 |
| Migration effort and risk | 4.0 |
| **Overall** | **4.0** |

### Option 3: flat and square, full-width rows (what the sidebar rows do now) — 3.1 / 5

- Radius 0 everywhere except status dots; rows full-bleed; separators and the accent bar carry the structure (Robinhood / terminal style).
- Very few rules, but it contradicts the warm Claude look the user chose and Apple's rounded controls; the select and buttons would also have to lose their rounding.

| Criterion | Score |
|---|---|
| Looks unified | 4.5 |
| Fits Claude and Apple | 2.0 |
| Code simplicity | 4.5 |
| Accessibility | 3.5 |
| Migration effort and risk | 2.5 (redo the work done in earlier rounds) |
| **Overall** | **3.1** |

**Chosen: Option 1.**

---

## 3. Decisions (made on the user's behalf; say if any is wrong)

| ID | Decision | Why |
|---|---|---|
| D1 | Radii: `--radius-control: 8px` (buttons, select, rows, chips), `--radius-panel: 12px` (popover, explanation box). Circle (`50%`) only for non-interactive marks | One interactive shape |
| D2 | Selected row = `--fill` plus the 3px accent bar; hover = `--fill` only. **No new color token** | A darker "selected" fill was tested and rejected: secondary text drops below 4.5:1 (light `#EBE9E0` 4.46, `#E8E6DC` 4.34; dark `#41413E` 4.20, `#44443F` 4.01) |
| D3 | The mobile indicator strip uses the same `.chip` (8px), not 12px | One chip |
| D4 | Select background is always `--surface` (dashboard and rules page) | It is a field, not part of the page; `--surface` separates it on both backgrounds |
| D5 | Replace every negative-margin tap area with one `.hit` rule (section 5) | One mechanism |
| D6 | One link style: text color `--text-secondary`, becomes `--text` with underline on hover and keyboard focus; `.link-emphasis` variant only for the popover link (always underlined, `--text`) | 5 styles become 1 plus 1 variant |
| D7 | `:focus-visible` keeps the outline but no longer sets `border-radius`; outline follows each element's own radius | Fixes F1 |
| D8 | Class count on a dashboard render must drop from 42 to 28 or fewer | F6 |

---

## 4. Inventory of every element, grouped into five families

All visible things on both pages, and the family each belongs to:

| Family | Variants (fewest possible) | Elements that become it today |
|---|---|---|
| **Text** | 4 sizes (`caption` 12, `body` 15, `title` 20, `display` 34), weight `strong`, color (`positive`, `negative`, `caution`, `muted`), `link` | page titles, captions, section titles, values, scores, descriptions, links (all 5 kinds), `strategy-name` |
| **Control** (clickable, 44px tall, 8px, same hover and focus) | `icon-button`, `field` (select) | theme button, language button, help button, popover close button, strategy select, rules filter select |
| **Row** (list line, inset 8px, hover `--fill`, selected `--fill` + bar) | `row` (static), `row is-selected` | symbol item, indicator item, rule row, rule-catalog rule row (highlighted via URL hash), sidebar footer link |
| **Surface** (boxed) | `panel` (12px, `--surface`, 1px border), `chip` (8px, 1px border, caption text) | popover, explanation box, tag "Insufficient data", usage chips, mobile indicator chips, loading placeholders (use `.row` height, `--separator` fill) |
| **Mark** (not clickable, content graphic) | `status-badge` (icon + word), `status-dot`, `sparkline`, `gate-marker` | pass/fail/unknown badges, market status dot, price sparkline, gate title icon |

Not counted as families (layout only): the sidebar and main grid, `detail-header`, `result-row`, `strategy-gate` tree line, 1px `--separator` dividers.

**Result: 5 families, 14 classes** (`caption title display strong link icon-button field row panel chip status-badge sparkline status-dot`) plus the existing color modifiers and layout containers. That replaces 42 one-off classes.

Tokens added to `base.css` (no new colors): `--radius-control: 8px; --radius-panel: 12px; --hit-size: 44px;`.

---

## 5. Specification (add to `docs/design.md` as "Shape and states")

| Rule | Value |
|---|---|
| Interactive elements | radius `--radius-control`; min height `--hit-size` (44px); no negative margins |
| Hover | background `--fill`; text becomes `--text`. Same for icon button, row, link hit area, select |
| Focus (keyboard) | 2px `--accent` outline, offset 2px, **follows the element's own radius**; rows use `outline-offset: -2px` so the ring is not clipped |
| Selected | `row.is-selected`: `--fill` + `box-shadow: inset 3px 0 var(--accent)`; `aria-current="true"` stays |
| Disabled / failed | `opacity` is not used (contrast); text becomes `--text-secondary` |
| Field | 1px `--separator` border, `--surface` background, radius control, padding `--space-3`, chevron from the browser |
| Row | `margin: 0 var(--space-2)`, `padding: var(--space-2) var(--space-2)`, radius control |
| Panel | radius panel, `--surface`, 1px `--separator` border, padding `--space-4` or `--space-5` |
| Chip | radius control, 1px `--separator` border, padding `0 var(--space-2)`, caption type, **height from line-height (16px) plus 2px border plus 4px padding, no fixed height** |
| Hit area (`.hit`) | `position: relative` and a `::after` pseudo-element that extends the clickable area to 44px without changing layout (replaces every negative-margin hack) |
| Circles | only `status-dot` (8px), `gate-marker`, and the sparkline; never on something clickable |

---

## 6. Steps and commits

1. **Spec.** Add "Shape and states" and the family table (sections 4 and 5) to `docs/design.md`; update the component table there. Commit.
2. **Base styles.** In `static/base.css`: radius and hit tokens; `.link`, `.row`, `.panel`, `.chip`, `.field`; `.hit`; focus rule fixed (D7); `.icon-button` moved onto the shared control rules. Commit.
3. **Dashboard.** Move `.help-button` and the popover close button onto `.icon-button` (delete `.help-button`); select onto `.field`; symbol, indicator and sidebar footer rows onto `.row` (selected row uses `is-selected`); popover onto `.panel`; mobile indicator chips and the tag onto `.chip`; placeholders to row height; the five link kinds to `.link`; gate marker to a named `.gate-marker`; `.strategy-name` onto `.strong`. Delete dead CSS. Commit.
4. **Rules page.** Select to `.field` with the shared background; explanation box to `.panel`; usage chips to `.chip`; rule rows and the highlighted row to `.row`; alias and back links to `.link`. Delete dead CSS. Commit.
5. **Docs.** Update `README.md` and `.claude/skills/stockboard-design/SKILL.md` (use only the families in `docs/design.md`). Commit.
6. **Audit** (section 7), independent review, score. Fix commits if needed.

---

## 7. Acceptance audit (all must pass; each measured with computed styles in the browser, both themes, both languages, widths 375, 1024 and 1512)

1. Every interactive element with a box (`button`, `select`, rows that are buttons or links) has `border-radius` exactly `8px`; no interactive element has `50%`. Inline text links have no box (hover only underlines), so they are exempt.
2. Every panel has `12px`; every chip has `8px`.
3. The help button and the theme button have identical computed `border-radius`, size, hover color and focus ring shape.
4. Select background is identical on the dashboard and the rules page.
5. Hovered row and selected row differ (selected has the accent bar).
6. Selected sidebar row and highlighted rules-page row have identical radius and bar.
7. No negative `margin` on any interactive element or row (`grep -c "margin:-"` is 0 in `static/`). The three gate headers that sit on the tree line use `margin-left:-24px` for tree geometry; they are not clickable.
8. Distinct classes on a dashboard render: 28 or fewer (was 42).
9. Contrast at least 4.5:1 for every text element, including text on `--fill` rows; both pages, both themes, both languages.
10. Tap targets at least 44px (an element with the `.hit` class counts when its `::after` is 44px); no horizontal overflow at 375, 1024, 1512.
11. Keyboard focus ring does not change the element's shape: no `:focus-visible` rule sets `border-radius`, and rows use an inset ring. (Checked in the stylesheet; script focus cannot enter the keyboard-focus state in the browser tool.)
12. All 44 existing tests still pass; line budgets: `index.html` at most 380, `rules.html` at most 140 (they should shrink).

---

## 8. Plan review

| Version | Score | Deductions |
|---|---|---|
| Draft | 4.2 | R1 first idea added a darker "selected" color; it breaks the 4.5:1 text contrast (measured); R2 `:focus-visible` shape change was unnoticed; R3 no acceptance checks for the families; R4 chips had a fixed 22px height |
| This file | 4.8 | R1 selected uses fill plus bar, no new token (D2); R2 D7; R3 section 7; R4 chip height from line-height. Remaining deductions: F1 could not be reproduced in the browser (found by code reading only); inset rows lose 16px of width, which may wrap long Chinese plus English rows on the symbol list (checked in step 3 at 300px) |

Open points for the user: (a) keep the accent bar on the selected row (D2) or use fill only; (b) hover color equal to selected fill is accepted because the bar tells them apart.

---

## 9. Result

Audit run in the browser at 375, 1024 and 1512px, both themes, both languages, both pages (script reads computed styles):

| Item | Dashboard | Rule catalog |
|---|---|---|
| 1 Interactive radius is 8px, none round | pass (12 combinations) | pass (12) |
| 2 Panels 12px, chips 8px | panel 12px | panel 12px, chips 8px |
| 3 Help and theme buttons identical (radius, size, color) | pass | n/a |
| 4 Select background the same on both pages | `rgb(255,255,255)` in light | same |
| 5 and 6 Selected row: 8px radius, fill, accent bar; unselected has no bar; same on both pages | pass | pass (URL-highlighted row identical) |
| 7 Negative margins | 3 (gate tree headers, not clickable) | 0 |
| 8 Distinct classes (was 42) | 28 | 22 |
| 9 Contrast at least 4.5:1 | 0 failures out of 256 to 315 text elements per combination | 0 failures out of 638 to 836 |
| 10 Tap targets at least 44px, no overflow | pass after a fix (see below) | pass |
| 11 Focus ring keeps shape | stylesheet check pass | pass |
| 12 Tests and line budgets | 44 passed; `index.html` 354 (was 379), `rules.html` 131 (was 137) | |

One real defect found by the audit and fixed in the same step: the sidebar footer row was 32px tall; interactive rows now have `min-height: var(--hit-size)`.
One defect in the audit script itself (it ignored the `.hit` pseudo-element height) was fixed before the final run.
