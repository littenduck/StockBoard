import numpy
import pandas

from stock_benchmark_backend import forward_returns


def build_daily_price(start_price, daily_growth, day_count, start="2024-01-01"):
    index = pandas.bdate_range(start, periods=day_count)
    return pandas.Series(start_price * (1 + daily_growth) ** numpy.arange(day_count), index=index)


def test_constant_growth_gives_compound_return_from_the_score_date():
    price = build_daily_price(100.0, 0.01, 30)
    table = forward_returns.forward_returns_build_table({"AAA": price}, [5])[5]
    assert numpy.isclose(table["AAA"].iloc[0], 1.01 ** 5 - 1)
    assert table["AAA"].iloc[-5:].isna().all()


def test_return_is_left_out_when_the_window_contains_a_missing_day():
    full = build_daily_price(100.0, 0.01, 30)
    holed = full.drop(pandas.Timestamp("2024-01-09"))
    table = forward_returns.forward_returns_build_table({"AAA": holed, "BBB": full}, [5])[5]
    assert pandas.isna(table["AAA"].loc[pandas.Timestamp("2024-01-05")])
    assert pandas.notna(table["BBB"].loc[pandas.Timestamp("2024-01-05")])


def test_sector_neutral_subtracts_the_etf_return_over_the_same_window():
    price = build_daily_price(100.0, 0.01, 30)
    etf_price = build_daily_price(50.0, 0.0, 30)
    return_table = forward_returns.forward_returns_build_table({"AAA": price}, [5])[5]
    etf_return_table = forward_returns.forward_returns_build_table({"XLK": etf_price}, [5])[5]
    excess = forward_returns.forward_returns_subtract_sector_etf(return_table, {"AAA": "XLK"}, etf_return_table)
    assert numpy.isclose(excess["AAA"].iloc[0], 1.01 ** 5 - 1)


def test_symbol_without_an_etf_mapping_is_left_out():
    price = build_daily_price(100.0, 0.01, 30)
    return_table = forward_returns.forward_returns_build_table({"AAA": price}, [5])[5]
    excess = forward_returns.forward_returns_subtract_sector_etf(return_table, {}, pandas.DataFrame(index=return_table.index))
    assert "AAA" not in excess.columns
