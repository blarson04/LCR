# Multifamily Rent-Growth Screener — Paper Brief (model v2.0.0)

*Auto-generated 2026-07-20 from the model outputs. Regenerate with
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
≈ **88%**) and **breaks down during the 2020–22 shock** (τ ≈ **0.12**) — an expected,
honestly-reported result. Every run is frozen to a pre-registration registry for an auditable
track record. It is positioned as a *screening framework, not a prediction engine*.

**The paper's spine:** *validation discipline, not data access, is the scarce input in market
selection.* Roughly 90% of a leading professional research product runs on the same free
sources this project uses; what separates the two is that every component, weight scheme, and
data build here had to survive a pre-registered test — and the ones that failed are published.
Every major exhibit below serves that one thesis.

**Headline numbers**
- Universe: **110 metros**, scored on the **2023** cross-section; panel spans **2015–2025**.
- Pre-COVID 3-yr: τ **0.585**, precision@10 **0.88**.  Shock 3-yr: τ **0.123**.
- Pooled 3-yr τ **0.431** vs. pooled 1-yr τ **0.490** (≈ equal → see finding #3).
- Worst single window: 3-yr starting **2022** (predicting the post-peak decline), τ **-0.040**.
- **Vintage rule (v3-P2):** every τ in this brief is a **finalized-data ceiling** unless marked real-time. The **real-time achievable** pooled 3-yr τ — using only proxies a user could have held at scoring time (validated v0.4 configuration) — is **0.420** (97% of the ceiling); pre-COVID real-time **0.596**.
- **Versus industry practice (v3 Phase 4):** a free replica of the leading industry conditions index scores pooled 3-yr τ **0.138** vs the composite's **0.431** (gap +0.293, 95% CI [+0.165, +0.446]) — and it is NOT re-packaged momentum (corr +0.23); see §5f.


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

## 2b. Data quality — the delineation problem (an infrastructure contribution)

**Federal metro-level series are silently corrupted by OMB delineation changes, and any
researcher using them inherits the problem.** When OMB redraws a metro's county membership
(2013, 2018, 2020, 2023 bulletins), the agencies adopt the new boundaries at different times
and *without breaking series identifiers*: QCEW area files switch boundaries between annual
files (2018→2019 and 2023→2024), and the ACS metro API returns each survey year under the
delineation current at release. The result is level breaks that masquerade as growth — this
project found fake metro job prints as large as **±17%** (New Orleans −16.9%, Fresno +15.6%)
and fake population/housing-stock changes as large as **−35%** (New Haven, whose Connecticut
geography switched from counties to planning regions), all inside otherwise-clean federal
data. Of this panel's 110 metros, **39 have county membership that differs across the
delineation vintages the panel spans** — the problem is the norm for long metro panels,
not an edge case.

**Detection protocol (now automated, run per refresh):** (1) cross-source growth diffs for
every measure with an independent sister series — QCEW jobs vs CES, BEA income vs QCEW pay,
Zillow home values vs FHFA HPI, ACS population vs Census PEP — flagging divergences beyond
4pp or 3σ of the within-year diff distribution; (2) a distributional gate blocking any input
growth beyond 4σ of its year's cross-section; (3) a boundary watchlist diffing each CBSA's
county membership against a committed reference; (4) verification by area-file-vs-county-sum
ratio. **Fix:** rebuild affected series from county-level data (county FIPS are stable across
delineations) aggregated on the current boundary; where a geography ceases to exist (the
Connecticut planning regions), chain across the seam with a boundary-stable growth rate.

**Stated honestly:** a validated edition of this screen shipped with nine corrupted metros,
and the first detections came from author skepticism about specific results, not from
automation. The protocol above is that skepticism systematized; publication is now
mechanically blocked until the panel's quality report is clean or every flag is dispositioned
in the public decision log. The #1 rank was held by a data artifact twice before these
controls existed — rank #1 is an extreme-value seat, and extreme values are
disproportionately errors.

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

## 4. Results — current ranking (2025 cross-section)

Columns after Score are the weighted z-score contribution of each bucket.

**Top 15**

| Rank | Metro | Score | Demand | Supply | Afford. | Moment. | Resil. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Knoxville, TN | +0.567 | +0.470 | -0.081 | -0.064 | +0.200 | +0.043 |
| 2 | Charleston-North Charleston, SC | +0.525 | +0.671 | -0.291 | -0.040 | +0.171 | +0.015 |
| 3 | Akron, OH | +0.484 | -0.072 | +0.291 | +0.117 | +0.138 | +0.011 |
| 4 | Omaha, NE-IA | +0.434 | +0.081 | +0.038 | +0.167 | +0.149 | -0.001 |
| 5 | Port St. Lucie, FL | +0.419 | +0.946 | -0.361 | -0.167 | +0.011 | -0.010 |
| 6 | Chattanooga, TN-GA | +0.390 | +0.408 | +0.026 | -0.015 | +0.018 | -0.048 |
| 7 | Lexington-Fayette, KY | +0.366 | +0.103 | +0.063 | +0.079 | +0.145 | -0.024 |
| 8 | Madison, WI | +0.362 | +0.035 | -0.128 | +0.177 | +0.275 | +0.003 |
| 9 | Buffalo-Cheektowaga, NY | +0.360 | -0.101 | +0.309 | +0.037 | +0.099 | +0.016 |
| 10 | Albany-Schenectady-Troy, NY | +0.354 | +0.025 | +0.244 | +0.087 | +0.014 | -0.015 |
| 11 | Tulsa, OK | +0.346 | +0.258 | +0.044 | +0.105 | -0.014 | -0.047 |
| 12 | Huntsville, AL | +0.317 | +0.695 | -0.411 | +0.102 | -0.021 | -0.048 |
| 13 | St. Louis, MO-IL | +0.317 | -0.056 | +0.212 | +0.127 | +0.074 | -0.039 |
| 14 | Portland-South Portland, ME | +0.311 | +0.215 | +0.060 | -0.013 | +0.071 | -0.023 |
| 15 | Wichita, KS | +0.304 | +0.069 | +0.001 | +0.101 | +0.108 | +0.025 |

**Bottom 10**

| Rank | Metro | Score | Demand | Supply | Afford. | Moment. | Resil. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 101 | Los Angeles-Long Beach-Anaheim, CA | -0.433 | -0.554 | +0.187 | -0.030 | -0.056 | +0.020 |
| 102 | Killeen-Temple, TX | -0.438 | -0.047 | -0.167 | -0.062 | -0.114 | -0.048 |
| 103 | Provo-Orem-Lehi, UT | -0.474 | +0.093 | -0.452 | +0.002 | -0.082 | -0.036 |
| 104 | El Paso, TX | -0.488 | -0.214 | +0.172 | -0.222 | +0.123 | -0.347 |
| 105 | Boise City, ID | -0.507 | +0.218 | -0.527 | +0.054 | -0.183 | -0.068 |
| 106 | Stockton-Lodi, CA | -0.508 | -0.247 | +0.132 | -0.282 | -0.112 | +0.000 |
| 107 | Modesto, CA | -0.548 | -0.506 | +0.248 | -0.232 | -0.041 | -0.016 |
| 108 | Lakeland-Winter Haven, FL | -0.566 | +0.568 | -0.695 | -0.406 | -0.052 | +0.019 |
| 109 | Riverside-San Bernardino-Ontario, CA | -0.756 | -0.274 | +0.002 | -0.412 | -0.069 | -0.004 |
| 110 | McAllen-Edinburg-Mission, TX | -0.897 | -0.251 | -0.285 | -0.243 | +0.000 | -0.119 |

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
| 1 | pre-covid | 4 | 0.655 | 0.83 |
| 1 | shock | 2 | 0.320 | 0.45 |
| 1 | normalization | 1 | 0.173 | 0.50 |
| 1 | POOLED | 7 | 0.490 | 0.67 |
| 3 | pre-covid | 4 | 0.585 | 0.88 |
| 3 | shock | 2 | 0.123 | 0.20 |
| 3 | POOLED | 6 | 0.431 | 0.65 |

**Every window**

| Horizon (y) | Pred. year | Regime | Metros | weighted-τ | precision@10 |
| --- | --- | --- | --- | --- | --- |
| 3 | 2016 | pre-covid | 110 | 0.612 | 0.90 |
| 3 | 2017 | pre-covid | 110 | 0.633 | 0.90 |
| 3 | 2018 | pre-covid | 110 | 0.589 | 0.70 |
| 3 | 2019 | pre-covid | 110 | 0.507 | 1.00 |
| 3 | 2021 | shock | 110 | 0.286 | 0.30 |
| 3 | 2022 | shock | 110 | -0.040 | 0.10 |
| 1 | 2016 | pre-covid | 110 | 0.730 | 0.90 |
| 1 | 2017 | pre-covid | 110 | 0.728 | 1.00 |
| 1 | 2018 | pre-covid | 110 | 0.622 | 0.80 |
| 1 | 2019 | pre-covid | 110 | 0.538 | 0.60 |
| 1 | 2021 | shock | 110 | 0.450 | 0.60 |
| 1 | 2022 | shock | 110 | 0.190 | 0.30 |
| 1 | 2023 | normalization | 110 | 0.173 | 0.50 |

**Precision lumpiness (appendix):** with n=110 metros, precision@10 moves in 0.1 lumps — one top-10 miss swings a window by 10 points. Co-reported once: pooled 3-yr precision@20 is **0.58** beside precision@10's 0.65 (per-window detail: `data/processed/precision_k.csv`). Same story at half the lump size; the pre-registered headline metric remains precision@10.

**Three findings for the paper**
1. **It works in normal times.** Pre-COVID 3-yr τ ≈ 0.59, precision@10 ≈ 88% — the
   top-10 picks landed in the realized top quartile ~88% of the time.
2. **It breaks down in the shock, as expected.** Shock 3-yr τ ≈ 0.12; the 2022-start window
   (predicting the post-peak correction) is slightly negative (τ -0.04). This vindicates
   the rule never to fit weights on the shock regime, and is reported rather than hidden.
3. **3-year ≈ 1-year (τ 0.43 vs 0.49).** The decision log hypothesized the model
   would do *better* at 3y if it captured fundamentals over momentum; instead they're comparable,
   suggesting momentum and fundamentals contribute similarly — a candidate for fitted-weight work.

*Caveat to state plainly: rent history starts ~2015, so windows are few and overlapping →
**directional evidence, not statistical significance.***

**Uncertainty, honestly stated (v3-P3).** The primary statement is the **per-window range**:
3-yr τ spanned **[-0.04, +0.63]** across 6
overlapping windows — calm windows near the top, shock windows near the bottom; no pooled
average conveys that spread. Jackknife: dropping any single window moves the pooled 3-yr τ only
within **[0.39, 0.53]**. Because neighboring metros co-move, a
**state-cluster bootstrap** (41 states) widens the pooled-τ 95% interval to
**[0.34, 0.55]**, and the equal-weight edge **survives** that
stricter test (gap CI [+0.037, +0.153]). Metro-cluster
pooled CIs elsewhere are **cross-sectional only** — conditional on the observed windows and
silent about regime risk.


---

## 5b. Economic effect size & the momentum question (v3 P4–P5)

**Top-10 edge in percentage points of realized 3-yr rent growth vs the universe median**
(the headline communication metric — τ translated into units investors understand):

| Window (T→T+3) | Composite (model) | Momentum (trailing rent) | 50/50 blend | Equal weight | Random (50-seed mean) |
| --- | --- | --- | --- | --- | --- |
| 2016 | 7.2 | 7.2 | 7.2 | 5.9 | 0.5 |
| 2017 | 7.2 | 6.2 | 6.3 | 4.9 | 0.3 |
| 2018 | 10.4 | 10.4 | 11.0 | 6.3 | 0.7 |
| 2019 | 12.8 | 10.6 | 11.6 | 8.9 | 0.5 |
| 2021 | 0.0 | -1.5 | 0.4 | -2.9 | -0.1 |
| 2022 | -1.7 | -4.3 | -5.5 | -4.3 | -0.4 |

Pooled top-10 edge: **composite +6.0 pp**, momentum +4.8 pp,
50/50 blend +5.2 pp, equal-weight +3.1 pp,
random ≈ 0.2 pp.

**The shock exhibit (the framing decider):** momentum's top-10 edge flipped negative in the
shock windows (**-1.5 pp in 2021, -4.3 pp in 2022**) while the
composite's held up far better (**+0.0 pp and -1.7 pp**) — the
fundamentals sleeve provided real downside protection exactly where momentum inverted.

**Orthogonality:** after controlling for trailing rent growth, the composite still predicts
forward growth (partial rank correlation pooled **+0.25**,
positive in every window). But the two strategies' errors co-move (correlation
**+0.61**, rising to ~0.77 in the shock), so the diversification
is partial. The 50/50 blend edges the composite on τ (0.45
vs 0.43) but has a worse worst-window
(-5.5 vs -1.7 pp) and a lower pooled
pp edge — no clear improvement.

