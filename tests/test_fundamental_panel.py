from stock_benchmark_backend import refresh_scheduler
from stock_benchmark_backend.strategy_evaluation import IndicatorValue


def test_fundamental_list_has_company_groups_only_and_keeps_unit_and_source():
    info = refresh_scheduler.refresh_scheduler_get_fundamental_indicator_info()
    assert info["return_on_equity_percent"] == {"group_id": "QUA", "unit": "%"}
    assert "market_capitalization_billion_usd" not in info  # not used by a rule in a company group
    assert {entry["group_id"] for entry in info.values()} <= {"IND", "QUA", "MGT", "VAL", "ACC"}  # MAC is macro, not company


def test_fundamental_value_list_only_lists_known_values_with_source():
    value_by_name = {
        "return_on_equity_percent": IndicatorValue("return_on_equity_percent", 148.75, "SEC EDGAR"),
        "gross_margin_percent": IndicatorValue("gross_margin_percent", None, "SEC EDGAR"),
        "vix_level": IndicatorValue("vix_level", 17.0, "CBOE"),  # not a fundamental indicator
    }
    value_list = refresh_scheduler.refresh_scheduler_build_fundamental_value_list(value_by_name)
    assert value_list == [{"indicator_name": "return_on_equity_percent", "group_id": "QUA", "unit": "%", "value": 148.75, "source": "SEC EDGAR"}]


def test_empty_price_history_gives_no_series_and_dates_lose_their_time_zone(monkeypatch):
    import pandas
    from stock_benchmark_backend import live_indicators

    class FakeTicker:
        def __init__(self, history):
            self.history_table = history

        def history(self, period, auto_adjust):
            return self.history_table

    monkeypatch.setattr(live_indicators.yfinance, "Ticker", lambda symbol: FakeTicker(pandas.DataFrame()))
    assert live_indicators.live_indicators_fetch_price_series_or_none("AAOI") is None

    dated = pandas.DataFrame({"Close": [1.0, 2.0]}, index=pandas.DatetimeIndex(["2021-10-29", "2021-11-01"]).tz_localize("America/New_York"))
    monkeypatch.setattr(live_indicators.yfinance, "Ticker", lambda symbol: FakeTicker(dated))
    series = live_indicators.live_indicators_fetch_price_series_or_none("AAPL")
    assert series.index.tz is None and series.index[0] == pandas.Timestamp("2021-10-29")
