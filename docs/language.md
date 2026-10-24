# Language

The interface has two languages, English (`en`, default) and Chinese (`zh`, shown as `zh-Hans`).
In Chinese mode Chinese is the main text and the English appears underneath in small gray type (see `docs/design.md`, Language).

## Writing both languages

- Every text in `config/rules.yaml`, `strategies/*.yaml` and `config/settings.yaml` that a person reads is an object `{en: "...", zh: "..."}`. Both are required and non-empty; the app refuses to start otherwise.
- English must not contain Chinese characters. Use the glossary below; do not invent variants.
- Technical terms stay English in both languages: GATE, VIX, SPX, DTE, IV, RV30, FGI, HY, bp, Delta, Put, Call.
- Interface strings live in `static/language.js` (`UI_TEXT`), with the same rule.

## Glossary

| 中文 | English |
|