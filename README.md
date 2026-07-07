# The Rent-Growth Screener

A transparent, backtested **screening framework** that ranks the ~110 largest US metros by
fundamentals that historically precede **3-year forward rent growth** — built entirely on free
public data and served as a Streamlit site. It is a research screen, not investment advice.

**Headline results** (finalized-data vintage unless noted; details in `paper/`):
- Top-10 edge: **+6.0 pp** of 3-yr rent growth vs the median market, pooled over six windows
- Pre-COVID: weighted Kendall's τ **0.59**, precision@10 **85%**; real-time-achievable pooled
  τ **0.38** (85% of the finalized ceiling 0.44)
- In the 2021–22 shock the edge largely disappears (τ ≈ 0.16) — reported, and flagged by a
  validated ex-ante rule
- Two provisional "nowcast" attempts **failed their pre-committed validation gate** (latest:
  84.7% signal retention vs ≥85% required) and are published as negative results

**The documents** — `decision-log.md` (every decision + why) · `v1-build-spec.md`, `v2-plan.md`,
`v3-plan.md` (build spec + two external critique rounds) · `paper/paper-brief.md` (all citable
numbers) · `paper/v2-findings.md`, `paper/nowcast-validation.md` (rigor pass + gate outcomes).

## Reproduce

```bash
py -m venv .venv && .venv\Scripts\activate      # Windows; use source .venv/bin/activate elsewhere
pip install -r requirements.txt                  # app only — runs the site from committed outputs
streamlit run app/streamlit_app.py
```

Rebuilding the data pipeline from raw sources additionally needs
`pip install -r requirements-pipeline.txt`, free API keys in `.env` (template:
`.env.example`), then:

```bash
python src/build_panel.py      # ingest + assemble the metro x year panel
python src/score.py            # indicators -> normalize -> composite ranking
python src/backtest.py         # walk-forward validation
python src/registry.py         # freeze a timestamped, immutable prediction run
```

Analysis modules (`src/baselines.py`, `ablation.py`, `uncertainty.py`, `weights.py`,
`temporal_uncertainty.py`, `momentum_effect.py`, `regime_flag.py`, `src/nowcast/*`) regenerate
every table in the paper brief. A CI smoke test (`.github/workflows/ci.yml`) checks that the
config validates, the model scores, and every site page renders on each push.

## Repository layout

| Path | What it holds |
|---|---|
| `config.py` | Universe rules, indicator weights, regimes, gate constants — the knobs |
| `src/ingest/` | One module per data source; raw downloads cached (gitignored) |
| `src/` | Panel build, indicators, normalization, scoring, backtest, analyses |
| `src/nowcast/` | The provisional-screen experiment (gated; currently unpublished) |
| `app/` | Streamlit site — `ui/` tokens+data, `views/` one file per page |
| `data/processed/` | Committed model outputs the site reads (no keys needed at runtime) |
| `predictions/` | Frozen, timestamped registry runs (never edited) |
| `paper/` | Auto-generated research briefs |

## Data sources & licensing

All inputs are free public data: **Census** (ACS, PEP, building permits, gazetteer),
**IRS SOI** migration, **BLS** (QCEW, CES), **BEA** regional accounts, **FRED**, and
**Zillow Research** (ZORI/ZHVI). US federal statistical data is public domain. Zillow Research
data is made freely available by Zillow with attribution — data in this repository that derives
from it is aggregated (metro-year averages), attributed here and on the site, and © Zillow where
applicable; see zillow.com/research/data for their terms before any redistribution of your own.
This project is unaffiliated with all of the above sources.
