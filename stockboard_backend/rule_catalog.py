"""Load config/rules.yaml: the one place where every rule is defined. A rule has no weight; strategies give it one."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import yaml

from stockboard_backend.localized_text import (
    LocalizedText, localized_text_build_from_raw_value, localized_text_build_optional_from_raw_value,
)

STATUS_SET = {"built", "todo", "no_data"}
METHOD_SET = {"api_fetch", "scrape", "computed", "ai_search", "manual"}
OPERATOR_SET = {"less_than", "less_or_equal", "greater_than", "greater_or_equal", "between", "is_true"}
QUANTIFIABLE_SET = {"yes", "part", "no"}


@dataclass
class RuleGroup:
    group_id: str
    display_name: LocalizedText
    description: LocalizedText
    aspect: Optional[LocalizedText] = None


@dataclass
class RuleCatalogEntry:
    rule_id: str
    name: LocalizedText
    description: LocalizedText
    method: Optional[str] = None
    quantifiable: Optional[str] = None
    status: Optional[str] = None
    indicator: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    band_of: Optional[str] = None
    legacy_id: List[str] = field(default_factory=list)
    note: Optional[LocalizedText] = None

    @property
    def group_id(self) -> str:
        return self.rule_id[:3]


@dataclass
class RuleCatalog:
    rule_group_list: List[RuleGroup]
    rule_entry_by_id: Dict[str, RuleCatalogEntry]


def rule_catalog_load_rule_catalog_from_yaml_file(rule_catalog_file_path: str) -> RuleCatalog:
    with open(rule_catalog_file_path, encoding="utf8") as rule_catalog_file:
        raw = yaml.safe_load(rule_catalog_file)
    entry_list = [RuleCatalogEntry(**{
        **raw_rule,
        "name": localized_text_build_from_raw_value(raw_rule.get("name"), "rule {} name".format(raw_rule["rule_id"])),
        "description": localized_text_build_from_raw_value(raw_rule.get("description"), "rule {} description".format(raw_rule["rule_id"])),
        "note": localized_text_build_optional_from_raw_value(raw_rule.get("note"), "rule {} note".format(raw_rule["rule_id"])),
    }) for raw_rule in raw["rule_list"]]
    group_list = [RuleGroup(
        group_id=raw_group["group_id"],
        display_name=localized_text_build_from_raw_value(raw_group.get("display_name"), "group {} name".format(raw_group["group_id"])),
        description=localized_text_build_from_raw_value(raw_group.get("description"), "group {} description".format(raw_group["group_id"])),
        aspect=localized_text_build_optional_from_raw_value(raw_group.get("aspect"), "group {} aspect".format(raw_group["group_id"])),
    ) for raw_group in raw["rule_group_list"]]
    return RuleCatalog(
        rule_group_list=group_list,
        rule_entry_by_id={entry.rule_id: entry for entry in entry_list},
    )


def rule_catalog_validate_rule_catalog_against_known_indicators(
    rule_catalog: RuleCatalog, known_indicator_id_set: Set[str],
) -> List[str]:
    """Returns error messages; an empty list means the catalog is valid.
    An indicator only has to exist for a rule that is already built; a todo rule may name one that is not written yet."""
    error_list = []
    group_id_set = {group.group_id for group in rule_catalog.rule_group_list}
    for entry in rule_catalog.rule_entry_by_id.values():
        if entry.group_id not in group_id_set:
            error_list.append("rule {} has no group {}".format(entry.rule_id, entry.group_id))
        if entry.status not in STATUS_SET:
            error_list.append("rule {} has unknown status {}".format(entry.rule_id, entry.status))
        if entry.method not in METHOD_SET:
            error_list.append("rule {} has unknown method {}".format(entry.rule_id, entry.method))
        if entry.quantifiable not in QUANTIFIABLE_SET:
            error_list.append("rule {} has unknown quantifiable {}".format(entry.rule_id, entry.quantifiable))
        if entry.operator is not None and entry.operator not in OPERATOR_SET:
            error_list.append("rule {} has unknown operator {}".format(entry.rule_id, entry.operator))
        if entry.operator not in (None, "is_true") and entry.value is None:
            error_list.append("rule {} has an operator but no value".format(entry.rule_id))
        if entry.band_of and entry.band_of not in rule_catalog.rule_entry_by_id:
            error_list.append("rule {} points to missing rule {}".format(entry.rule_id, entry.band_of))
        if entry.status == "built":
            if not entry.indicator:
                error_list.append("rule {} is built but has no indicator".format(entry.rule_id))
            elif entry.indicator not in known_indicator_id_set:
                error_list.append("rule {} uses unknown indicator {}".format(entry.rule_id, entry.indicator))
    return error_list
