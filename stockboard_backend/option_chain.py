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


def option_chain_determine_representative_put_contract_from_table(
    put_contract_table: pandas.DataFrame, underlying_price: float, expiration_date: datetime.date,
    today: datetime.date, target_absolute_delta: float, risk_free_rate_percent: float,
) -> Optional[SelectedPutContract]:
    """Out of the money put whose absolute delta is closest to the target. Only contracts with a live bid
    and ask count: when the market is closed yfinance returns empty quotes and meaningless implied
    volatility, so no contract is returned and the option rules read unknown."""
    days_to_expiration = (expiration_date - today).days
    best_contract = None
    for row in put_contract_table.itertuples():
        if row.strike >= underlying_price or row.bid <= 0 or row.ask <= 0 or row.impliedVolatility < 0.01:
            continue
        premium = (row.bid + row.ask) / 2
        absolute_delta = abs(option_chain_calculate_black_scholes_put_delta(
            underlying_price, row.strike, days_to_expiration, row.impliedVolatility, risk_free_rate_percent))
        if best_contract is None or abs(absolute_delta - target_absolute_delta) < abs(best_contract.absolute_delta - target_absolute_delta):
            best_contract = SelectedPutContract(
                expiration_date=expiration_date, strike_price=float(row.strike),
                absolute_delta=round(absolute_delta, 3), implied_volatility=float(row.impliedVolatility),
                premium=float(premium), days_to_expiration=days_to_expiration,
                annualized_return_percent=round(premium / row.strike * 365 / days_to_expiration * 100, 1),
                bid=float(row.bid), ask=float(row.ask),
                open_interest=option_chain_read_number_or_none(getattr(row, "openInterest", None)),
                volume=option_chain_read_number_or_none(getattr(row, "volume", None)))
    return best_contract


def option_chain_calculate_put_skew_points(put_contract_table: pandas.DataFrame, underlying_price: float) -> Optional[float]:
    """Implied volatility of the put struck about 10% below the price minus that of the at-the-money put, in volatility points.
    Only contracts with a live bid count (an empty quote has a meaningless implied volatility)."""
    live_table = put_contract_table[(put_contract_table["bid"] > 0) & (put_contract_table["impliedVolatility"] >= 0.01)]
    if len(live_table) < 2:
        return None
    at_the_money = live_table.iloc[(live_table["strike"] - underlying_price).abs().argsort().iloc[0]]
    out_of_the_money = live_table.iloc[(live_table["strike"] - underlying_price * 0.9).abs().argsort().iloc[0]]
    if out_of_the_money["strike"] >= at_the_money["strike"]:
        return None
    return round(float(out_of_the_money["impliedVolatility"] - at_the_money["impliedVolatility"]) * 100, 2)
