import os

import pytest

from stockboard_backend import indicator_calculation
from stockboard_backend.rule_catalog import RuleCatalog, RuleCatalogEntry, RuleGroup, \
    rule_catalog_load_rule_catalog_from_yaml_file, rule_catalog_validate_rule_catalog_against_known_indicators
from stockboard_backend.settings_loader import PROJECT_DIRECTORY
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


def build_catalog(*entry_list):
    return RuleCatalog([RuleGroup("A", "A", "")], {entry.rule_id: entry for entry in entry_list})


def test_strategy_rule_takes_definition_from_catalog_and_weight_override():
    catalog = build_catalog(RuleCatalogEntry("A01", "x < 1", 4, "automatic", "x", "less_than", 1))
    rule = strategy_loader_build_rule_definition_from_catalog({"rule_id": "A01", "weight": 2}, catalog)
    assert (rule.description, rule.indicator, rule.weight) == ("x < 1", "x", 2)
    assert strategy_loader_build_rule_definition_from_catalog({"rule_id": "A01"}, catalog).weight == 4


def test_strategy_rule_errors():
    catalog = build_catalog(RuleCatalogEntry("A01", "manual", 3, "user_answer"),
                            RuleCatalogEntry("A02", "copy", alias_of="A01"))
    for rule_id in ("A01", "A02", "A99"):
        with pytest.raises(ValueError):
            strategy_loader_build_rule_definition_from_catalog({"rule_id": rule_id}, catalog)


def test_catalog_validation_finds_problems():
    catalog = build_catalog(RuleCatalogEntry("A01", "no indicator", 3, "automatic"),
                            RuleCatalogEntry("A02", "copy", alias_of="A77"),
                            RuleCatalogEntry("B01", "no group", 3, "user_answer"))
    assert len(rule_catalog_validate_rule_catalog_against_known_indicators(catalog, set())) == 3
