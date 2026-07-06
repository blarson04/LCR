# Multifamily Rent-Growth Screener — Paper Brief (model v2.0.0)

*Auto-generated 2026-07-06 from the model outputs. Regenerate with
`python src/paper_brief.py`. Every number here is pulled directly from the processed data —
nothing is hand-typed. Companion docs: `decision-log.md` (the "why"), `v1-build-spec.md` (v1
how), `v2-plan.md` + `paper/v2-findings.md` (the rigor pass that produced v2).*

---

## 1. Summary (abstract-ready)

A transparent, backtested **screening framework** ranks the **110 largest US metros**
by their fundamentals for **3-year forward rent growth**, using only free public data. 8
indicators across five themes are normalized cross-sectionally within each year and combined
with hand-set weights into a composite score. Walk-forward validation shows the framework is
**strong in normal regimes** (pre-COVID 3-year weighted Kendall's τ ≈ **0.59**, precision@10
≈ **85%**) and **breaks down during the 2020–22 shock** (τ ≈ **0.16**) — an expected,
honestly-reported result. Every run is frozen to a pre-registration registry for an auditable
track record. It is positioned as a *screening framework, not a prediction engine*.

**Headline numbers**
- Universe: **110 metros**, scored on the **2023** cross-section; panel spans **2015–2025**.
- Pre-COVID 3-yr: τ **0.588**, precision@10 **0.85**.  Shock 3-yr: τ **0.157**.
- Pooled 3-yr τ **0.444** vs. pooled 1-yr τ **0.500** (≈ equal → see finding #3).
- Worst single window: 3-yr starting **2022** (predicting the post-peak decline), τ **-0.022**.

---

## 2. Data & universe

**Sources (all free, public):** Census ACS (population, housing stock, income),
IRS SOI county-to-county migration, BLS/QCEW (employment, wages, industry mix),
BEA Regional (personal income), Zillow Research (ZORI rent — the target — and ZHVI home
values), FRED (mortgage rate). County-grained sources are rolled up to metros via the Census
OMB CBSA delineation.

**Universe rule (frozen once for v1):** Metropolitan Statistical Areas with population
≥ **500,000** AND gap-free Zillow rent coverage starting no later than
**2016** → **110 metros**. Every metro that clears the
population floor but fails the rent gate is logged:

| Metro | Population | Reason |
| --- | --- | --- |
| San Juan-Bayamón-Caguas, PR | 2,037,875 | no ZORI rent coverage |

---

## 3. The model

8 indicators (the v2 de-duplicated set) in five themes; **hand-set weights**, summing to 100%. Each indicator is
**z-scored across metros within each year** (so a national shock cancels and only the
metro-to-metro spread survives); "inverse" indicators are sign-flipped so **higher = better**
everywhere; the weighted sum is the composite score, and metros are ranked within the year.

| Bucket | Indicator | Weight | Direction |
| --- | --- | --- | --- |
| Demand | net_migration | 20% | higher=better |
| Demand | job_growth | 12% | higher=better |
| Demand | income_growth | 8% | higher=better |
| Supply | permits_to_stock | 25% | inverse (higher=worse) |
| Affordability | rent_to_income | 12% | inverse (higher=worse) |
| Affordability | cost_to_own_vs_rent | 8% | higher=better |
| Momentum | trailing_rent_growth | 10% | higher=better |
| Resilience | employment_diversity | 5% | higher=better |

Bucket totals: **Demand 40% · Supply 25% · Affordability 20% · Momentum 10% · Resilience 5%.**
Missing indicators are treated as neutral (0) at scoring.

---

## 4. Results — current ranking (2023 cross-section)

Columns after Score are the weighted z-score contribution of each bucket.

**Top 15**

| Rank | Metro | Score | Demand | Supply | Afford. | Moment. | Resil. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Charleston-North Charleston, SC | +0.545 | +0.669 | -0.292 | -0.040 | +0.171 | +0.038 |
| 2 | Akron, OH | +0.506 | -0.073 | +0.291 | +0.117 | +0.138 | +0.034 |
| 3 | Omaha, NE-IA | +0.455 | +0.080 | +0.038 | +0.166 | +0.149 | +0.022 |
| 4 | Port St. Lucie, FL | +0.441 | +0.944 | -0.361 | -0.166 | +0.011 | +0.013 |
| 5 | Chattanooga, TN-GA | +0.413 | +0.407 | +0.026 | -0.015 | +0.018 | -0.023 |
| 6 | Lexington-Fayette, KY | +0.388 | +0.102 | +0.063 | +0.079 | +0.145 | -0.000 |
| 7 | Madison, WI | +0.384 | +0.034 | -0.128 | +0.177 | +0.275 | +0.025 |
| 8 | Buffalo-Cheektowaga, NY | +0.382 | -0.102 | +0.310 | +0.037 | +0.099 | +0.039 |
| 9 | Albany-Schenectady-Troy, NY | +0.376 | +0.024 | +0.244 | +0.086 | +0.014 | +0.008 |
| 10 | Dayton-Kettering-Beavercreek, OH | +0.375 | -0.070 | +0.237 | +0.106 | +0.099 | +0.003 |
| 11 | Tulsa, OK | +0.369 | +0.257 | +0.044 | +0.105 | -0.014 | -0.023 |
| 12 | St. Louis, MO-IL | +0.340 | -0.057 | +0.212 | +0.127 | +0.074 | -0.015 |
| 13 | Huntsville, AL | +0.339 | +0.693 | -0.412 | +0.102 | -0.021 | -0.023 |
| 14 | Portland-South Portland, ME | +0.334 | +0.214 | +0.060 | -0.013 | +0.071 | +0.001 |
| 15 | Deltona-Daytona Beach-Ormond Beach, FL | +0.299 | +0.687 | -0.232 | -0.151 | -0.013 | +0.008 |

**Bottom 10**

| Rank | Metro | Score | Demand | Supply | Afford. | Moment. | Resil. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 101 | Killeen-Temple, TX | -0.413 | -0.048 | -0.167 | -0.062 | -0.114 | -0.023 |
| 102 | Memphis, TN-MS-AR | -0.414 | -0.479 | +0.169 | -0.013 | -0.051 | -0.041 |
| 103 | Provo-Orem-Lehi, UT | -0.451 | +0.093 | -0.452 | +0.003 | -0.082 | -0.012 |
| 104 | El Paso, TX | -0.456 | -0.215 | +0.172 | -0.221 | +0.123 | -0.316 |
| 105 | Boise City, ID | -0.483 | +0.217 | -0.527 | +0.054 | -0.183 | -0.044 |
| 106 | Stockton-Lodi, CA | -0.483 | -0.246 | +0.132 | -0.280 | -0.112 | +0.023 |
| 107 | Modesto, CA | -0.522 | -0.504 | +0.248 | -0.231 | -0.041 | +0.007 |
| 108 | Lakeland-Winter Haven, FL | -0.542 | +0.567 | -0.695 | -0.404 | -0.052 | +0.042 |
| 109 | Riverside-San Bernardino-Ontario, CA | -0.730 | -0.274 | +0.002 | -0.410 | -0.069 | +0.020 |
| 110 | McAllen-Edinburg-Mission, TX | -0.870 | -0.250 | -0.285 | -0.242 | +0.000 | -0.094 |

*Pattern: supply-constrained, affordable, steady-demand metros rise to the top; metros that
over-built and then saw rents fall (Austin, Boise, Riverside) sit at the bottom — the model
flagged them on 2023 fundamentals.*

---

## 5. Results — walk-forward backtest (validation)

Each year's ranking is compared to **realized forward rent growth** (3-year primary, 1-year
contrast), ranked cross-sectionally; realized growth is winsorized at the 1st/99th percentile;
the model never sees the future. Metric: top-weighted Kendall's τ (weighted by realized rank)
and precision@10 (share of the top 10 landing in the realized top quartile).

