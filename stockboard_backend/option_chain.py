"""Pick one representative put contract per expiration window from the yfinance option chain."""
import datetime
import math
from dataclasses import dataclass
from typing import List, Optional

import pandas
import yfinance

DEFAULT_RISK_FREE_RATE_PERCENT = 4.0


@dataclass
class SelectedPutContract:
    expiration_date: datetime.date
    strike_price: float
    absolute_delta: float
    implied_volatility: float
    premium: float
    days_to_expiration: int
    annualized_return_percent: float
    bid: float = 0.0
    ask: float = 0.0
    open_interest: Optional[float] = None
    volume: Optional[float] = None


def option_chain_read_number_or_none(value) -> Optional[float]:
    return None if value is None or pandas.isna(value) else float(value)


def option_chain_fetch_expiration_date_list_by_symbol(symbol: str) -> List[datetime.date]:
    return [datetime.date.fromisoformat(text) for text in yfinance.Ticker(symbol).options]


def option_chain_determine_whether_date_is_monthly_expiration(expiration_date: datetime.date) -> bool:
    """Monthly options expire on the third Friday, which falls on day 15 to 21."""
    return expiration_date.weekday() == 4 and 15 <= expiration_date.day <= 21


def option_chain_determine_expiration_within_day_window(
    expiration_date_list: List[datetime.date], minimum_days: int, maximum_days: int, today: datetime.date,
) -> Optional[datetime.date]:
    """Prefer a monthly expiration in the window, else any expiration. Closest to the window middle wins."""
    candidate_list = [d for d in expiration_date_list if minimum_days <= (d - today).days <= maximum_days]
    monthly_list = [d for d in candidate_list if option_chain_determine_whether_date_is_monthly_expiration(d)]
    middle_days = (minimum_days + maximum_days) / 2
    pool = monthly_list or candidate_list
    return min(pool, key=lambda d: abs((d - today).days - middle_days)) if pool else None


def option_chain_fetch_put_contract_table_by_symbol_and_expiration(
    symbol: str, expiration_date: datetime.date,
) -> pandas.DataFrame:
    return yfinance.Ticker(symbol).option_chain(expiration_date.isoformat()).puts


def option_chain_fetch_call_contract_table_by_symbol_and_expiration(symbol: str, expiration_date: datetime.date) -> pandas.DataFrame:
    return yfinance.Ticker(symbol).option_chain(expiration_date.isoformat()).calls


def option_chain_determine_covered_call_strike_premium_percent(
    call_contract_table: pandas.DataFrame, underlying_price: float, target_percent: float = 10.0,
) -> Optional[float]:
    """How far above the price the covered call strike sits, in percent: the listed strike closest to the target above the price."""
    strike_series = call_contract_table["strike"][call_contract_table["strike"] > underlying_price]
    if strike_series.empty or underlying_price <= 0:
        return None
    target_strike = underlying_price * (1 + target_percent / 100)
    chosen_strike = strike_series.iloc[(strike_series - target_strike).abs().argsort().iloc[0]]
    return round(float((chosen_strike / underlying_price - 1) * 100), 2)


def option_chain_calculate_black_scholes_put_delta(
    underlying_price: float, strike_price: float, days_to_expiration: int,
    implied_volatility: float, risk_free_rate_percent: float,
) -> float:
    """Put delta, a number from -1 to 0. Returns -0.0 when the inputs cannot be priced."""
    years = days_to_expiration / 365
    if years <= 0 or implied_volatility <= 0 or underlying_price <= 0 or strike_price <= 0:
        return -0.0
    d_one = (math.log(underlying_price / strike_price)
             + (risk_free_rate_percent / 100 + implied_volatility ** 2 / 2) * years) / (implied_volatility * math.sqrt(years))
    return 0.5 * (1 + math.erf(d_one / math.sqrt(2))) - 1


def option_chain_calculate_black_scholes_put_price(
    underlying_price: float, strike_price: float, days_to_expiration: int, volatility: float, risk_free_rate_percent: float,
) -> float:
    years, rate = days_to_expiration / 365, risk_free_rate_percent / 100
    d_one = (math.log(underlying_price / strike_price) + (rate + volatility ** 2 / 2) * years) / (volatility * math.sqrt(years))
    d_two = d_one - volatility * math.sqrt(years)
    normal_cdf = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    return strike_price * math.exp(-rate * years) * normal_cdf(-d_two) - underlying_price * normal_cdf(-d_one)


