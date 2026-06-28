# Multifamily Market Screener — v1 Build Spec

*This is the **how** document — the working brief to hand to Claude Code. The companion `decision-log.md` is the **why** document; when this spec states a choice without justifying it, the rationale lives there. Read both.*

*Context for the build assistant: the author is new to coding but has solid real estate fundamentals. Explain what each module does and why as you build it, prefer clear readable code over clever code, and build in small, runnable increments so nothing is a black box.*

---

## 1. Objective

Build a reproducible framework that ranks ~110 large US metro areas by their potential for **3-year forward rent growth**, using only free public data, and serve it as an interactive Streamlit website. The framework is validated by a walk-forward backtest and every prediction run is frozen to a registry so the track record is auditable over time.

We call this a **screening framework**, not a prediction engine — it surfaces markets whose fundamentals historically precede outperformance, and reports honestly how it would have done.

---

## 2. Tech stack

- **Python 3.11+**, with `pandas`, `numpy`, `scipy` (for `scipy.stats.weightedtau`), `requests`.
- **Streamlit** for the website; **plotly** (choropleth map + charts) for visuals.
- **Deployment:** Streamlit Community Cloud (free, connects to a GitHub repo).
- Use a virtual environment and a pinned `requirements.txt`.
- Store API keys in a `.env` file (never commit it); read with `python-dotenv`.

---

## 3. Repository structure

```
multifamily-screener/
├── README.md
├── decision-log.md          # the why document (already written)
├── v1-build-spec.md         # this file
├── requirements.txt
├── .env.example             # lists required keys, no real values
├── config.py                # universe rules, indicator weights, regime windows, paths
├── data/
│   ├── raw/                 # cached source downloads (gitignored)
│   └── processed/           # cleaned metro × year panel
├── src/
│   ├── ingest/              # one module per source (see §4)
│   │   ├── zillow.py
│   │   ├── apartmentlist.py
│   │   ├── census.py
│   │   ├── irs_migration.py
│   │   ├── bls.py
│   │   ├── bea.py
│   │   └── fred.py
│   ├── build_panel.py       # merge all sources → metro × year panel
│   ├── indicators.py        # compute the 10 indicators, apply directions
│   ├── normalize.py         # cross-sectional z-score WITHIN each period
│   ├── score.py             # weighted composite + ranking
│   ├── backtest.py          # walk-forward, regimes, weighted tau + precision@k
│   └── registry.py          # freeze/timestamp each prediction run
├── predictions/             # timestamped frozen runs (JSON/parquet)
├── notebooks/               # exploration / sanity checks
└── app/
    └── streamlit_app.py
```

---

## 4. Data sources

All free. Pull the rawest sensible form, cache it in `data/raw/`, and do cleaning in code so the pipeline is reproducible. **Verify exact endpoints and file paths at build time** — portals move.

| Source | What we use it for | Granularity | Access | Notes |
|---|---|---|---|---|
| **Zillow Research (ZORI)** | **Primary rent series — the target variable** | Metro, monthly, ~2015+ | Zillow **Econ Data API** | Use the `Metro_ZORI_AllHomesPlusMultifamily` series. Prefer the API over hardcoded CSV URLs — Zillow changes download paths often. ZORI is *asking* rent, not executed (state as a limitation). |
| **Apartment List** | Rent corroboration + **vacancy index** (bonus supply signal) | Metro, monthly, ~2017+ | Free CSV download page | Shorter history than ZORI, so ZORI is the anchor; AL is a cross-check and supplies vacancy. |
| **Census — Population Estimates / ACS** | Population, income, housing stock (for permits ratio), renter-age cohorts | Metro (CBSA), annual | Census API (key) | Defines the universe; supplies the denominator for the permits ratio. |
| **Census — Building Permits Survey** | Building permits; multifamily pipeline | Metro, monthly/annual | Census API / flat files | Core of the Supply bucket. Separate out multifamily (5+ unit) permits. |
| **IRS SOI Migration Data** | Net domestic migration | County→county, annual | Flat file download | Aggregate counties to MSAs. One of the highest-signal free datasets. |
| **BLS (QCEW / LAUS / CES)** | Job growth, wage growth, employment diversification | Metro, monthly/annual | BLS API (key) | Diversification = industry concentration measure (e.g., HHI across sectors). |
| **BEA Regional** | Personal income, GDP by metro | Metro, annual | BEA API (key) | Income growth indicator + affordability denominator. |
| **FRED** | Convenient aggregator / cross-checks for several series | Metro where available | FRED API (`fredapi`) | Gentlest on-ramp; good first source to wire up end-to-end. |

**Known data gap (carry to the paper):** no capital-markets data — cap rates, cap-rate spreads, transaction volume — because those are paid (CoStar / RCA). The model predicts **rent growth**, our measurable proxy for "profitable"; it does not capture cap-rate movement or price appreciation.

---

## 5. The model

Ten indicators in five buckets. Full weights and the rationale for each are in `decision-log.md`; the summary:

- **Demand 40%** — net migration 14%, job growth 12%, income/wage growth 8%, population growth 6%.
- **Supply 25%** — permits ÷ housing stock 17% (inverse), multifamily pipeline intensity 8% (inverse).
- **Affordability 20%** — rent-to-income ratio 12% (inverse), cost-to-own-vs-rent gap 8%.
- **Momentum 10%** — trailing rent growth 10% (confirmation only).
- **Resilience 5%** — employment diversification 5%.

Pipeline of the model itself:
1. Build a clean **metro × year panel** with one column per raw input.
2. Compute the 10 **indicators**, flipping the inverse ones so that, for every indicator, higher = better.
3. **Normalize each indicator cross-sectionally *within each year*** (z-score across metros). This is essential and easy to get wrong — normalize per period, not over the whole panel, so a common national shock cancels out and only the metro-to-metro spread survives.
4. **Score** = weighted sum of normalized indicators. Rank metros by score.

Keep weights in `config.py` so they're trivial to change. v1 weights are **hand-set, not fitted** (interpretable and defensible).

---

## 6. Validation plan

This is what separates the project from a toy. Build `backtest.py` to do all of the following:

- **Target:** 3-year forward rent growth (from ZORI), ranked cross-sectionally. Also compute the 1-year version as a *contrast* (if the model does better at 3y than 1y, that's evidence it's capturing fundamentals, not momentum).
- **Walk-forward:** train/score on data up to year T, predict T→T+3, roll forward one year, repeat across the whole history. Never let the model see the future.
- **Rolling overlapping windows** are necessary given the short (~2015+) history — but they are NOT independent, so report results as **directional evidence**, not hard significance.
- **Regime segmentation** — report every result separately for: pre-COVID (~2015–2019), shock (2020–2022), normalization (2023–present), plus pooled. "Does it hold across regimes?" is a headline finding. **Tag each rolling window by the regime(s) it spans** (a window starting at the 2022 peak looks catastrophic; one ending there looks miraculous — that's timing, not skill).
- **Winsorize** extreme rent-growth values (cap at ~1st/99th percentile) and disclose it.
- **Metrics:**
  - *Scientific primary:* **top-weighted Kendall's tau** via `scipy.stats.weightedtau` (hyperbolic rank weighting, concentrates reward at the top of the ranking). Decide in code whether to weight by predicted rank, realized rank, or the symmetric default — leaning realized.
  - *Headline:* **top-quartile hit-rate / precision@10** ("N of my top 10 landed in the top quartile of realized rent growth").
  - Report both, per regime.
- **If we ever move to fitted weights:** never fit on the shock regime (2020 urban-flight reversed by 2022–23 → overfitting trap). Fit on calm regimes, test on others.

**Prediction registry** (`registry.py`): every production run freezes and timestamps the full output — scores, rankings, input-data snapshot, model version — to `predictions/`, never edited. This is pre-registration; it makes the live track record auditable and is a credibility differentiator for the write-up. Lock the evaluation metric *before* the first registry run.

---

## 7. The website (Streamlit v1)

Keep it focused; three things:
1. **Interactive US map** — metros as a choropleth/markers colored by composite score.
2. **Ranked table** — all ~110 metros, sortable, with score and key indicator values.
3. **Metro drill-down** — pick a metro, see its score, its rank, and each indicator's value and percentile, so the score is explainable.

Deploy to Streamlit Community Cloud from the GitHub repo. Add a short "Methodology & limitations" page that links back to the decision log's reasoning.

---

## 8. Suggested build order (milestones)

1. **M1 — One source, end to end.** Wire up FRED (easiest): fetch → cache → clean → into the panel. Get the plumbing right on the simplest source first.
2. **M2 — All sources + panel.** Add the remaining ingest modules; assemble the full metro × year panel. Define and freeze the metro universe here (500k+ MSAs with rent coverage); log dropped metros.
3. **M3 — Indicators + score.** Compute indicators, normalize within period, produce the current-day ranking. First real output.
4. **M4 — Backtest.** Walk-forward, regimes, winsorizing, weighted tau + precision@k. This is where you find out if it works.
5. **M5 — Streamlit app.** Map, table, drill-down.
6. **M6 — Deploy + registry.** Push live, freeze the first prediction run.

---

## 9. Guardrails / principles

- **Reproducibility first:** cache raw downloads, pin dependency versions, set a random seed where relevant.
- **Universe is gated by data:** a metro must clear 500k population AND have continuous rent history; log every drop and the reason.
- **Normalize within period, never across the whole panel.**
- **Don't over-fit recency:** v1 weights are hand-set; if/when fitted, never train on the shock regime.
- **Keep `decision-log.md` current** — append new decisions as they're made; it's also the raw material for the paper's process section.

---

## 10. Limitations to carry into the paper

- No capital-markets data (cap rates, transaction volume); rent growth is the proxy for profitability.
- ZORI is asking rent, not executed rent (can overstate momentum in fast-moving markets).
- Short usable history (~2015+) → few independent windows → overlapping windows are directional, not significance-grade.
- v1 weights are hand-set hypotheses, validated but not optimized.
