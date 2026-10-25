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
    old_id: str
    legacy_id: List[str]
    reason: LocalizedText


@dataclass
class RuleTopic:
    topic_id: str
    display_name: LocalizedText


@dataclass
class RuleGroup:
    group_id: str
    display_name: LocalizedText
    description: LocalizedText
    aspect: Optional[LocalizedText] = None
    topic_list: List[RuleTopic] = field(default_factory=list)


@dataclass
class RuleCatalogEntry:
    rule_id: str
    rule_name: str  # a short lower case name with underscores, like an indicator_name
    description: LocalizedText
    topic: Optional[str] = None  # the topic of its group, in config/rules.yaml
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
    unit: Optional[str] = None  # the unit of the indicator, shown after the number of a line
    indicator_description: Optional[LocalizedText] = None  # what the indicator measures, from config/indicators.yaml
    fetch_group: Optional[str] = None  # the three below come from the indicator
    fetch_every: Optional[str] = None
    max_age: Optional[str] = None

    @property
    def group_id(self) -> str:
        """R-MAC-03 belongs to the group MAC."""
        return self.rule_id.split("-")[1] if self.rule_id.startswith("R-") else self.rule_id[:3]


@dataclass
class RuleCatalog:
    rule_group_list: List[RuleGroup]
    rule_entry_by_id: Dict[str, RuleCatalogEntry]
    retired_rule_list: List[RetiredRule] = field(default_factory=list)
    indicator_registry: Optional[IndicatorRegistry] = None


RULE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
RULE_ID_PATTERN = re.compile(r"^R-([A-Z]{3})-(\d{2})$")
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
            "indicator_description": indicator.description, "unit": indicator.unit, "fetch_group": indicator.fetch_group, "fetch_every": indicator.fetch_every, "max_age": indicator.max_age}


LINE_SYMBOL_BY_OPERATOR = {"less_than": "<", "less_or_equal": "≤", "greater_than": ">", "greater_or_equal": "≥"}


ZH_UNIT_BY_UNIT = {"claims": "次申请", "purchases": "笔买入", "contracts": "张", "days": "天", "USD": "美元", "points": "点"}


def rule_catalog_describe_line(entry: "RuleCatalogEntry") -> dict:
    """The test of a rule in a few characters, in both languages: '< 4.5%' / '< 4.5%', '15 to 20' / '15 到 20', 'yes' / '是'."""
    if entry.operator == "is_true":
        return {"en": "yes", "zh": "是"}
    unit = entry.unit or ""

    def number(value):
        return format(value, ",") if isinstance(value, int) else str(value)

    def amount(value):  # one number with its unit; money reads as $200 billion and 2000 亿美元
        if unit == "USD billion":
            return {"en": "${:,} billion".format(value), "zh": "{:,} 亿美元".format(value * 10)}
        if unit == "USD":
            return {"en": "${}".format(number(value)), "zh": "{} 美元".format(number(value))}
        if unit == "%":
            return {"en": number(value) + "%", "zh": number(value) + "%"}
        return {"en": " ".join(filter(None, [number(value), unit])), "zh": " ".join(filter(None, [number(value), ZH_UNIT_BY_UNIT.get(unit, unit)]))}

    if entry.operator == "between":
        low, high = amount(entry.value[0]), amount(entry.value[1])
        return {"en": "{} to {}".format(low["en"], high["en"]), "zh": "{} 到 {}".format(low["zh"], high["zh"])}
    value = amount(entry.value)
    symbol = LINE_SYMBOL_BY_OPERATOR.get(entry.operator, "?")
    return {"en": "{} {}".format(symbol, value["en"]), "zh": "{} {}".format(symbol, value["zh"])}


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
        "description": localized_text_build_from_raw_value(raw_rule.get("description"), "rule {} description".format(raw_rule["rule_id"])),
        "note": localized_text_build_optional_from_raw_value(raw_rule.get("note"), "rule {} note".format(raw_rule["rule_id"])),
    }) for raw_rule in raw["rule_list"]]
    group_list = [RuleGroup(
        group_id=raw_group["group_id"],
        display_name=localized_text_build_from_raw_value(raw_group.get("display_name"), "group {} name".format(raw_group["group_id"])),
        description=localized_text_build_from_raw_value(raw_group.get("description"), "group {} description".format(raw_group["group_id"])),
        aspect=localized_text_build_optional_from_raw_value(raw_group.get("aspect"), "group {} aspect".format(raw_group["group_id"])),
        topic_list=[RuleTopic(raw_topic["topic_id"], localized_text_build_from_raw_value(
            raw_topic.get("display_name"), "topic {} name".format(raw_topic["topic_id"]))) for raw_topic in raw_group.get("topic_list") or []],
    ) for raw_group in raw["rule_group_list"]]
    retired_rule_list = [RetiredRule(
        old_id=raw_retired["old_id"], legacy_id=raw_retired.get("legacy_id") or [],
        reason=localized_text_build_from_raw_value(raw_retired.get("reason"), "retired rule {} reason".format(raw_retired["old_id"])),
    ) for raw_retired in raw.get("retired_rule_list") or []]
    return RuleCatalog(
        rule_group_list=group_list,
        rule_entry_by_id={entry.rule_id: entry for entry in entry_list},
        retired_rule_list=retired_rule_list,
        indicator_registry=registry,
    )


