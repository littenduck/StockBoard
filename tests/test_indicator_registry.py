import os

import pytest
import yaml

from stockboard_backend import indicator_calculation, indicator_registry, rule_catalog, settings_loader
from stockboard_backend.settings_loader import PROJECT_DIRECTORY

INDICATOR_FILE_PATH = os.path.join(PROJECT_DIRECTORY, "config", "indicators.yaml")


@pytest.fixture(scope="module")
def registry():
    return indicator_registry.indicator_registry_load_from_yaml_file(INDICATOR_FILE_PATH)


def test_the_project_registry_is_valid(registry):
    assert indicator_registry.indicator_registry_validate(registry) == []


def test_the_code_produces_exactly_the_built_indicators(registry):
    built = registry.built_indicator_name_set()
    assert built - indicator_calculation.PRODUCED_INDICATOR_NAME_SET == set(), "built in YAML but not produced by the code"
    assert indicator_calculation.PRODUCED_INDICATOR_NAME_SET - built == set(), "produced by the code but not built in YAML"


def test_durations_are_a_number_and_a_unit():
    parse = indicator_registry.indicator_registry_parse_duration_seconds
    assert parse("10m") == 600 and parse("6h") == 21600 and parse("3d") == 259200
    for bad in ("10", "m", "1w", "1.5h", ""):
        with pytest.raises(ValueError):
            parse(bad)


def test_a_group_is_fetched_as_often_as_its_busiest_indicator(registry):
    assert registry.group_fetch_every_seconds("yahoo_quote") == 600
    assert registry.group_fetch_every_seconds("edgar") == 86400


def write_registry(tmp_path, **changes):
    raw = yaml.safe_load(open(INDICATOR_FILE_PATH, encoding="utf8"))
    raw["indicator_list"][0].update(changes)
    path = tmp_path / "indicators.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf8")
    return indicator_registry.indicator_registry_load_from_yaml_file(str(path))


def test_validation_catches_a_bad_age_group_or_history(tmp_path):
    assert any("max_age shorter" in e for e in indicator_registry.indicator_registry_validate(write_registry(tmp_path, fetch_every="1d", max_age="1h")))
    assert any("not defined" in e for e in indicator_registry.indicator_registry_validate(write_registry(tmp_path, fetch_group="nowhere")))
    assert any("history" in e for e in indicator_registry.indicator_registry_validate(write_registry(tmp_path, history_source=None, history_start="2000")))
    assert any("duration" in e for e in indicator_registry.indicator_registry_validate(write_registry(tmp_path, fetch_every="soon")))


def test_rules_take_their_facts_from_the_indicator(registry):
    catalog = rule_catalog.rule_catalog_load_rule_catalog_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml"))
    indicator = registry.indicator_by_name["treasury_ten_year_yield"]
    for rule_id in ("R-MAC-03", "R-MAC-04"):  # two lines of one indicator
        entry = catalog.rule_entry_by_id[rule_id]
        assert (entry.method, entry.history_source, entry.status, entry.fetch_every, entry.max_age) == (
            indicator.method, indicator.history_source, indicator.status, indicator.fetch_every, indicator.max_age)
    assert catalog.rule_entry_by_id["R-POS-01"].method == "manual" and catalog.rule_entry_by_id["R-POS-01"].fetch_every is None


def test_a_rule_may_not_repeat_what_its_indicator_owns(registry):
    with pytest.raises(ValueError, match="repeats"):
        rule_catalog.rule_catalog_merge_indicator_fields(
            {"rule_id": "R-MAC-03", "indicator": registry.indicator_by_name["treasury_ten_year_yield"].indicator_id, "status": "built"}, registry)


def test_the_sidebar_reads_names_from_the_registry():
    settings = settings_loader.settings_loader_load_settings_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "settings.yaml"))
    assert [item.indicator_name for item in settings.market_indicator_list][:2] == ["vix_level", "vxn_level"]
    assert settings.market_indicator_list[0].is_higher_value_risky and settings.market_indicator_list[0].display_name.en == "VIX"


def test_every_indicator_has_a_short_id_and_a_long_name(registry):
    assert len(registry.indicator_by_id) == len(registry.indicator_by_name) == 122
    assert registry.indicator_by_id["I-001"].indicator_name == "federal_funds_target_rate_not_raised_in_182_days"
    ids = [indicator.indicator_id for indicator in registry.indicator_by_name.values()]
    assert ids == ["I-%03d" % number for number in range(1, 123)], "ids run 1 to 122 in file order"


def test_a_rule_resolves_its_indicator_id_to_the_name_and_keeps_the_id():
    catalog = rule_catalog.rule_catalog_load_rule_catalog_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml"))
    entry = catalog.rule_entry_by_id["R-MAC-03"]
    assert entry.indicator == "treasury_ten_year_yield" and entry.indicator_id == catalog.indicator_registry.indicator_by_name[entry.indicator].indicator_id


def test_validation_catches_a_bad_id_or_name(tmp_path):
    assert any("bad indicator_id" in e for e in indicator_registry.indicator_registry_validate(write_registry(tmp_path, indicator_id="I-1")))
    assert any("lower case" in e for e in indicator_registry.indicator_registry_validate(write_registry(tmp_path, indicator_name="Bad Name")))