**Resulting framing (decided from the evidence, per v3-P4):** *comparable to momentum on rank
agreement; better where it matters — a higher pp edge, genuine signal beyond momentum, and
materially smaller top-10 losses in the windows where momentum inverted. Diversification is
real but partial.*


---

## 5c. The regime flag, validated ex ante (v3-P6)

The site's elevated-uncertainty flag uses one rule, computable at scoring time from near-live
rent data: **flag the scoring year if national (median-metro) YoY asking-rent growth exceeds
7.5%**. The rule shipped on 2026-07-02, *before* this validation —
it is tested as-is, not tuned.

| Year | Nat. rent growth | Flag fires | Hindsight regime | 3y window τ | 1y window τ |
| --- | --- | --- | --- | --- | --- |
| 2016 | +3.6% | False | pre_covid | +0.61 | +0.73 |
| 2017 | +4.0% | False | pre_covid | +0.63 | +0.73 |
| 2018 | +3.9% | False | pre_covid | +0.59 | +0.62 |
| 2019 | +4.1% | False | pre_covid | +0.51 | +0.54 |
| 2020 | +4.3% | False | shock | — | — |
| 2021 | +10.0% | True | shock | +0.29 | +0.45 |
| 2022 | +10.7% | True | shock | -0.04 | +0.19 |
| 2023 | +4.1% | False | normalization | — | +0.17 |
| 2024 | +3.3% | False | normalization | — | — |
| 2025 | +2.9% | False | normalization | — | — |

