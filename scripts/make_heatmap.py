#!/usr/bin/env python3
"""Heatmap assets: yearly borough stats JSON, borough SVG paths, matrix heatmap PNG."""
import json
import math
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

# ---------- yearly stats per borough x tenure ----------
df = pd.read_csv("data/london_ppd.csv",
                 dtype={"price": "int64"}, parse_dates=["date"])
df = df[(df.ppd_category == "A") & (df.duration.isin(["F", "L"]))]
df = df[(df.price >= 10_000) & (df.price <= 50_000_000)]
df["year"] = df.date.dt.year

years = list(range(2006, 2027))
g = (df.groupby(["district", "year", "duration"])["price"]
       .agg(median="median", n="size").reset_index())

boroughs = {}
for d, sub in g.groupby("district"):
    rec = {}
    for ten in ("F", "L"):
        t = sub[sub.duration == ten].set_index("year").reindex(years)
        rec[ten] = [None if pd.isna(v) else round(v) for v in t["median"]]
        rec["n_" + ten.lower()] = [None if pd.isna(v) else int(v) for v in t["n"]]
    boroughs[d] = rec

with open("site/map_data.json", "w") as f:
    json.dump({"years": years, "boroughs": boroughs}, f)
print(f"map_data.json: {len(boroughs)} boroughs x {len(years)} years")

# ---------- GeoJSON -> SVG paths ----------
gj = json.load(open("data/london_boroughs.geojson"))

def rings(geom):
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    return [r for poly in geom["coordinates"] for r in poly]  # MultiPolygon

klat = math.cos(math.radians(51.5))
pts = [(lon * klat, -lat) for f in gj["features"] for r in rings(f["geometry"]) for lon, lat in r]
xs, ys = zip(*pts)
x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
W = 1000.0
H = round(W * (y1 - y0) / (x1 - x0), 1)
sc = W / (x1 - x0)

def proj(lon, lat):
    return round((lon * klat - x0) * sc, 1), round((-lat - y0) * sc, 1)

ALIASES = {"westminster": "City Of Westminster"}

paths = []
for f in gj["features"]:
    d = ""
    for ring in rings(f["geometry"]):
        seg = [proj(lon, lat) for lon, lat in ring]
        d += "M" + "L".join(f"{x},{y}" for x, y in seg) + "Z"
    raw = f["properties"]["name"]
    paths.append({"name": ALIASES.get(raw.lower(), raw.title()), "d": d})

with open("site/map_paths.json", "w") as f:
    json.dump({"viewBox": f"0 0 {W:g} {H}", "paths": paths}, f)
print(f"map_paths.json: {len(paths)} paths, viewBox 0 0 {W:g} {H}")

# name check vs PPD districts (case-insensitive)
ppd_names = {n.lower() for n in boroughs}
gj_names = {p["name"].lower() for p in paths}
assert ppd_names == gj_names, f"mismatch: {ppd_names ^ gj_names}"
print("names match")

# ---------- static matrix heatmap: freehold premium % ----------
piv_f = g[g.duration == "F"].pivot(index="district", columns="year", values="median")
piv_l = g[g.duration == "L"].pivot(index="district", columns="year", values="median")
n_f = g[g.duration == "F"].pivot(index="district", columns="year", values="n")
prem = (piv_f / piv_l - 1) * 100
prem = prem.mask(n_f < 30)  # too few freehold sales (City of London)
prem = prem[[y for y in years if y in prem.columns]]
order = prem.mean(axis=1).sort_values(ascending=False).index
prem = prem.loc[order]

cmap = LinearSegmentedColormap.from_list("claret", ["#f6efe2", "#e3a13f", "#990f3d", "#3d0618"])
cmap.set_bad("#d8d2c4")

fig, ax = plt.subplots(figsize=(13.5, 11))
m = ax.imshow(prem.values, aspect="auto", cmap=cmap, vmin=0, vmax=150)
ax.set_xticks(range(len(prem.columns)))
ax.set_xticklabels([str(y) + ("*" if y == 2026 else "") for y in prem.columns], fontsize=8.5, rotation=45)
ax.set_yticks(range(len(prem.index)))
ax.set_yticklabels(prem.index, fontsize=9)
for i in range(len(prem.index)):
    for j in range(len(prem.columns)):
        v = prem.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=6.2,
                    color="white" if v > 75 else "#221c18")
cb = fig.colorbar(m, ax=ax, shrink=0.5, pad=0.01)
cb.set_label("Freehold premium over leasehold, median price (%)", fontsize=9)
ax.set_title("How much more a freehold costs — premium over leasehold by borough and year\n"
             "(median prices; grey = under 30 freehold sales; * = partial year; capped at 150%)",
             fontsize=12, pad=14)
fig.tight_layout()
fig.savefig("output/borough_premium_heatmap.png", dpi=150)
print("saved borough_premium_heatmap.png")
