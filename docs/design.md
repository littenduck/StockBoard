# Design

Robinhood-style minimal. One HTML file, no framework, no chart library.

## Rules

- Fonts: `-apple-system, system-ui`. Numbers use `font-variant-numeric: tabular-nums`.
- Font sizes: 12px (caption), 15px (body), 28px (big number). No other sizes.
- Spacing: multiples of 8px only.
- Radius: 12px everywhere. No shadows. 1px lines only.
- Colors: light and dark mode from `prefers-color-scheme`. Up `#00C805`, down `#FF5000`, everything else gray.
- Score color: 75 or more green, 60 to 75 yellow, below 60 red, unknown gray.
- Volatility indicators where higher means more risk (`is_higher_value_risky: true`) use inverted up/down colors.
- Forbidden: animation, icon fonts, theme switcher, chart libraries.

## Layout

- Desktop (900px or wider): two columns. Left is a narrow sidebar (280px, sticky, scrolls by itself) holding lists. Right is the main area, which is the strategy tree.
- Sidebar, top to bottom: title, strategy dropdown, market indicator list, symbol list (indices and stocks mixed). Lists, not cards: one row per item, no borders, the selected symbol has a thin left bar.
- Main area: the selected symbol, its two results (pass, score), then the gates as a tree with a vertical line.
- Phone: stacked, sidebar on top. Clicking a symbol scrolls to the main area.

## Components (only these four)

| Class | Shows |
|---|---|
| `indicator-item` | name, value, daily change |
| `symbol-item` | symbol, pass mark, score, price, daily change |
| `strategy-gate` | one gate: title, pass mark, rule rows |
| `strategy-rule-row` | rule id, description, status mark, measured value |

## Status marks

Pass `✅`, fail `❌`, unknown `❓`, not applicable `➖`.
