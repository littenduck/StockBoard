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

Daily change of these indicators is reported in basis points (`change_unit: basis_points`); volatility indices and prices report percent change.

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

## Symbol trend and momentum

| indicator_id | Meaning | Source |
|---|---|---|
| `relative_strength_index_two_day` | RSI over 2 days, 0 to 100 (Connors pullback) | yfinance daily history |
| `relative_strength_index_fourteen_day` | RSI over 14 days, 0 to 100 | yfinance daily history |
| `price_above_fifty_day_average` | close above 50 day average | yfinance daily history |
| `fifty_day_average_above_two_hundred_day_average` | 50 day average above 200 day average (golden cross state) | yfinance daily history |
| `price_below_five_day_average` | close below 5 day average (short-term pullback) | yfinance daily history |
| `distance_from_fifty_two_week_high_percent` | percent below the 52 week high (0 = at the high) | yfinance daily history |
| `volume_ratio_to_twenty_day_average` | last volume divided by the previous 20 day average | yfinance daily history |
| `return_six_month_percent` | price change over 126 trading days, percent | yfinance daily history |

## Symbol option contract (per expiration window)

Computed for the representative put of each expiration window.

| indicator_id | Meaning | Source |
|---|---|---|
| `selected_put_absolute_delta` | Black-Scholes delta, absolute value | computed from yfinance chain |
| `selected_put_days_to_expiration` | days to expiration | yfinance chain |
| `selected_put_annualized_return_percent` | bid divided by strike, annualized | yfinance chain |
| `selected_put_implied_volatility_exceeds_realized` | implied volatility above realized | yfinance chain |

## History series (FRED and Cboe)

`stockboard_backend/history_series.py` rebuilds these indicators as a date-indexed series from free history, so a backtest and the live dashboard can share one definition. `python -m stockboard_backend.history_series` fetches every one and prints its first and last date, row count and latest value next to the start date in the rule catalog (the first date is later than the catalog start when a rolling window needs warm-up). The daily put/call cache is built once with `python -m stockboard_backend.cboe_data` (about 1,900 small requests, then only new days).

| indicator_id | Built from |
|---|---|
| `federal_funds_target_rate_not_raised_in_182_days` | FRED DFEDTAR (1982 to 2008-12-15) joined to DFEDTARU; true when the rate is not above its level 182 calendar days earlier |
| `six_month_treasury_bill_yield_minus_federal_funds_rate` | FRED DGS6MO minus DFF |
| `treasury_ten_year_yield` | FRED DGS10 |
| `treasury_ten_year_yield_twenty_day_change_basis_points` | FRED DGS10, change over 20 observations times 100 |
| `high_yield_credit_spread_basis_points` | FRED BAMLH0A0HYM2 times 100 (FRED keeps about 3 years) |
| `high_yield_credit_spread_twenty_day_change_basis_points` | FRED BAMLH0A0HYM2, change over 20 observations times 100 |
| `moodys_baa_minus_ten_year_treasury_spread` | FRED BAA10Y |
| `treasury_ten_year_minus_two_year_spread` | FRED T10Y2Y |
| `treasury_ten_year_minus_three_month_spread` | FRED T10Y3M |
| `consumer_price_index_year_over_year_percent` | FRED CPIAUCSL, 12 month percent change of the latest values (the point-in-time version uses ALFRED vintages) |
| `core_pce_price_index_year_over_year_percent` | FRED PCEPILFE, 12 month percent change |
| `sahm_rule_recession_indicator` | FRED SAHMREALTIME |
| `initial_jobless_claims_four_week_average` | FRED ICSA, 4 week mean |
| `chicago_fed_national_activity_index_three_month_average` | FRED CFNAIMA3 |
| `wti_crude_oil_price` | FRED DCOILWTICO |
| `wti_crude_oil_one_month_change_percent` | FRED DCOILWTICO, change over 21 observations |
| `m2_money_supply_year_over_year_percent` | FRED M2SL, 12 month percent change |
| `federal_reserve_total_assets_thirteen_week_change_percent` | FRED WALCL, change over 13 weeks |
| `market_value_to_gdp_percent` | FRED NCBEILQ027S (millions) divided by 1,000 and by GDP (billions) |
| `trade_policy_uncertainty_ten_year_percentile` | FRED EPUTRADE, percentile of the last 120 months |
| `us_epu_thirty_day_average_percentile_five_year` | FRED USEPUINDXD, 30 day mean, percentile of the last 5 years |
| `vix_level` | Cboe VIX_History.csv, close |
| `vix_term_structure_is_contango` | Cboe VIX below VIX3M (from 2009-09-18) |
| `vxn_to_vix_ratio` | Cboe VXN divided by VIX (from 2009-09-14) |
| `vix_to_twenty_day_average_ratio` | Cboe VIX divided by its 20 day mean |
| `put_call_ratio_total_five_day_average` | Cboe total put/call: old CSV 2006-11-01 to 2019-10-04, then the daily files kept in `data/cache/cboe_total_put_call.csv`; 5 day mean |

