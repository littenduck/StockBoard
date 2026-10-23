# Indicator

Every indicator a strategy rule can use. A rule refers to an indicator by its `indicator_id`.
A value that cannot be fetched is `unknown` (shown as ❓, left out of the score).

## Volatility (market, same for every symbol)

| indicator_id | Meaning | Source |
|---|---|---|
| `vix_level` | VIX close | yfinance `^VIX` |
| `vxn_level` | VXN close | yfinance `^VXN` |
| `vvix_level` | VVIX close | yfinance `^VVIX` |
| `vix_term_structure_is_contango` | `^VIX` below `^VIX3M` | yfinance |

## Rates and credit (market)

| indicator_id | Meaning | Source |
|---|---|---|
| `treasury_ten_year_yield` | 10Y yield, percent | FRED `DGS10` (public CSV, no key) |
| `treasury_ten_year_yield_twenty_day_change_basis_points` | 20 trading day change | FRED `DGS10` |
| `high_yield_credit_spread_basis_points` | HY option adjusted spread | FRED `BAMLH0A0HYM2` |

## Market trend and sentiment

| indicator_id | Meaning | Source |
|---|---|---|
| `spx_above_two_hundred_day_average` | `^GSPC` close above its 200 day average | yfinance |
| `fear_greed_index` | CNN Fear and Greed | no free stable source, always unknown for now |

## Symbol technicals

| indicator_id | Meaning | Source |
|---|---|---|
| `last_price` | latest close | yfinance |
| `fifty_two_week_range_percentile` | position in 52 week range, 0 to 100 | yfinance daily history |
| `price_above_two_hundred_day_average` | close above 200 day average | yfinance daily history |
| `realized_volatility_thirty_day` | annualized, percent | yfinance daily history |
| `no_earnings_before_expiration` | no earnings date within the longest day count of the first (standard) expiration window | yfinance calendar |

## Symbol option contract (per expiration window)

Computed for the representative put of each expiration window.

| indicator_id | Meaning | Source |
|---|---|---|
| `selected_put_absolute_delta` | Black-Scholes delta, absolute value | computed from yfinance chain |
| `selected_put_days_to_expiration` | days to expiration | yfinance chain |
| `selected_put_annualized_return_percent` | bid divided by strike, annualized | yfinance chain |
| `selected_put_implied_volatility_exceeds_realized` | implied volatility above realized | yfinance chain |

## Not built yet

Account values (net value, cash, positions) and the strategy gates that need them (capital structure, position limits). Macro event dates (FOMC, CPI) are kept by hand in `config/settings.yaml`.
