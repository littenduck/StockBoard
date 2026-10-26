"""Load config/settings.yaml into typed settings."""
import datetime
import os
from dataclasses import dataclass, field
from typing import FrozenSet, List

import yaml

from stockboard_backend import indicator_registry
from stockboard_backend.localized_text import LANGUAGE_CODE_SET, LocalizedText, localized_text_build_from_raw_value

PROJECT_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class MarketIndicatorSetting:
    indicator_name: str
    display_name: LocalizedText
    is_higher_value_risky: bool = False


@dataclass
class ExpirationWindowSetting:
    minimum_days: int
    maximum_days: int

    @property
    def label(self) -> str:
        return "{}-{}".format(self.minimum_days, self.maximum_days)


@dataclass
class ApplicationSettings:
    refresh_interval_minutes: int
    default_strategy_id: str
    market_indicator_list: List[MarketIndicatorSetting]
    watchlist_symbol_list: List[str]
    option_expiration_window_list: List[ExpirationWindowSetting]
    target_absolute_delta: float
    macro_event_calendar: list
    stale_after_minutes: int = 60
    allowed_origin_list: List[str] = field(default_factory=list)
    max_requests_per_second: float = 30
    market_holiday_date_set: FrozenSet[datetime.date] = frozenset()
    market_early_close_date_set: FrozenSet[datetime.date] = frozenset()
    default_language: str = "en"
    macro_event_covered_until: dict = field(default_factory=dict)


def settings_loader_validate_language_code(language_code: str) -> str:
    if language_code not in LANGUAGE_CODE_SET:
        raise ValueError("default_language must be one of {}".format(sorted(LANGUAGE_CODE_SET)))
    return language_code


def settings_loader_build_sidebar_indicator_list(indicator_id_list: list, settings_file_path: str) -> List[MarketIndicatorSetting]:
    """The sidebar shows these indicators; their display name and whether a higher value is risky live in config/indicators.yaml."""
    registry = indicator_registry.indicator_registry_load_from_yaml_file(
        os.path.join(os.path.dirname(settings_file_path), "indicators.yaml"))
    sidebar_list = []
    for indicator_id in indicator_id_list:
        indicator = registry.indicator_by_id.get(indicator_id)
        if indicator is None or indicator.display_name is None:
            raise ValueError("sidebar indicator {} needs a display_name in config/indicators.yaml".format(indicator_id))
        sidebar_list.append(MarketIndicatorSetting(indicator.indicator_name, indicator.display_name, indicator.is_higher_value_risky))
    return sidebar_list


def settings_loader_validate_symbol_list(symbol_list) -> List[str]:
    if not symbol_list or not all(isinstance(symbol, str) and symbol.strip() for symbol in symbol_list):
        raise ValueError("config/symbols.yaml needs a non-empty symbol_list of tickers")
    if len(set(symbol_list)) != len(symbol_list):
        raise ValueError("config/symbols.yaml lists a symbol twice")
    return list(symbol_list)


def settings_loader_load_settings_from_yaml_file(settings_file_path: str) -> ApplicationSettings:
    with open(settings_file_path) as settings_file:
        raw = yaml.safe_load(settings_file)
    with open(os.path.join(os.path.dirname(settings_file_path), "symbols.yaml")) as symbols_file:
        symbol_list = settings_loader_validate_symbol_list(yaml.safe_load(symbols_file)["symbol_list"])
    return ApplicationSettings(
        refresh_interval_minutes=raw["refresh_interval_minutes"],
        default_strategy_id=raw["default_strategy_id"],
        market_indicator_list=settings_loader_build_sidebar_indicator_list(raw["market_indicator_list"], settings_file_path),
        watchlist_symbol_list=symbol_list,
        option_expiration_window_list=[ExpirationWindowSetting(**item) for item in raw["option_expiration_window_list"]],
        target_absolute_delta=raw["target_absolute_delta"],
        macro_event_calendar=raw.get("macro_event_calendar") or [],
        macro_event_covered_until=raw.get("macro_event_covered_until") or {},
        stale_after_minutes=raw.get("stale_after_minutes", 60),
        allowed_origin_list=raw.get("allowed_origin_list") or [],
        max_requests_per_second=raw.get("max_requests_per_second", 30),
        default_language=settings_loader_validate_language_code(raw.get("default_language", "en")),
        market_holiday_date_set=frozenset(
            datetime.date.fromisoformat(str(text)) for text in raw.get("market_holiday_list") or []),
        market_early_close_date_set=frozenset(
            datetime.date.fromisoformat(str(text)) for text in raw.get("market_early_close_list") or []),
    )
