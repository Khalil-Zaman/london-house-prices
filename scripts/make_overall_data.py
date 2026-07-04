#!/usr/bin/env python3
"""Overall-market page data: London monthly prices (all tenures) + UK CPI +
S&P 500, NASDAQ-100 and GBP/USD monthly closes -> site/overall.json.

Sources (fetched fresh on every run, cached in data/market/):
- Yahoo Finance chart API: ^GSPC, ^NDX, GBPUSD=X, monthly bars
- ONS series D7BT (CPI all items index, 2015=100), dataset MM23
"""
import datetime
import json
import pathlib
import subprocess

import pandas as pd

MARKET_DIR = pathlib.Path("data/market")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1mo&period1=1120176000&period2=9999999999"
ONS_CPI = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7bt/mm23/data"

def fetch(url, dest):
    subprocess.run(["curl", "-sfL", "--retry", "3", "-H", f"User-Agent: {UA}",
                    url, "-o", dest], check=True)

def yahoo_monthly(path):
    """month 'YYYY-MM' -> close. Timestamps are month starts (sometimes offset
    a day across timezones), so shift +2 days before bucketing."""
    r = json.load(open(path))["chart"]["result"][0]
    out = {}
    for ts, close in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]):
        if close is None:
            continue
        d = datetime.datetime.fromtimestamp(ts, datetime.UTC) + datetime.timedelta(days=2)
        out[d.strftime("%Y-%m")] = round(close, 4)
    return out

def main():
    MARKET_DIR.mkdir(exist_ok=True)
    for sym, name in [("%5EGSPC", "gspc"), ("%5ENDX", "ndx"), ("GBPUSD%3DX", "gbpusd")]:
        fetch(YAHOO.format(sym=sym), MARKET_DIR / f"{name}.json")
    fetch(ONS_CPI, MARKET_DIR / "cpi.json")

    spx = yahoo_monthly(MARKET_DIR / "gspc.json")
    ndx = yahoo_monthly(MARKET_DIR / "ndx.json")
    fx = yahoo_monthly(MARKET_DIR / "gbpusd.json")

    cpi = {}
    for m in json.load(open(MARKET_DIR / "cpi.json"))["months"]:
        d = datetime.datetime.strptime(m["date"], "%Y %b")  # e.g. "2026 MAY"
        cpi[d.strftime("%Y-%m")] = float(m["value"])

    # ---------- house series: every standard sale, all tenures ----------
    df = pd.read_csv("data/london_ppd.csv", dtype={"price": "int64"}, parse_dates=["date"])
    df = df[(df.ppd_category == "A") & (df.price >= 10_000) & (df.price <= 50_000_000)]
    df["month"] = df.date.dt.strftime("%Y-%m")
    g = df.groupby("month")["price"].agg(median="median", mean="mean", n="size")

    months = sorted(g.index)
    def series(src, label):
        out, last = [], None
        for m in months:
            if m in src:
                last = src[m]
            elif last is None:
                raise SystemExit(f"{label}: no value at or before {m}")
            out.append(last)  # carry forward when a source lags the house data
        return out

    out = {
        "months": months,
        "house_median": [round(v) for v in g.loc[months, "median"]],
        "house_mean": [round(v) for v in g.loc[months, "mean"]],
        "house_n": [int(v) for v in g.loc[months, "n"]],
        "cpi": series(cpi, "CPI"),
        "spx": series(spx, "S&P 500"),
        "ndx": series(ndx, "NASDAQ-100"),
        "gbpusd": series(fx, "GBP/USD"),
    }
    with open("site/overall.json", "w") as f:
        json.dump(out, f)
    print(f"site/overall.json: {len(months)} months ({months[0]} .. {months[-1]}), "
          f"CPI to {max(cpi)}, SPX to {max(spx)}")

if __name__ == "__main__":
    main()
