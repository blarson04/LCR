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

### 2026-07-07 — v3 build-spec Phase 4 OUTCOME: composite reliably beats the industry-style index — and our "re-packaged momentum" prediction was WRONG

One run, per the spec below; first results are final. **The free-Arbor replica scores pooled 3-yr τ 0.113 / precision@10 0.28 against the composite's 0.444 / 0.65 (same run, same years, same metros). Gap +0.331, 95% CI [+0.202, +0.483] — a reliable edge, the largest over any baseline we have tested.** In the baseline table the industry-style index lands *below persistence* (0.216) and above only random: worse than every naive alternative including plain rent momentum (0.391).

**Our Phase 0 prediction FAILED, and we publish that:** the replica's correlation with `trailing_rent_growth` is only +0.213 pooled (+0.230 mean per-year rank corr) — professional-style conditions indices are **not** re-packaged momentum. The honest diagnosis is less flattering: the extra conditions components (unemployment levels, demographics, vacancy, absorption) *dilute* the predictive signal rather than repackage it. Note what this does and does not indict — equal weighting per se is not the failure (equal weight over OUR eight validated indicators scores 0.368); the failure is the component set chosen for investor-conditions storytelling rather than tested against a prediction target. Housekeeping done with this phase (not gated): the naive-baseline rows in `baseline_comparison.csv` were regenerated on the current panel so the published table is a single data vintage, and the equal-weight row's stale label ("10 ind.") was corrected to the v2 reality ("8 ind.").

**Fairness caveats, stated with the claim wherever it is published:** the replica covers 6 of Arbor's 10 categories (capital markets, taxes, ZORDI, insurance omitted per spec) on our 110-metro universe (theirs: top 50); their matrix targets "opportunistic multifamily investment" broadly and never claims to predict 3-yr rent growth — this result scores industry *practice* (equal-weight conditions indices) at OUR task, not Arbor's product at theirs. Vintage: CREMI download 2026-07-07 (1995–2026Q1), ACS through 2024, current panel.

Artifacts: `src/industry_baseline.py` (runner), `data/processed/industry_baseline.csv` (detail incl. gap CI + momentum corr), row "Industry-style index (equal weight)" added to `baseline_comparison.csv` (surfaces on the Track record page), findings section in `paper/v3-findings.md`. Paper-brief integration lands with Phase 7 ("versus industry practice" subsection).

### 2026-07-07 — v3 build-spec Phase 4 EXECUTION SPEC: industry-baseline replica (logged BEFORE any accuracy runs)

Fixes the free-Arbor replica's exact construction per the Phase 0 freeze ("the replica will not be tuned in either direction after first results"). The Arbor-Chandan Opportunity Matrix (Spring 2026, methodology p.20/22): 10 equal-weighted categories, variables equal-weighted within each, largest-50-metro universe. Our replica runs their scheme on our 110-metro universe with free components only.

**Category mapping, fixed a priori (6 of 10 included, 12 variables):**
1. *Capital Markets* — **OMITTED** (proprietary lending data; the frozen Phase 0 deviation). The Phase 2 question of a CREMI cap-rate stand-in is **declined**: Phase 0 froze the omission, and adding a block now — with post-hoc freedom over its direction and composition — is the tuning the rule prohibits. Cap rates stay context.
2. *Performance Fundamentals* — CREMI MF `NOI.Index`, `Asset.Value`, `Absorption.Units` (the Phase 3 annual frames; higher = better).
3. *Tax Conditions* — **OMITTED**: not in the frozen §3 component list (free in principle, but state-resolution and never acquired; adding it now would be a post-Phase-0 spec change).
4. *Labor Market* ×4 — `job_growth` (QCEW, higher better); `income_growth` as the wage-growth stand-in (BEA, disclosed proxy; higher better); unemployment level = CREMI `MSAUR` annual value (lower better; disclosed: MSAUR is CREMI's within-metro standardized series, not the raw rate); 1-yr Δ `MSAUR` (lower better — Arbor's a-priori direction, NOT the flipped orientation the C6b gate found predictive).
5. *Population Growth* — YoY growth of ACS population (consecutive-year guard; no 2020/2021 values; higher better).
6. *Demographics* ×2 — ACS renter median household income (`B25119_003E`) and renter under-35 householder share (`B25007`), both higher better (Arbor: spending power + young age profile). Acquired 2026-07-07: 107–110/110 per year, `census.build_renter_demographics_panel()`.
7. *Rental Vacancy* — panel `rental_vacancy` level (lower better).
8. *Renter Demand (ZORDI)* — **EXCLUDED**, exactly as Phase 0 anticipated (history starts 2020-06; cannot cover the walk-forward scoring years).
9. *Affordability* — `rent_to_income` (the WWJ-equivalent per build-spec §2; lower better).
10. *Climate Risk / Insurance* — **OMITTED** (Phase 2: not freely acquirable; C5 rejection carries over).

