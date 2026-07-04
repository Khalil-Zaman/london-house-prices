#!/usr/bin/env python3
"""Leasehold vs freehold analysis for Greater London, 2006-2026.

Input:  data/london_ppd.csv  (filtered Land Registry Price Paid Data)
Output: output/*.csv and output/*.png
"""
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

FREEHOLD = "#1f77b4"
LEASEHOLD = "#d62728"

print("Loading...")
df = pd.read_csv(
    "data/london_ppd.csv",
    dtype={"price": "int64", "prop_type": "category", "old_new": "category",
           "duration": "category", "district": "category", "ppd_category": "category"},
    parse_dates=["date"],
)
print(f"rows: {len(df):,}")

# Standard sales only (category A = full market value, standard tenure),
# known tenure, sane prices
df = df[(df.ppd_category == "A") & (df.duration.isin(["F", "L"]))]
df = df[(df.price >= 10_000) & (df.price <= 50_000_000)]
df["month"] = df.date.dt.to_period("M").dt.to_timestamp()
df["tenure"] = df.duration.map({"F": "Freehold", "L": "Leasehold"})
print(f"after filters: {len(df):,}")
print(df.groupby("tenure", observed=True).size())

districts = sorted(df.district.unique())
print(f"districts ({len(districts)}): {districts}")

# ---------- London-wide monthly series ----------
london = (df.groupby(["month", "tenure"], observed=True)["price"]
            .agg(mean="mean", median="median", n="size")
            .reset_index())
london.to_csv("output/london_monthly_tenure.csv", index=False)

piv_mean = london.pivot(index="month", columns="tenure", values="mean")
piv_med = london.pivot(index="month", columns="tenure", values="median")

fig, axes = plt.subplots(2, 1, figsize=(13, 10), sharex=True)
for ax, piv, label in [(axes[0], piv_mean, "Mean"), (axes[1], piv_med, "Median")]:
    for tenure, color in [("Freehold", FREEHOLD), ("Leasehold", LEASEHOLD)]:
        ax.plot(piv.index, piv[tenure], color=color, alpha=0.25, lw=0.8)
        ax.plot(piv.index, piv[tenure].rolling(12, center=True).mean(),
                color=color, lw=2.2, label=f"{tenure} (12m avg)")
    ax.set_title(f"{label} sale price, Greater London", fontsize=12)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"£{v/1000:,.0f}k"))
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)
fig.suptitle("Freehold vs Leasehold — Greater London, 2006–2026\n"
             "Land Registry Price Paid Data (standard sales, category A)",
             fontsize=14)
fig.tight_layout()
fig.savefig("output/london_freehold_vs_leasehold.png", dpi=150)
plt.close(fig)
print("saved london_freehold_vs_leasehold.png")

# ---------- Borough breakdown: small multiples (quarterly median) ----------
df["quarter"] = df.date.dt.to_period("Q").dt.to_timestamp()
boro = (df.groupby(["district", "quarter", "tenure"], observed=True)["price"]
          .agg(mean="mean", median="median", n="size")
          .reset_index())
boro.to_csv("output/borough_quarterly_tenure.csv", index=False)

# also save the precise monthly borough series the user asked for
boro_m = (df.groupby(["district", "month", "tenure"], observed=True)["price"]
            .agg(mean="mean", median="median", n="size")
            .reset_index())
boro_m.to_csv("output/borough_monthly_tenure.csv", index=False)

ncols, nrows = 6, 6
fig, axes = plt.subplots(nrows, ncols, figsize=(22, 18), sharex=True)
for i, d in enumerate(districts):
    ax = axes[i // ncols][i % ncols]
    sub = boro[boro.district == d].pivot(index="quarter", columns="tenure", values="median")
    for tenure, color in [("Freehold", FREEHOLD), ("Leasehold", LEASEHOLD)]:
        if tenure in sub:
            ax.plot(sub.index, sub[tenure], color=color, lw=1.4)
    ax.set_title(d, fontsize=9)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"£{v/1e6:.1f}m" if v >= 1e6 else f"£{v/1000:.0f}k"))
    ax.tick_params(labelsize=7)
    ax.grid(alpha=0.3)
for j in range(len(districts), nrows * ncols):
    axes[j // ncols][j % ncols].axis("off")
fig.suptitle("Median sale price by borough — Freehold (blue) vs Leasehold (red), quarterly 2006–2026",
             fontsize=16, y=1.0)
fig.tight_layout()
fig.savefig("output/borough_grid.png", dpi=130, bbox_inches="tight")
plt.close(fig)
print("saved borough_grid.png")

# ---------- Latest-year borough comparison bar chart ----------
recent = df[df.date >= df.date.max() - pd.DateOffset(months=12)]
bar = (recent.groupby(["district", "tenure"], observed=True)["price"]
             .median().unstack().sort_values("Freehold", ascending=True))
fig, ax = plt.subplots(figsize=(11, 13))
y = range(len(bar))
ax.barh([i + 0.2 for i in y], bar["Freehold"], height=0.38, color=FREEHOLD, label="Freehold")
ax.barh([i - 0.2 for i in y], bar["Leasehold"], height=0.38, color=LEASEHOLD, label="Leasehold")
ax.set_yticks(list(y))
ax.set_yticklabels(bar.index, fontsize=9)
ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"£{v/1e6:.1f}m" if v >= 1e6 else f"£{v/1000:.0f}k"))
ax.set_title(f"Median price by borough, last 12 months (to {df.date.max():%b %Y})")
ax.legend()
ax.grid(axis="x", alpha=0.3)
fig.tight_layout()
fig.savefig("output/borough_latest_bars.png", dpi=150)
plt.close(fig)
print("saved borough_latest_bars.png")

# ---------- Summary stats ----------
def yearly_stats(year):
    sub = df[df.date.dt.year == year]
    g = sub.groupby("tenure", observed=True)["price"]
    return g.mean(), g.median(), g.size()

for yr in (2006, 2016, 2025):
    mean, med, n = yearly_stats(yr)
    print(f"\n{yr}:")
    for t in ("Freehold", "Leasehold"):
        print(f"  {t}: mean £{mean[t]:,.0f}  median £{med[t]:,.0f}  n={n[t]:,}")
