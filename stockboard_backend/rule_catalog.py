"""Load config/rules.yaml: the one place where every rule is defined. A rule has no weight; strategies give it one.
A rule that names an indicator takes that indicator's method, history and status from config/indicators.yaml."""
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import yaml

from stockboard_backend.indicator_registry import IndicatorRegistry, indicator_registry_load_from_yaml_file
from stockboard_backend.localized_text import (
    LocalizedText, localized_text_build_from_raw_value, localized_text_build_optional_from_raw_value,
)

STATUS_SET = {"built", "todo", "no_data"}
METHOD_SET = {"api_fetch", "scrape", "computed", "ai_search", "manual"}
OPERATOR_SET = {"less_than", "less_or_equal", "greater_than", "greater_or_equal", "between", "is_true"}
QUANTIFIABLE_SET = {"yes", "part", "no"}
BACKTESTABLE_SET = {"yes", "no"}
# history_source is "name" or "name:detail" (for example fred:DGS10); the name must be one of these free sources.
KNOWN_HISTORY_SOURCE_NAME_SET = {
    "fred", "alfred", "cboe", "edgar", "dolthub", "yfinance", "cnn", "aaii", "naaim", "finra", "shiller", "damodaran",
    "gpr", "federalreserve", "sec", "fja05680", "wayback", "ritter", "rule",
}
HISTORY_START_PATTERN = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")  # a year, a month or a day


@dataclass
class RetiredRule:
    rule_id: str
    legacy_id: List[str]
    reason: LocalizedText


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
    backtestable: Optional[str] = None
    status: Optional[str] = None
    indicator: Optional[str] = None  # the indicator_name; the rule file writes the short id (indicator_id) and the loader resolves it
    indicator_id: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    band_of: Optional[str] = None
    history_source: Optional[str] = None
    history_start: Optional[str] = None
    legacy_id: List[str] = field(default_factory=list)
    note: Optional[LocalizedText] = None
    indicator_description: Optional[LocalizedText] = None  # what the indicator measures, from config/indicators.yaml
    fetch_group: Optional[str] = None  # the three below come from the indicator
    fetch_every: Optional[str] = None
    max_age: Optional[str] = None

    @property
    def group_id(self) -> str:
        return self.rule_id[:3]


@dataclass
class RuleCatalog:
    rule_group_list: List[RuleGroup]
    rule_entry_by_id: Dict[str, RuleCatalogEntry]
    retired_rule_list: List[RetiredRule] = field(default_factory=list)
    indicator_registry: Optional[IndicatorRegistry] = None


INDICATOR_OWNED_FIELD_LIST = ["method", "quantifiable", "backtestable", "history_source", "history_start", "status"]


def rule_catalog_merge_indicator_fields(raw_rule: dict, registry: Optional[IndicatorRegistry]) -> dict:
    """The facts a rule shares with its indicator. A rule must not repeat them, so they can never disagree."""
    indicator = registry.indicator_by_id.get(raw_rule.get("indicator")) if registry and raw_rule.get("indicator") else None
    if indicator is None:
        return raw_rule
    repeated = [name for name in INDICATOR_OWNED_FIELD_LIST if name in raw_rule]
    if repeated:
        raise ValueError("rule {} repeats {} that indicator {} owns; delete them from config/rules.yaml".format(
            raw_rule["rule_id"], ", ".join(repeated), indicator.indicator_name))
    return {**raw_rule, "indicator": indicator.indicator_name, "indicator_id": indicator.indicator_id,
            **{name: getattr(indicator, name) for name in INDICATOR_OWNED_FIELD_LIST},
            "indicator_description": indicator.description, "fetch_group": indicator.fetch_group, "fetch_every": indicator.fetch_every, "max_age": indicator.max_age}


LINE_SYMBOL_BY_OPERATOR = {"less_than": "<", "less_or_equal": "≤", "greater_than": ">", "greater_or_equal": "≥"}


def rule_catalog_describe_line(entry: "RuleCatalogEntry") -> str:
    """The test of a rule in a few characters: '< 4.5', '15 to 20', 'yes'."""
    if entry.operator == "is_true":
        return "yes"
    if entry.operator == "between":
        return "{} to {}".format(*entry.value)
    return "{} {}".format(LINE_SYMBOL_BY_OPERATOR.get(entry.operator, "?"), entry.value)


def rule_catalog_find_rule_list_of_indicator(rule_catalog: "RuleCatalog", indicator_name: str) -> list:
    """Every rule that tests this indicator, in catalog order: the lines of one measure."""
    return [entry for entry in rule_catalog.rule_entry_by_id.values() if entry.indicator == indicator_name]


