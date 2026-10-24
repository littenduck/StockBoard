---
name: stockboard-strategy
description: Use when writing or editing a StockBoard strategy file in strategies/ or adding an indicator. Covers rule format, scoring, the pass veto and indicator ids.
---

Read `docs/strategy.md` for the file format and scoring, and `docs/indicator.md` for the indicator ids a rule may use. A new indicator must be added to `docs/indicator.md` and to `stockboard_backend/indicator_calculation.py` before a rule uses it. Every text a person reads is written in both languages as `{en, zh}`, using the glossary in `docs/language.md`; run `pytest` to check. Function names follow `module_verb_object` with no abbreviations.