**Result:** the flag fires in **2021 and 2022 only** — exactly the windows where accuracy broke
(mean flagged 3-yr τ **+0.12** vs unflagged **+0.59**) — with **zero
false positives** across seven calm years. Disclosed miss: 2020, a demand shock that never moved
rents (also not a scoreable 3-yr window); rules based on rent speed cannot see shocks that don't
move rents. The hindsight regime labels remain for backtest *reporting*; the live flag uses only
this ex-ante rule.


---

## 5d. The current screen: a validated 2024 vintage, extended to 2028 (v3.1)

**The gate arc.** Every fresher-than-finalized configuration faced the same pre-registered
gate (≥85% retention of pooled 3-yr τ AND ≥7/10 mean top-10 overlap), one attempt each, all
outcomes published: 2025 nowcast **74.8% — FAIL**; +CES jobs **84.66% — FAIL** (pulled, not
rounded up); **2024-vintage** (all finalized inputs, single PEP-migration substitution)
**95.52% retention, 8.29/10 overlap — PASS**; **v0.4 state-chained income** (2026-07-08)
**96.56% retention, 7.43/10 overlap — PASS**, publishing a validated **2025→2028 current
screen** beside the 2024-vintage primary. The vintage screen is a **2024→2027 call**,
refreshed each fall as new vintages land.