def rule_catalog_load_rule_catalog_from_yaml_file(rule_catalog_file_path: str, indicator_file_path: Optional[str] = None) -> RuleCatalog:
    """indicator_file_path defaults to indicators.yaml next to the rule file; without one the rules must carry their own fields."""
    indicator_file_path = indicator_file_path or os.path.join(os.path.dirname(rule_catalog_file_path), "indicators.yaml")
    registry = (indicator_registry_load_from_yaml_file(indicator_file_path)
                if os.path.exists(indicator_file_path) else None)
    with open(rule_catalog_file_path, encoding="utf8") as rule_catalog_file:
        raw = yaml.safe_load(rule_catalog_file)
    entry_list = [RuleCatalogEntry(**{
        **rule_catalog_merge_indicator_fields(raw_rule, registry),
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
    retired_rule_list = [RetiredRule(
        rule_id=raw_retired["rule_id"], legacy_id=raw_retired.get("legacy_id") or [],
        reason=localized_text_build_from_raw_value(raw_retired.get("reason"), "retired rule {} reason".format(raw_retired["rule_id"])),
    ) for raw_retired in raw.get("retired_rule_list") or []]
    return RuleCatalog(
        rule_group_list=group_list,
        rule_entry_by_id={entry.rule_id: entry for entry in entry_list},
        retired_rule_list=retired_rule_list,
        indicator_registry=registry,
    )


def rule_catalog_validate_rule_catalog_against_known_indicators(
    rule_catalog: RuleCatalog, known_indicator_name_set: Set[str],
) -> List[str]:
    """Returns error messages; an empty list means the catalog is valid.
    An indicator only has to exist for a rule that is already built; a todo rule may name one that is not written yet."""
    error_list = []
    group_id_set = {group.group_id for group in rule_catalog.rule_group_list}
    registry = rule_catalog.indicator_registry
    for entry in rule_catalog.rule_entry_by_id.values():
        if entry.group_id not in group_id_set:
            error_list.append("rule {} has no group {}".format(entry.rule_id, entry.group_id))
        if entry.status not in STATUS_SET:
            error_list.append("rule {} has unknown status {}".format(entry.rule_id, entry.status))
        if entry.method not in METHOD_SET:
            error_list.append("rule {} has unknown method {}".format(entry.rule_id, entry.method))
        if entry.quantifiable not in QUANTIFIABLE_SET:
            error_list.append("rule {} has unknown quantifiable {}".format(entry.rule_id, entry.quantifiable))
        if entry.backtestable not in BACKTESTABLE_SET:
            error_list.append("rule {} has unknown backtestable {}".format(entry.rule_id, entry.backtestable))
        if entry.operator is not None and entry.operator not in OPERATOR_SET:
            error_list.append("rule {} has unknown operator {}".format(entry.rule_id, entry.operator))
        if entry.operator not in (None, "is_true") and entry.value is None:
            error_list.append("rule {} has an operator but no value".format(entry.rule_id))
        if (entry.history_source is None) != (entry.history_start is None):
            error_list.append("rule {} needs history_source and history_start together".format(entry.rule_id))
        if entry.history_source is not None and entry.history_source.split(":")[0] not in KNOWN_HISTORY_SOURCE_NAME_SET:
            error_list.append("rule {} has unknown history source {}".format(entry.rule_id, entry.history_source))
        if entry.history_start is not None and not HISTORY_START_PATTERN.match(str(entry.history_start)):
            error_list.append("rule {} has a bad history_start {}".format(entry.rule_id, entry.history_start))
        if registry is not None and entry.indicator and entry.indicator not in registry.indicator_by_name:
            error_list.append("rule {} uses indicator {} that is not in config/indicators.yaml".format(entry.rule_id, entry.indicator))
        if registry is not None and entry.indicator_id and registry.indicator_by_id[entry.indicator_id].indicator_name != entry.indicator:
            error_list.append("rule {} has an indicator that does not match its id".format(entry.rule_id))
        if entry.band_of and entry.band_of not in rule_catalog.rule_entry_by_id:
            error_list.append("rule {} points to missing rule {}".format(entry.rule_id, entry.band_of))
        if entry.status == "built":
            if not entry.indicator:
                error_list.append("rule {} is built but has no indicator".format(entry.rule_id))
            elif entry.indicator not in known_indicator_name_set:
                error_list.append("rule {} uses unknown indicator {}".format(entry.rule_id, entry.indicator))
    for retired in rule_catalog.retired_rule_list:
        if retired.rule_id in rule_catalog.rule_entry_by_id:
            error_list.append("retired rule {} is back in the catalog; ids are never reused".format(retired.rule_id))
    return error_list
