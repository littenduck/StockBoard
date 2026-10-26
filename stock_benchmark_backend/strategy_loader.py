"""Load strategy YAML files into StrategyDefinition objects. Rules come from the rule catalog by id."""
import glob
import os
from typing import Dict, List, Set

import yaml

from stock_benchmark_backend.localized_text import localized_text_build_from_raw_value
from stock_benchmark_backend.rule_catalog import RuleCatalog
from stock_benchmark_backend.strategy_evaluation import (
    GateDefinition, RuleDefinition, StrategyDefinition, StrategyThresholds,
)


def strategy_loader_build_rule_definition_from_catalog(raw_rule: dict, rule_catalog: RuleCatalog) -> RuleDefinition:
    """A strategy entry is {rule_id, weight, veto?}; the test itself comes from the catalog.
    A rule the app has no data for (a manual rule, or one without an indicator) is allowed; it always evaluates to unknown."""
    entry = rule_catalog.rule_entry_by_id.get(raw_rule["rule_id"])
    if entry is None:
        raise ValueError("rule {} is not in config/rules.yaml".format(raw_rule["rule_id"]))
    if "variant_group" in raw_rule:
        raise ValueError("rule {}: variant_group is retired; list each tier as its own rule".format(entry.rule_id))
    weight = raw_rule.get("weight")
    if not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= 5:
        raise ValueError("rule {}: weight must be an integer from 1 to 5".format(entry.rule_id))
    veto = raw_rule.get("veto", False)
    if not isinstance(veto, bool):
        raise ValueError("rule {}: veto must be true or false".format(entry.rule_id))
    if veto and entry.method == "manual":
        raise ValueError("rule {} is manual, it is always unknown and cannot be a veto".format(entry.rule_id))
    return RuleDefinition(
        rule_id=entry.rule_id, rule_name=entry.rule_name, description=entry.description, indicator=entry.indicator,
        operator=entry.operator, weight=weight, value=entry.value, veto=veto, method=entry.method, status=entry.status)


def strategy_loader_load_strategy_definition_from_yaml_file(
    strategy_file_path: str, rule_catalog: RuleCatalog,
) -> StrategyDefinition:
    with open(strategy_file_path, encoding="utf8") as strategy_file:
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
    strategy_definition: StrategyDefinition, known_indicator_name_set: Set[str],
) -> List[str]:
    """Returns error messages; an empty list means the strategy is valid."""
    error_list = []
    for gate in strategy_definition.gate_list:
        for rule in gate.rule_list:
            if rule.status == "built" and rule.indicator not in known_indicator_name_set:
                error_list.append("{}: rule {} uses unknown indicator {}".format(
                    strategy_definition.strategy_id, rule.rule_id, rule.indicator))
    return error_list