**Horizon extension (disclosed-priors decision, not a blind gate — the study is the evidence).**
`src/horizon_decay.py`: the composite *strengthens* with horizon while momentum decays —
pooled τ at h=3/4/5: **0.43 / 0.46 /
0.50** with top-10 pp edges **+6.0 /
+8.5 / +11.1**, vs momentum τ
0.39/0.38/0.40 — the
original "fundamentals express over time" hypothesis confirmed directly. Decision: a
**2024→2028 (4-yr) extended view is published**, always labeled; **h≥5 is refused** because
every testable 5-yr window starts pre-COVID (sample selection), and we say so.


---

## 5e. New signals tested — and all rejected (v3 Phase 3)

The Arbor–Chandan benchmark review surfaced six candidate signals, frozen in a pre-registered
list before any accuracy work. Two died in the coverage audit (ZORDI history too short for the
annual model; insurance burden not freely acquirable). The surviving five each got **one
attempt** at the standard three-part gate (standalone τ > 0.10 AND max |corr| vs the scored
indicators < 0.70 AND value-add at a fixed 10% weight with a metro-cluster bootstrap CI
excluding 0):

| Candidate | Standalone 3y τ | Max |corr| (with) | Value-add Δτ @10% | 95% CI | Adopted |
| --- | --- | --- | --- | --- | --- |
| C1 CREMI MF absorption | +0.085 | 0.12 (cost_to_own_vs_rent) | -0.027 | [-0.068, +0.015] | no |
| C2 CREMI MF NOI | +0.083 | 0.42 (trailing_rent_growth) | -0.021 | [-0.058, +0.011] | no |
| C3 CREMI MF asset price | +0.186 | 0.26 (trailing_rent_growth) | -0.011 | [-0.040, +0.016] | no |
| C6a delta rental_vacancy | +0.072 | 0.08 (rent_to_income) | -0.051 | [-0.097, -0.000] | no |
| C6b delta unemployment (MSAUR) | +0.218 | 0.18 (job_growth) | +0.012 | [-0.011, +0.038] | no |

