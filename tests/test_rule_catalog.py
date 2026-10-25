import os

import pytest

from stockboard_backend import indicator_calculation
from stockboard_backend.localized_text import CHINESE_CHARACTER_PATTERN, LocalizedText
from stockboard_backend.rule_catalog import RetiredRule, RuleCatalog, RuleCatalogEntry, RuleGroup, \
    rule_catalog_load_rule_catalog_from_yaml_file, rule_catalog_validate_rule_catalog_against_known_indicators
from stockboard_backend.settings_loader import PROJECT_DIRECTORY, settings_loader_load_settings_from_yaml_file
from stockboard_backend.strategy_loader import strategy_loader_build_rule_definition_from_catalog, \
    strategy_loader_load_all_strategy_definitions_from_directory

CATALOG_FILE_PATH = os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml")


def test_project_catalog_and_strategies_are_valid():
    catalog = rule_catalog_load_rule_catalog_from_yaml_file(CATALOG_FILE_PATH)
    assert rule_catalog_validate_rule_catalog_against_known_indicators(
        catalog, indicator_calculation.KNOWN_INDICATOR_ID_SET) == []
    strategy_by_id = strategy_loader_load_all_strategy_definitions_from_directory(
        os.path.join(PROJECT_DIRECTORY, "strategies"), catalog)
    assert "sell_put_four_in_one" in strategy_by_id


def build_entry(rule_id, **overrides):
    fields = dict(name=LocalizedText("n", "名"), description=LocalizedText("d", "述"), method="computed",
                  quantifiable="yes", backtestable="yes", status="built", indicator="x", operator="less_than", value=1)
    fields.update(overrides)
    return RuleCatalogEntry(rule_id, **fields)


def build_catalog(*entry_list):
    group = RuleGroup("TST", LocalizedText("T", "T"), LocalizedText("", ""))
    return RuleCatalog([group], {entry.rule_id: entry for entry in entry_list})


def test_strategy_rule_takes_the_test_from_the_catalog_and_the_weight_from_the_strategy():
    catalog = build_catalog(build_entry("TST-01"))
    rule = strategy_loader_build_rule_definition_from_catalog({"rule_id": "TST-01", "weight": 2}, catalog)
    assert (rule.name.en, rule.indicator, rule.operator, rule.value, rule.weight, rule.veto) == ("n", "x", "less_than", 1, 2, False)
    assert strategy_loader_build_rule_definition_from_catalog(
        {"rule_id": "TST-01", "weight": 5, "veto": True}, catalog).veto is True


def test_manual_rule_can_be_listed_but_never_vetoes():
    catalog = build_catalog(build_entry("TST-01", method="manual", status="no_data", indicator=None, operator=None, value=None))
    rule = strategy_loader_build_rule_definition_from_catalog({"rule_id": "TST-01", "weight": 3}, catalog)
    assert rule.indicator is None and rule.method == "manual"
    with pytest.raises(ValueError):
        strategy_loader_build_rule_definition_from_catalog({"rule_id": "TST-01", "weight": 5, "veto": True}, catalog)


def test_strategy_rule_errors():
    catalog = build_catalog(build_entry("TST-01"))
    for raw_rule in ({"rule_id": "TST-99", "weight": 3}, {"rule_id": "TST-01"}, {"rule_id": "TST-01", "weight": 6},
                     {"rule_id": "TST-01", "weight": 0}, {"rule_id": "TST-01", "weight": 2.5},
                     {"rule_id": "TST-01", "weight": 3, "veto": "yes"}, {"rule_id": "TST-01", "weight": 3, "variant_group": "g"}):
        with pytest.raises(ValueError):
            strategy_loader_build_rule_definition_from_catalog(raw_rule, catalog)


def test_catalog_validation_finds_problems():
    catalog = build_catalog(build_entry("TST-01", indicator=None),
                            build_entry("TST-02", status="soon"),
                            build_entry("TST-03", band_of="TST-77"),
                            build_entry("TST-04", operator="near"),
                            build_entry("TST-05", value=None),
                            build_entry("TST-06", backtestable="maybe"),
                            build_entry("ZZZ-01", indicator="x"))
    assert len(rule_catalog_validate_rule_catalog_against_known_indicators(catalog, {"x"})) == 7


def test_history_fields_follow_the_format():
    catalog = build_catalog(build_entry("TST-01", history_source="fred:DGS10", history_start="1962-01-02"),
                            build_entry("TST-02", history_source="fred", history_start="1962"),
                            build_entry("TST-03", history_source="fred:DGS10"),
                            build_entry("TST-04", history_source="paid_vendor", history_start="2020-01-01"),
                            build_entry("TST-05", history_source="fred", history_start="last year"))
    errors = rule_catalog_validate_rule_catalog_against_known_indicators(catalog, {"x"})
    assert len(errors) == 3 and all(rule_id in " ".join(errors) for rule_id in ("TST-03", "TST-04", "TST-05"))


