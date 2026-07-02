# Multifamily Market Screening — Decision Log

*Purpose: a running record of the decisions we make and **why**, so we can retrace our reasoning as the project grows. Add new entries at the top of the log as they happen. Keep it light — one decision, one short rationale.*

---

## Living snapshot: current v1 indicator weights

Each indicator is normalized **across all metros** (percentile / z-score) *before* its weight is applied.

| Category | Indicator | Weight | Direction | Source |
|---|---|---|---|---|
| **Demand (40%)** | Net domestic migration | 14% | higher = better | IRS flows + Census |
| | Job growth (YoY, total nonfarm) | 12% | higher = better | BLS |
| | Income / wage growth | 8% | higher = better | BEA / BLS |
| | Population growth | 6% | higher = better | Census |
| **Supply (25%)** | Permits ÷ existing housing stock | 17% | higher = **worse** | Census BPS |
| | Multifamily pipeline intensity | 8% | higher = **worse** | Census BPS |
| **Affordability (20%)** | Rent-to-income ratio (level) | 12% | higher = **worse** | Zillow + BEA |
| | Cost-to-own vs. rent gap | 8% | higher = better | Zillow |
| **Momentum (10%)** | Trailing rent growth (YoY) | 10% | higher = better (confirmation only) | Zillow / Apartment List |
| **Resilience (5%)** | Employment diversification | 5% | higher = better | BLS |

---

## Decision log

### 2026-07-02 — v2.1 nowcast M3: FAILED the pre-committed gate → internal experiment

