# StockBoard

A personal stock dashboard. The left sidebar lists market indicators (VIX, VXN, VVIX, 10Y, HY spread) and symbols, each with a **pass** result, a **score** and a price sparkline. Select a symbol to see its strategy tree on the right, gate by gate and rule by rule. A status bar shows whether the market is open and how old the data is. English by default; the globe button switches to Chinese, shown with the English underneath. Light theme by default; the half-circle button switches to dark.

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

Icons come from the official Tabler Icons package (MIT, see `licenses/`). Node.js is only needed to update them: `npm install` (installs `@tabler/icons` at the pinned version), then `.venv/bin/python scripts/build_icons.py` rewrites `static/icons.svg`, `static/favicon.svg` and the license copy. `node_modules/` is git-ignored and is not deployed.

## Layout

| Path | What |
|---|---|
| `config/indicators.yaml` | every measured quantity, defined once: source, method, history, status, and the fetch schedule (`fetch_group`, `fetch_every`, `max_age`) |
| `config/rules.yaml` | every rule, defined once, in 15 categories from macro to detail (190 rules: 156 on an indicator, 34 manual); a rule is an indicator plus the line to test; strategies reference rules by id |
| `config/settings.yaml` | refresh interval, which indicators fill the sidebar cards, option expiration windows, the release calendar |
| `data/symbols/<SYMBOL>/`, `data/market/` | what was downloaded, one file per answer (latest only; not in git): a restart reads it and asks a source again only when it is due. `result.json` in a symbol's folder is that symbol's computed result. Delete a folder to forget a symbol |
| `data/logs/stockboard.log` | written on every run (not in git): one line per fetch with its seconds, one per symbol, one summary per refresh; `grep "refresh done" data/logs/stockboard.log` |
| `config/symbols.yaml` | the symbols the dashboard follows, in order |
| `config/strategies/*.yaml` | strategies: gates, rules, per-strategy weights and veto flags (see `docs/strategy.md`) |
| `docs/design.md` | page design rules (colors, type, shape and states, five element families, status badges, layout) |
| `docs/indicator.md` | the three levels (indicator, rule, strategy), every indicator, its meaning and source, the fetch schedule |
| `docs/language.md` | English and Chinese glossary and writing rules |
| `docs/strategy.md` | strategy file format, scoring, pass veto |
| `stockboard_backend/` | Python package, one module per job, function names are `module_verb_object` |
| `static/index.html`, `static/rules.html`, `static/base.css`, `static/language.js`, `static/rule-card.js` | dashboard, rule catalog page (`/rules`), shared design tokens, interface text in both languages, the hover card that shows a rule's full record |
| `docs/deployment.md` | where it runs (Oracle VM, Tailscale), the firewall, how to operate and update it |
| `docs/api.md` | JSON API (`/api/v1`) for the page and any future client |
| `.claude/skills/` | skills that point Claude at the design and strategy docs |

## Two results per symbol

- **Pass**: false if any rule marked `veto: true` fails.
- **Score**: weighted share of passed rules, 0 to 100.

They are independent. Rules with missing data show 未知 and are left out of the score. Option rules need live bid and ask quotes, so they show 未知 while the market is closed.
