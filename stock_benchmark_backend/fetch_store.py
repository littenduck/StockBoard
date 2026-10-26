"""Keep on disk what the fetch cache downloaded, so a restart reads it instead of downloading it again.

One pickle file per downloaded answer, the latest only (a new answer replaces the old one):
  data/symbols/<SYMBOL>/<group>.pkl   an answer about one symbol (company figures, option chains, short interest ...), and the part
                                      of a batched answer that belongs to the symbol (its price history, its latest quote)
  data/market/<group>.pkl             an answer that is the same for every symbol (FRED, CNN, AAII ...)
Each file holds {group, key, fetched_at, value}. A file that cannot be read (another pandas version, a cut write) is skipped, so the
answer is simply downloaded again. Delete a symbol's folder to forget it.
"""
import os
import pickle
import re
from typing import Any, Dict, Optional, Tuple

from stock_benchmark_backend.run_log import run_log_write

SPLIT_KEY = "all"  # a batched answer: a dict by symbol, kept as one file per symbol
MARKET_KEY_SET = {None, "treasury"}  # answers that belong to no symbol; every other key is a symbol


def fetch_store_safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._^=\-]", "_", name).lstrip(".") or "_"


def fetch_store_write_file(file_path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    temporary_file_path = file_path + ".tmp"
    with open(temporary_file_path, "wb") as temporary_file:
        pickle.dump(payload, temporary_file)
    os.replace(temporary_file_path, file_path)


def fetch_store_save_answer(store_directory: str, group_id: str, key: Optional[str], fetched_at: float, value: Any) -> None:
    if key == SPLIT_KEY and isinstance(value, dict):
        for symbol, part in value.items():
            fetch_store_write_file(os.path.join(store_directory, "symbols", fetch_store_safe_name(symbol), group_id + ".pkl"),
                                   {"group": group_id, "key": SPLIT_KEY, "symbol": symbol, "fetched_at": fetched_at, "value": part})
    elif key in MARKET_KEY_SET:
        fetch_store_write_file(os.path.join(store_directory, "market", fetch_store_safe_name("{}__{}".format(group_id, key or "")) + ".pkl"),
                               {"group": group_id, "key": key, "fetched_at": fetched_at, "value": value})
    else:
        fetch_store_write_file(os.path.join(store_directory, "symbols", fetch_store_safe_name(key), group_id + ".pkl"),
                               {"group": group_id, "key": key, "fetched_at": fetched_at, "value": value})


def fetch_store_load_answers(store_directory: str) -> Dict[Tuple[str, Optional[str]], Tuple[float, Any]]:
    """{(group, key): (fetched_at, value)}; the parts of a batched answer are put back together, dated by their oldest part."""
    answer_by_key: Dict[Tuple[str, Optional[str]], Tuple[float, Any]] = {}
    for directory, _, file_name_list in os.walk(store_directory):
        for file_name in sorted(file_name_list):
            if not file_name.endswith(".pkl"):
                continue
            file_path = os.path.join(directory, file_name)
            try:
                with open(file_path, "rb") as stored_file:
                    payload = pickle.load(stored_file)
                group_id, key, fetched_at, value = payload["group"], payload["key"], float(payload["fetched_at"]), payload["value"]
                if key == SPLIT_KEY:
                    old_fetched_at, part_by_symbol = answer_by_key.get((group_id, key), (fetched_at, {}))
                    part_by_symbol[payload["symbol"]] = value
                    answer_by_key[(group_id, key)] = (min(old_fetched_at, fetched_at), part_by_symbol)
                else:
                    answer_by_key[(group_id, key)] = (fetched_at, value)
            except Exception as error:  # an unreadable file only means one more download
                run_log_write("store skipped {} {}".format(file_path, str(error)[:100]))
    return answer_by_key
