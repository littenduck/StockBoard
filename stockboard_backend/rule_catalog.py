"""Load config/rules.yaml: the one place where every rule is defined."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import yaml

from stockboard_backend.localized_text import (
    LocalizedText, localized_text_build_from_raw_value, localized_text_build_optional_from_raw_value,
)

AVAILABILITY_SET = {"automatic", "missing_data_source", "account_data", "user_answer", "trade_plan", "not_implemented"}


@dataclass
class RuleGroup:
    group_id: str
    display_name: LocalizedText
    description: LocalizedText


@dataclass
class RuleCatalogEntry:
    rule_id: str
    description: LocalizedText
    default_weight: Optional[int] = None
    availability: Optional[str] = None
    indicator: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    alias_of: Optional[str] = None
    note: Optional[LocalizedText] = None

    @property
    def group_id(self) -> str:
        return self.rule_id[0]


@dataclass
class RuleCatalog:
    rule_group_list: List[RuleGroup]
    rule_entry_by_id: Dict[str, RuleCatalogEntry]


def rule_catalog_load_rule_catalog_from_yaml_file(rule_catalog_file_path: str) -> RuleCatalog:
    with open(rule_catalog_file_path) as rule_catalog_file:
        raw = yaml.safe_load(rule_catalog_file)
    entry_list = [RuleCatalogEntry(**{
        **raw_rule,
        "description": localized_text_build_from_raw_value(raw_rule.get("description"), "rule {} description".format(raw_rule["rule_id"])),
        "note": localized_text_build_optional_from_raw_value(raw_rule.get("note"), "rule {} note".format(raw_rule["rule_id"])),
    }) for raw_rule in raw["rule_list"]]
    group_list = [RuleGroup(
        group_id=raw_group["group_id"],
        display_name=localized_text_build_from_raw_value(raw_group.get("display_name"), "group {} name".format(raw_group["group_id"])),
        description=localized_text_build_from_raw_value(raw_group.get("description"), "group {} description".format(raw_group["group_id"])),
    ) for raw_group in raw["rule_group_list"]]
    return RuleCatalog(
        rule_group_list=group_list,
        rule_entry_by_id={entry.rule_id: entry for entry in entry_list},
    )


def rule_catalog_validate_rule_catalog_against_known_indicators(
    rule_catalog: RuleCatalog, known_indicator_id_set: Set[str],
) -> List[str]:
    """Returns error messages; an empty list means the catalog is valid."""
    error_list = []
    group_id_set = {group.group_id for group in rule_catalog.rule_group_list}
    for entry in rule_catalog.rule_entry_by_id.values():
        if entry.group_id not in group_id_set:
            error_list.append("rule {} has no group {}".format(entry.rule_id, entry.group_id))
        if entry.alias_of:
            if entry.alias_of not in rule_catalog.rule_entry_by_id:
                error_list.append("rule {} points to missing rule {}".format(entry.rule_id, entry.alias_of))
            continue
        if entry.availability not in AVAILABILITY_SET:
            error_list.append("rule {} has unknown availability {}".format(entry.rule_id, entry.availability))
        if entry.indicator and entry.indicator not in known_indicator_id_set:
            error_list.append("rule {} uses unknown indicator {}".format(entry.rule_id, entry.indicator))
        if entry.availability == "automatic" and not entry.indicator:
            error_list.append("rule {} is automatic but has no indicator".format(entry.rule_id))
    return error_list
