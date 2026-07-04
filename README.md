# London House Prices — Freehold vs Leasehold (2006–2026)

Monthly average sale prices for Greater London split by tenure, with a breakdown
across all 33 boroughs (32 boroughs + City of London).

## Data sources

- **Land Registry Price Paid Data** (gov.uk) — every registered sale, with a
  Freehold/Leasehold flag and district (borough). This is the analysis source:
  the UK HPI full file does *not* contain a tenure split (it has property type,
  new/old, cash/mortgage, buyer status only).
- **UK HPI full file** (March 2026 release, `data/ukhpi_full.csv`) — used for
  validation. Our freehold median tracks the HPI London terraced price and our
  leasehold median tracks the HPI flat price almost exactly at both ends of the
  series.

## Pipeline

1. `scripts/download_filter.py` — streams the 21 yearly PPD files (2006–2026),
   keeps Greater London rows → `data/london_ppd.csv` (2.30M sales, 87MB).
2. `scripts/analyze.py` — filters to standard sales (PPD category A), known
   tenure, prices £10k–£50m (2.04M sales: 930k freehold, 1.110M leasehold),
   then aggregates and charts.

Run: `.venv/bin/python scripts/download_filter.py && .venv/bin/python scripts/analyze.py`

## Outputs

| File | Contents |
|---|---|
| `output/london_monthly_tenure.csv` | Precise monthly mean/median/count by tenure, London-wide |
| `output/borough_monthly_tenure.csv` | Same, per borough (33 × 245 months × 2 tenures) |
| `output/borough_quarterly_tenure.csv` | Quarterly version (less noisy for charting) |
| `output/london_freehold_vs_leasehold.png` | 20-year London series, mean + median |
| `output/borough_grid.png` | 33-borough small multiples, quarterly medians |
| `output/borough_latest_bars.png` | Median by borough, last 12 months |
| `output/borough_premium_heatmap.png` | Borough × year matrix of the freehold premium (%) |
| `index.html` + `site/*.json` | Local dashboard (see below) |
| `overall.html` + `site/overall.json` | Whole-market page: prices vs CPI, S&P 500, NASDAQ-100 |
| `uk.html` + `site/uk_*.json` | UK-wide page: HPI for every nation/region/district + heatmap |

## Dashboard

`python3 -m http.server 8917 --bind 127.0.0.1` from the project root, then open
http://127.0.0.1:8917/. Features: interactive monthly chart (per-area, or
"All areas — one graph" comparing all 33 boroughs at once, by tenure or
freehold premium), a choropleth heat map with a year slider (2006–2026), and
the static plates. Data prep: `scripts/make_dashboard_data.py` and
`scripts/make_heatmap.py` (borough boundaries from the london_boroughs GeoJSON
in `data/`; "Westminster" is aliased to PPD's "City Of Westminster").

`overall.html` ("The Opportunity Cost") tracks the whole market — the monthly
median across **all** standard sales, any tenure — with a selectable start
month, a nominal / today's-£ (CPI) toggle, linear/log scale, and two
counterfactual lines: the same money in the S&P 500 or NASDAQ-100 (monthly
closes, converted to GBP at spot; price return only, no dividends).
Data prep: `scripts/make_overall_data.py`, which fetches ONS CPI (D7BT) and
Yahoo Finance (^GSPC, ^NDX, GBPUSD=X) into `data/market/` and writes
`site/overall.json`.

`uk.html` ("The State of the Nation") covers the whole UK via the official
UK House Price Index: monthly average price or 12-month % change for the UK,
four nations, nine English regions and all 360 local-authority districts, plus
a district-level choropleth (year slider, diverging ramp for rising/falling).
Data prep: `scripts/make_uk_data.py`, which downloads the newest HPI full-file
release and ONS LAD-2024 boundaries (Barnsley & Sheffield re-keyed to their
current GSS codes; Isles of Scilly has no HPI series; NI's index is quarterly).

## Headline findings

| Year | Freehold mean / median | Leasehold mean / median |
|---|---|---|
| 2006 | £368k / £267.5k | £268k / £217.5k |
| 2016 | £682k / £500k | £520k / £401k |
| 2025 | £853k / £633k | £549k / £440k |

- **The gap has widened dramatically.** Freehold median +137% over 20 years;
  leasehold +102%. In 2006 a freehold cost ~23% more than a leasehold (median);
  by 2025 it cost ~44% more.
- **Leasehold prices have been flat since ~2016** (£401k → £440k median in nine
  years, a fall in real terms), while freehold kept climbing until 2022.
  Consistent with the cladding/EWS1 crisis, escalating service charges and
  ground-rent scandal, and leasehold-reform uncertainty weighing on flats.
- **The gap is widest in prime central London** (Kensington & Chelsea freehold
  median ~£3.6m vs leasehold ~£900k) and narrowest in outer east boroughs
  (Barking & Dagenham, Bexley, Newham).
- City of London freehold series is extremely sparse (almost everything in the
  Square Mile is leasehold) — treat that panel as anecdotal.

## Caveats

- **Tenure is heavily confounded with property type**: leasehold ≈ flats,
  freehold ≈ houses. Much of the divergence is a houses-vs-flats story.
- **Registration lag**: the last ~6–12 months of Price Paid Data are incomplete,
  so the tail of the series (late 2025 → May 2026) will revise upward as more
  sales register. Don't read the final-months dip as a crash.
- Category A (standard, full-market-value) sales only; mean is skewed by the
  prime-London tail — prefer the median series.
