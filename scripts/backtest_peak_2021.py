"""Backtest five plans that start at the 2021-11-22 QQQ peak with 100k each.

Plans
  A  All-in QQQ at the start, hold.
  B  All-in TQQQ at the start, hold.
  C  Keep the 100k pool, buy 1500 QQQ on the first trading day of every month.
     Unspent cash sits idle at 0%.
  D  Hold TQQQ while QQQ closes above its 225-day SMA, hold cash otherwise.
  E  Hold TQQQ while the 100-day SMA of QQQ is above the 225-day SMA
     (golden cross), hold cash after it falls below (death cross).
  F  Keep the 100k pool, buy 1000 QQQ every 14 days (biweekly). The pool runs out
     after about 100 buys, after which no more buys are made.

Scenarios
  ideal         no tax. The chart uses this one.
  CA tax        federal + California state tax, with the 30-day wash-sale rule.
  CA no wash    same tax, wash-sale rule switched off, to show its effect.
  fed only      federal tax only (a state with no income tax), with wash-sale rule.

Assumptions: dividends are included (auto-adjusted prices). ETF expense ratios
are already in the price because the price tracks the net asset value. Trades
fill at the close of the signal day at the close price, with no slippage or spread.

Tax assumptions (US, top-bracket investor, calendar tax years):
  short-term gain (held 1 year or less): ordinary rate 37% + 3.8% NIIT, plus state
  long-term gain (held more than 1 year): 20% + 3.8% NIIT, plus state
  state tax treats all gains as ordinary income at the top rate (CA: 13.3%)
  losses net against gains of the same term in the same year, then across terms,
  then carry forward. The $3,000 ordinary-income loss deduction is not used.
  tax for each year is paid on 31 Dec from the portfolio; the position still
  held at the end is treated as sold on the last day (liquidation tax).
  wash sale: a loss on a sale is disallowed if the same ETF was bought within
  30 days before or after the sale and that replacement was not sold with it.
  The disallowed loss is added to the replacement's cost basis, and the
  replacement's holding period starts from the sold lot's purchase date.

Run:  python3 scripts/backtest_peak_2021.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402

START = "2021-11-22"
CAPITAL = 100_000.0
MONTHLY = 1_500.0
BIWEEKLY = 1_000.0
MA_DAYS = 225
FAST_MA_DAYS = 100
# Top-bracket rates. Short-term gains are taxed as ordinary income, so the top
# federal bracket (37%) applies. Long-term gains use the top LTCG bracket (20%).
# NIIT (3.8%) is added on top of both, since the investor is above the MAGI threshold.
FEDERAL_ORDINARY = 0.37
FEDERAL_LTCG = 0.20
NIIT = 0.038
CA_TOP_RATE = 0.133  # 12.3% top bracket + 1% mental health surcharge
WASH_DAYS = 30
OUT_DIR = Path(__file__).resolve().parent.parent / "backtest_output"


def load_closes() -> pd.DataFrame:
    # Start early so the 225-day SMA is already filled on START.
    # auto_adjust=True folds dividends into the prices, so returns include them.
    raw = yf.download(
        ["QQQ", "TQQQ"], start="2020-01-01", auto_adjust=True, progress=False
    )
    return raw[["Close"]].droplevel(0, axis=1).dropna()


@dataclass
class Lot:
    # One purchase. A lot is sold whole (plans here sell everything at once),
    # so each lot has one sell day and one set of proceeds.
    purchased: pd.Timestamp  # actual purchase day, used for the wash-sale window
    shares: float
    cost: float  # dollars paid
    # Holding-period start. Starts equal to the purchase day, but a wash-sale
    # replacement takes the earlier date of the lot whose loss was disallowed.
    buy_day: pd.Timestamp | None = None
    sell_day: pd.Timestamp | None = None
    proceeds: float = 0.0
    adjust: float = 0.0  # disallowed wash-sale losses added to basis
    # Shares of this lot still available to be a wash-sale replacement. One share
    # can only match one disallowed loss, so this is used up as matches are made.
    replacement_left: float = 0.0

    def __post_init__(self) -> None:
        self.buy_day = self.purchased
        self.replacement_left = self.shares


class Book:
    """Cash plus lots of one ETF.

    Costs are zero everywhere: the backtest assumes fills at the close price with
    no spread or slippage (the user asked to drop friction and keep tax only).
    """

    def __init__(self) -> None:
        self.cash = CAPITAL
        self.lots: list[Lot] = []
        self.trades = 0

    def held(self) -> list[Lot]:
        return [lot for lot in self.lots if lot.sell_day is None]

    def buy(self, day: pd.Timestamp, dollars: float, price: float, cost: float) -> None:
        self.cash -= dollars
        self.lots.append(Lot(day, dollars / (price * (1 + cost)), dollars))
        self.trades += 1

    def sell_all(self, day: pd.Timestamp, price: float, cost: float) -> None:
        sold = self.held()
        if not sold:
            return
        for lot in sold:
            lot.sell_day = day
            lot.proceeds = lot.shares * price * (1 - cost)
            self.cash += lot.proceeds
        self.trades += 1

    def shares(self) -> float:
        return sum(lot.shares for lot in self.held())

    def value(self, price: float) -> float:
        return self.cash + self.shares() * price


def timing(px: pd.Series, on: pd.Series) -> tuple[Book, pd.Series]:
    """Hold the ETF while `on` is True, hold cash while it is False.

    The signal uses the day's close and trades fill at that same close. That is
    slightly optimistic, because the signal is only known after the close, but
    the difference is small for a daily system. Each switch is one trade.
    """
    book = Book()
    equity = []
    for day, price in px.items():
        if on[day] and book.cash > 0:
            book.buy(day, book.cash, price, 0.0)
        elif not on[day] and book.shares() > 0:
            book.sell_all(day, price, 0.0)
        equity.append(book.value(price))
    return book, pd.Series(equity, index=px.index)


def dca(px: pd.Series) -> tuple[Book, pd.Series]:
    """Put 1500 into QQQ on the first trading day of each month.

    The 100k is one pool. Each monthly buy comes out of it, and what is left is
    cash at 0%. Each monthly buy is its own lot, so each one has its own holding
    period for tax purposes.
    """
    month_key = px.index.to_period("M")
    first_day_of_month = px.index[month_key != np.roll(month_key, 1)]
    # The first row is the start day, so it is not a DCA buy.
    buy_days = set(first_day_of_month[1:])

    book = Book()
    equity = []
    for day, price in px.items():
        if day in buy_days and book.cash >= MONTHLY:
            book.buy(day, MONTHLY, price, 0.0)
        equity.append(book.value(price))
    return book, pd.Series(equity, index=px.index)


def biweekly_dca(px: pd.Series) -> tuple[Book, pd.Series]:
    """Put 1000 into QQQ every 14 days from the 100k pool.

    The 14-day grid starts on START. A target falling on a non-trading day buys on
    the next trading day. The pool covers about 100 buys, so the last few years
    of the window get no new buys once cash drops below 1000.
    """
    targets = pd.date_range(START, px.index[-1], freq="14D")[1:]
    buy_days = set(px.index[px.index.searchsorted(targets)].intersection(px.index))

    book = Book()
    equity = []
    for day, price in px.items():
        if day in buy_days and book.cash >= BIWEEKLY:
            book.buy(day, BIWEEKLY, price, 0.0)
        equity.append(book.value(price))
    return book, pd.Series(equity, index=px.index)


def is_long_term(bought: pd.Timestamp, sold: pd.Timestamp) -> bool:
    # Long-term means held MORE than one year. Selling on the exact anniversary is
    # still short-term, which is why this is a strict comparison.
    return sold > bought + pd.DateOffset(years=1)


def realized_gains(book: Book, end_day: pd.Timestamp, end_price: float, wash_on: bool) -> tuple[list, float]:
    """Gains per sale after wash-sale adjustments, plus the total loss disallowed.

    Wash-sale rule (IRS, 30 days either side): a loss is disallowed when the same
    security is bought within 30 days before or after the sale. The disallowed
    loss is not lost. It is added to the replacement's basis, so the loss comes
    back when the replacement is sold. The replacement's holding period also
    starts from the sold lot's purchase date.
    """
    # Liquidation: everything still held is sold on the last day, so the final
    # tax year includes the gain or loss on the position still held.
    for lot in book.held():
        lot.sell_day = end_day
        lot.proceeds = lot.shares * end_price

    gains = []
    disallowed_total = 0.0
    for sale in sorted(book.lots, key=lambda lot: lot.sell_day):
        basis = sale.cost + sale.adjust
        raw = sale.proceeds - basis
        disallowed = 0.0
        # Only losses can be disallowed. Gains are always recognized.
        if wash_on and raw < 0:
            loss_per_share = -raw / sale.shares
            need = sale.shares
            # A replacement is any other lot bought within 30 days of the sale that
            # is still held after the sale. Lots sold on the same day as this sale
            # do not count, because the IRS needs the replacement shares to be kept.
            # Buys before the sale count too, if they are still held at that point.
            candidates = [
                lot for lot in book.lots
                if lot is not sale
                and abs((lot.purchased - sale.sell_day).days) <= WASH_DAYS
                and (lot.sell_day is None or lot.sell_day > sale.sell_day)
                and lot.replacement_left > 0
            ]
            for rep in sorted(candidates, key=lambda lot: lot.purchased):
                if need <= 0:
                    break
                use = min(need, rep.replacement_left)
                rep.replacement_left -= use
                rep.adjust += loss_per_share * use
                # Holding-period tacking: the replacement inherits the older start date.
                rep.buy_day = min(rep.buy_day, sale.buy_day)
                disallowed += loss_per_share * use
                need -= use
            disallowed_total += disallowed
        # Recognized gain = raw gain, minus the part of a loss that was disallowed.
        recognized = raw + disallowed
        gains.append((sale.sell_day, recognized, is_long_term(sale.buy_day, sale.sell_day)))
    return gains, disallowed_total


def settle_taxes(book: Book, index: pd.DatetimeIndex, end_price: float,
                 state_rate: float, wash_on: bool) -> tuple[dict, float]:
    """Tax paid per day, and total wash-sale disallowed losses.

    Tax is computed per calendar year on realized gains. The 31 Dec payment is a
    simplification: real US tax is paid the following April from cash, so this
    slightly overstates the cost of the timing. Taxes are paid out of the portfolio,
    which reduces the equity curve from the payment day onward.
    Simplifications: state tax is applied at the top rate to all gains, the
    federal SALT deduction is ignored (conservative), and the $3,000 ordinary-income
    loss deduction is ignored, as the user asked. Losses carry forward without limit.
    """
    end_day = index[-1]
    gains, disallowed_total = realized_gains(book, end_day, end_price, wash_on)
    short_rate = FEDERAL_ORDINARY + NIIT + state_rate
    long_rate = FEDERAL_LTCG + NIIT + state_rate

    tax_by_day: dict[pd.Timestamp, float] = {}
    carry_st = carry_lt = 0.0
    for year in range(index[0].year, index[-1].year + 1):
        rows = [row for row in gains if row[0].year == year]
        st = sum(gain for _, gain, long in rows if not long) + carry_st
        lt = sum(gain for _, gain, long in rows if long) + carry_lt
        # Netting order: first short against long within the year. Only what is left
        # is taxed, and any leftover loss goes to next year. Loss carry-forward keeps
        # its term (short stays short, long stays long), as the IRS requires.
        if st < 0 < lt:
            offset = min(-st, lt)
            st, lt = st + offset, lt - offset
        elif lt < 0 < st:
            offset = min(-lt, st)
            st, lt = st - offset, lt + offset
        # A positive net gain is taxed at its term's rate. A net loss is not taxed,
        # it only carries forward.
        tax = max(st, 0) * short_rate + max(lt, 0) * long_rate
        carry_st, carry_lt = min(st, 0), min(lt, 0)
        # Pay on the last trading day of the year. The final year pays the liquidation
        # tax too, because the position still held was treated as sold on this day.
        pay_day = index[index.year == year][-1]
        tax_by_day[pay_day] = tax_by_day.get(pay_day, 0.0) + tax
    return tax_by_day, disallowed_total


def after_tax(equity: pd.Series, tax_by_day: dict) -> pd.Series:
    """Subtract each year's tax from the equity curve from its payment day onward."""
    paid = pd.Series(0.0, index=equity.index)
    for day, tax in tax_by_day.items():
        paid.loc[day:] += tax
    return equity - paid


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    return float((equity / running_max - 1).min())