**Construction:** each variable within-year z-scored across the universe with its orientation applied a priori as listed; **no auto-orientation anywhere in the replica** (orientation-fitting would tune it); variable-level neutral fill 0 where missing (Cleveland/Dayton CREMI, ACS gaps, 2021 pop growth); category score = mean of its variables; composite = mean of the six category scores (equal weights among included categories — rank-equivalent to leaving all ten at 10%).

**Evaluation protocol:** standard walk-forward (`backtest.evaluate_predictions`) on the same usable prediction years and metros as the model; pooled 3-yr weighted τ + precision@10 (1-yr as foil); metro-cluster bootstrap (B=800, seed 42) CI on the gap = composite τ − replica τ; correlation of the replica score with normalized `trailing_rent_growth` (pooled + mean per-year rank corr). The Phase 0 prediction stands as logged: that correlation will be high ("industry conditions indices are re-packaged momentum"). Deliverables: `industry_baseline.csv`, a plain-language row in the baseline table / Track record ("Industry-style index (equal weight)"), findings-doc section. First results are final; both outcomes publish.

### 2026-07-07 — v3 build-spec Phase 3 OUTCOME: all five candidates FAIL the gate → 0 adoptions, model stays frozen v2.0.0

The one-shot runs (execution spec immediately below) are complete; output `data/processed/tier3_gates.csv`; full write-up `paper/v3-findings.md`. **No candidate passed all three prongs — the model remains the frozen 8-indicator v2.0.0, no version bump, no regeneration.** This is within the pre-registered expectation ("0–2 adoptions; most will fail, as P5–P7 did").

| Candidate | standalone 3y τ (>0.10) | max \|corr\| (<0.70) | value-add Δτ @10% | 95% CI (excl. 0) | verdict |
| --- | --- | --- | --- | --- | --- |
| C1 CREMI MF absorption | 0.085 ✗ | 0.115 ✓ | −0.027 | [−0.068, +0.015] ✗ | reject → context |
| C2 CREMI MF NOI | 0.083 ✗ | 0.419 ✓ | −0.021 | [−0.058, +0.011] ✗ | reject → context |
| C3 CREMI MF asset price | 0.186 ✓ | 0.263 ✓ | −0.011 | [−0.040, +0.016] ✗ | reject → context |
| C6a Δ rental vacancy | 0.072 ✗ | 0.078 ✓ | −0.051 | [−0.097, −0.000] ✗ | reject |
| C6b Δ unemployment (MSAUR) | 0.218 ✓ (flipped) | 0.177 ✓ | +0.012 | [−0.011, +0.038] ✗ | reject → context |

