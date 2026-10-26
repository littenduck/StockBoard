---
name: stockboard-strategy
description: Use when writing or editing a StockBoard strategy file in config/strategies/ or adding an indicator. Covers rule format, scoring, the pass veto and indicator ids.
---

Read `docs/strategy.md` for the file format and scoring, and `docs/indicator.md` for the indicator ids a rule may use. A new indicator must be added to `config/indicators.yaml` (with its `fetch_group`, `fetch_every` and `max_age`), to `docs/indicator.md` and to `PRODUCED_INDICATOR_ID_SET` in `stockboard_backend/indicator_calculation.py` before a rule uses it; a test checks the YAML and the code agree. A rule goes in `config/rules.yaml` and only names the indicator and the line to test. Every text a person reads is written in both languages as `{en, zh}`, using the glossary in `docs/language.md`; run `pytest` to check. Function names follow `module_verb_object` with no abbreviations.
