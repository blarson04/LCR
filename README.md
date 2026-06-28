# Multifamily Market Screener

A reproducible framework that ranks ~110 large US metros by their potential for
**3-year forward rent growth**, using only free public data, served as an
interactive Streamlit site. It is a **screening framework**, not a prediction
engine: it surfaces markets whose fundamentals historically precede
outperformance, and reports honestly how it would have done.

- **Why** each choice was made → [`decision-log.md`](decision-log.md)
- **How** it's built → [`v1-build-spec.md`](v1-build-spec.md)

## Setup

```bash
# 1. Create and activate a virtual environment
py -m venv .venv
.venv\Scripts\activate            # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your API keys
copy .env.example .env            # then edit .env and paste your keys
```

All keys are free. The first source wired up is **FRED** — get a key (instant)
at <https://fred.stlouisfed.org/docs/api/api_key.html>.

## Check it works

```bash
.venv\Scripts\python.exe config.py            # validates weights + paths
.venv\Scripts\python.exe src\ingest\fred.py   # fetches + caches a FRED series
```

## Repository layout

| Path | What it holds |
|---|---|
| `config.py` | Universe rules, indicator weights, regime windows, paths — the knobs |
| `src/ingest/` | One module per data source (FRED done; others in progress) |
| `src/build_panel.py` | Merge all sources → metro × year panel |
| `src/indicators.py` | Compute the 10 indicators, apply directions |
| `src/normalize.py` | Cross-sectional z-score **within each period** |
| `src/score.py` | Weighted composite + ranking |
| `src/backtest.py` | Walk-forward, regimes, weighted tau + precision@k |
| `src/registry.py` | Freeze/timestamp each prediction run |
| `app/streamlit_app.py` | The website |
| `data/raw/` | Cached source downloads (gitignored) |
| `data/processed/` | Cleaned metro × year panel |
| `predictions/` | Timestamped, frozen prediction runs |

## Build status

- [x] **M1** — One source (FRED) end to end: fetch → cache → clean
- [x] **M2** — All sources + metro × year panel (110 metros × 2015–2025); universe frozen
- [x] **M3** — Indicators + normalize (within-year z) + weighted score → first ranking
- [ ] **M4** — Backtest (walk-forward, regimes, tau + precision@k)
- [ ] **M5** — Streamlit app (map, table, drill-down)
- [ ] **M6** — Deploy + first frozen prediction run
