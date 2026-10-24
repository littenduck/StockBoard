---
name: stockboard-design
description: Use when changing any StockBoard page (static/index.html, static/rules.html, static/base.css): layout, colors, type, buttons, rows, boxes, strategy tree. Text is plain HTML tags (h1, h2, h3, p, small, strong, a) with no text classes. Keeps one shape language and the Claude-style warm palette.
---

Read `docs/design.md` first and follow it exactly.

- Text is plain HTML tags (h1, h2, h3, p, li, small, strong, a). Do not add text classes; the tag decides the look.
- Build only from the element classes listed in `docs/design.md`: `.icon-button`, `.field`, `.row`, `.box`, `.status-badge`, `.status-dot`, `.sparkline`. (`.sparkline` is an inline SVG with no CSS.) Helper classes also exist: `.icon`, `.placeholder`, and the page-local animation `.panel-enter`. Compose them; do not add a new element class.
- One radius: `--radius` (8px) for everything.
- English companions are always `<small lang="en">`, on their own line under the Chinese line.
- Icons come from `static/icons.svg` (Tabler); never hand-draw one.
- No negative margins on anything clickable or any row.
- Type, color and spacing come from the tokens in `static/base.css`; layout columns are page-local. Both pages share `static/base.css`; put a style in the page only when it is layout.
