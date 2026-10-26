"""Decide when a source must be asked again, and keep what it answered until then.

The rules come from config/indicators.yaml: every fetch group has a market_hours_only flag and optional fetch_at times, and its interval is the
shortest fetch_every of its indicators. A refresh asks the cache for each group; the cache calls the real fetch function only when the group is due,
so an indicator that is not due costs no request.
"""
import datetime
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from stock_benchmark_backend.indicator_registry import IndicatorRegistry
from stock_benchmark_backend.fetch_store import fetch_store_load_answers, fetch_store_save_answer
from stock_benchmark_backend.run_log import run_log_write

NEW_YORK_TIME_ZONE = ZoneInfo("America/New_York")
FAILED_RETRY_SECONDS = 15 * 60
RAISE = object()


class FetchCache:
    """Keeps the last answer of every (group, key) pair. A key is a symbol for per-symbol groups and None for market wide groups."""

    def __init__(self, registry: IndicatorRegistry, market_is_open: Callable[[float], bool], clock: Callable[[], float] = time.time,
                 store_directory: Optional[str] = None):
        self.registry = registry
        self.market_is_open = market_is_open
        self.clock = clock
        self._entry_by_key: Dict[Tuple[str, Optional[str]], Tuple[float, Any]] = {}
        self.store_directory = store_directory
        if store_directory:  # what an earlier run downloaded; it is asked again only when it is due
            self._entry_by_key.update(fetch_store_load_answers(store_directory))
            run_log_write("store loaded {} answers from {}".format(len(self._entry_by_key), store_directory))
        self._retry_after_by_key: Dict[Tuple[str, Optional[str]], float] = {}
        self._forced_due_key_set = set()
        self._lock_by_key: Dict[Tuple[str, Optional[str]], threading.Lock] = {}
        self._guard = threading.Lock()
        self.request_count_by_group: Dict[str, int] = {}

    def _lock_for(self, key: Tuple[str, Optional[str]]) -> threading.Lock:
        with self._guard:
            return self._lock_by_key.setdefault(key, threading.Lock())

    def every_seconds(self, group_id: str) -> int:
        return self.registry.group_fetch_every_seconds(group_id)

    def anchored_time_has_passed(self, group_id: str, last_fetched_at: float, now: float) -> bool:
        """True when a fetch_at time of day (New York) fell between the last fetch and now."""
        group = self.registry.fetch_group_by_id[group_id]
        now_new_york = datetime.datetime.fromtimestamp(now, NEW_YORK_TIME_ZONE)
        for time_of_day in group.fetch_at:
            latest = datetime.datetime.combine(now_new_york.date(), time_of_day, NEW_YORK_TIME_ZONE)
            if latest > now_new_york:
                latest -= datetime.timedelta(days=1)
            if last_fetched_at < latest.timestamp():
                return True
        return False

    def is_due(self, group_id: str, last_fetched_at: Optional[float], now: float) -> bool:
        if last_fetched_at is None:
            return True  # never asked: ask once, even after the close
        if self.anchored_time_has_passed(group_id, last_fetched_at, now):
            return True
        group = self.registry.fetch_group_by_id[group_id]
        if group.market_hours_only and not self.market_is_open(now):
            return False
        return now - last_fetched_at >= self.every_seconds(group_id)

    def get(self, group_id: str, key: Optional[str], fetch_function: Callable[[], Any], default: Any = RAISE) -> Tuple[Any, Optional[float]]:
        """(value, time it was fetched). Calls fetch_function only when due. A failed fetch keeps the old value and tries again in
        15 minutes; with no old value the error is raised, or default is returned (with no fetch time) when one is given, and the
        next attempt also waits 15 minutes. One fetch per key runs at a time and a second caller reuses its answer."""
        cache_key = (group_id, key)
        with self._lock_for(cache_key):
            now = self.clock()
            entry = self._entry_by_key.get(cache_key)
            if entry is None and default is not RAISE and self._retry_after_by_key.get(cache_key, 0) > now:
                return default, None
            forced = cache_key in self._forced_due_key_set
            if entry is not None and not forced and (not self.is_due(group_id, entry[0], now) or self._retry_after_by_key.get(cache_key, 0) > now):
                return entry[1], entry[0]
            started = time.perf_counter()
            try:
                value = fetch_function()
            except Exception as error:
                run_log_write("fetch {} {} FAILED {:.2f}s {}".format(group_id, key or "-", time.perf_counter() - started, str(error)[:120]))
                if entry is None and default is RAISE:
                    raise
                self._retry_after_by_key[cache_key] = now + FAILED_RETRY_SECONDS
                print("fetch failed:", group_id, key, error)
                return (default, None) if entry is None else (entry[1], entry[0])
            run_log_write("fetch {} {} ok {:.2f}s".format(group_id, key or "-", time.perf_counter() - started))
            self._retry_after_by_key.pop(cache_key, None)
            self._forced_due_key_set.discard(cache_key)
            self.request_count_by_group[group_id] = self.request_count_by_group.get(group_id, 0) + 1
            self._entry_by_key[cache_key] = (now, value)
            if self.store_directory:
                try:
                    fetch_store_save_answer(self.store_directory, group_id, key, now, value)
                except Exception as error:  # a full disk must not stop the app
                    run_log_write("store failed {} {} {}".format(group_id, key or "-", str(error)[:100]))
            return value, now

    def peek(self, group_id: str, key: Optional[str], default: Any = None) -> Any:
        """The last answer kept, without asking."""
        entry = self._entry_by_key.get((group_id, key))
        return default if entry is None else entry[1]

    def force_due(self, group_id: str, key: Optional[str]) -> None:
        """The next get asks the source again whatever the schedule says."""
        self._forced_due_key_set.add((group_id, key))

    def is_anything_due(self) -> bool:
        """True when some answer already kept is due again (a group never asked is handled by the first refresh)."""
        now = self.clock()
        with self._guard:
            entry_list = list(self._entry_by_key.items())
        return any(self.is_due(group_id, fetched_at, now) and self._retry_after_by_key.get((group_id, key), 0) <= now
                   for (group_id, key), (fetched_at, _) in entry_list)

    def last_fetched_at(self, group_id: str) -> Optional[float]:
        with self._guard:
            fetched_at_list = [entry[0] for (group, _), entry in self._entry_by_key.items() if group == group_id]
        return max(fetched_at_list) if fetched_at_list else None