Notes, all disclosed: (1) **C2 (NOI), the pre-registered "one to watch," failed on standalone signal** (τ 0.083); its top correlation (+0.42 with `trailing_rent_growth`) is exactly the NOI ≈ rents − expenses redundancy the spec flagged as the concern. (2) **C3 has real standalone signal (τ 0.186) but adds nothing** the composite doesn't already have — consistent with the P5 finding that appreciation tracks trailing rents. (3) **C6b was auto-orient FLIPPED**: *rising* unemployment in the scoring year predicted stronger 3-yr forward rent growth (τ 0.218) — a counter-cyclical mean-reversion artifact of the 2015–2024 sample (shock-year recoveries), the strongest standalone candidate of the five, yet still no reliable value-add. (4) C6a's value-add CI sits essentially entirely below zero — adding Δ-vacancy would *hurt*. Consequence: CREMI series remain available as context (via `src/ingest/cremi.py`); any site surfacing is a Phase 6 presentation decision. The recurring result now spans eight gated candidates over two cycles: **no new free signal has reliably improved the frozen composite** — the parsimony is earned, and the gate keeps doing its job. Negative result publishes (this entry + findings doc; paper-brief integration lands with Phase 7).

### 2026-07-07 — v3 build-spec Phase 3 EXECUTION SPEC (logged BEFORE the one-shot gate runs)

Fixes the exact candidate constructions before any accuracy is computed, per the no-gate-shopping guardrail. Gate mechanics are the frozen v2 gate verbatim (within-year z across the panel universe; standalone pooled 3-yr τ > 0.10 AND max |corr| vs the 8 scored indicators < 0.70 AND value-add at fixed 10% augmentation weight with metro-cluster bootstrap CI (B=800, seed 42) excluding 0; one attempt per candidate; both outcomes published). Code: `tier2_gate.gate()` extended with an external-`frame` path (CREMI sources are not panel columns); the extension was regression-verified to reproduce the spent P6 gate's path exactly on today's panel before this entry (equipment check, not a gate re-run — the P6 verdict stands).

**Candidate frames (one attempt each, output `tier3_gates.csv`):**
- **C1** = CREMI Multifamily `Absorption.Units` annual (calendar-mean of quarterly) sub-index value, as published. Prior orientation: higher = better.
- **C2** = CREMI Multifamily `NOI.Index` annual sub-index value, as published. Higher = better. (CREMI publishes these as standardized sub-index values, so the published level IS the growth signal; no additional differencing.)
- **C3** = CREMI Multifamily `Asset.Value` annual sub-index value, as published. Higher = better.
- **C6a** = 1-yr delta of panel `rental_vacancy` (ACS). Deltas only across consecutive years — the 2020 ACS gap means no 2020 or 2021 delta (a naive diff would silently produce a 2-yr delta; guarded). Rising = worse.
- **C6b** = 1-yr delta of CREMI `MSAUR` annual value, same consecutive-year guard. Rising = worse.

`auto_orient` stays enabled exactly as in the v2 gate (any flip is disclosed in the output). CREMI's two missing metros (Cleveland, Dayton) take the standard neutral fill (candidate z = 0) in the value-add leg. Nothing in this entry was informed by any predictive computation on any candidate.

### 2026-07-07 — v3 build-spec Phase 2 complete: candidate coverage audit (no accuracy computed)

Acquisition + coverage only, per the Phase 0 separation. Results (full table: `data/candidate_coverage.md`): **C1/C2/C3** (CREMI multifamily absorption, NOI, asset price) — 108/110 coverage, 1995–2026Q1 → proceed to Phase 3 gates. **C6a** (Δ vacancy, from panel, 110/110) and **C6b** (Δ unemployment via CREMI MSAUR, 108/110) → proceed. **C4 ZORDI** — 110/110 but history starts 2020-06 → killed for the annual model exactly as pre-registered (live-layer candidate only). **C5 insurance burden** — rejected on acquisition: no ACS summary table exists (IPUMS microdata requires a registered extract, failing free reproducibility); the expense channel is partially covered by C2. Also observed and logged, NOT candidates (list closed): CREMI carries metro `Market.Cap.Rate` and `Occupancy.Rate` — free metro cap rates soften a stated limitation; candidacy would need a new dated entry. Phase 3 (five gates, one attempt each) and Phase 4 (industry baseline) may now run.

### 2026-07-07 — v3 build-spec Phase 0: pre-registration of the Tier-3 candidate gates and the industry baseline