def summarize(name: str, scenario: str, equity: pd.Series, trades: int,
              total_tax: float, wash_loss: float) -> dict:
    final = float(equity.iloc[-1])
    return {
        "plan": name,
        "scenario": scenario,
        "final_value": round(final, 2),
        "profit": round(final - CAPITAL, 2),
        "return_pct": round((final / CAPITAL - 1) * 100, 1),
        "max_drawdown_pct": round(max_drawdown(equity) * 100, 1),
        "trades": trades,
        "total_tax": round(total_tax, 2),
        "wash_loss_disallowed": round(wash_loss, 2),
    }


SCENARIOS = [
    # name, taxed, state rate, wash-sale rule on
    # ideal: no tax, the chart uses this one.
    ("ideal", False, 0.0, False),
    # CA tax: federal plus California at its top rate, the main scenario.
    ("CA tax", True, CA_TOP_RATE, True),
    # CA no wash: same tax with the wash-sale rule off, to isolate its effect.
    ("CA no wash", True, CA_TOP_RATE, False),
    # fed only: for a state with no income tax (e.g. TX, FL, WA).
    ("fed only", True, 0.0, True),
]


def run_scenarios(close: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    qqq = close["QQQ"]
    tqqq = close["TQQQ"]
    qqq_px = qqq.loc[START:]
    tqqq_px = tqqq.loc[START:]
    always = pd.Series(True, index=qqq_px.index)
    sma_slow = qqq.rolling(MA_DAYS).mean()
    on_d = (qqq > sma_slow).loc[START:]
    on_e = (qqq.rolling(FAST_MA_DAYS).mean() > sma_slow).loc[START:]

    # name -> (price series used for the book, function returning (book, equity)).
    # A and C trade QQQ, B and D/E trade TQQQ. D and E use QQQ's moving averages
    # for the signal but hold TQQQ, so the signal and the traded asset differ.
    plans = {
        "A QQQ hold": (qqq_px, lambda: timing(qqq_px, always)),
        "B TQQQ hold": (tqqq_px, lambda: timing(tqqq_px, always)),
        "C QQQ DCA": (qqq_px, lambda: dca(qqq_px)),
        "F QQQ biweekly DCA": (qqq_px, lambda: biweekly_dca(qqq_px)),
        "D SMA225 TQQQ": (tqqq_px, lambda: timing(tqqq_px, on_d)),
        "E MA100x225 TQQQ": (tqqq_px, lambda: timing(tqqq_px, on_e)),
    }

    curves: dict[str, pd.DataFrame] = {}
    rows = []
    for scenario, taxed, state_rate, wash_on in SCENARIOS:
        columns = {}
        for name, (px, run) in plans.items():
            book, equity = run()
            tax_total = 0.0
            wash_total = 0.0
            if taxed:
                tax_by_day, wash_total = settle_taxes(book, px.index, px.iloc[-1], state_rate, wash_on)
                equity = after_tax(equity, tax_by_day)
                tax_total = sum(tax_by_day.values())
            columns[name] = equity
            rows.append(summarize(name, scenario, equity, book.trades, tax_total, wash_total))
        curves[scenario] = pd.DataFrame(columns).dropna()
    return curves, pd.DataFrame(rows)


def make_animation(equity: pd.DataFrame, path: Path) -> None:
    labels = {
        "A QQQ hold": "A  QQQ all-in, hold",
        "B TQQQ hold": "B  TQQQ all-in, hold",
        "C QQQ DCA": "C  QQQ DCA 1,500/mo",
        "F QQQ biweekly DCA": "F  QQQ DCA 1,000 every 2 wks",
        "D SMA225 TQQQ": "D  QQQ SMA225 -> TQQQ",
        "E MA100x225 TQQQ": "E  QQQ MA100/225 cross -> TQQQ",
    }
    colors = {
        "A QQQ hold": "#4C72B0",
        "B TQQQ hold": "#DD8452",
        "C QQQ DCA": "#55A868",
        "F QQQ biweekly DCA": "#64B5CD",
        "D SMA225 TQQQ": "#C44E52",
        "E MA100x225 TQQQ": "#8172B3",
    }

    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=110)
    dates = equity.index
    lines = {}
    for col in equity.columns:
        (line,) = ax.plot([], [], lw=2.2, color=colors[col], label=labels[col])
        lines[col] = line
    ax.axhline(CAPITAL, color="grey", ls="--", lw=1, label="Starting 100k")
    ax.set_xlim(dates[0], dates[-1])
    lo = min(equity.min().min(), CAPITAL) * 0.9
    hi = equity.max().max() * 1.08
    ax.set_ylim(lo, hi)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    ax.set_title("Starting at the 2021-11-22 QQQ peak with 100k each (ideal, no tax)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    date_text = ax.text(0.99, 0.03, "", transform=ax.transAxes, ha="right", fontsize=11)

    # One frame per 3 trading days keeps the GIF small and smooth. The last date
    # is always included so the animation ends on the final value.
    frame_idx = list(range(0, len(dates), 3)) + [len(dates) - 1]

    def update(k: int):
        i = frame_idx[k]
        for col, line in lines.items():
            line.set_data(dates[: i + 1], equity[col].values[: i + 1])
        date_text.set_text(f"{dates[i]:%Y-%m-%d}   " + "   ".join(
            f"{col.split()[0]}: ${equity[col].iloc[i]/1000:,.1f}k" for col in equity.columns
        ))
        return [*lines.values(), date_text]

    anim = FuncAnimation(fig, update, frames=len(frame_idx), interval=50, blit=False)
    anim.save(path, writer=PillowWriter(fps=20))
    plt.close(fig)


def make_static_chart(equity: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=120)
    for col in equity.columns:
        ax.plot(equity.index, equity[col], lw=1.8, label=col)
    ax.axhline(CAPITAL, color="grey", ls="--", lw=1)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    # Static chart uses the ideal curves only, as the user asked. Taxes are in the table.
    ax.set_title("Equity curves from 2021-11-22 (100k start, ideal, no tax)")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    close = load_closes()
    curves, summary = run_scenarios(close)

    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", 20)
    print(f"Start {START}  End {close.index[-1]:%Y-%m-%d}")
    print(summary.to_string(index=False))

    for scenario, df in curves.items():
        slug = scenario.replace(" ", "_")
        df.round(2).to_csv(OUT_DIR / f"equity_curves_{slug}.csv")
    summary.to_csv(OUT_DIR / "summary.csv", index=False)
    make_static_chart(curves["ideal"], OUT_DIR / "equity_static.png")
    make_animation(curves["ideal"], OUT_DIR / "equity_animation.gif")
    # The equity curve for each scenario is saved to its own CSV, so a tax scenario
    # can be checked against the ideal curve line by line.
    print(f"\nWrote outputs to {OUT_DIR}")


if __name__ == "__main__":
    main()
