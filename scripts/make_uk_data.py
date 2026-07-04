#!/usr/bin/env python3
"""UK-wide page data from the UK House Price Index full file.

- refreshes data/ukhpi_full.csv to the newest published release (probes back
  from the current month; keeps the existing file if nothing newer is up)
- downloads ONS LAD (Dec 2024, BUC) boundaries -> data/uk_lad.geojson
- writes site/uk_data.json (monthly price + 12m change per area),
  site/uk_map_data.json (yearly per district) and site/uk_map_paths.json (SVG)
"""
import datetime
import json
import math
import pathlib
import subprocess

import pandas as pd

HPI = pathlib.Path("data/ukhpi_full.csv")
LAD_GJ = pathlib.Path("data/uk_lad.geojson")
HPI_URL = "https://publicdata.landregistry.gov.uk/market-trend-data/house-price-index-data/UK-HPI-full-file-{ym}.csv"
LAD_URL = ("https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
           "Local_Authority_Districts_December_2024_Boundaries_UK_BUC/FeatureServer/0/query"
           "?where=1%3D1&outFields=LAD24CD,LAD24NM&outSR=4326&f=geojson")

START = "2006-01"
UK = "K02000001"
COUNTRIES = ["E92000001", "S92000003", "W92000004", "N92000002"]
REGION_PREFIX = "E12"
LA_PREFIXES = ("E06", "E07", "E08", "E09", "W06", "S12", "N09")
# HPI moved Barnsley & Sheffield to new GSS codes; the LAD24 boundary file has the old ones
CODE_ALIASES = {"E08000016": "E08000038", "E08000019": "E08000039"}

def refresh_hpi():
    today = datetime.date.today()
    for back in range(1, 8):
        m = today.month - back, today.year
        y, mo = (m[1] - 1, m[0] + 12) if m[0] < 1 else (m[1], m[0])
        ym = f"{y}-{mo:02d}"
        url = HPI_URL.format(ym=ym)
        head = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                               "-I", url], capture_output=True, text=True)
        if head.stdout.strip() == "200":
            print(f"downloading UK HPI release {ym}...")
            subprocess.run(["curl", "-sfL", "--retry", "3", url, "-o", HPI], check=True)
            return
    print("no HPI release found online; using existing file")

def main():
    refresh_hpi()
    if not LAD_GJ.exists():
        subprocess.run(["curl", "-sfL", "--retry", "3", LAD_URL, "-o", LAD_GJ], check=True)

    df = pd.read_csv(HPI, usecols=["Date", "RegionName", "AreaCode", "AveragePrice", "12m%Change"])
    df["month"] = pd.to_datetime(df.Date, format="%d/%m/%Y").dt.strftime("%Y-%m")
    df = df[df.month >= START]
    last = df.month.max()
    months = pd.period_range(START, last, freq="M").strftime("%Y-%m").tolist()

    def keep(code):
        return code == UK or code in COUNTRIES or code.startswith(REGION_PREFIX) \
            or code[:3] in LA_PREFIXES

    df = df[df.AreaCode.map(keep)]
    names = df.drop_duplicates("AreaCode").set_index("AreaCode").RegionName.to_dict()

    areas = {}
    for code, sub in df.groupby("AreaCode"):
        s = sub.set_index("month").reindex(months)
        group = ("uk" if code == UK else "country" if code in COUNTRIES
                 else "region" if code.startswith(REGION_PREFIX) else "district")
        areas[code] = {
            "name": names[code], "group": group,
            "price": [None if pd.isna(v) else round(v) for v in s.AveragePrice],
            "yoy": [None if pd.isna(v) else round(v, 1) for v in s["12m%Change"]],
        }
    order = ([UK] + COUNTRIES
             + sorted((c for c in areas if areas[c]["group"] == "region"), key=lambda c: areas[c]["name"])
             + sorted((c for c in areas if areas[c]["group"] == "district"), key=lambda c: areas[c]["name"]))
    with open("site/uk_data.json", "w") as f:
        json.dump({"months": months, "order": order, "areas": areas}, f)
    print(f"uk_data.json: {len(order)} areas x {len(months)} months (to {last})")

    # ---------- yearly per-district map data ----------
    la = df[df.AreaCode.str[:3].isin(LA_PREFIXES)].copy()
    la["year"] = la.month.str[:4].astype(int)
    years = [int(y) for y in sorted(la.year.unique())]
    g = la.groupby(["AreaCode", "year"]).AveragePrice.mean()
    districts = {}
    for code in la.AreaCode.unique():
        s = g.loc[code].reindex(years)
        price = [None if pd.isna(v) else round(v) for v in s]
        chg = [None] * len(years)
        for i in range(1, len(years)):
            if price[i] and price[i - 1]:
                chg[i] = round((price[i] / price[i - 1] - 1) * 100, 1)
        districts[code] = {"name": names[code], "price": price, "chg": chg}
    with open("site/uk_map_data.json", "w") as f:
        json.dump({"years": years, "districts": districts}, f)
    print(f"uk_map_data.json: {len(districts)} districts x {len(years)} years")

    # ---------- GeoJSON -> SVG paths ----------
    gj = json.load(open(LAD_GJ))

    def rings(geom):
        if geom["type"] == "Polygon":
            return geom["coordinates"]
        return [r for poly in geom["coordinates"] for r in poly]

    klat = math.cos(math.radians(54.5))
    pts = [(lon * klat, -lat) for f in gj["features"] for r in rings(f["geometry"]) for lon, lat in r]
    xs, ys = zip(*pts)
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    W = 1000.0
    H = round(W * (y1 - y0) / (x1 - x0), 1)
    sc = W / (x1 - x0)

    def proj(lon, lat):
        return round((lon * klat - x0) * sc, 1), round((-lat - y0) * sc, 1)

    paths = []
    for f in gj["features"]:
        d = ""
        for ring in rings(f["geometry"]):
            seg = [proj(lon, lat) for lon, lat in ring]
            d += "M" + "L".join(f"{x},{y}" for x, y in seg) + "Z"
        code = f["properties"]["LAD24CD"]
        paths.append({"code": CODE_ALIASES.get(code, code),
                      "name": f["properties"]["LAD24NM"], "d": d})
    with open("site/uk_map_paths.json", "w") as f:
        json.dump({"viewBox": f"0 0 {W:g} {H}", "paths": paths}, f)
    print(f"uk_map_paths.json: {len(paths)} paths, viewBox 0 0 {W:g} {H}")

    missing = {p["code"] for p in paths} - set(districts)
    extra = set(districts) - {p["code"] for p in paths}
    print(f"on map without HPI data (grey): {sorted(missing)}")
    print(f"in HPI without a shape: {sorted(extra)}")

if __name__ == "__main__":
    main()
