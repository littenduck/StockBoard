import os

import pandas

from stockboard_backend import fetch_cache, fetch_store, indicator_registry
from stockboard_backend.settings_loader import PROJECT_DIRECTORY


def build_registry():
    return indicator_registry.indicator_registry_load_from_yaml_file(os.path.join(PROJECT_DIRECTORY, "config", "indicators.yaml"))


def test_an_answer_about_one_symbol_and_a_market_answer_go_to_their_own_files(tmp_path):
    fetch_store.fetch_store_save_answer(str(tmp_path), "yahoo_company", "AAPL", 100.0, {"price": 1})
    fetch_store.fetch_store_save_answer(str(tmp_path), "fred", None, 200.0, [1, 2])
    fetch_store.fetch_store_save_answer(str(tmp_path), "fred", "treasury", 300.0, "series")
    assert (tmp_path / "symbols" / "AAPL" / "yahoo_company.pkl").exists()
    assert (tmp_path / "market" / "fred__.pkl").exists() and (tmp_path / "market" / "fred__treasury.pkl").exists()
    loaded = fetch_store.fetch_store_load_answers(str(tmp_path))
    assert loaded[("yahoo_company", "AAPL")] == (100.0, {"price": 1}) and loaded[("fred", None)] == (200.0, [1, 2]) and loaded[("fred", "treasury")][1] == "series"


def test_a_batched_answer_is_kept_per_symbol_and_put_back_together(tmp_path):
    history = {"AAPL": pandas.DataFrame({"Close": [1.0, 2.0]}), "^VIX": pandas.DataFrame({"Close": [3.0]})}
    fetch_store.fetch_store_save_answer(str(tmp_path), "yahoo_history", "all", 100.0, history)
    assert (tmp_path / "symbols" / "AAPL" / "yahoo_history.pkl").exists() and (tmp_path / "symbols" / "^VIX" / "yahoo_history.pkl").exists()
    fetched_at, value = fetch_store.fetch_store_load_answers(str(tmp_path))[("yahoo_history", "all")]
    assert fetched_at == 100.0 and set(value) == {"AAPL", "^VIX"} and value["AAPL"]["Close"].tolist() == [1.0, 2.0]


def test_a_file_that_cannot_be_read_is_skipped(tmp_path):
    fetch_store.fetch_store_save_answer(str(tmp_path), "finra", "AAPL", 1.0, "ok")
    (tmp_path / "symbols" / "MSFT").mkdir(parents=True)
    (tmp_path / "symbols" / "MSFT" / "finra.pkl").write_bytes(b"not a pickle")
    assert list(fetch_store.fetch_store_load_answers(str(tmp_path))) == [("finra", "AAPL")]


def test_a_new_cache_reuses_what_an_earlier_one_kept_until_it_is_due(tmp_path):
    clock = {"now": 1000.0}
    first = fetch_cache.FetchCache(build_registry(), lambda now: True, lambda: clock["now"], store_directory=str(tmp_path))
    calls = []
    first.get("fred", None, lambda: calls.append("first") or "value")
    second = fetch_cache.FetchCache(build_registry(), lambda now: True, lambda: clock["now"] + 3600, store_directory=str(tmp_path))
    assert second.get("fred", None, lambda: calls.append("second") or "new")[0] == "value" and calls == ["first"]  # fred is due every day
    third = fetch_cache.FetchCache(build_registry(), lambda now: True, lambda: clock["now"] + 3 * 86400, store_directory=str(tmp_path))
    assert third.get("fred", None, lambda: calls.append("third") or "new")[0] == "new" and calls == ["first", "third"]


def test_a_cache_without_a_store_directory_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fetch_cache.FetchCache(build_registry(), lambda now: True).get("fred", None, lambda: 1)
    assert list(tmp_path.iterdir()) == []
