---
name: stockboard-design
description: Use when changing any StockBoard page (static/index.html, static/rules.html, static/base.css): layout, colors, fonts, buttons, rows, panels, strategy tree. Keeps one shape language and the Claude-style warm palette.
---

Read `docs/design.md` first and follow it exactly. Build pages only from the five element families there (Text, Control, Row, Surface, Mark); do not add a new element class, compose the existing ones. Every color, size, radius and spacing comes from the tokens in `static/base.css`. Anything clickable has the shared radius, 44px hit area, hover and focus ring; never use negative margins or `border-radius: 50%` on something clickable. Icons come from `static/icons.svg` (Tabler); never hand-draw one. Both pages share `static/base.css`; put a style in the page only when it is layout.
