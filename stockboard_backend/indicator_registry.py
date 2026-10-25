"""Load config/indicators.yaml: every measured quantity, defined once, with where it comes from and how often it is fetched.

A rule points at an indicator by id; the facts about how the value is obtained (method, history, status) and when it is fetched or
too old (fetch_every, max_age) belong to the indicator, so they are written once however many rules use it.
"""
import datetime
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import yaml

from stockboard_backend.localized_text import LocalizedText, localized_text_build_optional_from_raw_value

SCOPE_SET = {"market", "symbol", "window"}
STATUS_SET = {"built", "todo"}
METHOD_SET = {"api_fetch", "scrape", "computed", "ai_search"}
QUANTIFIABLE_SET = {"yes", "part", "no"}
BACKTESTABLE_SET = {"yes", "no"}
# history_source is "name" or "name:detail" (for example fred:DGS10); the name must be one of these free sources.
KNOWN_HISTORY_SOURCE_NAME_SET = {
    "fred", "alfred", "cboe", "edgar", "dolthub", "yfinance", "cnn", "aaii", "naaim", "finra", "shiller", "damodaran",
    "gpr", "federalreserve", "sec", "fja05680", "wayback", "ritter", "rule",
}
HISTORY_START_PATTERN = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")  # a year, a month or a day
DURATION_PATTERN = re.compile(r"^(\d+)([mhd])$")
SECONDS_PER_UNIT = {"m": 60, "h": 3600, "d": 86400}
TIME_OF_DAY_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@dataclass
class FetchGroup:
    fetch_group_id: str
    market_hours_only: bool = False
    fetch_at: List[datetime.time] = field(default_factory=list)  # New York time of day
    note: str = ""


@dataclass
class IndicatorDefinition:
    indicator_id: str
    scope: str
    status: str
    method: Optional[str] = None
    quantifiable: Optional[str] = None
    backtestable: Optional[str] = None
    history_source: Optional[str] = None
    history_start: Optional[str] = None
    fetch_group: Optional[str] = None
    fetch_every: Optional[str] = None
    max_age: Optional[str] = None
    display_name: Optional[LocalizedText] = None
    is_higher_value_risky: bool = False

    @property
    def fetch_every_seconds(self) -> Optional[int]:
        return None if self.fetch_every is None else indicator_registry_parse_duration_seconds(self.fetch_every)

    @property
    def max_age_seconds(self) -> Optional[int]:
        return None if self.max_age is None else indicator_registry_parse_duration_seconds(self.max_age)


@dataclass
class IndicatorRegistry:
    fetch_group_by_id: Dict[str, FetchGroup]
    indicator_by_id: Dict[str, IndicatorDefinition]

    def built_indicator_id_set(self) -> Set[str]:
        return {indicator.indicator_id for indicator in self.indicator_by_id.values() if indicator.status == "built"}

    def group_fetch_every_seconds(self, fetch_group_id: str) -> int:
        """A group is fetched as often as its most frequent indicator needs."""
        return min(indicator.fetch_every_seconds for indicator in self.indicator_by_id.values()
                   if indicator.fetch_group == fetch_group_id and indicator.status == "built")


def indicator_registry_parse_duration_seconds(text: str) -> int:
    """'10m', '6h' or '3d' as seconds."""
    match = DURATION_PATTERN.match(str(text))
    if not match:
        raise ValueError("bad duration {!r}: use a number and m, h or d, for example 10m, 6h or 1d".format(text))
    return int(match.group(1)) * SECONDS_PER_UNIT[match.group(2)]


def indicator_registry_load_from_yaml_file(indicator_file_path: str) -> IndicatorRegistry:
    with open(indicator_file_path, encoding="utf8") as indicator_file:
        raw = yaml.safe_load(indicator_file)
    group_by_id = {}
    for raw_group in raw.get("fetch_group_list") or []:
        group_by_id[raw_group["fetch_group_id"]] = FetchGroup(
            fetch_group_id=raw_group["fetch_group_id"], market_hours_only=bool(raw_group.get("market_hours_only", False)),
            fetch_at=[datetime.time(int(text[:2]), int(text[3:])) for text in map(str, raw_group.get("fetch_at") or [])
                      if TIME_OF_DAY_PATTERN.match(text)],
            note=raw_group.get("note", ""))
    indicator_by_id = {}
    for raw_indicator in raw["indicator_list"]:
        indicator_by_id[raw_indicator["indicator_id"]] = IndicatorDefinition(**{
            **raw_indicator,
            "display_name": localized_text_build_optional_from_raw_value(
                raw_indicator.get("display_name"), "indicator {} name".format(raw_indicator["indicator_id"])),
            "history_start": None if raw_indicator.get("history_start") is None else str(raw_indicator["history_start"]),
        })
    return IndicatorRegistry(fetch_group_by_id=group_by_id, indicator_by_id=indicator_by_id)


def indicator_registry_validate(indicator_registry: IndicatorRegistry) -> List[str]:
    """Returns error messages; an empty list means the registry is valid."""
    error_list = []
    for indicator in indicator_registry.indicator_by_id.values():
        name = "indicator " + indicator.indicator_id
        if indicator.scope not in SCOPE_SET:
            error_list.append("{} has unknown scope {}".format(name, indicator.scope))
        if indicator.status not in STATUS_SET:
            error_list.append("{} has unknown status {}".format(name, indicator.status))
        if indicator.method is not None and indicator.method not in METHOD_SET:
            error_list.append("{} has unknown method {}".format(name, indicator.method))
        if indicator.quantifiable is not None and indicator.quantifiable not in QUANTIFIABLE_SET:
            error_list.append("{} has unknown quantifiable {}".format(name, indicator.quantifiable))
        if indicator.backtestable is not None and indicator.backtestable not in BACKTESTABLE_SET:
            error_list.append("{} has unknown backtestable {}".format(name, indicator.backtestable))
        if (indicator.history_source is None) != (indicator.history_start is None):
            error_list.append("{} needs history_source and history_start together".format(name))
        if indicator.history_source is not None and indicator.history_source.split(":")[0] not in KNOWN_HISTORY_SOURCE_NAME_SET:
            error_list.append("{} has unknown history source {}".format(name, indicator.history_source))
        if indicator.history_start is not None and not HISTORY_START_PATTERN.match(indicator.history_start):
            error_list.append("{} has a bad history_start {}".format(name, indicator.history_start))
        if indicator.status == "built":
            if indicator.method is None:
                error_list.append("{} is built but has no method".format(name))
            if indicator.fetch_group not in indicator_registry.fetch_group_by_id:
                error_list.append("{} is built but its fetch_group {} is not defined".format(name, indicator.fetch_group))
            try:
                every, age = indicator.fetch_every_seconds, indicator.max_age_seconds
                if every is None or age is None:
                    error_list.append("{} is built but needs fetch_every and max_age".format(name))
                elif age < every:
                    error_list.append("{} has a max_age shorter than its fetch_every".format(name))
            except ValueError as error:
                error_list.append("{}: {}".format(name, error))
    used_group_set = {indicator.fetch_group for indicator in indicator_registry.indicator_by_id.values() if indicator.status == "built"}
    for group_id in indicator_registry.fetch_group_by_id:
        if group_id not in used_group_set:
            error_list.append("fetch group {} has no built indicator".format(group_id))
    return error_list
