# Plan: type that renders like Markdown, fewer components

Branch: `feature/ui-consistency` (PR #3, not merged yet). This plan builds on the shared styles already on that branch and adds commits to it; no new branch.
Execution: each step below is written to be run by a fresh Haiku subagent that reads only this file plus the brief; the main session checks diff, tests and the audit in section 7 after every step.
Earlier plans (UI and API v1, bilingual, one shape language) are in git history.

---

## 1. The problem, verified

Measured in the running page (Chinese mode, strategy help popover):

| Element in the popover | Size | Weight | What it is |
|---|---|---|---|
| Title "Sell Put 四合一" | 20px | 600 | `h2.title` |
| English under the title | **12px** | 400 | `span.translation` |
| Summary sentence | 15px | **600** | `p.strong` |
| English under the summary | **12px** | 400 | `span.translation` |
| Each body paragraph | 15px | 400 | `p` |
| English under each body paragraph | **15px** | 400, gray | `p.translation-paragraph` |
| Source line | 12px | 400, gray | `p.caption` |

So the English line is 12px under the title and summary but 15px under the paragraphs, and the first sentence of the body is bold. All of that is what the user saw.

**Root causes**
1. Three different styles for the same job (English companion): `translation` (12px block), `translation-inline` (12px, same line), `translation-paragraph` (15px block). I added the 15px one on purpose for readability; it breaks consistency.
2. Text roles are spread over four classes (`caption`, `title`, `display`, `strong`) that are also applied to arbitrary tags, so the same tag looks different on different pages. Usage today: `caption` 39 times, `display` 31, `title` 18, `strong` 8, `link` 16.
3. The type vocabulary does not match anything a reader already knows.

---

## 2. The new type system: plain HTML tags, rendered like Markdown

No text classes. The tag decides the look. Five text elements, four sizes:

| Markdown | HTML tag | Size / weight / line | Used for |
|---|---|---|---|
| `#` H1 | `h1` | 28 / 600 / 32, letter-spacing -0.02em | symbol name, page title, the big verdict and score figures |
| `##` H2 | `h2` | 20 / 600 / 24 | app name, popover title, rule group titles |
| `###` H3 | `h3` | 15 / 600 / 20 | gate titles, strategy name, the summary sentence |
| body | `p`, `li` | 15 / 400 / 20 | everything else that is read |
| small | `small` | 12 / 400 / 16, `--text-secondary` | labels, timestamps, notes, **every English companion** |
| bold | `strong` | weight 600, same size as its parent | emphasis inside a line |
| link | `a` | see below | all links |

Sizes in use: **28, 20, 15, 12** (was 34, 20, 15, 12). Weights: 400 and 600.

**The one English rule (no exceptions):** in Chinese mode the English text is `<small lang="en">`, always on its own line directly under the Chinese line it translates, always 12px gray. That covers titles, labels, rule descriptions and **every help paragraph**. Delete `translation`, `translation-inline`, `translation-paragraph`.

**Links:** one style. Gray `--text-secondary`, no underline; hover and keyboard focus turn it `--text` and underline it. Inside a paragraph or list item (`p a`, `li a`) a link is always `--text` and underlined, like Markdown. The 44px hit area is built into every `a` (pseudo-element), so the `hit` class goes away. `link`, `link-emphasis` and `hit` are deleted.

**Vertical rhythm** (one rule, inside any `.box`, the popover and the explanation box): `.box > * + * { margin-top: 12px }`, `.box > h2 + * { margin-top: 8px }`, and an English companion hugs its line: `small[lang="en"] { margin-top: 4px }`. A paragraph that follows an English companion gets the normal 12px, so Chinese and English pairs read as units.

**Sidebar and header labels** (Strategy, Market, Symbols, Verdict, Score, Missing-data note) become plain `small`; in Chinese mode their English is the `<small lang="en">` line under them. Cost: three sidebar labels and two header labels grow by one 16px line in Chinese mode.

---

## 3. Components after the cleanup (the list the user asked for)

| Family | What exists | Count |
|---|---|---|
| **Text** | tags only: `h1` `h2` `h3` `p` `li` `small` `strong` `a`, plus the four color modifiers `.positive` `.negative` `.caution` `.muted` | 8 tags, 4 modifiers |
| **Control** | `.icon-button` (theme, language, help, close), `.field` (select with chevron) | 2 |
| **List row** | `.row` (hover, selected with accent pill, static) | 1 |
| **Box** | `.box`: bordered, 8px, `--surface`. It is the popover, the explanation box, and (as `small.box`) the small tags and chips | 1 |
| **Mark** | `.status-badge` (icon plus word), `.status-dot`, `.sparkline` | 3 |

That is **7 element classes** (was 14; six styled in `base.css` plus `.sparkline`, an inline SVG with no CSS), plus helpers `.icon`, `.placeholder` and the page-local `.panel-enter`, with the 12px panel radius dropped: **one radius, 8px**, for everything (`--radius-panel` is deleted).
Layout-only containers stay but are not components: the page grid, `aside`, `main`, `.detail-header`, `.result-row`, `.strategy-gate`, `.status-bar`, `.strategy-line`, `.symbol-header`, `.top-row`, `.page-header`, `.filter-row`, `.rule-group`, `.usage`, `.rule-meta`.
Target: **18 or fewer distinct classes on a dashboard render** (28 now) and **14 or fewer on the rule catalog page** (22 now).

---

## 4. Old to new mapping (use exactly this)

| Old | New |
|---|---|
| `h1.title`, `h2.title` | `h2` (app name, popover title, rule group title) |
| `h2.display` (symbol name), `h1.display` (rules page title) | `h1` |
| `p.display` (verdict, score figures) | `h1` inside `.result-row` |
| `.caption` on `span`, `p`, `h2`, `a`, `label`, `summary` | `small` (tag changed), links keep `a` |
| `.strong` | `strong` tag, or `h3` when it is a title (gate title, strategy name, summary sentence) |
| `.translation` (block) | `<small lang="en">` |
| `.translation-inline` | `<small lang="en">` (now also a separate line) |
| `.translation-paragraph` | `<small lang="en">` |
| `.link`, `.link-emphasis`, `.hit` | plain `a` |
| `.panel` | `.box` |
| `.chip` | `<small class="box">` |
| `.gate-marker` | style the gate header's `svg` structurally: `.strategy-gate > header > svg` |
| `.detail-note` | `<small>` (structural selector) |
| `--radius-panel`, `--font-*` leftovers | delete |

Kept unchanged: `.icon-button`, `.field`, `.row`, `.status-badge`, `.status-dot`, `.sparkline`, `.icon`, color modifiers, `aria-current`, `data-status`.

---

## 5. Decisions (made for the user; say if any is wrong)

| ID | Decision | Why |
|---|---|---|
| D1 | Four sizes (28, 20, 15, 12), not three | Markdown's rendered minimum is H1, H2, body, small; H3 is bold body. A three-size version would make the popover title 15px semibold, which is too weak |
| D2 | The 34px display size goes down to 28 | One H1 for page title, symbol name and the big figures |
| D3 | English companion is always 12px, even for long help paragraphs | The user's complaint is exactly mixed sizes; one rule is worth some reading comfort. Contrast of `--text-secondary` on `--surface` is 5.4 to 6.2:1 |
| D4 | English always under the Chinese, even for short labels | No inline exception to remember |
| D5 | One radius (8px) | Fewer tokens, one shape |
| D6 | Big figures use `h1` | The scheme has no separate "number" style; the label above each figure is `small` |

---

## 6. Steps and commits

Step 1 is documentation, step 2 is additive (nothing breaks), steps 3 to 5 migrate, step 6 deletes the old classes. The page works after every step.

1. **Docs.** Rewrite the Type section of `docs/design.md` and the Elements section to sections 2 and 3 of this file; update `docs/language.md` (English companion rule); update `.claude/skills/stockboard-design/SKILL.md` (text is plain tags; no text classes). Commit.
2. **Add tag styles.** In `static/base.css` add (do not delete anything yet): `h1`, `h2`, `h3`, `small`, `small[lang="en"]`, `strong`, `a` (including the hover, focus, `p a` and `li a` rules and a `a::after` 44px hit area), `.box` and the `.box` rhythm rules. Move the heading resets so a bare `h1` to `h3` gets its size. Commit. (Classed elements keep their old look because class selectors outrank tags.)
3. **Language helpers.** In `static/language.js`: `languageRenderText(localizedText)` returns the primary text plus `<small lang="en">` in Chinese mode (remove the `isInline` argument); `languageRenderParagraphs` returns `<p>zh</p><small lang="en">en</small>` pairs; remove `translation-paragraph`. Update every call site in `static/index.html` and `static/rules.html` that passed `true`. Commit.
4. **Dashboard.** Migrate `static/index.html` with the mapping in section 4: markup in the HTML and in every JS template string, and the page CSS (delete rules for removed classes; add structural selectors where needed). Commit.
5. **Rule catalog.** Same for `static/rules.html`. Commit.
6. **Delete.** Remove from `static/base.css`: `.caption`, `.title`, `.display`, `.strong`, `.translation`, `.translation-inline`, `.translation-paragraph`, `.link`, `.link-emphasis`, `.hit`, `.panel`, `.chip`, `--radius-panel`, and their old `h1, h2, h3, h4, p, ul` size resets. `grep` must find none of these names in `static/`. Commit.
7. **Audit** (section 7), independent review and score. Fix commits if needed.

Parallel: steps 4 and 5 touch different files and may run at the same time after step 3. Everything else is sequential.

---

## 7. Acceptance audit (computed styles in the browser, both themes, both languages, widths 375, 1024, 1512, both pages)

1. Font sizes found on screen are exactly {28px, 20px, 15px, 12px}; weights exactly {400, 600}.
2. In Chinese mode every element with `lang="en"` is 12px, gray (`--text-secondary`), weight 400 and `display: block`; the strategy help popover has no English at any other size.
3. `grep -rn` for `caption|title|display|strong|translation|link-emphasis|\bhit\b|\.panel|\.chip` as CSS class names finds nothing in `static/` (the tags `strong` and `small` are fine).
4. Distinct classes: dashboard 18 or fewer (popover open), rule catalog 14 or fewer.
5. In the popover the order is: `h2` title, its English `small`, `h3` summary, its English `small`, then `p` / `small` pairs, then a `small` source line, then the link. Sizes follow section 2 and every `p` pair has the same spacing.
6. Every earlier acceptance item still passes: interactive radius 8px and none round; contrast at least 4.5:1 on every text element; tap targets at least 44px (a link counts through its `::after`; links inside dense rows are 36px because the row is about 37px tall and a 44px area would overlap neighbours); no horizontal overflow; selected row and URL-highlighted row identical; no negative margin on any interactive element or row.
7. 44 tests pass; line budgets: `index.html` at most 354, `rules.html` at most 137 (6 lines added to replace an inline `onclick` with a `hashchange` handler), `base.css` at most 70.

---

## 8. Plan review

| Version | Score | Deductions |
|---|---|---|
| Draft | 4.1 | P1 steps would have broken the page between commits (delete before migrate); P2 the English rule had a hidden exception for paragraphs; P3 no acceptance check for the English size; P4 links needed an always-underlined variant for the popover |
| This file | 4.7 | P1 additive then migrate then delete (section 6); P2 D3; P3 audit item 2; P4 `p a`/`li a` rule. Remaining deductions: four sizes, not three (D1); English at 12px under long paragraphs is smaller than ideal (D3); the big figures are `h1` elements, which is not strictly semantic (D6); Chinese mode adds a line under each label (D4) |
| Rule catalog migration, audited in the browser on 2026-10-25 | 4.7 | Both pages, light and dark, English and Chinese, widths 375, 1024 and 1512: sizes are exactly 28, 20, 15 and 12px and weights 400 and 600; every `lang="en"` element is 12px gray block; contrast is at least 4.5:1 everywhere; radius is 8px or none; no negative margins; rule ids stay on one line; no horizontal overflow (the rule catalog page overflowed in English at 1024 and 375 because the strategy chips could not wrap, fixed). Deductions: the dashboard has 19 distinct classes against the budget of 18 (this branch added none); the select is 42px inside a 44px field; the selected row and the URL-highlighted row were not re-measured. Budgets now: 59 tests, `index.html` 354 lines, `rules.html` 136, `base.css` 61 |

Open points for the user: (a) four sizes or three; (b) keep English at 12px under long paragraphs, or allow a 15px exception (the old behavior); (c) English under short labels, or inline.
