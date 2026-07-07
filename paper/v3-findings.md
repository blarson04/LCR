# v3 Findings — Benchmark-Driven Build (Arbor–Chandan Review)

*Companion to `v3-build-spec.md` (the active plan) and `paper/v2-findings.md` (the v2
record). Each phase's results land here as they complete. Governance record:
`decision-log.md`.*

---

## Phase 3 — Tier-3 candidate gates: five candidates, zero adoptions (2026-07-07)

The Arbor–Chandan benchmark review surfaced six candidate signals (frozen in Phase 0,
before any accuracy work). C4 (ZORDI) was killed on history and C5 (insurance burden) on
acquisition in the Phase 2 coverage audit; the surviving five each got **one attempt** at
the standard three-part gate — standalone predictive τ > 0.10, max |corr| vs the eight
scored indicators < 0.70, and reliably positive value-add when augmenting the composite at
a fixed 10% weight (metro-cluster bootstrap CI excluding 0). The exact candidate
constructions were logged before the runs (decision-log, Phase 3 execution spec).

| Candidate | standalone 3y τ | max \|corr\| (vs) | value-add Δτ @10% | 95% CI | adopted? |
| --- | --- | --- | --- | --- | --- |
| C1 CREMI MF absorption | 0.085 | 0.115 (cost_to_own_vs_rent) | −0.027 | [−0.068, +0.015] | no |
| C2 CREMI MF NOI | 0.083 | 0.419 (trailing_rent_growth) | −0.021 | [−0.058, +0.011] | no |
| C3 CREMI MF asset price | 0.186 | 0.263 (trailing_rent_growth) | −0.011 | [−0.040, +0.016] | no |
| C6a Δ rental vacancy | 0.072 | 0.078 (rent_to_income) | −0.051 | [−0.097, −0.000] | no |
| C6b Δ unemployment (MSAUR)* | 0.218 | 0.177 (job_growth) | +0.012 | [−0.011, +0.038] | no |

\* auto-oriented: the *flipped* direction (rising unemployment → stronger forward rent
growth) is what carries the signal. Disclosed below.

**What each result means:**

- **C1 (absorption).** The direct demand-read hypothesis didn't survive: the CREMI
  multifamily absorption sub-index has essentially no standalone 3-yr signal on our
  universe (τ 0.085), and it is *not* redundant with anything we score (max |corr| 0.115)
  — it is simply weak at this horizon.
- **C2 (NOI) — the pre-registered "one to watch."** Failed on standalone signal (τ 0.083).
  Its strongest correlation, +0.42 with `trailing_rent_growth`, is precisely the
  NOI ≈ rents − expenses overlap the build spec flagged in advance. The first free
  expense-inclusive operating signal turns out to add no forward information the rent
  side didn't already carry.
- **C3 (asset price).** The one CREMI candidate with genuine standalone signal (τ 0.186),
  consistent with the P5 finding that appreciation tracks trailing rents — and for the
  same reason, it adds nothing reliable on top of the composite (Δτ −0.011, CI spanning
  zero). Signal, but not *new* signal.
- **C6a (Δ vacancy).** Weak standalone (τ 0.072) and the value-add CI sits essentially
  entirely below zero — augmenting with vacancy *changes* would actively hurt. (Vacancy
  *levels* were already gated out as P6 in v2.)
- **C6b (Δ unemployment).** The most interesting negative result. The pre-specified
  orientation (rising unemployment = worse) produced a *negative* standalone τ; under the
  gate's standard auto-orientation, the flipped signal — metros with **rising**
  unemployment in the scoring year going on to **stronger** 3-yr rent growth — is the
  strongest standalone candidate of the five (τ 0.218). That is a counter-cyclical
  mean-reversion pattern of the 2015–2024 sample (shock-year labor markets recovering
  into rent booms), not a mechanism we would bet a scored weight on, and the gate agreed:
  value-add +0.012 with a CI straddling zero. It stays a context observation.

**Consequence.** Zero adoptions (pre-registered expectation: 0–2). The model remains the
frozen 8-indicator v2.0.0 — no version bump, no regeneration, no site changes. Across two
gate cycles (P5–P7 in v2; C1–C3, C6a, C6b here), **eight candidates have now been tested
and none has reliably improved the composite** — the parsimonious spec is earned, not
asserted. The CREMI series (including cap rates and occupancy, noted in the Phase 2 audit
but outside the frozen list) remain available as context via `src/ingest/cremi.py`.

*Data vintage: panel through 2024 (QCEW 2024 gaps for Cleveland/Dayton as disclosed);
CREMI download of 2026-07-07 (1995–2026Q1, 108/110 metros, division mapping disclosed in
`data/candidate_coverage.md`). Gate mechanics and thresholds identical to v2
(`src/tier2_gate.py`); runner `src/tier3_gates.py`; raw output
`data/processed/tier3_gates.csv`.*
