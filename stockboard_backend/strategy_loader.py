"""Load strategy YAML files into StrategyDefinition objects."""
import glob
import os
from typing import Dict, List, Set

import yaml

from stockboard_backend.strategy_evaluation import (
    GateDefinition, RuleDefinition, StrategyDefinition, StrategyThresholds,
)


def strategy_loader_load_strategy_definition_from_yaml_file(strategy_file_path: str) -> StrategyDefinition:
    with open(strategy_file_path) as strategy_file:
        raw = yaml.safe_load(strategy_file)
    gate_list = [
        GateDefinition(
            gate_id=raw_gate["gate_id"], display_name=raw_gate["display_name"],
            per_expiration_window=raw_gate.get("per_expiration_window", False),
            rule_list=[RuleDefinition(
                rule_id=raw_rule["rule_id"], description=raw_rule["description"], indicator=raw_rule["indicator"],
                operator=raw_rule["operator"], weight=raw_rule["weight"], value=raw_rule.get("value"),
                variant_group=raw_rule.get("variant_group")) for raw_rule in raw_gate["rules"]])
        for raw_gate in raw["gates"]
    ]
    return StrategyDefinition(
        strategy_id=raw["strategy_id"], display_name=raw["display_name"], source=raw.get("source", ""),
        thresholds=StrategyThresholds(**raw.get("thresholds", {})), gate_list=gate_list)


def strategy_loader_load_all_strategy_definitions_from_directory(
    strategy_directory_path: str,
) -> Dict[str, StrategyDefinition]:
    strategy_definition_by_id = {}
    for strategy_file_path in sorted(glob.glob(os.path.join(strategy_directory_path, "*.yaml"))):
        strategy_definition = strategy_loader_load_strategy_definition_from_yaml_file(strategy_file_path)
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