**Zero adoptions — the model stays the frozen 8-indicator v2.** Notable negatives: CREMI NOI
(the pre-registered "one to watch") failed on standalone signal, and its +0.42 correlation with
trailing rent growth is exactly the NOI ≈ rents − expenses redundancy flagged in advance; the
asset-price sub-index has real signal (τ 0.186) but adds nothing the composite lacks; and the
Δ-unemployment candidate was auto-orient *flipped* — rising unemployment predicting stronger
3-yr rent growth (a counter-cyclical recovery artifact of the 2015–24 sample) — yet still
cleared no value-add bar. Across two gate cycles, **no candidate has shown a reliably
detectable improvement over the composite**. Stated with its limits: with only ~6
overlapping evaluation windows the value-add test has limited power against small true
improvements, so these are "not detectably better" results, not "proven useless" — and the
project defaults to parsimony rather than to accumulation.


---

## 5f. Versus industry practice (v3 Phase 4)

**The observation that motivates this section (for the paper intro):** the leading industry
market-selection index (the Arbor–Chandan Multifamily Opportunity Matrix) runs **~90% on the
same free public sources this project uses** — of its ten equal-weighted categories, only the
capital-markets block (~10%) is proprietary. Professional market selection is, in data terms,
mostly free; what this project adds is validation discipline, not data access.

That converts the implicit claim into an explicit test: does a validated, deliberately
weighted screen beat industry-style practice at the prediction task? We replicated the
matrix's form — ten equal-weighted categories, variables equal-weighted within — from free
components on our 6-of-10 replicable
categories, froze the construction in a dated log entry before the run (orientations fixed
a priori, no auto-orientation, no tuning after first results), and ran the standard
walk-forward:

| Ranking rule | Pooled 3-yr τ | Precision@10 |
| --- | --- | --- |
| Full model (composite) | +0.431 | 0.65 |
| Best single indicator | +0.391 | 0.65 |
| Momentum only (trailing rent) | +0.391 | 0.65 |
| Equal weight (8 ind.) | +0.340 | 0.58 |
| Persistence (trailing h-yr) | +0.216 | 0.38 |
| Industry-style index (equal weight) | +0.138 | 0.33 |
| Random (avg of seeds) | +0.002 | 0.26 |

**Gap: composite − industry replica = +0.293 pooled 3-yr τ (95%
metro-cluster CI [+0.165, +0.446])** — the largest reliable
edge over any baseline tested; the industry-style index lands *below persistence* and above
only random.

**Our pre-registered prediction failed, and that is itself a finding.** Phase 0 logged the
expectation that the industry index would be "re-packaged momentum" (high correlation with
trailing rent growth). It is not: pooled correlation **+0.23**
(mean per-year rank correlation +0.23). The diagnosis the data
supports is harsher: the conditions components (unemployment levels, demographics, vacancy,
absorption) *dilute* predictive signal rather than repackage it. Nor is equal weighting the
failure — equal weight over our own eight validated indicators scores respectably (see table).
The failure is a component set assembled for investor-conditions narrative rather than tested
against a prediction target.

**Fairness caveats (attach to any use of this result):** the replica covers 6 of 10 categories
(capital markets proprietary; taxes, ZORDI, insurance excluded per the frozen spec) on our
110-metro universe (theirs: top 50); the industry matrix targets "opportunistic multifamily
investment" broadly and never claims to predict 3-yr rent growth. This scores the *practice*
of equal-weight conditions indices at our task, not any vendor's product at theirs.

