"""FastAPI server: the web page plus a versioned JSON API (/api/v1) that any client can use."""
import contextlib
import dataclasses
import datetime
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from stockboard_backend import (indicator_calculation, market_data, refresh_scheduler, request_limiter, rule_catalog,
                                settings_loader, snapshot_storage, strategy_loader)

PROJECT_DIRECTORY = settings_loader.PROJECT_DIRECTORY
application_settings = settings_loader.settings_loader_load_settings_from_yaml_file(
    os.path.join(PROJECT_DIRECTORY, "config", "settings.yaml"))
application_rule_catalog = rule_catalog.rule_catalog_load_rule_catalog_from_yaml_file(
    os.path.join(PROJECT_DIRECTORY, "config", "rules.yaml"))
strategy_definition_by_id = strategy_loader.strategy_loader_load_all_strategy_definitions_from_directory(
    os.path.join(PROJECT_DIRECTORY, "strategies"), application_rule_catalog)

validation_error_list = rule_catalog.rule_catalog_validate_rule_catalog_against_known_indicators(
    application_rule_catalog, indicator_calculation.KNOWN_INDICATOR_ID_SET) + [
    error for strategy_definition in strategy_definition_by_id.values()
    for error in strategy_loader.strategy_loader_validate_strategy_definition_against_known_indicators(
        strategy_definition, indicator_calculation.KNOWN_INDICATOR_ID_SET)]
if validation_error_list or application_settings.default_strategy_id not in strategy_definition_by_id:
    raise SystemExit("Invalid configuration: " + "; ".join(validation_error_list or ["default strategy missing"]))


@contextlib.asynccontextmanager
async def web_server_run_application_lifespan(application: FastAPI):
    refresh_scheduler.refresh_scheduler_start_background_refresh_thread(
        application_settings, strategy_definition_by_id)
    yield


app = FastAPI(lifespan=web_server_run_application_lifespan)
if application_settings.allowed_origin_list:
    app.add_middleware(CORSMiddleware, allow_origins=application_settings.allowed_origin_list, allow_methods=["GET"])
if application_settings.max_requests_per_second > 0:
    app.add_middleware(request_limiter.RequestLimiterMiddleware,
                       requests_per_second=application_settings.max_requests_per_second)

# (file stamp, parsed snapshot). Replaced as one tuple, so concurrent requests need no lock.
snapshot_cache = (None, None)


def web_server_load_snapshot_or_empty_snapshot() -> dict:
    """Parse the snapshot file once and reuse it until the refresher replaces the file.

    A snapshot from an older schema counts as missing; the refresher rebuilds it.
    """
    global snapshot_cache
    path = refresh_scheduler.SNAPSHOT_FILE_PATH
    status = os.stat(path) if os.path.exists(path) else None
    # The stamp is read before the file, so the cached content is never older than its stamp.
    stamp = (path, status and (status.st_ino, status.st_mtime_ns, status.st_size))
    if snapshot_cache[0] != stamp:
        snapshot = snapshot_storage.snapshot_storage_load_snapshot_from_json_file(path)
        if snapshot is None or snapshot.get("schema_version") != refresh_scheduler.SNAPSHOT_SCHEMA_VERSION:
            snapshot = {"schema_version": refresh_scheduler.SNAPSHOT_SCHEMA_VERSION, "generated_at": None,
                        "market_indicator_card_list": [], "symbol_result_list": [], "failed_symbol_list": []}
        snapshot_cache = (stamp, snapshot)
    return snapshot_cache[1]


def web_server_find_strategy_id_or_raise(strategy_id: Optional[str]) -> str:
    chosen_strategy_id = strategy_id or application_settings.default_strategy_id
    if chosen_strategy_id not in strategy_definition_by_id:
        raise HTTPException(status_code=404, detail="Unknown strategy: " + chosen_strategy_id)
    return chosen_strategy_id


def web_server_build_status(generated_at: Optional[str]) -> dict:
    """Computed per request so clients can judge freshness against the server clock, not their own."""
    return {
        "server_time": refresh_scheduler.refresh_scheduler_get_current_exchange_time_text(),
        "generated_at": generated_at,
        "market_is_open": market_data.market_data_determine_whether_us_market_is_open(
            datetime.datetime.now(datetime.timezone.utc), application_settings.market_holiday_date_set,
            application_settings.market_early_close_date_set),
        "refresh_interval_minutes": application_settings.refresh_interval_minutes,
        "stale_after_minutes": application_settings.stale_after_minutes,
    }


@app.get("/")
def web_server_get_index_page() -> FileResponse:
    return FileResponse(os.path.join(PROJECT_DIRECTORY, "static", "index.html"),
                        headers={"Cache-Control": "no-cache"})


@app.get("/rules")
def web_server_get_rule_catalog_page() -> FileResponse:
    return FileResponse(os.path.join(PROJECT_DIRECTORY, "static", "rules.html"), headers={"Cache-Control": "no-cache"})


@app.get("/language.js")
def web_server_get_language_script() -> FileResponse:
    return FileResponse(os.path.join(PROJECT_DIRECTORY, "static", "language.js"), headers={"Cache-Control": "no-cache"})