**Summary by horizon × regime**

| Horizon (y) | Regime | Windows | Mean weighted-τ | Mean precision@10 |
| --- | --- | --- | --- | --- |
| 1 | pre-covid | 4 | 0.636 | 0.78 |
| 1 | shock | 2 | 0.349 | 0.45 |
| 1 | normalization | 1 | 0.256 | 0.60 |
| 1 | POOLED | 7 | 0.500 | 0.66 |
| 3 | pre-covid | 4 | 0.588 | 0.85 |
| 3 | shock | 2 | 0.157 | 0.25 |
| 3 | POOLED | 6 | 0.444 | 0.65 |

**Every window**

| Horizon (y) | Pred. year | Regime | Metros | weighted-τ | precision@10 |
| --- | --- | --- | --- | --- | --- |
| 3 | 2016 | pre-covid | 110 | 0.620 | 0.80 |
| 3 | 2017 | pre-covid | 110 | 0.625 | 0.90 |
| 3 | 2018 | pre-covid | 110 | 0.586 | 0.70 |
| 3 | 2019 | pre-covid | 110 | 0.520 | 1.00 |
| 3 | 2021 | shock | 110 | 0.336 | 0.40 |
| 3 | 2022 | shock | 110 | -0.022 | 0.10 |
| 1 | 2016 | pre-covid | 110 | 0.732 | 0.80 |
| 1 | 2017 | pre-covid | 110 | 0.724 | 1.00 |
| 1 | 2018 | pre-covid | 110 | 0.613 | 0.80 |
| 1 | 2019 | pre-covid | 110 | 0.475 | 0.50 |
| 1 | 2021 | shock | 110 | 0.502 | 0.60 |
| 1 | 2022 | shock | 110 | 0.196 | 0.30 |
| 1 | 2023 | normalization | 110 | 0.256 | 0.60 |

