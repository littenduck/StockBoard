import datetime
import io
import urllib.error

import pandas
import pytest

from stock_benchmark_backend import cboe_data

VIX_CSV = "DATE,OPEN,HIGH,LOW,CLOSE\n01/02/1990,17.24,17.24,17.24,17.24\n01/03/1990,18.19,18.19,18.19,18.19\n"
SKEW_CSV = "DATE,SKEW\n01/02/1990,126.09\n01/03/1990,123.54\n"
OLD_PUT_CALL_CSV = (
    "Volume and Put/Call Ratio data is compiled for the convenience of site visitors.\n"
    ", PRODUCT: TOTAL,,EXCHANGE: Cboe,\n"
    "DATE,CALLS,PUTS,TOTAL,P/C Ratio\n"
    "11/1/2006,1401036,1271445,2672481,0.91\n"
    "11/2/2006,1348240,1218592,2566832,0.9\n"
    "10/04/2019, 2175006, 2289715, 4464721, 1.05\n"
)
DAILY_JSON = '{"ratios": [{"name": "INDEX PUT/CALL RATIO", "value": "1.10"}, {"name": "TOTAL PUT/CALL RATIO", "value": "0.93"}]}'


def test_index_history_uses_the_close_column_or_the_single_value_column():
    vix = cboe_data.cboe_data_parse_index_history_csv(VIX_CSV)
    assert list(vix.values) == [17.24, 18.19] and vix.index[0] == pandas.Timestamp("1990-01-02")
    skew = cboe_data.cboe_data_parse_index_history_csv(SKEW_CSV)
    assert list(skew.values) == [126.09, 123.54]


def test_old_put_call_csv_skips_the_notice_lines_and_stray_spaces():
    series = cboe_data.cboe_data_parse_old_put_call_csv(OLD_PUT_CALL_CSV)
    assert list(series.values) == [0.91, 0.9, 1.05]
    assert series.index[0] == pandas.Timestamp("2006-11-01") and series.index[-1] == pandas.Timestamp("2019-10-04")


def test_daily_statistics_json_gives_the_total_ratio_or_none():
    assert cboe_data.cboe_data_parse_daily_statistics_json(DAILY_JSON) == 0.93
    assert cboe_data.cboe_data_parse_daily_statistics_json('{"ratios": []}') is None


def raise_http_error(code):
    def urlopen(url, timeout=None):
        raise urllib.error.HTTPError(url, code, "x", {}, io.BytesIO(b""))
    return urlopen


def test_a_missing_day_is_none_but_a_server_error_is_raised(monkeypatch):
    monkeypatch.setattr(cboe_data.urllib.request, "urlopen", raise_http_error(403))
    assert cboe_data.cboe_data_fetch_daily_total_put_call_ratio(datetime.date(2026, 10, 24)) is None
    monkeypatch.setattr(cboe_data.urllib.request, "urlopen", raise_http_error(500))
    with pytest.raises(urllib.error.HTTPError):
        cboe_data.cboe_data_fetch_daily_total_put_call_ratio(datetime.date(2026, 10, 23))


def test_cache_update_skips_weekends_and_holidays_and_resumes(tmp_path):
    cache_path = str(tmp_path / "cache" / "put_call.csv")
    requested = []

    def fetch_day(day):
        requested.append(day)
        return None if day == datetime.date(2019, 10, 9) else 1.0 + day.day / 100  # 2019-10-09 plays a holiday

    first = cboe_data.cboe_data_update_total_put_call_cache(cache_path, datetime.date(2019, 10, 14), 0, fetch_day)
    # 7, 8, 10, 11 and 14 October are trading days; 9 October has no file; 12 and 13 October are a weekend.
    assert [day.isoformat() for day in first.index.date] == ["2019-10-07", "2019-10-08", "2019-10-10", "2019-10-11", "2019-10-14"]
    assert datetime.date(2019, 10, 12) not in requested and datetime.date(2019, 10, 13) not in requested
    requested.clear()
    second = cboe_data.cboe_data_update_total_put_call_cache(cache_path, datetime.date(2019, 10, 16), 0, fetch_day)
    assert requested == [datetime.date(2019, 10, 15), datetime.date(2019, 10, 16)]
    assert len(second) == 7


def test_cache_update_keeps_progress_when_a_request_fails(tmp_path):
    cache_path = str(tmp_path / "put_call.csv")
    calls = []

    def fetch_day(day):
        calls.append(day)
        if len(calls) == 3:
            raise RuntimeError("network down")
        return 1.0

    with pytest.raises(RuntimeError):
        cboe_data.cboe_data_update_total_put_call_cache(cache_path, datetime.date(2019, 10, 14), 0, fetch_day)
    assert len(cboe_data.cboe_data_load_put_call_cache(cache_path)) == 2


def test_combined_put_call_series_joins_the_old_csv_and_the_cache(tmp_path):
    cache_path = str(tmp_path / "put_call.csv")
    old_series = cboe_data.cboe_data_parse_old_put_call_csv(OLD_PUT_CALL_CSV)
    cboe_data.cboe_data_save_put_call_cache(
        pandas.Series([9.9, 0.8], index=pandas.to_datetime(["2019-10-03", "2019-10-07"])), cache_path)
    combined = cboe_data.cboe_data_build_total_put_call_ratio_series(cache_path, old_series)
    assert combined.index[-2:].strftime("%Y-%m-%d").tolist() == ["2019-10-04", "2019-10-07"]
    assert combined.loc["2019-10-04"] == 1.05 and combined.index.is_unique


def test_combined_put_call_series_works_without_a_cache_file(tmp_path):
    old_series = cboe_data.cboe_data_parse_old_put_call_csv(OLD_PUT_CALL_CSV)
    assert len(cboe_data.cboe_data_build_total_put_call_ratio_series(str(tmp_path / "none.csv"), old_series)) == 3
