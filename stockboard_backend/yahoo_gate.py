"""One gate in front of every Yahoo request: at most two at a time, and a count of what comes back.

yfinance sends its requests through YfData.get. Wrapping that one method keeps the number of simultaneous requests low (a burst is the
likeliest thing to get an address limited) and counts requests, rate-limit answers and other errors so a change in how Yahoo treats this
server shows up in the log. A failed request costs more than one: yfinance retries it once with a fresh cookie and crumb.
"""
import collections
import datetime
import threading
import time

from yfinance import data as yfinance_data

MAX_CONCURRENT_YAHOO_REQUESTS = 2
LOG_EVERY_SECONDS = 3600
semaphore = threading.BoundedSemaphore(MAX_CONCURRENT_YAHOO_REQUESTS)
counts: collections.Counter = collections.Counter()
state = {"installed": False, "last_log_at": time.time()}


def yahoo_gate_record(label: str) -> None:
    counts[label] += 1
    counts["requests"] += 1 if label.startswith("status ") or label == "exception" else 0


def yahoo_gate_install() -> None:
    """Wrap YfData.get once; calling it again does nothing."""
    if state["installed"]:
        return
    original_get = yfinance_data.YfData.get

    def gated_get(self, *args, **kwargs):
        with semaphore:
            try:
                response = original_get(self, *args, **kwargs)
            except Exception as error:
                yahoo_gate_record("exception")
                yahoo_gate_record("exception " + type(error).__name__)
                raise
            yahoo_gate_record("status {}".format(getattr(response, "status_code", "?")))
            yahoo_gate_log_summary_if_due()
            return response

    yfinance_data.YfData.get = gated_get
    state["installed"] = True


def yahoo_gate_log_summary_if_due(now: float = None) -> None:
    now = now or time.time()
    if now - state["last_log_at"] < LOG_EVERY_SECONDS:
        return
    state["last_log_at"] = now
    errors = {label: count for label, count in counts.items() if label not in ("requests", "status 200")}
    print("yahoo requests since start: {} total, {} ok, other: {}".format(counts["requests"], counts["status 200"], errors or "none"))
