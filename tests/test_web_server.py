import json

import pytest
from fastapi import HTTPException

from stockboard_backend import refresh_scheduler, snapshot_storage, web_server

STRATEGY_ID = web_server.application_settings.default_strategy_id


def build_symbol_result(symbol):
    return {
        "symbol": symbol, "price": 10.0, "change_value": 1.5, "change_unit": "percent",
        "sparkline_close_price_list": [9.0, 10.0],
        "evaluation_by_strategy_id": {STRATEGY_ID: {
            "strategy_id": STRATEGY_ID, "symbol": symbol, "is_pass": True, "score_percent": 80.0,
            "unknown_weight_ratio": 0.0, "gate_result_list": []}},
    }


@pytest.fixture
def snapshot_file_path(tmp_path, monkeypatch):
    path = tmp_path / "latest_snapshot.json"
    monkeypatch.setattr(refresh_scheduler, "SNAPSHOT_FILE_PATH", str(path))
    return path


def write_snapshot(path, **overrides):
    snapshot = {
        "schema_version": refresh_scheduler.SNAPSHOT_SCHEMA_VERSION,
        "generated_at": "2026-10-23T15:52:19-04:00", "market_indicator_card_list": [],
        "symbol_result_list": [build_symbol_result("BBB"), build_symbol_result("AAA")],
        "failed_symbol_list": ["CCC"],
    }
    snapshot.update(overrides)
    path.write_text(json.dumps(snapshot))


def test_snapshot_keeps_order_and_reports_status(snapshot_file_path):
    write_snapshot(snapshot_file_path)
    response = web_server.web_server_get_dashboard_snapshot(STRATEGY_ID)
    assert [card["symbol"] for card in response["symbol_card_list"]] == ["BBB", "AAA"]
    assert response["failed_symbol_list"] == ["CCC"]
    assert isinstance(response["status"]["market_is_open"], bool)
    assert response["status"]["generated_at"] == "2026-10-23T15:52:19-04:00"
    assert response["status"]["stale_after_minutes"] == web_server.application_settings.stale_after_minutes


def test_old_schema_snapshot_counts_as_missing(snapshot_file_path):
    write_snapshot(snapshot_file_path, schema_version=1)
    response = web_server.web_server_get_dashboard_snapshot(STRATEGY_ID)
    assert response["symbol_card_list"] == [] and response["status"]["generated_at"] is None


def test_unknown_strategy_and_symbol_return_404(snapshot_file_path):
    write_snapshot(snapshot_file_path)
    with pytest.raises(HTTPException) as strategy_error:
        web_server.web_server_get_dashboard_snapshot("missing_strategy")
    with pytest.raises(HTTPException) as symbol_error:
        web_server.web_server_get_strategy_evaluation_for_symbol(STRATEGY_ID, "ZZZ")
    assert strategy_error.value.status_code == 404 and symbol_error.value.status_code == 404


def test_evaluation_for_symbol(snapshot_file_path):
    write_snapshot(snapshot_file_path)
    assert web_server.web_server_get_strategy_evaluation_for_symbol(STRATEGY_ID, "AAA")["symbol"] == "AAA"


def test_rule_catalog_lists_usage():
    response = web_server.web_server_get_rule_catalog()
    rule_by_id = {rule["rule_id"]: rule for group in response["group_list"] for rule in group["rule_list"]}
    assert any(usage["strategy_id"] == STRATEGY_ID and usage["veto"] and usage["weight"] == 5
               for usage in rule_by_id["EVT-01"]["used_by"])
    assert rule_by_id["THS-03"]["used_by"] == [] and rule_by_id["THS-03"]["status"] == "no_data"
    assert rule_by_id["THS-03"]["method"] == "manual"
    assert rule_by_id["SEN-12"]["band_of"] == "SEN-01" and rule_by_id["SEN-12"]["operator"] == "less_than"
    assert set(rule_by_id["SEN-01"]["name"]) == {"en", "zh"} and "weight" not in rule_by_id["SEN-01"]


def test_strategy_list_is_bilingual_with_english_default():
    response = web_server.web_server_get_strategy_list()
    assert response["default_language"] == "en"
    first_strategy = response["strategy_list"][0]
    assert first_strategy["strategy_id"] == STRATEGY_ID
    for field_name in ("display_name", "summary", "help_text", "source"):
        assert set(first_strategy[field_name]) == {"en", "zh"}


def test_schema_two_snapshot_counts_as_missing(snapshot_file_path):
    write_snapshot(snapshot_file_path, schema_version=2)
    assert web_server.web_server_get_dashboard_snapshot(STRATEGY_ID)["symbol_card_list"] == []


def test_unchanged_snapshot_file_is_parsed_once(snapshot_file_path):
    write_snapshot(snapshot_file_path)
    assert web_server.web_server_load_snapshot_or_empty_snapshot() is web_server.web_server_load_snapshot_or_empty_snapshot()


def test_replaced_snapshot_file_is_loaded_again(snapshot_file_path):
    write_snapshot(snapshot_file_path)
    assert web_server.web_server_load_snapshot_or_empty_snapshot()["failed_symbol_list"] == ["CCC"]
    replacement = json.loads(snapshot_file_path.read_text())
    replacement["failed_symbol_list"] = ["DDD"]
    # The refresher replaces the file through a temporary file, which gives it a new identity.
    snapshot_storage.snapshot_storage_save_snapshot_to_json_file(replacement, str(snapshot_file_path))
    assert web_server.web_server_load_snapshot_or_empty_snapshot()["failed_symbol_list"] == ["DDD"]