`v3-build-spec.md` (committed 03eddef) folds the Arbor–Chandan benchmark review into a phased build. **Reconciliation first, because the spec was drafted before this week's execution:** its Phase 1 is complete and partially superseded — P1.1's CES re-run was executed 2026-07-06 (**FAIL, 84.66%**, edition pulled) and the staleness problem was subsequently solved by the **lagged-vintage gate (PASS, 95.52%)**; the CES gate is spent and **must not be re-run**. P1.2/P1.3 (vintage-honest reporting, temporal uncertainty) and all of Phase 5 (momentum orthogonality, pp effect sizes, ex-ante regime flag) shipped this week. Phase 6's carried Tier-3 items are largely done or superseded by the vintage edition; the §4 presentation adoptions and Phase 7 remain.

**Frozen NOW, before any coverage or accuracy work (this entry is the Phase 0 deliverable):**

1. **Candidate list, verbatim from spec §2, closed:** C1 CREMI multifamily absorption sub-index; C2 CREMI multifamily NOI-growth sub-index; C3 CREMI asset-price sub-index; C4 ZORDI (evaluated in a future nowcast/live layer only, never the annual model); C5 ACS/IPUMS insurance burden (default: context layer; score entry only via gate); C6 one-year deltas of vacancy and unemployment. No additions without a new dated entry.
2. **Gate, verbatim from v2:** standalone predictive τ → redundancy vs existing indicators → value-add at a fixed 10% augmentation weight with metro-cluster bootstrap CI; adopt only if standalone τ > 0.10 AND max |corr| < 0.70 AND value-add CI excludes 0. One attempt per candidate. Expected outcome: most fail, as P5–P7 did.
3. **Coverage kill-rule:** any candidate covering fewer than **100 of the 110 metros** after CBSA mapping is rejected on coverage before any accuracy is computed. Phase 2 (acquisition + coverage audit) is strictly separated from Phase 3 (gates) so coverage decisions cannot be contaminated by predictive peeking.
4. **Industry-baseline replication spec (§3):** an Arbor-style equal-weighted conditions index on our 110-metro universe, free components only, run through the standard walk-forward vs 3-yr forward rent growth and added to the baseline table with a bootstrap CI on the gap vs the composite, plus its correlation with `trailing_rent_growth` (prediction, logged now: high). **Known deviations, disclosed in advance:** the proprietary capital-markets block (~10%) is omitted; ZORDI history is likely too short for annual walk-forward windows and may be excluded; category mapping onto our universe is approximate; equal weights are used because that is the practice under test — never as a scheme to adopt. The replica will not be tuned in either direction after first results.

### 2026-07-07 — Horizon-extension publication decision (disclosed priors; not a blind gate)

**Question (author):** how far ahead can we publish before reliability fails? **Study:** `src/horizon_decay.py` (output `data/processed/horizon_decay.csv`) evaluates the composite, the 2024-vintage configuration, and momentum at horizons 1–6.

**Findings:** the composite strengthens with horizon while momentum decays — pooled τ at h=3/4/5 is 0.444/0.479/0.507 with the top-10 pp edge rising +6.0→+8.4→+10.7, and the edge over momentum widening every year out (the original "fundamentals express over time" hypothesis, finally confirmed). The 2024-vintage config at h=4: τ 0.449 (93.7% of finalized-h4), +7.2 pp, worst window −1.1 pp, including a shock-start (2021) window.

**Why this is NOT called a gate:** the study itself produced the numbers; any "gate" written now would be theater. Instead this is a publication decision with criteria and priors fully disclosed: (a) h4 pooled τ ≥ h3's ✓; (b) beats momentum at h4 ✓ (0.449 vs 0.380); (c) vintage-config retention vs finalized-h4 ≥85% ✓ (93.7%); (d) no window worse than −2 pp ✓ (−1.1).