def option_chain_calculate_implied_volatility_from_put_price(
    put_price: float, underlying_price: float, strike_price: float, days_to_expiration: int, risk_free_rate_percent: float,
) -> Optional[float]:
    """The volatility that makes the Black-Scholes put worth put_price, found by bisection (a decimal such as 0.27).
    Worked out here from the quote instead of trusting the figure in the Yahoo table, which is meaningless when the quote is stale.
    None when the price is below the put's floor or above its ceiling."""
    if days_to_expiration <= 0 or underlying_price <= 0 or strike_price <= 0 or put_price <= 0:
        return None
    low, high = 0.01, 5.0
    price_at = lambda volatility: option_chain_calculate_black_scholes_put_price(
        underlying_price, strike_price, days_to_expiration, volatility, risk_free_rate_percent)
    if not price_at(low) <= put_price <= price_at(high):
        return None
    for _ in range(60):
        middle = (low + high) / 2
        low, high = (middle, high) if price_at(middle) < put_price else (low, middle)
    return (low + high) / 2


def option_chain_determine_representative_put_contract_from_table(
    put_contract_table: pandas.DataFrame, underlying_price: float, expiration_date: datetime.date,
    today: datetime.date, target_absolute_delta: float, risk_free_rate_percent: float,
) -> Optional[SelectedPutContract]:
    """Out of the money put whose absolute delta is closest to the target. Only contracts with a live bid
    and ask count: when the market is closed yfinance returns empty quotes, so no contract is returned and the option
    rules read unknown. The implied volatility is worked out from the mid price, not read from the Yahoo table."""
    days_to_expiration = (expiration_date - today).days
    best_contract = None
    for row in put_contract_table.itertuples():
        if row.strike >= underlying_price or row.bid <= 0 or row.ask <= 0:
            continue
        premium = (row.bid + row.ask) / 2
        implied_volatility = option_chain_calculate_implied_volatility_from_put_price(
            premium, underlying_price, row.strike, days_to_expiration, risk_free_rate_percent)
        if implied_volatility is None:
            continue
        absolute_delta = abs(option_chain_calculate_black_scholes_put_delta(
            underlying_price, row.strike, days_to_expiration, implied_volatility, risk_free_rate_percent))
        if best_contract is None or abs(absolute_delta - target_absolute_delta) < abs(best_contract.absolute_delta - target_absolute_delta):
            best_contract = SelectedPutContract(
                expiration_date=expiration_date, strike_price=float(row.strike),
                absolute_delta=round(absolute_delta, 3), implied_volatility=float(implied_volatility),
                premium=float(premium), days_to_expiration=days_to_expiration,
                annualized_return_percent=round(premium / row.strike * 365 / days_to_expiration * 100, 1),
                bid=float(row.bid), ask=float(row.ask),
                open_interest=option_chain_read_number_or_none(getattr(row, "openInterest", None)),
                volume=option_chain_read_number_or_none(getattr(row, "volume", None)))
    return best_contract


def option_chain_calculate_put_skew_points(
    put_contract_table: pandas.DataFrame, underlying_price: float, days_to_expiration: int = 30, risk_free_rate_percent: float = DEFAULT_RISK_FREE_RATE_PERCENT,
) -> Optional[float]:
    """Implied volatility of the put struck about 10% below the price minus that of the at-the-money put, in volatility points.
    Each volatility is worked out from the mid of a live bid and ask; strikes without a live quote do not count."""
    live_table = put_contract_table[(put_contract_table["bid"] > 0) & (put_contract_table["ask"] > 0)]
    if len(live_table) < 2:
        return None

    def volatility_of(row) -> Optional[float]:
        return option_chain_calculate_implied_volatility_from_put_price(
            (row["bid"] + row["ask"]) / 2, underlying_price, row["strike"], days_to_expiration, risk_free_rate_percent)

    at_the_money = live_table.iloc[(live_table["strike"] - underlying_price).abs().argsort().iloc[0]]
    out_of_the_money = live_table.iloc[(live_table["strike"] - underlying_price * 0.9).abs().argsort().iloc[0]]
    if out_of_the_money["strike"] >= at_the_money["strike"]:
        return None
    at_the_money_volatility, out_of_the_money_volatility = volatility_of(at_the_money), volatility_of(out_of_the_money)
    if at_the_money_volatility is None or out_of_the_money_volatility is None:
        return None
    return round((out_of_the_money_volatility - at_the_money_volatility) * 100, 2)
