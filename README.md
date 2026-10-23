# StockBoard

A personal stock dashboard. First row: market indicators (VIX, VXN, VVIX, 10Y, HY spread). Below: one card per symbol with a **pass** mark and a **score**. Click a card to see the strategy tree on the right, gate by gate and rule by rule.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn stockboard_backend.web_server:app --port 8000
```

Open http://localhost:8000. Data refreshes in the background every `refresh_interval_minutes`, only while the US market is open (the first snapshot is taken at startup). Refresh once by hand:

```bash
.venv/bin/python -m stockboard_backend.refresh_scheduler --once
```

Test: `.venv/bin/python -m pytest tests`

## Layout

| Path | What |
|---|---|
| `config/settings.yaml` | refresh interval, indicator cards, watchlist, option expiration windows |
| `strategies/*.yaml` | strategies: gates, rules, weights (see `docs/strategy.md`) |
| `docs/design.md` | page design rules |
| `docs/indicator.md` | every indicator, its meaning and source |
| `docs/strategy.md` | strategy file format, scoring, pass veto |
| `stockboard_backend/` | Python package, one module per job, function names are `module_verb_object` |
| `static/index.html` | the whole front end |
| `.claude/skills/` | skills that point Claude at the design and strategy docs |

## Two results per symbol

- **Pass**: false if any weight 5 rule fails (veto).
- **Score**: weighted share of passed rules, 0 to 100.

They are independent. Rules with missing data show ❓ and are left out of the score. Option rules need live bid and ask quotes, so they show ❓ while the market is closed.
