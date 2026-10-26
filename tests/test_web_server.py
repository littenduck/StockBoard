import json
import os

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
               for usage in rule_by_id["R-EVT-01"]["used_by"])
    assert rule_by_id["R-THS-03"]["used_by"] == [] and rule_by_id["R-THS-03"]["status"] == "no_data"
    assert rule_by_id["R-THS-03"]["method"] == "manual"
    assert rule_by_id["R-SEN-04"]["band_of"] == "R-SEN-03" and rule_by_id["R-SEN-04"]["operator"] == "less_than"
    assert rule_by_id["R-SEN-01"]["rule_name"] == "vix_at_least_15" and "weight" not in rule_by_id["R-SEN-01"]


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


def test_rule_card_script_is_served():
    response = web_server.web_server_get_rule_card_script()
    assert os.path.exists(response.path) and "ruleCardBind" in open(response.path, encoding="utf8").read()


def test_rule_text_script_is_served():
    response = web_server.web_server_get_rule_text_script()
    assert os.path.exists(response.path) and "ruleTextRenderIndicator" in open(response.path, encoding="utf8").read()


def test_the_rule_list_carries_the_indicator_text_and_the_lines_of_the_measure():
    group_list = web_server.web_server_get_rule_catalog()["group_list"]
    rule_by_id = {rule["rule_id"]: rule for group in group_list for rule in group["rule_list"]}
    rule = rule_by_id["R-MAC-03"]
    assert rule["indicator_description"]["en"].startswith("Yield on the 10-year")
    assert [item["rule_id"] for item in rule["indicator_line_list"]] == ["R-MAC-03", "R-MAC-04"]
    assert [item["line"]["en"] for item in rule["indicator_line_list"]] == ["< 4.5%", "< 5.0%"]
    assert rule_by_id["R-POS-01"]["indicator_description"] is None and rule_by_id["R-POS-01"]["indicator_line_list"] == []


def test_indicator_catalog_lists_every_indicator_once_with_its_rules():
    response = web_server.web_server_get_indicator_catalog()
    indicator_list = [indicator for group in response["group_list"] for indicator in group["indicator_list"]]
    registry = web_server.application_rule_catalog.indicator_registry
    assert sorted(item["indicator_id"] for item in indicator_list) == sorted(item.indicator_id for item in registry.indicator_by_name.values())
    rule_id_set = set(web_server.application_rule_catalog.rule_entry_by_id)
    by_id = {item["indicator_id"]: item for item in indicator_list}
    assert [item["rule_id"] for item in by_id["I-003"]["rule_list"]] == ["R-MAC-03", "R-MAC-04"]
    assert by_id["I-003"]["rule_list"][0]["line"]["en"] == "< 4.5%" and by_id["I-003"]["unit"] == "%"
    assert all(rule["rule_id"] in rule_id_set for item in indicator_list for rule in item["rule_list"])
    group_of = {item["indicator_id"]: group["group_id"] for group in response["group_list"] for item in group["indicator_list"]}
    assert group_of["I-003"] == "MAC" and group_of["I-052"] == "OTHER"  # VXN is on the market bar only
    assert by_id["I-052"]["on_market_bar"] and by_id["I-052"]["rule_list"] == []


def test_strategy_list_carries_gates_with_weights_and_vetoes():
    strategy = next(item for item in web_server.web_server_get_strategy_list()["strategy_list"] if item["strategy_id"] == STRATEGY_ID)
    rule_list = [rule for gate in strategy["gate_list"] for rule in gate["rule_list"]]
    assert strategy["max_unknown_weight_ratio"] == 0.20 and strategy["gate_list"][0]["gate_id"].startswith("gate_0")
    assert any(rule["rule_id"] == "R-EVT-01" and rule["veto"] and rule["weight"] == 5 for rule in rule_list)
    assert all(rule["rule_id"] in web_server.application_rule_catalog.rule_entry_by_id and rule["line"]["en"] for rule in rule_list)


def test_strategy_page_needs_a_known_strategy():
    with pytest.raises(HTTPException) as error:
        web_server.web_server_get_strategy_page("nope")
    assert error.value.status_code == 404


STATIC_DIRECTORY = os.path.join(web_server.PROJECT_DIRECTORY, "static")
PAGE_FILE_NAME_LIST = ["index.html", "rules.html", "indicators.html", "strategies.html", "strategy.html"]


def test_every_page_loads_only_files_the_server_serves_and_stays_short():
    import re
    route_path_set = {route.path for route in web_server.app.routes}
    for file_name in PAGE_FILE_NAME_LIST:
        text = open(os.path.join(STATIC_DIRECTORY, file_name), encoding="utf8").read()
        for path in re.findall(r'(?:src|href)="(/[a-z.\-]*)(?:[#"])', text):
            assert path == "/" or path in route_path_set, "{} loads {}".format(file_name, path)
        assert text.count("\n") <= (354 if file_name == "index.html" else 140), file_name


def test_the_catalog_pages_use_only_known_text_keys():
    import re
    language_text = open(os.path.join(STATIC_DIRECTORY, "language.js"), encoding="utf8").read()
    key_set = set(re.findall(r"^\s*(?:\w+: \{.*\},\s*)?(\w+): \{ en:", language_text, re.M)) | set(re.findall(r"\b(\w+): \{ en:", language_text))
    for file_name in ["rules.html", "indicators.html", "strategies.html", "strategy.html", "page.js"]:
        text = open(os.path.join(STATIC_DIRECTORY, file_name), encoding="utf8").read()
        for key in re.findall(r"language(?:Text|Localize)\('(\w+)'", text) + re.findall(r"data-title-key=\"(\w+)\"", text):
            assert key in key_set, "{} uses the unknown text {}".format(file_name, key)

def test_the_version_is_read_from_the_version_file_only():
    with open(os.path.join(web_server.PROJECT_DIRECTORY, "VERSION"), encoding="utf8") as version_file:
        version = version_file.read().strip()
    assert web_server.APP_VERSION == version and web_server.web_server_get_version() == {"version": version}
    assert web_server.web_server_build_status("2026-01-01T00:00:00-05:00")["version"] == version


def test_nothing_else_writes_the_version_number():
    import re
    with open(os.path.join(web_server.PROJECT_DIRECTORY, "VERSION"), encoding="utf8") as version_file:
        version = version_file.read().strip()
    assert re.match(r"^\d+\.\d+\.\d+$", version)
    for directory in ("static", "stockboard_backend"):
        for name in os.listdir(os.path.join(web_server.PROJECT_DIRECTORY, directory)):
            path = os.path.join(web_server.PROJECT_DIRECTORY, directory, name)
            if os.path.isfile(path) and name.endswith((".py", ".js", ".html")):
                assert version not in open(path, encoding="utf8").read(), "{} writes the version {}".format(path, version)


def test_the_license_names_the_copyright_holder():
    text = open(os.path.join(web_server.PROJECT_DIRECTORY, "LICENSE"), encoding="utf8").read()
    assert text.startswith("MIT License") and "Copyright (c) 2026 littenduck" in text