@app.get("/icons.svg")
def web_server_get_icon_sprite() -> FileResponse:
    return FileResponse(os.path.join(PROJECT_DIRECTORY, "static", "icons.svg"), media_type="image/svg+xml",
                        headers={"Cache-Control": "no-cache"})


@app.get("/favicon.svg")
def web_server_get_favicon() -> FileResponse:
    return FileResponse(os.path.join(PROJECT_DIRECTORY, "static", "favicon.svg"), media_type="image/svg+xml",
                        headers={"Cache-Control": "no-cache"})


@app.get("/base.css")
def web_server_get_base_stylesheet() -> FileResponse:
    return FileResponse(os.path.join(PROJECT_DIRECTORY, "static", "base.css"), headers={"Cache-Control": "no-cache"})


@app.get("/api/v1/rules")
def web_server_get_rule_catalog() -> dict:
    """Every rule grouped by category, with the strategies (and their weights and veto flags) that use it."""
    usage_list_by_rule_id = {}
    for strategy in strategy_definition_by_id.values():
        for gate in strategy.gate_list:
            for rule in gate.rule_list:
                usage_list_by_rule_id.setdefault(rule.rule_id, []).append(
                    {"strategy_id": strategy.strategy_id, "display_name": dataclasses.asdict(strategy.display_name),
                     "weight": rule.weight, "veto": rule.veto})
    entry_list = list(application_rule_catalog.rule_entry_by_id.values())
    return {"default_language": application_settings.default_language, "group_list": [{
        "group_id": group.group_id, "display_name": dataclasses.asdict(group.display_name),
        "description": dataclasses.asdict(group.description),
        "aspect": dataclasses.asdict(group.aspect) if group.aspect else None,
        "rule_list": [{
            "rule_id": entry.rule_id, "name": dataclasses.asdict(entry.name),
            "description": dataclasses.asdict(entry.description), "method": entry.method,
            "quantifiable": entry.quantifiable, "backtestable": entry.backtestable,
            "history_source": entry.history_source, "history_start": entry.history_start, "status": entry.status,
            "indicator": entry.indicator,
            "operator": entry.operator, "value": entry.value, "band_of": entry.band_of, "legacy_id": entry.legacy_id,
            "note": dataclasses.asdict(entry.note) if entry.note else None,
            "used_by": usage_list_by_rule_id.get(entry.rule_id, []),
        } for entry in entry_list if entry.group_id == group.group_id],
    } for group in application_rule_catalog.rule_group_list]}


@app.get("/api/v1/strategies")
def web_server_get_strategy_list() -> dict:
    return {
        "default_strategy_id": application_settings.default_strategy_id,
        "default_language": application_settings.default_language,
        "strategy_list": [{"strategy_id": s.strategy_id, "display_name": dataclasses.asdict(s.display_name),
                           "summary": dataclasses.asdict(s.summary), "help_text": dataclasses.asdict(s.help_text),
                           "source": dataclasses.asdict(s.source)}
                          for s in sorted(strategy_definition_by_id.values(),
                                          key=lambda s: s.strategy_id != application_settings.default_strategy_id)],
    }


@app.get("/api/v1/snapshot")
def web_server_get_dashboard_snapshot(strategy_id: Optional[str] = None) -> dict:
    chosen_strategy_id = web_server_find_strategy_id_or_raise(strategy_id)
    snapshot = web_server_load_snapshot_or_empty_snapshot()
    symbol_card_list = []
    for symbol_result in snapshot["symbol_result_list"]:
        evaluation = symbol_result["evaluation_by_strategy_id"][chosen_strategy_id]
        symbol_card_list.append({
            "symbol": symbol_result["symbol"], "price": symbol_result["price"],
            "change_value": symbol_result["change_value"], "change_unit": symbol_result["change_unit"],
            "is_pass": evaluation["is_pass"], "score_percent": evaluation["score_percent"],
            "unknown_weight_ratio": evaluation["unknown_weight_ratio"],
            "sparkline_close_price_list": symbol_result["sparkline_close_price_list"],
        })
    return {
        "schema_version": snapshot["schema_version"],
        "status": web_server_build_status(snapshot["generated_at"]),
        "strategy_id": chosen_strategy_id,
        "max_unknown_weight_ratio": strategy_definition_by_id[chosen_strategy_id].thresholds.max_unknown_weight_ratio,
        "market_indicator_card_list": snapshot["market_indicator_card_list"],
        "symbol_card_list": symbol_card_list,
        "failed_symbol_list": snapshot["failed_symbol_list"],
    }


@app.get("/api/v1/evaluations/{strategy_id}/{symbol}")
def web_server_get_strategy_evaluation_for_symbol(strategy_id: str, symbol: str) -> dict:
    chosen_strategy_id = web_server_find_strategy_id_or_raise(strategy_id)
    for symbol_result in web_server_load_snapshot_or_empty_snapshot()["symbol_result_list"]:
        if symbol_result["symbol"] == symbol:
            return symbol_result["evaluation_by_strategy_id"][chosen_strategy_id]
    raise HTTPException(status_code=404, detail="Unknown symbol: " + symbol)
