import pytest

from stockboard_backend.localized_text import (
    LocalizedText, localized_text_build_from_raw_value, localized_text_build_optional_from_raw_value,
)


def test_builds_and_trims_both_languages():
    assert localized_text_build_from_raw_value({"en": " Pass ", "zh": "通过"}, "f") == LocalizedText("Pass", "通过")


@pytest.mark.parametrize("raw_value", [{"en": "Pass"}, {"en": "", "zh": "通过"}, {"en": "Pass", "zh": "  "}, "通过", None])
def test_rejects_incomplete_values_and_names_the_field(raw_value):
    with pytest.raises(ValueError, match="rule A01 description"):
        localized_text_build_from_raw_value(raw_value, "rule A01 description")


def test_optional_value():
    assert localized_text_build_optional_from_raw_value(None, "note") is None
    assert localized_text_build_optional_from_raw_value({"en": "a", "zh": "甲"}, "note").zh == "甲"