def rule_catalog_validate_numbering_and_topics(rule_catalog: RuleCatalog) -> List[str]:
    """Ids run 01, 02, 03 ... in the order of the file inside every group (no gaps, no repeats), and a topic is one unbroken run of rules."""
    error_list = []
    next_number_by_group: Dict[str, int] = {}
    topic_by_group = {group.group_id: {topic.topic_id for topic in group.topic_list} for group in rule_catalog.rule_group_list}
    seen_topic_set: Set[tuple] = set()
    last_topic_by_group: Dict[str, Optional[str]] = {}
    for entry in rule_catalog.rule_entry_by_id.values():
        match = RULE_ID_PATTERN.match(entry.rule_id)
        if not match:
            error_list.append("rule id {} must look like R-MAC-03".format(entry.rule_id))
            continue
        group_id, number = match.group(1), int(match.group(2))
        expected = next_number_by_group.get(group_id, 1)
        if number != expected:
            error_list.append("rule {} is out of order: {} comes next in its group".format(entry.rule_id, "R-{}-{:02d}".format(group_id, expected)))
        next_number_by_group[group_id] = number + 1
        if topic_by_group.get(group_id) and entry.topic not in topic_by_group[group_id]:
            error_list.append("rule {} has an unknown topic {}".format(entry.rule_id, entry.topic))
        key = (group_id, entry.topic)
        if last_topic_by_group.get(group_id) != entry.topic and key in seen_topic_set:
            error_list.append("topic {} of group {} is split in two runs".format(entry.topic, group_id))
        seen_topic_set.add(key)
        last_topic_by_group[group_id] = entry.topic
    for group in rule_catalog.rule_group_list:
        for topic in group.topic_list:
            if (group.group_id, topic.topic_id) not in seen_topic_set:
                error_list.append("topic {} of group {} has no rule".format(topic.topic_id, group.group_id))
    return error_list


def rule_catalog_validate_rule_catalog_against_known_indicators(
    rule_catalog: RuleCatalog, known_indicator_name_set: Set[str],
) -> List[str]:
    """Returns error messages; an empty list means the catalog is valid.
    An indicator only has to exist for a rule that is already built; a todo rule may name one that is not written yet."""
    error_list = []
    group_id_set = {group.group_id for group in rule_catalog.rule_group_list}
    registry = rule_catalog.indicator_registry
    for entry in rule_catalog.rule_entry_by_id.values():
        if not RULE_NAME_PATTERN.match(entry.rule_name or ""):
            error_list.append("rule {} needs a rule_name of lower case words joined by underscores".format(entry.rule_id))
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
    error_list += rule_catalog_validate_numbering_and_topics(rule_catalog)
    rule_name_list = [entry.rule_name for entry in rule_catalog.rule_entry_by_id.values()]
    for rule_name in sorted({name for name in rule_name_list if rule_name_list.count(name) > 1}):
        error_list.append("two rules share the rule_name {}".format(rule_name))
    live_legacy_id_list = [legacy for entry in rule_catalog.rule_entry_by_id.values() for legacy in entry.legacy_id]
    for retired in rule_catalog.retired_rule_list:
        if retired.old_id in live_legacy_id_list or retired.old_id in rule_catalog.rule_entry_by_id:
            error_list.append("retired rule {} is back in the catalog; ids are never reused".format(retired.old_id))
    for legacy in sorted({legacy for legacy in live_legacy_id_list if live_legacy_id_list.count(legacy) > 1}):
        error_list.append("the legacy id {} is on more than one rule".format(legacy))
    error_list += rule_catalog_validate_tiers(rule_catalog)
    return error_list


def rule_catalog_validate_tiers(rule_catalog: RuleCatalog) -> List[str]:
    """A band_of line measures the same indicator as its main rule, and the lines of one measure that share an operator run in one direction."""
    error_list: List[str] = []
    line_list_by_main_id: Dict[str, List[RuleCatalogEntry]] = {}
    for entry in rule_catalog.rule_entry_by_id.values():
        if not entry.band_of:
            continue
        main = rule_catalog.rule_entry_by_id.get(entry.band_of)
        if main is None:
            continue
        if entry.indicator != main.indicator:
            error_list.append("rule {} is a line of {} but measures another indicator".format(entry.rule_id, main.rule_id))
        line_list_by_main_id.setdefault(main.rule_id, []).append(entry)
    for main_id, band_list in line_list_by_main_id.items():
        main = rule_catalog.rule_entry_by_id[main_id]
        value_list = [entry.value for entry in [main] + band_list if entry.operator == main.operator and isinstance(entry.value, (int, float))]
        if value_list != sorted(value_list) and value_list != sorted(value_list, reverse=True):
            error_list.append("the lines of {} are not sorted in one direction".format(main_id))
    return error_list