### Sentiment sources

| indicator_id | Built from |
|---|---|
| `fear_greed_index` | CNN `graphdata` JSON from 2021-01-04 (needs a cnn.com Referer and Origin header) |
| `aaii_bullish_percent`, `aaii_bullish_minus_bearish_percent` | AAII `sentiment.xls`, which blocks scripts, so the newest Internet Archive copy is read |
| `naaim_exposure_index` | NAAIM `USE_Data-since-Inception_*.xlsx`, the newest copy the Internet Archive holds |

The archive copies can be weeks behind the live sites and the archive answers 429 when asked too fast (the fetcher waits and retries). `python -m stockboard_backend.sentiment_data` prints the row count and date range of each.

### Company indicators (SEC EDGAR and FINRA)

`history_series_build_company_indicator_table(ticker, price_series)` returns one row per day with one column per company indicator id. Set the environment variable `EDGAR_CONTACT` (for example an email address) first: SEC asks every client to identify itself.

- **Point in time**: each filed figure is used from the day its filing reached EDGAR, and the earliest filing of a period wins over later restatements.
- **Trailing twelve months** come from a 10-K (the fiscal year) or a 10-Q (last fiscal year plus this year to date minus the same stretch a year earlier).
- **Columns without a price**: `trailing_twelve_month_eps`, revenue growth (1 year, 3 year CAGR), `eps_three_year_cagr_percent`, `return_on_equity_percent`, `return_on_invested_capital_percent` (approximate: operating income taxed at 21% over equity plus debt minus cash), `gross_margin_percent`, free cash flow and its yearly change, `net_debt_to_ebitda`, `interest_coverage_ratio`, `operating_cash_flow_to_net_income_ratio`, `shares_outstanding_year_over_year_percent`, `dividend_to_free_cash_flow_ratio`.
- **Columns that need a daily close**: `market_capitalization_billion_usd`, `free_cash_flow_yield_percent`, `enterprise_value_to_ebitda`, `price_earnings_ttm_to_five_year_median_ratio`.
- **FINRA**: `short_interest_percent_of_shares_outstanding` is the twice-monthly short position divided by the latest share count on file (history from 2017-12-29).
- **Not built yet**: the insider rules (`edgar:form345`) and the filing-based rules (`edgar:submissions`: audit problems, earnings dates).

`python -m stockboard_backend.fundamental_series AAPL` prints a sample of the table for one ticker.

## Planned indicators (not built yet)

Every rule in `config/rules.yaml` names the indicator that will give its value. These indicators do not exist in the code yet; the rule that uses each one, and where its free history comes from, is listed here. The meaning of each is in the rule's description.

