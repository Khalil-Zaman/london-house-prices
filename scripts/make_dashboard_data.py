#!/usr/bin/env python3
"""Pivot the monthly tenure CSVs into JSON for the dashboard's interactive chart."""
import json
import pandas as pd

london = pd.read_csv("output/london_monthly_tenure.csv", parse_dates=["month"])
boro = pd.read_csv("output/borough_monthly_tenure.csv", parse_dates=["month"])

london["area"] = "Greater London"
boro = boro.rename(columns={"district": "area"})
df = pd.concat([london, boro], ignore_index=True)

months = pd.date_range(df.month.min(), df.month.max(), freq="MS")
month_labels = [m.strftime("%Y-%m") for m in months]

def roll(s):
    return s.rolling(12, center=True, min_periods=6).mean()

series = {}
for area, g in df.groupby("area"):
    series[area] = {}
    for tenure, t in g.groupby("tenure"):
        t = t.set_index("month").reindex(months)
        series[area][tenure] = {
            "median": [None if pd.isna(v) else round(v) for v in t["median"]],
            "mean": [None if pd.isna(v) else round(v) for v in t["mean"]],
            "median_roll": [None if pd.isna(v) else round(v) for v in roll(t["median"])],
            "mean_roll": [None if pd.isna(v) else round(v) for v in roll(t["mean"])],
            "n": [None if pd.isna(v) else int(v) for v in t["n"]],
        }

areas = ["Greater London"] + sorted(a for a in series if a != "Greater London")
out = {"areas": areas, "months": month_labels, "series": series}
with open("site/data.json", "w") as f:
    json.dump(out, f)
print(f"site/data.json: {len(areas)} areas x {len(month_labels)} months")
