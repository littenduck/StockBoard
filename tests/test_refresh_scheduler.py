import types

from stock_benchmark_backend import refresh_scheduler, snapshot_storage


def build_snapshot(symbol_list, failed_symbol_list=()):
    return {"schema_version": refresh_scheduler.SNAPSHOT_SCHEMA_VERSION, "symbol_result_list": [{"symbol": symbol} for symbol in symbol_list],
            "failed_symbol_list": list(failed_symbol_list)}


def test_a_changed_symbol_list_makes_the_refresh_due_even_when_nothing_else_is(monkeypatch):
    settings = types.SimpleNamespace(watchlist_symbol_list=["SPY", "QQQ", "NEW"])
    monkeypatch.setattr(snapshot_storage, "snapshot_storage_load_snapshot_from_json_file", lambda path: build_snapshot(["SPY", "QQQ"]))
    assert refresh_scheduler.refresh_scheduler_determine_whether_refresh_is_due(settings) is True


def test_a_symbol_that_failed_still_counts_as_followed(monkeypatch):
    settings = types.SimpleNamespace(watchlist_symbol_list=["SPY", "BAD"], market_holiday_date_set=frozenset(), market_early_close_date_set=frozenset(),
                                     refresh_interval_minutes=10)
    monkeypatch.setattr(snapshot_storage, "snapshot_storage_load_snapshot_from_json_file", lambda path: build_snapshot(["SPY"], ["BAD"]))
    monkeypatch.setattr(refresh_scheduler.os.path, "getmtime", lambda path: refresh_scheduler.time.time())
    fetch_cache = types.SimpleNamespace(is_anything_due=lambda: False)
    assert refresh_scheduler.refresh_scheduler_determine_whether_refresh_is_due(settings, fetch_cache) is False


def test_the_dolthub_iv_history_is_off_by_default_and_has_a_short_timeout():
    from stock_benchmark_backend import dolthub_data, settings_loader
    import os
    settings = settings_loader.settings_loader_load_settings_from_yaml_file(os.path.join(settings_loader.PROJECT_DIRECTORY, "config", "settings.yaml"))
    assert settings.fetch_dolthub_iv_history is False
    assert dolthub_data.DOLTHUB_TIMEOUT_SECONDS * dolthub_data.ATTEMPT_COUNT <= 60