| indicator_id | Rules | History source |
|---|---|---|
| `federal_funds_target_rate_not_raised_in_182_days` | `MAC-01` | `fred:DFEDTAR+DFEDTARU` |
| `six_month_treasury_bill_yield_minus_federal_funds_rate` | `MAC-02` | `fred:DGS6MO+DFF` |
| `high_yield_credit_spread_twenty_day_change_basis_points` | `MAC-06` | `fred:BAMLH0A0HYM2` |
| `moodys_baa_minus_ten_year_treasury_spread` | `MAC-22`, `MAC-23` | `fred:BAA10Y` |
| `treasury_ten_year_minus_two_year_spread` | `MAC-07` | `fred:T10Y2Y` |
| `treasury_ten_year_minus_three_month_spread` | `MAC-17` | `fred:T10Y3M` |
| `consumer_price_index_year_over_year_percent` | `MAC-08` | `alfred:CPIAUCSL` |
| `core_pce_price_index_year_over_year_percent` | `MAC-18` | `alfred:PCEPILFE` |
| `sahm_rule_recession_indicator` | `MAC-09` | `fred:SAHMREALTIME` |
| `initial_jobless_claims_four_week_average` | `MAC-19` | `fred:ICSA` |
| `chicago_fed_national_activity_index_three_month_average` | `MAC-20` | `fred:CFNAIMA3` |
| `us_dollar_index_twenty_day_change_percent` | `MAC-10` | `yfinance:DX-Y.NYB` |
| `wti_crude_oil_price` | `MAC-11` | `fred:DCOILWTICO` |
| `wti_crude_oil_one_month_change_percent` | `MAC-16` | `fred:DCOILWTICO` |
| `m2_money_supply_year_over_year_percent` | `MAC-12` | `fred:M2SL` |
| `federal_reserve_total_assets_thirteen_week_change_percent` | `MAC-21` | `fred:WALCL` |
| `sector_etf_return_minus_spy_return_one_hundred_twenty_six_day` | `IND-01` | `yfinance:sector-etfs` |
| `sector_next_year_eps_estimate_four_week_change_median_percent` | `IND-02` | `dolthub:earnings` |
| `trailing_twelve_month_eps` | `QUA-01` | `edgar:companyfacts` |
| `revenue_year_over_year_percent` | `QUA-02` | `edgar:companyfacts` |
| `revenue_three_year_cagr_percent` | `QUA-03` | `edgar:companyfacts` |
| `eps_three_year_cagr_percent` | `QUA-13` | `edgar:companyfacts` |
| `return_on_invested_capital_percent` | `QUA-04` | `edgar:companyfacts` |
| `return_on_equity_percent` | `QUA-14` | `edgar:companyfacts` |
| `gross_margin_percent` | `QUA-05` | `edgar:companyfacts` |
| `trailing_twelve_month_free_cash_flow` | `QUA-06` | `edgar:companyfacts` |
| `free_cash_flow_year_over_year_change` | `QUA-15` | `edgar:companyfacts` |
| `net_debt_to_ebitda` | `QUA-07`, `QUA-11` | `edgar:companyfacts` |
| `interest_coverage_ratio` | `QUA-12` | `edgar:companyfacts` |
| `operating_cash_flow_to_net_income_ratio` | `QUA-08`, `QUA-16` | `edgar:companyfacts` |
| `eps_estimate_next_year_four_week_change_percent` | `QUA-09` | `dolthub:earnings` |
| `buy_rating_share_percent` | `QUA-10` | `yfinance:upgrades_downgrades` |
| `insider_net_open_market_selling_percent_of_shares_180_days` | `MGT-01` | `edgar:form345` |
| `insider_open_market_purchase_count_90_days` | `MGT-05` | `edgar:form345` |
| `shares_outstanding_year_over_year_percent` | `MGT-02`, `MGT-06` | `edgar:companyfacts` |
| `dividend_to_free_cash_flow_ratio` | `MGT-03` | `edgar:companyfacts` |
| `no_audit_or_late_filing_problem_in_last_365_days` | `MGT-04` | `edgar:submissions` |
| `sp500_forward_pe` | `VAL-01` | `wayback:sp-dji-eps` |
| `equity_risk_premium_simple_percent` | `VAL-03` | `shiller:ie_data` |
| `shiller_cape` | `VAL-11` | `shiller:ie_data` |
| `damodaran_implied_equity_risk_premium_percent` | `VAL-12` | `damodaran:implied-erp` |
| `market_value_to_gdp_percent` | `VAL-04`, `VAL-14` | `fred:NCBEILQ027S` |
| `price_earnings_ttm_to_five_year_median_ratio` | `VAL-05` | `edgar:companyfacts` |
| `forward_pe_to_trailing_pe_ratio` | `VAL-06` | `dolthub:earnings` |
| `enterprise_value_to_ebitda` | `VAL-07` | `edgar:companyfacts` |
| `peg_ratio` | `VAL-13` | `dolthub:earnings` |
| `free_cash_flow_yield_percent` | `VAL-08`, `VAL-10` | `edgar:companyfacts` |
| `vxn_to_vix_ratio` | `SEN-03` | `yfinance:^VXN` |
| `aaii_bullish_minus_bearish_percent` | `SEN-05` | `aaii:sentiment` |
| `aaii_bullish_percent` | `SEN-20` | `aaii:sentiment` |
| `naaim_exposure_index` | `SEN-06`, `SEN-21` | `naaim:exposure-index` |
| `put_call_ratio_total_five_day_average` | `SEN-07`, `SEN-22` | `cboe:putcall` |
| `no_mega_ipo_in_last_30_trading_days` | `SEN-08` | `ritter:ipo-data` |
| `short_interest_percent_of_shares_outstanding` | `SEN-09`, `SEN-19` | `finra:short-interest` |
| `sp500_share_above_two_hundred_day_average_percent` | `TRD-02`, `TRD-21` | `fja05680:sp500-components` |
| `rsp_to_spy_ratio_above_two_hundred_day_average` | `TRD-22` | `yfinance:RSP` |
| `no_new_fifty_two_week_low_in_last_20_days` | `TRD-23` | `yfinance:daily-prices` |
| `return_one_hundred_twenty_six_day_minus_spy_percent` | `TRD-09` | `yfinance:daily-prices` |
| `distance_above_sixty_day_low_close_percent` | `TRD-14` | `yfinance:daily-prices` |
| `absolute_distance_from_two_hundred_day_average_percent` | `TRD-24` | `yfinance:daily-prices` |
| `average_true_range_fourteen_day_percent` | `TRD-15` | `yfinance:daily-prices` |
| `spmo_holding_rank` | `TRD-16`, `TRD-25` | `sec:n-port` |
| `no_fomc_meeting_inside_option_life` | `EVT-02` | `federalreserve:fomc-calendar` |
| `no_cpi_or_pce_release_inside_option_life` | `EVT-03` | `fred:release-dates` |
| `no_election_day_inside_option_life` | `EVT-04` | `rule:us-election-calendar` |
| `no_jobs_report_within_one_day` | `EVT-05` | `fred:PAYEMS-release-dates` |
| `no_ex_dividend_date_inside_option_life` | `EVT-06` | `yfinance:dividends` |
| `trade_policy_uncertainty_ten_year_percentile` | `EVT-07` | `fred:EPUTRADE` |
| `geopolitical_risk_index_thirty_day_average_percentile_five_year` | `EVT-08` | `gpr:daily` |
| `us_epu_thirty_day_average_percentile_five_year` | `EVT-14` | `fred:USEPUINDXD` |
| `industry_leader_has_no_earnings_inside_option_life` | `EVT-10` | `edgar:submissions` |
| `customers_and_suppliers_have_no_earnings_inside_option_life` | `EVT-11` | `edgar:submissions` |
| `is_spmo_rebalance_window` | `EVT-12` | `rule:spmo-rebalance-calendar` |
| `no_quadruple_witching_in_next_five_trading_days` | `EVT-13` | `rule:option-expiration-calendar` |
| `market_capitalization_billion_usd` | `LIQ-01`, `LIQ-06`, `LIQ-07` | `edgar:companyfacts` |
| `average_daily_trading_value_twenty_day_usd` | `LIQ-03`, `LIQ-08` | `yfinance:daily-prices` |
| `selected_put_bid_ask_spread_percent_of_mid` | `LIQ-04` | `dolthub:options` |
| `selected_put_open_interest` | `LIQ-05` | `none yet` |
| `selected_put_volume` | `LIQ-09` | `none yet` |
| `implied_volatility_percentile` | `VOL-01`, `VOL-06`, `VOL-07` | `dolthub:volatility_history` |
| `vix_to_twenty_day_average_ratio` | `VOL-02` | `cboe:VIX_History` |
| `implied_volatility_to_one_month_ago_ratio` | `VOL-08` | `dolthub:options` |
| `one_sigma_expected_move_thirty_day_percent` | `VOL-04` | `dolthub:options` |
| `put_skew_ten_percent_otm_minus_atm_iv_points` | `VOL-05` | `dolthub:options` |
| `selected_option_days_to_expiration` | `CTR-03` | `dolthub:options` |
| `selected_expiration_is_third_friday` | `CTR-04` | `rule:option-expiration-calendar` |
| `selected_put_strike_discount_percent` | `CTR-05` | `dolthub:options` |
| `selected_put_strike_below_support` | `CTR-06` | `dolthub:options` |
| `selected_strike_is_multiple_of_five` | `CTR-07` | `dolthub:options` |
| `selected_call_strike_premium_percent` | `CTR-08` | `dolthub:options` |
| `selected_call_days_to_expiration` | `CTR-09` | `dolthub:options` |
| `selected_put_strike_outside_one_sigma_move` | `CTR-10` | `dolthub:options` |
| `selected_put_monthly_premium_percent` | `RET-02`, `RET-07` | `dolthub:options` |
| `selected_option_implied_leverage` | `RET-03` | `dolthub:options` |
| `selected_put_breakeven_discount_percent` | `RET-04` | `dolthub:options` |
| `selected_put_probability_of_profit` | `RET-05` | `dolthub:options` |

## Not built yet

Account values (net value, cash, positions) and the strategy gates that need them (capital structure, position limits). Macro event dates (FOMC, CPI) are kept by hand in `config/settings.yaml` until the calendar sources in the rule catalog are built.