**Decision:** the 2024-vintage screen MAY additionally show a **2024→2028 extended-horizon view**, always labeled as such, with the decay-study numbers linked; the 3-year screen remains the primary claim. **h≥5 is NOT publishable**: every available window starts pre-COVID (2016–19), so shock-start behavior cannot be assessed — the strong h5/h6 numbers are partly sample selection, and we say so.

### 2026-07-07 — v3.1 gate OUTCOME: **PASS** → the 2024-vintage screen is validated for publication

The one-shot run (spec immediately below) passed both prongs with margin: retention **95.52%** (0.424 vs 0.444 pooled 3-yr τ; gap 95% CI [−0.003, +0.035] — statistically near-indistinguishable from the finalized model) and mean top-10 overlap **8.29/10** (per-year 6–10). Consequence executed: the **2024-vintage screen (a 2024→2027 call, vintage-labeled)** becomes the validated current screen — built, frozen to the registry, and published on the site as the primary cross-section, with the 2023 fully-finalized screen retained for the track record. The provisional-nowcast pull of 2026-07-06 is unaffected (`NOWCAST_PUBLISHED` stays false; that was a different, current-year-proxy configuration).

The three-gate arc is now complete and public: **74.8% (fail) → 84.66% (fail by 0.34, pulled) → 95.52% (pass)** — each attempt pre-registered, each outcome published, the design fixed between attempts by diagnosis rather than threshold-shopping.

### 2026-07-07 — v3.1 "lagged-vintage screen" specification (logged BEFORE its one-shot gate run)

**Motivation (author):** a 2023→2026 screen is ~80% elapsed — no business can act on it. Rather than re-iterating current-year proxies, we move the *vintage*: ACS 2024 (Sep 2025) and BEA county income 2024 (Nov 2025) are now published, so a **2024-vintage screen (a 2024→2027 call, roughly half remaining)** can be built almost entirely on finalized data. Ingest windows extended accordingly (ACS1 + BEA through 2024; panel rebuilt — 2024 row: population/stock/income 110/110, QCEW jobs/pay/HHI 108/110, rents/permits complete).

**Specification (proxy scheme v0.3 — exactly one substitution):** score year T with all finalized inputs; `net_migration` = Census PEP net domestic migration for T (the M1-validated proxy, level r≈0.99 / rank ≈0.90) over ACS population T. The two metros with a QCEW-2024 transition gap (Cleveland, Dayton) carry jobs/pay/diversity from 2023 (disclosed fallback). Nothing else changes; the frozen v2 model is untouched. Cadence going forward: refresh each year when the T-vintage federal data lands (~Nov T+1).

**Full disclosure of priors (anti-gate-shopping):** the attempt-1 decomposition (published 2026-07-02, before this design) already showed the "only migration proxied" configuration retains ~95% of pooled 3-yr τ. This spec is *informed by that diagnosis* — that is what decompositions are for — and the gate is run regardless, fresh, with both prongs.

**Gate (identical thresholds, one attempt, both outcomes published):** historical pseudo-test substituting PEP-for-IRS in every usable scoring year must retain **≥ 85%** of the finalized model's pooled 3-yr weighted τ **AND** average top-10 overlap **≥ 7/10**. Pass → the 2024-vintage screen is published as a **validated current screen** (vintage-labeled, registry-frozen). Fail → negative result #3, nothing ships.

### 2026-07-06 — v3-P1 gate OUTCOME: FAIL by a hair → provisional edition PULLED (negative result #2)

The pre-committed one-shot re-run (spec: proxy_map v0.2, CES employment; entry immediately below) was executed once. Result: pseudo-nowcast pooled 3-yr τ **0.376** vs finalized **0.444** → retention **84.66%** (gate: ≥ 85%); mean top-10 overlap **6.7/10** (gate: ≥ 7). Gap +0.068, 95% CI [+0.013, +0.120]. **Both prongs missed — narrowly — and the gate is binding: FAIL.**

