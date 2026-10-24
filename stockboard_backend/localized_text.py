"""Text a person reads, in English and Chinese. Data files write it as {en: "...", zh: "..."}."""
import re
from dataclasses import dataclass
from typing import Any, Optional

LANGUAGE_CODE_SET = {"en", "zh"}
CHINESE_CHARACTER_PATTERN = re.compile(r"[㐀-鿿]")


@dataclass
class LocalizedText:
    en: str
    zh: str


def localized_text_build_from_raw_value(raw_value: Any, field_name: str) -> LocalizedText:
    """Raises ValueError naming the field when the value is not {en, zh} with both filled in."""
    if not isinstance(raw_value, dict):
        raise ValueError("{} must be {{en: ..., zh: ...}}, got {!r}".format(field_name, raw_value))
    for language_code in sorted(LANGUAGE_CODE_SET):
        text = raw_value.get(language_code)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("{} is missing its {} text".format(field_name, language_code))
    return LocalizedText(en=raw_value["en"].strip(), zh=raw_value["zh"].strip())


def localized_text_build_optional_from_raw_value(raw_value: Any, field_name: str) -> Optional[LocalizedText]:
    return None if raw_value is None else localized_text_build_from_raw_value(raw_value, field_name)
