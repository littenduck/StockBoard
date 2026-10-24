"""Load config/settings.yaml into typed settings."""
import datetime
import os
from dataclasses import dataclass, field
from typing import FrozenSet, List

import yaml

PROJECT_DIRECTORY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class MarketIndicatorSetting:
    indicator_id: str
    display_name: str
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
    market_holiday_date_set: FrozenSet[datetime.date] = frozenset()
    market_early_close_date_set: FrozenSet[datetime.date] = frozenset()


def settings_loader_load_settings_from_yaml_file(settings_file_path: str) -> ApplicationSettings:
    with open(settings_file_path) as settings_file:
        raw = yaml.safe_load(settings_file)
    return ApplicationSettings(
        refresh_interval_minutes=raw["refresh_interval_minutes"],
        default_strategy_id=raw["default_strategy_id"],
        market_indicator_list=[MarketIndicatorSetting(**item) for item in raw["market_indicator_list"]],
        watchlist_symbol_list=raw["watchlist_symbol_list"],
        option_expiration_window_list=[ExpirationWindowSetting(**item) for item in raw["option_expiration_window_list"]],
        target_absolute_delta=raw["target_absolute_delta"],
        macro_event_calendar=raw.get("macro_event_calendar") or [],
        stale_after_minutes=raw.get("stale_after_minutes", 60),
        allowed_origin_list=raw.get("allowed_origin_list") or [],
        market_holiday_date_set=frozenset(
            datetime.date.fromisoformat(str(text)) for text in raw.get("market_holiday_list") or []),
        market_early_close_date_set=frozenset(
            datetime.date.fromisoformat(str(text)) for text in raw.get("market_early_close_list") or []),
    )
