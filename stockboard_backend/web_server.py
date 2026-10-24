"""FastAPI server: the page plus three JSON endpoints."""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from stockboard_backend import indicator_calculation, refresh_scheduler, settings_loader, snapshot_storage, strategy_loader

PROJECT_DIRECTORY = settings_loader.PROJECT_DIRECTORY
application_settings = settings_loader.settings_loader_load_settings_from_yaml_file(
    os.path.join(PROJECT_DIRECTORY, "config", "settings.yaml"))
strategy_definition_by_id = strategy_loader.strategy_loader_load_all_strategy_definitions_from_directory(
    os.path.join(PROJECT_DIRECTORY, "strategies"))

validation_error_list = [
    error for strategy_definition in strategy_definition_by_id.values()
    for error in strategy_loader.strategy_loader_validate_strategy_definition_against_known_indicators(
        strategy_definition, indicator_calculation.KNOWN_INDICATOR_ID_SET)]
if validation_error_list or application_settings.default_strategy_id not in strategy_definition_by_id:
    raise SystemExit("Invalid configuration: " + "; ".join(validation_error_list or ["default strategy missing"]))

app = FastAPI()


@app.on_event("startup")
def web_server_start_background_refresh() -> None:
    refresh_scheduler.refresh_scheduler_start_background_refresh_thread(
        application_settings, strategy_definition_by_id)


def web_server_load_snapshot_or_empty_snapshot() -> dict:
    snapshot = snapshot_storage.snapshot_storage_load_snapshot_from_json_file(refresh_scheduler.SNAPSHOT_FILE_PATH)
    if snapshot is None or snapshot.get("schema_version") != refresh_scheduler.SNAPSHOT_SCHEMA_VERSION:
        return {"generated_at": None, "market_indicator_card_list": [], "symbol_result_list": [],
                "failed_symbol_list": []}
    return snapshot


def web_server_find_strategy_id_or_raise(strategy_id: Optional[str]) -> str:
    chosen_strategy_id = strategy_id or application_settings.default_strategy_id
    if chosen_strategy_id not in strategy_definition_by_id:
        raise HTTPException(status_code=404, detail="Unknown strategy: " + chosen_strategy_id)
    return chosen_strategy_id


@app.get("/")
def web_server_get_index_page() -> FileResponse:
    return FileResponse(os.path.join(PROJECT_DIRECTORY, "static", "index.html"))


@app.get("/api/strategy_list")
def web_server_get_strategy_list() -> dict:
    return {
        "default_strategy_id": application_settings.default_strategy_id,
        "strategy_list": [{"strategy_id": s.strategy_id, "display_name": s.display_name}
                          for s in strategy_definition_by_id.values()],
    }


@app.get("/api/snapshot")
def web_server_get_dashboard_snapshot(strategy_id: Optional[str] = None) -> dict:
    chosen_strategy_id = web_server_find_strategy_id_or_raise(strategy_id)
    snapshot = web_server_load_snapshot_or_empty_snapshot()
    symbol_card_list = []
    for symbol_result in snapshot["symbol_result_list"]:
        evaluation = symbol_result["evaluation_by_strategy_id"][chosen_strategy_id]
        symbol_card_list.append({
            "symbol": symbol_result["symbol"], "price": symbol_result["price"],
            "change_value": symbol_result["change_value"], "change_unit": symbol_result["change_unit"],
            "is_pass": evaluation["is_pass"],
            "score_percent": evaluation["score_percent"], "unknown_weight_ratio": evaluation["unknown_weight_ratio"],
        })
    return {
        "updated": snapshot["generated_at"], "strategy_id": chosen_strategy_id,
        "max_unknown_weight_ratio": strategy_definition_by_id[chosen_strategy_id].thresholds.max_unknown_weight_ratio,
        "market_indicator_card_list": snapshot["market_indicator_card_list"],
        "symbol_card_list": symbol_card_list,
    }


@app.get("/api/evaluation/{strategy_id}/{symbol}")
def web_server_get_strategy_evaluation_for_symbol(strategy_id: str, symbol: str) -> dict:
    chosen_strategy_id = web_server_find_strategy_id_or_raise(strategy_id)
    for symbol_result in web_server_load_snapshot_or_empty_snapshot()["symbol_result_list"]:
        if symbol_result["symbol"] == symbol:
            return symbol_result["evaluation_by_strategy_id"][chosen_strategy_id]
    raise HTTPException(status_code=404, detail="Unknown symbol: " + symbol)