The pseudo-nowcast backtest (rebuild history with the nowcast's proxies — PEP migration + carry-forward slow indicators + live rent/permits — and run the standard walk-forward) retains only **75%** of the finalized model's pooled 3-yr τ (0.332 vs 0.444; gap +0.112, 95% CI [+0.038, +0.182] — *reliably* below the ≥85% bar) and averages **6.1/10** top-10 overlap (below the ≥7/10 bar). Per the gate committed **before** M3 ran, **the nowcast does NOT publish** — v2.1 ships as an internal experiment with this documented negative result (a finding worth a paragraph in the paper).

**Diagnosis (decomposition confirms it):** pooled 3-yr τ by variant — finalized **0.444**; only-migration-proxied **0.423 (95%)**; pseudo-but-jobs+income-finalized **0.427 (96%)**; full pseudo **0.332 (75%)**. So the migration proxy costs almost nothing, and **carrying forward `job_growth` + `income_growth` accounts for essentially the entire failure**. The nowcast is *one input away*: fresh current-year employment/wage data (CES) would lift retention to ~96%, clearing the 85% gate. CES is deferred only because BLS metro employment needs a bot-blocked area-code crosswalk. **Future work:** source CES (e.g. via FRED's SAE series) and re-run M3 — the nowcast's viability hinges on fresh jobs data, not on migration.

**Consequence:** M5 (surfacing the provisional ranking on the site) is **gated OFF** — the provisional 2025 ranking stays an internal artifact, not a default view. M4 (registry provisional flag + reconciliation) may still be built to freeze the provisional run *as provisional* alongside this negative result.

### 2026-07-02 — v2.1 nowcast M1: migration proxy validated; M3 gate pre-committed

Starting the v2.1 nowcast layer (see `v2.1-nowcast-spec.md`, `paper/nowcast-validation.md`). The layer feeds fast proxies for slow inputs into the **unchanged** frozen v2 scoring path; it shortens the data lag, it does NOT extend the 3-year forecast horizon.

**M1 linchpin result (the make-or-break):** Census PEP net domestic migration proxies the slow IRS migration (v2's one indispensable indicator) very well — level r ≈ 0.99, per-year rank ≈ 0.90 (dipping only in the 2020–21 shock). Substituting PEP into the full v2 composite barely moves the ranking (median Spearman 0.98, top-10 overlap ~9/10). Carry-forward proxies are safe: housing stock YoY rank-persistence 1.00; employment-diversity HHI 0.84. **The linchpin holds → proceed to M2/M3.** proxy_map version 0.1.

**Pre-committed M3 go/no-go gate (decided BEFORE M3 runs, per the guardrail):** publish the nowcast **iff** the pseudo-nowcast retains **≥ 85% of the full model's pooled 3-yr weighted τ** AND its **top-10 overlap with the finalized ranking averages ≥ 7/10**. If it fails, v2.1 ships as an internal experiment with a documented negative result (still a paper paragraph). Choosing thresholds after seeing results would be the same sin as picking the metric after the backtest.

### 2026-07-01 — Tier-2 candidates gated: vacancy & AI-exposure NOT adopted

Two new signals were tested against the pre-committed gate — standalone predictive τ + redundancy + does-it-*reliably*-improve-τ (metro-cluster bootstrap CI). See `src/tier2_gate.py` and `data/processed/tier2_gates.csv`.

- **Vacancy (P6)** — ACS rental vacancy rate (chosen over Apartment List for reproducibility; AL download URLs move). Standalone 3y τ +0.19, but augmenting the composite at 10% doesn't reliably help (Δτ −0.028, CI [−0.093, +0.016]) and it's partly redundant with `cost_to_own_vs_rent` (r 0.38).
- **AI-exposure (P7)** — an **industry-level proxy**: metro employment share in the highest gen-AI-exposure NAICS sectors (Information, Finance & Insurance, Professional/Scientific/Technical, Management of companies), built from the already-cached QCEW data because BLS OEWS occupation files block bot downloads (HTTP 403). Genuinely **non-redundant** (max |r| 0.26) but weak standalone (+0.09) and **zero reliable value-add** (Δτ +0.003, CI [−0.040, +0.039]).

**Decision:** neither is adopted as a scored indicator — the gate guards against adding noise/complexity (the same discipline that vetoed the P2 cuts and the P5 second screen). Both are kept as panel columns for **context/description**. Headline: across P5–P7, **no new free signal reliably improved the model**, reinforcing that it is a parsimonious, honestly-bounded framework. AI-exposure remains a novel descriptive layer; occupation-level OEWS is a future refinement if accessible data is found.

### 2026-07-01 — v2 model: adopt the de-duplicated 8-indicator scheme

After a Tier-1 rigor pass (baselines, ablation, uncertainty, weight robustness — see `v2-plan.md` and `paper/v2-findings.md`), v2 drops two redundant indicators: **`population_growth`** (folded into `net_migration`, r=0.62) and **`mf_pipeline`** (folded into `permits_to_stock`, r=0.77). The metro-cluster bootstrap showed the 8-indicator scheme matches the v1 10-indicator model with **no reliable accuracy loss** (3-yr weighted τ ≈ 0.44, overlapping CIs), so we prefer the more parsimonious set. Bucket totals are unchanged (Demand 40 / Supply 25 / Affordability 20 / Momentum 10 / Resilience 5).

We deliberately do **not** free-fit the weights: only equal-weight was *reliably* worse than the best scheme; among hypothesis-driven schemes the differences were within noise, so tuning would chase noise. Honest framing carried into v2: the composite has real 3-yr signal and reliably beats equal-weight and persistence, but is **not** reliably better than a trailing-rent-growth (momentum) one-liner, and **`net_migration` is the single indispensable indicator**. Model version → 2.0.0; the v1 model is preserved in git history and the frozen v1 registry run.

### 2026-06-28 — Build-time data-source decisions (M2 ingest)

These are implementation choices made while wiring up the data pipeline. They're recorded here because several are non-obvious and shouldn't be silently "corrected" later, and because the build spec asks to keep this log current.

**BLS via QCEW open-data files, not the BLS time-series API.** Job growth, wage growth, and employment diversification all come from the QCEW (Quarterly Census of Employment and Wages) open-data CSVs (`data.bls.gov/cew/...`), which need no API key. Reasons: QCEW is a near-census of employer reports (more accurate than the CES sample), it delivers employment + wages + full industry mix in a single file per metro-year, and it avoids both the BLS API's rate limits and a separate CBSA→BLS-area-code crosswalk. QCEW lags ~6–9 months, which is immaterial for an annual panel on a 3-year horizon. A `BLS_API_KEY` is kept in `.env` for optional future cross-checks but is intentionally unused in v1.

**BEA income via county→metro roll-up.** BEA's CAINC1 table (personal income, population, per-capita income) is served at county level; the API rejects MSA geography. So we pull counties and aggregate to metros with the shared crosswalk — the same pattern as IRS migration and permits. Per-capita income is derived as metro personal income ÷ metro population.

**Shared county→CBSA crosswalk.** The county-grained sources (IRS migration, building permits, BEA income) all roll up through one module built from the Census OMB July-2023 delineation file (393 Metropolitan CBSAs). Its CBSA codes match the ACS API's, so everything joins on one clean key.

**Rent and home-value series (Zillow).** Both ZORI (rent, the target) and ZHVI (home value, for the cost-to-own-vs-rent indicator) use the *smoothed, seasonally-adjusted, all-homes-plus-multifamily* series, annualized as the mean of monthly values. Seasonal adjustment keeps month-of-year effects out of the growth math.

**Net migration = net domestic, persons.** From IRS data we use the "Total Migration-US" aggregate (which excludes foreign migration), measured in exemptions (≈ persons), summed across a metro's counties so intra-metro moves cancel. Each file pair (e.g. 2022↔2023) is labeled as the later year.

**Employment diversification = HHI across private NAICS sectors.** Herfindahl index of employment across the 20 private NAICS sectors (QCEW sector level). Higher HHI = more concentrated = less resilient; the indicator flips it so higher = better.

**Apartment List deferred to v1.1.** The spec scopes Apartment List as a bonus (rent cross-check + vacancy), not one of the 10 core indicators, so it's deferred to reach a first ranking sooner.

### 2026-06-28 — Metro universe: 500k population floor

**Metro universe — MSAs with 500k+ population (~110 metros), gated by rent-data coverage.**
Include Metropolitan Statistical Areas (not Micropolitan) with population ≥ 500,000, which yields roughly 110 metros. Reasons: a 1M floor (~55 metros) would exclude the mid-size emerging markets the tool exists to find (Boise, Huntsville, Chattanooga, Knoxville, Provo, Greenville); a 250k floor (~185 metros) pulls in markets where multifamily is not a liquid institutional asset and where free rent-index coverage gets patchy. 500k balances cross-section size (a healthy N for weighted Kendall's tau), genuine multifamily liquidity, and reliable data coverage.
*Effective rule:* 500k+ population **and** continuous rent-index coverage back to the baseline (ZORI reaches ~2015; Apartment List ~2017). Metros lacking clean history are dropped — and we log which metros were dropped and why, since that transparency is itself part of the methodology. Fix the universe once for v1 rather than redefining it annually (population moves slowly enough that this won't bias the backtest and it keeps the panel clean).

### 2026-06-28 — Validation: accuracy tracking, retraining approach & evaluation metric

**Prediction registry — freeze and timestamp every model run.**
Each time the model runs, freeze and timestamp the full output (scores, rankings, the input-data snapshot, and the model version) and never edit it. As outcomes mature, score the frozen predictions against what actually happened. This is de facto pre-registration: it prevents hindsight self-deception and builds a credible, checkable public track record — a real differentiator for the LinkedIn write-up, since almost nobody lets their old market calls be audited.

**Training & refinement via walk-forward validation, not a live retrain loop.**
The binding feedback lag is not the few-month data-publication lag — it is the 3-year horizon itself, so a "retrain on live realized accuracy" loop has a ~3-year cycle and would be retraining on noise for years. Instead use walk-forward: train on data up to year T, predict T→T+3, roll forward one year, retrain including the newly-resolved data, repeat across the whole history. This simulates the live retraining loop on historical data where outcomes already exist, so we learn *now* whether retraining actually helps. It is also the honest validation method — the model never sees the future.

**Retrain on a deliberate cadence (e.g., annual), not continuously.**
Continuous retraining on a handful of new metro-years chases recent noise and amplifies the regime/recency overfitting we flagged in the COVID entry. But a frozen model also goes stale (rates, supply cycles, AI-labor shifts). So: retrain on a set cadence, always against a held-out test, and always benchmarked head-to-head against the frozen original so we can *prove* the retrain helped rather than assume it. Defer the actual cadence until real resolved outcomes accumulate. Live accuracy is treated as calibration and narrative, not an automatic retrain trigger.

**Evaluation metric — top-weighted Kendall's tau (scientific primary); top-quartile hit-rate (headline).**
Primary, the thing we validate and train against: top-weighted Kendall's tau. It concentrates the reward at the top of the ranking (getting the best markets right) while keeping the statistical efficiency of a continuous, whole-ranking metric — which matters given how few independent outcome cohorts we have. Implementation: `scipy.stats.weightedtau` (hyperbolic rank weighting by default). Parameter to settle in code: weight by predicted rank, realized rank, or the symmetric average (scipy's default) — leaning toward realized rank. Headline, for communication: top-quartile hit-rate / precision@10 — visceral and checkable ("7 of my top 10 markets landed in the top quartile of realized rent growth"). Report both, segmented per regime. Lock the metric *before* the prediction registry goes live, or the pre-registration is meaningless. Note: "accuracy" means accuracy against rent growth — our measurable proxy for "profitable" — and excludes cap-rate movement and price appreciation, which sit behind paid data.

### 2026-06-28 — Backtest design: forecast horizon & COVID-era handling

**Forecast horizon — 3-year primary target, 1-year reported as a contrast.**
Primary prediction target is 3-year forward rent growth, ranked cross-sectionally against other metros. The 1-year result is computed and reported too, but as a foil, not the target. Why 3-year: it is the horizon where fundamentals (migration, supply pipeline, affordability) express themselves and where momentum mean-reverts, so it actually tests the model's thesis; a 1-year target would mostly reward momentum and contradict our decision to down-weight it. It also matches the asset — multifamily is illiquid and underwritten over multi-year holds — and is the only horizon where supply mean-reversion is visible. Reporting 1-year alongside is itself useful: if the model does better at 3-year than 1-year, that gap is evidence the fundamentals are real and not just momentum.
*Binding constraint:* usable free rent-index history only goes back to ~2014–2015, so there are few independent 3-year windows. We use rolling, overlapping 3-year windows and treat results as directional evidence — explicitly NOT as independent observations, so we do not overstate statistical significance.

**COVID era — keep all of it; split conceptually, segment by regime, never exclude.**
Do not delete the COVID years. Split them: 2021–2022 (the rent spike) is genuinely anomalous (stimulus, one-time household formation, remote-work migration) and its magnitudes should not be "learned" from. But 2023–2024 (the normalization) is the supply thesis playing out in real time — overbuilt Sunbelt metros got crushed while supply-constrained markets held up — which is the best evidence the model works. Excluding it would be cherry-picking and would throw away the most valuable test.
What we do instead:
- Rank cross-sectionally *within each period*, so a national common shock (everyone's rent jumps together) largely cancels and only the metro-to-metro spread survives.
- Winsorize extreme rent-growth values (cap at ~1st/99th percentile) and disclose it, so a few 2021 blowouts do not dominate.
- Segment the backtest into regimes — pre-COVID baseline (~2015–2019), shock (2020–2022), normalization (2023–present) — and report each separately alongside a pooled result. "Does the framework hold across regimes?" becomes a headline finding, not a buried caveat.
- Tag every rolling window by the regime(s) it spans. Point-to-point growth means a window starting at the 2022 peak looks catastrophic and one ending at the peak looks miraculous — that reflects timing, not the model — so windows must be interpreted by regime.

*Forward caution (for when/if we move from hand-set to fitted weights):* never fit weights on the shock period. The 2020 urban-flight divergence reversed by 2022–2023, so a model trained on it would "learn" a pattern that was about to invert — a textbook overfitting trap. Fit on calm regimes, test on others, never the reverse.

### 2026-06-28 — Project setup & v1 framework

**Framing — "screening framework," not "prediction engine."**
We position the project as a transparent, systematic framework that screens markets on fundamentals that historically precede outperformance, validated by backtesting. More defensible and more credible for the paper and for LinkedIn than claiming to predict the future.

**Data — free/public sources only for v1.**
Census, IRS county-to-county migration, BLS, BEA, FRED, Zillow Research, Apartment List. Reasons: zero cost; full reproducibility is itself a credibility strength (anyone can verify the work); free data covers most demand and supply drivers. Paid data (CoStar, Yardi, RealPage) is deferred unless the concept proves out.
*Known limitation to state in the paper:* no capital-markets data — cap rates, cap-rate spreads, transaction volume — because those live behind paid sources.

**Tech stack — Python + pandas for the model, Streamlit for the website.**
One language for both the analysis and the site (instead of learning three), free and low-friction deployment, and the gentlest path for a new coder. A React/JavaScript build would look marginally slicker but roughly triples the learning curve for no real gain at v1.

**Build tools — Claude Code for engineering; chat / Cowork for methodology and writing.**
Use each tool where it's strongest: Claude Code for the data pipeline, model, and site; conversation for designing the methodology and drafting the paper.

**Scope — start narrow, prove it, then widen.**
~Top 100 metros and a focused indicator set for v1. Cheap to learn on; easy to expand if it works, and cheap to have learned the lesson if it doesn't.

**Methodology — transparent weighted scoring model (not black-box ML) for v1.**
Interpretable and defensible: we can explain every market's score. Regression / ML can be layered in later once the baseline is validated.

**Normalization — normalize each indicator across metros before weighting.**
Raw indicators sit on wildly different scales, so weights only mean what they appear to mean after each indicator is converted to a cross-metro percentile or z-score.

**Migration (14%) ranked above job growth (12%).**
Migration is more of a *leading* indicator, less prone to the heavy revisions that affect BLS employment data, and captures cost-of-living, tax, and lifestyle drivers that job numbers miss.
*Important nuance:* this was decided on migration's **own merits**, NOT primarily on the AI-job-displacement thesis. Because the model is *relative* (every indicator normalized across metros), a national, across-the-board drop in hiring largely washes out in the cross-section; AI would only undermine job growth as a signal if it hit metros *unevenly* — and where it does, that unevenness is itself a signal we'd want to capture, not discard.

**Supply held at 25% for v1.**
Already weighted more heavily than amateurs typically would, and the recent Sunbelt oversupply cycle supports a high weight. Held (not raised) pending the backtest, because supply is mean-reverting — a strong negative near-term but potentially a positive on a 2–3 year horizon. The backtest may argue for raising it.

**Momentum kept low at 10%, as confirmation only.**
Trailing rent growth is double-edged: it mean-reverts over the 1–3 year window we care about, and it's partly already captured by the supply and affordability buckets (high momentum pulls in new supply and burns affordability runway).

---

## Parked for v2 (named extensions for the paper)

- **AI / automation exposure indicator** — score each metro by its occupational mix's exposure to AI displacement. Models the AI thesis *directly* (rather than proxying it through migration weights), and is a novel, timely paper angle.
- **Momentum × supply interaction** — high recent rent growth *combined with* a heavy incoming supply pipeline should score sharply negative (the classic setup for a market about to roll over).

---

## Open questions still to decide

*All v1 framework questions resolved as of 2026-06-28. The build spec (`v1-build-spec.md`) is the current working document. New questions that arise during the build go here.*