**Three findings for the paper**
1. **It works in normal times.** Pre-COVID 3-yr τ ≈ 0.59, precision@10 ≈ 85% — the
   top-10 picks landed in the realized top quartile ~85% of the time.
2. **It breaks down in the shock, as expected.** Shock 3-yr τ ≈ 0.16; the 2022-start window
   (predicting the post-peak correction) is slightly negative (τ -0.02). This vindicates
   the rule never to fit weights on the shock regime, and is reported rather than hidden.
3. **3-year ≈ 1-year (τ 0.44 vs 0.50).** The decision log hypothesized the model
   would do *better* at 3y if it captured fundamentals over momentum; instead they're comparable,
   suggesting momentum and fundamentals contribute similarly — a candidate for fitted-weight work.

*Caveat to state plainly: rent history starts ~2015, so windows are few and overlapping →
**directional evidence, not statistical significance.***

---

## 6. Pre-registration & reproducibility

Every production run is frozen, timestamped, and never edited (registry), making the live track
record auditable — a core credibility differentiator.

- **Model version:** 2.0.0 · **git commit:** b8cba72
- **Frozen run:** 20260701T215522Z (top metro: Charleston-North Charleston, SC)
- **Evaluation metric (locked before first run):** top-weighted Kendall's tau (scipy.stats.weightedtau); rank basis = realized; headline = precision@10 (top-quartile hit-rate).
- Raw downloads cached; pipeline reproducible end-to-end from free sources.

---

## 7. Limitations (carry into the paper)

- No capital-markets data (cap rates, transaction volume) — paid; **rent growth is the proxy for profitability**.
- **ZORI is asking rent, not executed rent** (can overstate momentum in fast markets).
- Short usable history (~2015+) → few independent windows → directional, not significance-grade.
- **Weights are hand-set hypotheses, validated but not optimized** (v2 uses the de-duplicated 8-indicator set).
- Universe frozen once (mild survivorship); Apartment List vacancy signal deferred to v1.1.

---

## 8. Suggested paper structure

1. **Introduction** — the gap (no transparent, auditable, free-data multifamily screener).
2. **Framework** — screening vs. prediction; the five themes and why (→ `decision-log.md`).
3. **Data** — sources, universe definition, the rent-coverage gate, dropped metros (§2).
4. **Methodology** — indicators, within-year normalization, weighting, scoring (§3).
5. **Validation** — walk-forward design, regimes, winsorizing, metrics; results (§5).
6. **Findings & discussion** — the regime story, 3y≈1y, what the top/bottom say (§4–5).
7. **Pre-registration & reproducibility** — the registry as a differentiator (§6).
8. **Limitations & future work** — §7 + fitted weights, AI-exposure indicator, vacancy.