Consequence executed as pre-committed: the provisional edition is **pulled from the site** (`config.NOWCAST_PUBLISHED = False`; the sidebar edition toggle and the Validated-vs-provisional page disappear; the About page explains the pulled experiment honestly). No further proxy iterations may run without a new pre-registered specification. We explicitly decline to round 84.66% to 85% or to relitigate the threshold post hoc — a gate that bends at the margin is decoration, and the near-miss is precisely where the discipline has value.

What the attempt established (published, not wasted): the CES employment proxy works (agreement 0.90–0.96 vs QCEW) and moved retention from **74.8% → 84.7%** and overlap from **6.1 → 6.7** — the diagnosis was right, the fix was real, and the remaining gap now sits in the carried-forward income growth (the AHE wage proxy was rejected on QA) and residual PEP noise. Any future attempt requires: a new dated spec entry (e.g., a QA-validated income proxy), the same gate verbatim, one attempt.

### 2026-07-06 — v3-P1 CES proxy specification (logged BEFORE the one-shot gate run)

Data QA (`src/nowcast/ces_qa.py`, outputs in `data/processed/nowcast/ces_qa_*.csv`) is complete; per the pre-commitment, the exact proxy specification is recorded here **before** M3 runs, and M3 runs **once**.

**QA findings (coverage + agreement only; no gate metrics were computed):**
- CES metro total-nonfarm employment via FRED: **110/110** metros mapped (name-based legacy series ids, discovered by search and saved in `ces_qa_coverage.csv`); 103/110 current into 2026. Annual-average growth rank-agrees with the finalized QCEW growth the model uses at **Spearman 0.90–0.96 in every overlap year (2016–2023)** → **adopted** as the `job_growth` proxy.
- CES average hourly earnings (constructible SMU ids, 110/110 found): growth rank-agrees with finalized BEA income growth at only **0.0–0.26** (composition effects) → **REJECTED**; `income_growth` remains carried-forward. No other wage proxy will be tried for this gate attempt.

**Specification (proxy_map v0.2), changed from v0.1 in exactly one way:** `job_growth` = YoY growth of annual-average CES metro employment for the scoring year (carry-forward fallback for the few metros whose series is stale); every other indicator's treatment is unchanged (PEP migration; live rent/permits/home values; carried income, diversity, stock, population, income denominators). The pseudo-nowcast (M3) applies this identical scheme to historical years. Known limitation, disclosed: FRED serves current CES vintages, not true real-time unrevised prints — same caveat as PEP.

**Gate (verbatim from the 2026-07-06 pre-commitment, one attempt):** pseudo-nowcast retains **≥ 85%** of the finalized model's pooled 3-yr weighted τ **AND** mean top-10 overlap **≥ 7/10**. Pass → the provisional edition is promoted to a validated current screen. Fail → published negative result #2 and the provisional edition is **pulled**. Both outcomes will be published.

### 2026-07-06 — Gate-taxonomy amendment (acknowledged), edition renames, and the CES re-run pre-commitment

Prompted by the v3 outside critique (`v3-plan.md` §3), which correctly identified that surfacing the failed-gate nowcast as a labeled "experimental" tab was a **reinterpretation of the gate's consequence after seeing the result** — the original gate said "internal experiment," and the "disclosed-experimental ≠ validated publication" rationale was constructed post hoc. We acknowledge that as a governance wobble and formalize the fix:

1. **Amended publication taxonomy (from this date forward):** *validated* (passed its pre-committed gate) / *provisional-experimental* (failed or not-yet-gated, publishable only with the gate outcome and divergence numbers displayed inline) / *internal* (not published). This amendment legitimizes the current provisional edition **going forward**; it does not retroactively clean the original sequence, which stays in the log as-is.
2. **Gates now specify threshold AND consequence AND number of attempts.** Amendments only via dated entries written *before* the run they affect.
3. **Author decision (v3 §8):** the provisional 2025 edition **stays live while the CES fix is built** (option b), with the required amendments: per-year top-10 overlap numbers on the disclosure itself (mean 6.1/10; 3/10 in 2023), and the editions **renamed** — "Accurate" → **"Validated — finalized 2023"**, "Speculative" → **"Provisional — experimental 2025"** — because "accurate" overclaims a τ-0.44 model.
4. **CES re-run pre-commitment (binding):** the v3-P1 nowcast fix gets **one attempt** at the original gate, verbatim: pseudo-nowcast retains **≥ 85%** of the finalized model's pooled 3-yr weighted τ **AND** mean top-10 overlap **≥ 7/10**. Consequence: pass → the provisional edition becomes the validated current screen; fail → published negative result #2 and the provisional edition is **pulled** (no keep-with-banner second bite). No further proxy iterations without a new pre-registered spec. The exact CES proxy specification will be logged in a dated entry *before* M3 runs; data-quality QA of the proxy inputs (coverage, historical correlation vs QCEW/BEA) is permitted before that entry, but no accuracy evaluation against the gate metrics.

### 2026-07-02 — v2.1 nowcast surfaced as a clearly-labeled EXPERIMENTAL view

Follow-up to the M3 gate failure. The pre-committed gate governs whether the nowcast is published as a **validated** call — it failed, so it is NOT presented as validated. Author's decision: still surface the provisional 2025 ranking as an explicitly-labeled **experimental / speculative** tab, behind a prominent banner disclosing it fails the bar (~75% τ retention < 85%), is edged out by a momentum baseline pooled, and diverges from the finalized ranking in recent years. The **validated 2023 ranking remains the default** on every other tab. This is consistent with the gate (a transparently-disclosed experimental view is not the same as a validated publication) and preserves the pre-registration ethos. Accuracy for reference: 3-yr pooled τ 0.332 (finalized 0.444); normal-regime τ 0.480 / precision@10 0.78. Reconciliation against finalized data remains future work.

### 2026-07-02 — v2.1 nowcast M3: FAILED the pre-committed gate → internal experiment

The pseudo-nowcast backtest (rebuild history with the nowcast's proxies — PEP migration + carry-forward slow indicators + live rent/permits — and run the standard walk-forward) retains only **75%** of the finalized model's pooled 3-yr τ (0.332 vs 0.444; gap +0.112, 95% CI [+0.038, +0.182] — *reliably* below the ≥85% bar) and averages **6.1/10** top-10 overlap (below the ≥7/10 bar). Per the gate committed **before** M3 ran, **the nowcast does NOT publish** — v2.1 ships as an internal experiment with this documented negative result (a finding worth a paragraph in the paper).

**Diagnosis (decomposition confirms it):** pooled 3-yr τ by variant — finalized **0.444**; only-migration-proxied **0.423 (95%)**; pseudo-but-jobs+income-finalized **0.427 (96%)**; full pseudo **0.332 (75%)**. So the migration proxy costs almost nothing, and **carrying forward `job_growth` + `income_growth` accounts for essentially the entire failure**. The nowcast is *one input away*: fresh current-year employment/wage data (CES) would lift retention to ~96%, clearing the 85% gate. CES is deferred only because BLS metro employment needs a bot-blocked area-code crosswalk. **Future work:** source CES (e.g. via FRED's SAE series) and re-run M3 — the nowcast's viability hinges on fresh jobs data, not on migration.

**Consequence:** M5 (surfacing the provisional ranking on the site) is **gated OFF** — the provisional 2025 ranking stays an internal artifact, not a default view.

**Final v2.1 disposition (2026-07-02):** the nowcast is **left out of production** and finalized as a documented experiment. Rationale: it fails the pre-committed gate, and the only viable rescue (fresh CES employment/wages) is a *noisier* proxy than the finalized jobs data that produced the 96% ceiling, so it might not clear 85% even if built — forcing a marginal pass with noisier data would cut against the project's rigor-over-reach principle. The CES-via-FRED path is confirmed feasible (FRED's SAE metro series are reachable with our key) and is the **prioritized future step** if v2.1 is revisited; the migration linchpin already works, so the nowcast is one accessible input away from viable. M4 (registry provisional freeze) not built — nothing published to pre-register.

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
