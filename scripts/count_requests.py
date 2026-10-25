"""Run one full dashboard refresh and count the outgoing requests by host and Yahoo endpoint.
Usage: .venv/bin/python scripts/count_requests.py [--twice]   (--twice runs a second refresh right after the first)
Network calls are counted where yfinance (YfData.get) and urllib (urlopen) make them; nothing is blocked or changed."""
import collections
import os
import sys
import threading
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yfinance import data as yfinance_data  # noqa: E402

counts = collections.Counter()
lock = threading.Lock()


def record(url: str) -> None:
    parts = urllib.parse.urlsplit(str(url if isinstance(url, str) else getattr(url, "full_url", url)))
    path = "/".join(parts.path.split("/")[:4])
    with lock:
        counts[(parts.netloc, path if "yahoo" in parts.netloc else "")] += 1


original_yf_get = yfinance_data.YfData.get
original_urlopen = urllib.request.urlopen


def counted_yf_get(self, url, *args, **kwargs):
    record(url)
    return original_yf_get(self, url, *args, **kwargs)


def counted_urlopen(url, *args, **kwargs):
    record(url)
    return original_urlopen(url, *args, **kwargs)


yfinance_data.YfData.get = counted_yf_get
urllib.request.urlopen = counted_urlopen

from stockboard_backend import refresh_scheduler, rule_catalog, settings_loader, strategy_loader  # noqa: E402
from stockboard_backend.settings_loader import PROJECT_DIRECTORY  # noqa: E402


def load_everything():
    settings = settings_loader.settings_loader_load_settings_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "settings.yaml"))
    catalog = rule_catalog.rule_catalog_load_rule_catalog_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml"))
    strategy_directory = next(path for path in (os.path.join(PROJECT_DIRECTORY, "config", "strategies"), os.path.join(PROJECT_DIRECTORY, "strategies"))
                              if os.path.isdir(path))
    return settings, strategy_loader.strategy_loader_load_all_strategy_definitions_from_directory(strategy_directory, catalog)


def report(label: str) -> None:
    total = sum(counts.values())
    print(f"\n== {label}: {total} requests")
    for (host, path), count in sorted(counts.items(), key=lambda item: -item[1]):
        print(f"{count:5d}  {host} {path}")
    counts.clear()


if __name__ == "__main__":
    settings, strategies = load_everything()
    refresh_scheduler.refresh_scheduler_build_dashboard_snapshot(settings, strategies)
    report("refresh 1 (cold)")
    if "--twice" in sys.argv:
        refresh_scheduler.refresh_scheduler_build_dashboard_snapshot(settings, strategies)
        report("refresh 2 (right after)")
