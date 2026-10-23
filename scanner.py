"""Fetch prices with yfinance, score each symbol, write data.json."""
import json
import os
import time

import pandas as pd
import yaml
import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data.json")


def load_config():
    with open(os.path.join(HERE, "config.yaml")) as f:
        return yaml.safe_load(f)


def rsi(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss)


def macd_hist(close):
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    return macd - macd.ewm(span=9, adjust=False).mean()


def score_symbol(df, rules):
    close, vol = df["Close"], df["Volume"]
    sma50, sma200 = close.rolling(50).mean(), close.rolling(200).mean()
    hist = macd_hist(close)
    r = rsi(close)
    last = close.iloc[-1]
    checks = {
        "trend_up": bool(last > sma50.iloc[-1] > sma200.iloc[-1]),
        "macd_bull": bool(hist.iloc[-1] > 0 and hist.iloc[-1] > hist.iloc[-2]),
        "rsi_ok": bool(50 <= r.iloc[-1] <= 70),
        "breakout": bool(last >= close.iloc[-20:].max()),
        "volume_spike": bool(vol.iloc[-1] > 1.5 * vol.iloc[-21:-1].mean()),
    }
    score = sum(rules[k]["weight"] for k, ok in checks.items() if ok)
    return {
        "price": round(float(last), 2),
        "change_pct": round(float(last / close.iloc[-2] - 1) * 100, 2),
        "rsi": round(float(r.iloc[-1]), 1),
        "score": score,
        "signals": [k for k, ok in checks.items() if ok],
    }


def download(symbols, period):
    raw = yf.download(symbols, period=period, interval="1d", group_by="ticker",
                      auto_adjust=True, progress=False, threads=True)
    out = {}
    for s in symbols:
        try:
            df = raw[s].dropna(subset=["Close"])
            if len(df):
                out[s] = df
        except KeyError:
            pass
    return out


def run():
    cfg = load_config()
    gauges, stocks, errors = [], [], []

    gdata = download([g["symbol"] for g in cfg["gauges"]], "1mo")
    for g in cfg["gauges"]:
        df = gdata.get(g["symbol"])
        if df is None or len(df) < 2:
            errors.append(g["symbol"])
            continue
        c = df["Close"]
        gauges.append({"symbol": g["symbol"], "name": g["name"],
                       "price": round(float(c.iloc[-1]), 2),
                       "change_pct": round(float(c.iloc[-1] / c.iloc[-2] - 1) * 100, 2)})

    sdata = download(cfg["watchlist"], "1y")
    for s in cfg["watchlist"]:
        df = sdata.get(s)
        if df is None or len(df) < 210:
            errors.append(s)
            continue
        stocks.append({"symbol": s, **score_symbol(df, cfg["rules"])})
    stocks.sort(key=lambda x: -x["score"])

    result = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "gauges": gauges,
              "stocks": stocks, "errors": errors,
              "rules": {k: v["desc"] for k, v in cfg["rules"].items()}}
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(result, f)
    os.replace(tmp, DATA_PATH)
    return result


if __name__ == "__main__":
    res = run()
    print(res["updated"], len(res["stocks"]), "stocks,", len(res["gauges"]), "gauges, errors:", res["errors"])
