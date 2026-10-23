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

- Desktop (900px or wider): two columns. Left two thirds is the board, right one third is the strategy panel (sticky).
- Board: first row is indicator cards, below it is the symbol grid (indices and stocks mixed).
- Phone: stacked. Clicking a symbol card scrolls to the strategy panel.

## Components (only these four)

| Class | Shows |
|---|---|
| `indicator-card` | name, value, daily change |
| `symbol-card` | symbol, pass mark, score, price, daily change |
| `strategy-gate` | one gate: title, pass mark, rule rows |
| `strategy-rule-row` | rule id, description, status mark, measured value |

## Status marks

Pass `✅`, fail `❌`, unknown `❓`, not applicable `➖`.