**Robustness pair (pre-registered 2026-07-08, first results final):** the two strongest hostile objections were tested directly. Restricted to the 50 largest metros (the industry universe) the replica has no detectable signal at all; scored at tasks closer to its implied objective (1-yr horizon; a blended rent + asset-value target) it does no better. The composite is reliably ahead on every exhibit:

- **3y rent growth** (top-50 subuniverse): composite +0.301 vs replica -0.018, gap +0.319 (95% CI [+0.164, +0.505])
- **1y rent growth** (full universe): composite +0.490 vs replica +0.169, gap +0.321 (95% CI [+0.220, +0.424])
- **3y rent + asset-value blend** (full universe): composite +0.252 vs replica -0.096, gap +0.347 (95% CI [+0.243, +0.471])


---

## 6. Pre-registration & reproducibility

Every production run is frozen, timestamped, and never edited (registry), making the live track
record auditable — a core credibility differentiator.

- **Model version:** 2.0.0 · **git commit:** aa89561
- **Frozen run:** 20260708T150402Z (top metro: Albany-Schenectady-Troy, NY)
- **Evaluation metric (locked before first run):** top-weighted Kendall's tau; rank basis = realized; headline = precision@10.
- Raw downloads cached; pipeline reproducible end-to-end from free sources.

---

## 7. Limitations (carry into the paper)

- No capital-markets inputs in the score (transactions, lending); **rent growth is the proxy
  for profitability**. Free metro cap-rate and occupancy series do exist (Atlanta Fed CREMI,
  found in the v3 coverage audit — softening the original "cap rates are paid-only" claim);
  they are context only, never gated candidates under the frozen v3 list.
- **ZORI is asking rent, not executed rent** (can overstate momentum in fast markets).
- Short usable history (~2015+) → few independent windows → directional, not significance-grade.
- **Weights are hand-set hypotheses, validated but not optimized** (v2 uses the de-duplicated 8-indicator set).
- Universe frozen once (mild survivorship); Apartment List vacancy signal deferred to v1.1.

---

## 8. Paper structure (v4 revision — the validation-discipline spine)

*Spine: validation discipline, not data access, is the scarce input in market selection.
Every exhibit serves it. Venue: SSRN working paper + a practitioner write-up first; if
refereed, a practitioner outlet (e.g., Journal of Real Estate Portfolio Management), not an
academic econ journal — the contribution is disciplined method applied to practice.*

1. **Introduction** — the gap (no transparent, auditable, free-data multifamily screener);
   the ~90%-free observation AND the headline contrast (composite 3-yr τ vs the
   industry-style replica, §5f) moved up front: together they motivate everything.
2. **Framework** — screening vs. prediction; the five themes and why (→ `decision-log.md`).
3. **Data** — sources, universe definition, the rent-coverage gate, dropped metros (§2).
4. **Data quality** — the delineation problem, detection protocol, county-rollup fix (§2b).
   Framed as an infrastructure contribution useful to any researcher using metro-level
   federal data — including the honest paragraph that a validated edition shipped with nine
   corrupted metros before the protocol existed.
5. **Methodology** — indicators, within-year normalization, weights (per the pending
   monetization decision), scoring (§3).
6. **Validation** — walk-forward design, regimes, winsorizing, metrics; per-window ranges as
   the PRIMARY uncertainty statement; the four-attempt gate arc with both failures (§5, §5d).
7. **Versus industry practice** — the replica result, the failed "re-packaged momentum"
   prediction published as logged, the robustness pair (top-50 subuniverse; alternate-task
   fairness), and the fairness caveats inline (§5f). The claim is "equal-weight conditions
   indices are not rent-growth predictors," never "we beat [vendor]."
8. **Mechanism** — the horizon finding: the composite strengthens toward 4–5-year horizons
   while momentum decays — direct evidence that fundamentals express over time (§5b).
9. **Gated candidates** — eight rejections with the low-power-honest framing: "no reliably
   detectable improvement; with ~6 windows the test has limited power, so we default to
   parsimony" (§5e).
10. **Registry & reproducibility** — the frozen-run registry, and the binding 2028
    pre-commitment to publish the realized performance of the 2025→2028 screen whatever it
    shows (§6).
11. **Limitations & future work** — §7, stated as limits on the claims, not disclaimers.
