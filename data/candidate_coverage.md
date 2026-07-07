# Phase 2 — Candidate coverage & history audit (v3 build spec)

*Deliverable of build-spec Phase 2 (2026-07-07). Acquisition and coverage ONLY — no
predictive accuracy was computed for any candidate (pre-committed separation from Phase 3).
Kill-rule: <100/110 metro coverage rejects a candidate before any accuracy work.*

| # | Candidate | Source | Universe coverage | Usable history | Cadence / lag | Phase-2 verdict |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Multifamily absorption (`Absorption.Units`) | Atlanta Fed CREMI | **108/110** | 1995–2026Q1 | quarterly, ~1–2q | **Proceed to Phase 3** |
| C2 | Multifamily NOI growth (`NOI.Index`) | Atlanta Fed CREMI | **108/110** | 1995–2026Q1 | quarterly, ~1–2q | **Proceed to Phase 3** |
| C3 | Multifamily asset price (`Asset.Value`) | Atlanta Fed CREMI | **108/110** | 1995–2026Q1 | quarterly, ~1–2q | **Proceed to Phase 3** |
| C4 | ZORDI renter-demand index | Zillow Research | 110/110 | **2020-06 → 2026-05 only** | monthly, ~1mo | **Killed for the annual model** (history far too short for 3-yr walk-forward windows, exactly as pre-registered); retained as a candidate for a future live/nowcast layer |
| C5 | Insurance burden | ACS / IPUMS | — | — | — | **Rejected on acquisition**: ACS summary data has no homeowner-premium table (all ACS "insurance" variables are industry-of-employment); the IPUMS microdata route requires a registered extract, failing the free-reproducibility standard. The expense channel is partially covered by C2 (NOI is expense-inclusive). Context paragraph in the paper stands. |
| C6a | 1-yr Δ rental vacancy | ACS (already in panel) | 110/110 | 2015–2024 (no 2020 ACS) | annual, ~1y | **Proceed to Phase 3** |
| C6b | 1-yr Δ unemployment (`MSAUR`) | Atlanta Fed CREMI | **108/110** | 1995–2026Q1 | quarterly | **Proceed to Phase 3** |

**Mapping notes (disclosed):** CREMI files four large metros as metropolitan divisions; the
principal division maps to its parent CBSA (LA 31084→31080, Miami 33124→33100, NY 35614→35620,
SF 41884→41860). Cleveland OH and Dayton OH are absent from CREMI multifamily entirely (the
two gaps in 108/110); they take the standard neutral-fill treatment at scoring time if any
CREMI candidate is adopted.

**Observed but NOT candidates (frozen list is closed):** the CREMI multifamily file also
carries `Market.Cap.Rate` and `Occupancy.Rate` — notable because metro-level cap rates were
previously believed paid-only (this softens a stated project limitation). Any candidacy for
these requires a new dated decision-log entry before any accuracy is computed.

**Caches:** `data/raw/cremi/` (results file ~165 MB, gitignored; re-download via
`src/ingest/cremi.py` with a browser User-Agent — the site soft-blocks bots) and
`data/raw/zillow/Metro_zordi_month.csv`. Ingest: `src/ingest/cremi.py` →
`build_mf_annual()` (annual means of quarterly, mapped to our CBSA codes).

**Phase 4 readiness:** the industry-baseline replica's free components are now acquirable
(CREMI ×3, labor from QCEW/CES, ACS demographics + vacancy, rent-to-income equivalent,
ZORDI where history allows); the proprietary capital-markets block remains omitted-and-
disclosed, though CREMI's cap-rate series may partially stand in — a spec decision to log
before Phase 4 runs.