def test_a_retired_id_cannot_come_back():
    catalog = build_catalog(build_entry("TST-01"))
    catalog.retired_rule_list = [RetiredRule("TST-01", [], LocalizedText("gone", "没了")), RetiredRule("TST-02", ["A01"], LocalizedText("gone", "没了"))]
    errors = rule_catalog_validate_rule_catalog_against_known_indicators(catalog, {"x"})
    assert len(errors) == 1 and "TST-01" in errors[0]


def test_manual_rules_are_never_backtestable():
    catalog = rule_catalog_load_rule_catalog_from_yaml_file(CATALOG_FILE_PATH)
    for entry in catalog.rule_entry_by_id.values():
        if entry.method == "manual":
            assert entry.backtestable == "no", entry.rule_id


def test_every_backtestable_rule_names_its_free_history():
    catalog = rule_catalog_load_rule_catalog_from_yaml_file(CATALOG_FILE_PATH)
    for entry in catalog.rule_entry_by_id.values():
        if entry.backtestable == "yes":
            assert entry.history_source and entry.history_start, entry.rule_id
            assert entry.method != "manual" and entry.status != "no_data", entry.rule_id
            assert entry.operator, entry.rule_id + " has no line to test"
        else:
            assert entry.history_source is None and entry.history_start is None, entry.rule_id


def test_the_project_catalog_has_no_retired_id_and_keeps_every_legacy_id():
    catalog = rule_catalog_load_rule_catalog_from_yaml_file(CATALOG_FILE_PATH)
    assert {retired.rule_id for retired in catalog.retired_rule_list} == {"VAL-02", "LIQ-02", "EVT-09"}
    kept = {legacy for entry in catalog.rule_entry_by_id.values() for legacy in entry.legacy_id}
    kept |= {legacy for retired in catalog.retired_rule_list for legacy in retired.legacy_id}
    assert len(kept) == 119


def test_todo_rule_may_name_an_indicator_that_does_not_exist_yet():
    catalog = build_catalog(build_entry("TST-01", status="todo", indicator="not_written_yet"))
    assert rule_catalog_validate_rule_catalog_against_known_indicators(catalog, set()) == []


FORBIDDEN_ENGLISH_WORD_LIST = ["loose grade", "strict grade", "loose level", "strict level", "Not applicable", "not applicable"]


def assert_localized_text_is_complete(localized_text, field_name):
    assert localized_text.en and localized_text.zh, field_name
    assert not CHINESE_CHARACTER_PATTERN.search(localized_text.en), "Chinese left in English: " + field_name
    for word in FORBIDDEN_ENGLISH_WORD_LIST:
        assert word not in localized_text.en, "off-glossary '{}' in {}".format(word, field_name)


def test_every_catalog_text_is_bilingual_and_follows_the_glossary():
    catalog = rule_catalog_load_rule_catalog_from_yaml_file(CATALOG_FILE_PATH)
    for group in catalog.rule_group_list:
        assert_localized_text_is_complete(group.display_name, "group " + group.group_id)
        assert_localized_text_is_complete(group.description, "group description " + group.group_id)
    for entry in catalog.rule_entry_by_id.values():
        assert_localized_text_is_complete(entry.name, "rule name " + entry.rule_id)
        assert_localized_text_is_complete(entry.description, "rule description " + entry.rule_id)
        if entry.note:
            assert_localized_text_is_complete(entry.note, "note " + entry.rule_id)


def test_every_tier_line_points_to_a_main_rule_of_the_same_category():
    catalog = rule_catalog_load_rule_catalog_from_yaml_file(CATALOG_FILE_PATH)
    for entry in catalog.rule_entry_by_id.values():
        if entry.band_of:
            main_rule = catalog.rule_entry_by_id[entry.band_of]
            assert main_rule.band_of is None, entry.rule_id + " points to a rule that is itself a tier line"
            assert main_rule.group_id == entry.group_id, entry.rule_id


def test_every_strategy_and_indicator_text_is_bilingual():
    catalog = rule_catalog_load_rule_catalog_from_yaml_file(CATALOG_FILE_PATH)
    strategy_by_id = strategy_loader_load_all_strategy_definitions_from_directory(
        os.path.join(PROJECT_DIRECTORY, "strategies"), catalog)
    for strategy in strategy_by_id.values():
        for field_name in ("display_name", "source", "summary", "help_text"):
            assert_localized_text_is_complete(getattr(strategy, field_name), strategy.strategy_id + " " + field_name)
        assert strategy.help_text.en.count("\n\n") == strategy.help_text.zh.count("\n\n"), \
            strategy.strategy_id + " help paragraphs must pair up"
        for gate in strategy.gate_list:
            assert_localized_text_is_complete(gate.display_name, strategy.strategy_id + " " + gate.gate_id)
    settings = settings_loader_load_settings_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "settings.yaml"))
    assert settings.default_language == "en"
    for indicator_setting in settings.market_indicator_list:
        assert_localized_text_is_complete(indicator_setting.display_name, indicator_setting.indicator_id)
