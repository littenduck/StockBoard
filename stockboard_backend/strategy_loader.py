"""Load strategy YAML files into StrategyDefinition objects. Rules come from the rule catalog by id."""
import glob
import os
from typing import Dict, List, Set

import yaml

from stockboard_backend.localized_text import localized_text_build_from_raw_value
from stockboard_backend.rule_catalog import RuleCatalog
from stockboard_backend.strategy_evaluation import (
    GateDefinition, RuleDefinition, StrategyDefinition, StrategyThresholds,
)


def strategy_loader_build_rule_definition_from_catalog(raw_rule: dict, rule_catalog: RuleCatalog) -> RuleDefinition:
    """A strategy entry is {rule_id, weight?, variant_group?}; everything else comes from the catalog."""
    entry = rule_catalog.rule_entry_by_id.get(raw_rule["rule_id"])
    if entry is None:
        raise ValueError("rule {} is not in config/rules.yaml".format(raw_rule["rule_id"]))
    if entry.alias_of:
        raise ValueError("rule {} is a copy of {}; use {}".format(entry.rule_id, entry.alias_of, entry.alias_of))
    if not entry.indicator:
        raise ValueError("rule {} cannot be computed automatically ({})".format(entry.rule_id, entry.availability))
    return RuleDefinition(
        rule_id=entry.rule_id, description=entry.description, indicator=entry.indicator, operator=entry.operator,
        weight=raw_rule.get("weight", entry.default_weight), value=entry.value,
        variant_group=raw_rule.get("variant_group"))


def strategy_loader_load_strategy_definition_from_yaml_file(
    strategy_file_path: str, rule_catalog: RuleCatalog,
) -> StrategyDefinition:
    with open(strategy_file_path) as strategy_file:
        raw = yaml.safe_load(strategy_file)
    gate_list = [
        GateDefinition(
            gate_id=raw_gate["gate_id"], display_name=localized_text_build_from_raw_value(
                raw_gate.get("display_name"), "{} gate {} name".format(raw["strategy_id"], raw_gate["gate_id"])),
            per_expiration_window=raw_gate.get("per_expiration_window", False),
            rule_list=[strategy_loader_build_rule_definition_from_catalog(raw_rule, rule_catalog)
                       for raw_rule in raw_gate["rules"]])
        for raw_gate in raw["gates"]
    ]
    def localized_field(field_name: str):
        return localized_text_build_from_raw_value(raw.get(field_name), "{} {}".format(raw["strategy_id"], field_name))

    return StrategyDefinition(
        strategy_id=raw["strategy_id"], display_name=localized_field("display_name"), source=localized_field("source"),
        thresholds=StrategyThresholds(**raw.get("thresholds", {})), gate_list=gate_list,
        summary=localized_field("summary"), help_text=localized_field("help"))


def strategy_loader_load_all_strategy_definitions_from_directory(
    strategy_directory_path: str, rule_catalog: RuleCatalog,
) -> Dict[str, StrategyDefinition]:
    strategy_definition_by_id = {}
    for strategy_file_path in sorted(glob.glob(os.path.join(strategy_directory_path, "*.yaml"))):
        strategy_definition = strategy_loader_load_strategy_definition_from_yaml_file(strategy_file_path, rule_catalog)
        strategy_definition_by_id[strategy_definition.strategy_id] = strategy_definition
    return strategy_definition_by_id


def strategy_loader_validate_strategy_definition_against_known_indicators(
    strategy_definition: StrategyDefinition, known_indicator_id_set: Set[str],
) -> List[str]:
    """Returns error messages; an empty list means the strategy is valid."""
    error_list = []
    for gate in strategy_definition.gate_list:
        for rule in gate.rule_list:
            if rule.indicator not in known_indicator_id_set:
                error_list.append("{}: rule {} uses unknown indicator {}".format(
                    strategy_definition.strategy_id, rule.rule_id, rule.indicator))
            if not 1 <= rule.weight <= 5:
                error_list.append("{}: rule {} weight must be 1 to 5".format(
                    strategy_definition.strategy_id, rule.rule_id))
    return error_list
