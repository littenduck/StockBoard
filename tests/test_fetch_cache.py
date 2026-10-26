import datetime
import os
import threading
import time
from zoneinfo import ZoneInfo

import pytest

from stock_benchmark_backend import fetch_cache, indicator_registry
from stock_benchmark_backend.settings_loader import PROJECT_DIRECTORY
from stock_benchmark_backend.strategy_evaluation import IndicatorValue

NEW_YORK = ZoneInfo("America/New_York")
MINUTE, HOUR = 60, 3600


def new_york_time(hour, minute=0, day=22):  # Thursday 2026-10-22
    return datetime.datetime(2026, 10, day, hour, minute, tzinfo=NEW_YORK).timestamp()


@pytest.fixture
def registry():
    return indicator_registry.indicator_registry_load_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "indicators.yaml"))


class Clock:
    def __init__(self, now):
        self.now, self.open = now, True

    def __call__(self):
        return self.now


def build_cache(registry, clock):
    return fetch_cache.FetchCache(registry, lambda now: clock.open, clock)


def counting_fetch(counter):
    def fetch():
        counter.append(1)
        return len(counter)
    return fetch


def test_an_intraday_group_is_asked_every_ten_minutes_while_the_market_is_open(registry):
    clock, calls = Clock(new_york_time(10)), []
    cache = build_cache(registry, clock)
    for _ in range(7):  # ticks of one minute
        cache.get("yahoo_options", "AAPL", counting_fetch(calls))
        clock.now += MINUTE
    assert len(calls) == 1
    clock.now += 4 * MINUTE  # 11 minutes after the first fetch
    cache.get("yahoo_options", "AAPL", counting_fetch(calls))
    assert len(calls) == 2


def test_each_symbol_has_its_own_entry(registry):
    clock, calls = Clock(new_york_time(10)), []
    cache = build_cache(registry, clock)
    cache.get("yahoo_options", "AAPL", counting_fetch(calls))
    cache.get("yahoo_options", "MSFT", counting_fetch(calls))
    assert len(calls) == 2


def test_a_market_hours_group_is_not_asked_after_the_close(registry):
    clock, calls = Clock(new_york_time(15, 30)), []
    cache = build_cache(registry, clock)
    cache.get("yahoo_options", "AAPL", counting_fetch(calls))
    clock.open, clock.now = False, new_york_time(19)
    cache.get("yahoo_options", "AAPL", counting_fetch(calls))
    assert len(calls) == 1
    assert cache.is_anything_due() is False


def test_prices_are_loaded_once_after_the_close_at_the_fetch_at_time(registry):
    clock, calls = Clock(new_york_time(15, 55)), []
    cache = build_cache(registry, clock)
    cache.get("yahoo_quote", "market", counting_fetch(calls))
    clock.open, clock.now = False, new_york_time(16, 10)   # closed, before 16:20
    cache.get("yahoo_quote", "market", counting_fetch(calls))
    assert len(calls) == 1
    clock.now = new_york_time(16, 25)                       # 16:20 has passed
    assert cache.is_anything_due() is True
    cache.get("yahoo_quote", "market", counting_fetch(calls))
    clock.now = new_york_time(23)
    cache.get("yahoo_quote", "market", counting_fetch(calls))
    assert len(calls) == 2


def test_a_daily_group_is_not_asked_again_within_a_day_but_is_asked_before_the_open(registry):
    clock, calls = Clock(new_york_time(7)), []
    cache = build_cache(registry, clock)
    cache.get("fred", None, counting_fetch(calls))
    for hour in range(8, 24):                               # the rest of the day: nothing due
        clock.now = new_york_time(hour)
        cache.get("fred", None, counting_fetch(calls))
    assert len(calls) == 1
    clock.now = new_york_time(6, 5, day=23)                 # the next morning, 06:00 has passed (and 23 hours have not)
    cache.get("fred", None, counting_fetch(calls))
    assert len(calls) == 2


def test_a_failed_fetch_keeps_the_old_value_and_waits_fifteen_minutes(registry):
    clock = Clock(new_york_time(10))
    cache = build_cache(registry, clock)
    assert cache.get("yahoo_options", "AAPL", lambda: "first") == ("first", clock.now)
    clock.now += 11 * MINUTE
    attempts = []

    def failing():
        attempts.append(1)
        raise RuntimeError("down")

    assert cache.get("yahoo_options", "AAPL", failing)[0] == "first"
    clock.now += 5 * MINUTE
    assert cache.get("yahoo_options", "AAPL", failing)[0] == "first" and len(attempts) == 1
    clock.now += 11 * MINUTE
    cache.get("yahoo_options", "AAPL", failing)
    assert len(attempts) == 2


def test_a_first_fetch_that_fails_raises_or_returns_the_default_and_then_waits(registry):
    clock = Clock(new_york_time(10))
    cache = build_cache(registry, clock)
    with pytest.raises(RuntimeError):
        cache.get("edgar", "AAPL", lambda: (_ for _ in ()).throw(RuntimeError("down")))
    attempts = []

    def failing():
        attempts.append(1)
        raise RuntimeError("down")

    assert cache.get("edgar", "MSFT", failing, default={}) == ({}, None)
    assert cache.get("edgar", "MSFT", failing, default={}) == ({}, None) and len(attempts) == 1
    clock.now += 16 * MINUTE
    cache.get("edgar", "MSFT", failing, default={})
    assert len(attempts) == 2


def test_two_callers_at_once_make_one_request(registry):
    cache = fetch_cache.FetchCache(registry, lambda now: True, time.time)
    calls = []

    def slow():
        calls.append(1)
        time.sleep(0.2)
        return "answer"

    results = []
    threads = [threading.Thread(target=lambda: results.append(cache.get("fred", None, slow)[0])) for _ in range(4)]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    assert results == ["answer"] * 4 and len(calls) == 1


def test_a_value_older_than_its_max_age_is_dropped(registry):
    now = new_york_time(10)
    fresh = IndicatorValue("treasury_ten_year_minus_two_year_spread", 0.3, "x", observed_at=now - 2 * 86400)
    old = IndicatorValue("moodys_baa_minus_ten_year_treasury_spread", 1.4, "x", observed_at=now - 30 * 86400)  # max_age 10d
    unstamped = IndicatorValue("vix_level", 19.0, "x")
    kept = indicator_registry.indicator_registry_drop_stale_values(
        {value.indicator_name: value for value in (fresh, old, unstamped)}, registry, now)
    assert set(kept) == {"treasury_ten_year_minus_two_year_spread", "vix_level"}
