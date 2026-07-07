# Multifamily Screener — V3 Build Spec

*Companion to `v3-plan.md` (the critique that scoped v3), `decision-log.md`, and
`v2-findings.md`. This document folds the Arbor–Chandan "Top Markets" Spring 2026 report
review into the v3 plan and turns the whole thing into a phased build process. Two inputs
drove it: (1) the v3 critique's Tier 1–3 roadmap, and (2) a benchmark review of how a
professional shop builds and presents the same kind of product. Thesis unchanged and
sharpened: **can free public data forecast the best rental markets without paying for
proprietary feeds?**

---

## 1. Benchmark review — what the Arbor–Chandan matrix is, and isn't

**What it is:** a cross-sectional *conditions index*. Fifty metros, ten equal-weighted
categories (~10% each; variables equal-weighted within category), scored on current-period
data, presented as "where opportunity is now."

**What it isn't:** a forecast. There is no target variable — "opportunity" is never defined
as anything measurable — therefore no backtest, no out-of-sample check, no uncertainty, no
track record, and no way for the ranking to ever be shown wrong. The strongest possible
contrast with this project, and the contrast *is* the portfolio story.

**Specific methodological gaps (do not import):**

- **Equal weighting.** Their methodology states all ten categories receive equal weight.
  Our P4 bootstrap showed naive equal weighting is the one scheme *reliably worse* than a
  thoughtful hand-set scheme. We tested the thing they assumed.
- **Undisclosed whipsaw.** Their own appendix (Table 3) shows six-month rank moves of
  San Jose +31, Boston −27, Phoenix +25, Denver +24, Milwaukee +18 — on a 50-metro
  universe — with no stability discussion anywhere. Our rank ranges and (planned)
  stability stats are ahead of professional practice.
- **Mixed vintages, silently.** ZORDI through Feb 2026 sits beside 2024 ACS demographics
  and Q2-2025 CREMI with no vintage discussion. Our vintage-honesty rule (every number
  states the data vintage it assumes) is a differentiator; their Table 2 "Source; Through
  [date]" column is, ironically, the right *format* for disclosing it — we adopt the
  format and actually reason about it.
- **Redundancy.** Population growth (10%) alongside five demographic variables and
  migration-adjacent measures; our correlation-gated de-duplication is stricter.
- **Target ambiguity.** Investor-facing inputs (cap rates, lending, taxes, insurance) are
  blended with renter-demand inputs into one undefined score. Our single defined target
  (3-yr forward rent growth) keeps the model falsifiable.

**The thesis-level finding (import loudly):** remove the one proprietary layer — Chandan's
lending-volume and cap-rate data, ~10% of their matrix — and roughly **90% of a
professional research product runs on the same free sources this project uses** (Atlanta
Fed, Census, BLS, Zillow, Tax Foundation, Lincoln Institute, FAU). Quote-ready support for
the free-data thesis, and the setup for the industry baseline in §3.

---

## 2. Equation improvements — the gated candidate list (all free)

Every candidate below goes through the standard pre-committed gate from v2 (standalone
predictive τ → redundancy vs existing indicators → reliably positive value-add at a fixed
weight, metro-cluster bootstrap CI), with the candidate list **frozen in Phase 0 before any
accuracy is computed**. Expectation set now: most will fail, as P5–P7 did. That is the gate
working, and each failure is a paper paragraph.

| # | Candidate | Source (free) | Cadence / lag | Prior | Rationale & concerns |
| --- | --- | --- | --- | --- | --- |
| C1 | **CREMI multifamily absorption sub-index** | Atlanta Fed CREMI | Quarterly, ~1–2q lag | **Medium-high** | Direct demand-vs-new-supply balance read; fresher than permits; complements rather than duplicates `permits_to_stock` (verify correlation). |
| C2 | **CREMI multifamily NOI growth sub-index** | Atlanta Fed CREMI | Quarterly, ~1–2q lag | **Medium-high** | First free *expense-inclusive* operating signal — the only candidate that can see the FL/CA insurance-and-tax shock the model is currently blind to. Watch redundancy with `trailing_rent_growth` (NOI ≈ rents − expenses). |
| C3 | CREMI asset-price growth sub-index | Atlanta Fed CREMI | Quarterly | Low | P5 showed appreciation tracks trailing rent growth (r ≈ 0.78); likely redundant. Test cheaply since it arrives with C1/C2. |
| C4 | **ZORDI** (Zillow Observed Renter Demand Index) | Zillow Research | Monthly, ~1mo lag | Medium (nowcast layer only) | Renter search activity = fastest free demand signal. History is short (verify at download; likely too short for the annual walk-forward) → route to the **v2.1 nowcast layer** as a live-demand input beside CES, not into the annual model. |
| C5 | Insurance burden (premiums as share of home value; insured share; 10-yr change) | ACS / IPUMS | Annual, ~1y lag | Low for the score; **high for context** | Solves the "expense side of the ledger is invisible" open question. Mechanism for *rent growth* is ambiguous (cost shocks can cut supply → rents up, or push out-migration → rents down); mechanism for investor NOI is clear. Default: context layer with the FL worked example; score entry only if it passes the gate. |
| C6 | Delta family: 1-yr *change* in vacancy and unemployment | ACS / BLS (already in panel or adjacent) | Annual | Low | Their matrix uses direction-of-change variables; ours is all levels/flows. Cheap to test from existing data. |

**Explicitly not pursued for the score:** property-tax and state-tax indices (weak causal
path to *rent growth*; taxes hit NOI and are largely capitalized; migration already
captures the people-follow-low-taxes channel — keep as context columns at most); WWJ
rental affordability index (it is `rent_to_income` under another name — note it in the
paper as convergent validation, don't add it); renter-under-35 share (context).

**Coverage kill-rule (pre-committed):** any candidate covering fewer than ~100 of the 110
metros after CBSA mapping is rejected on coverage *before* any accuracy is computed, to
keep the universe frozen and comparisons clean.

---

## 3. The industry baseline (highest-value new analysis)

Build a **free-Arbor-style conditions index** on our 110-metro universe: their category
structure and equal weights, populated with the free components only (CREMI ×3, labor ×4,
population growth, ACS demographics, vacancy, WWJ-equivalent affordability, ZORDI where
history allows, ACS insurance), with the proprietary capital-markets block omitted and
disclosed. Then run it through the **standard walk-forward evaluation against 3-yr forward
rent growth** and add it as a row in the P1 baseline table with a bootstrap CI on the gap.

Why this is worth a phase of its own: it converts the project's implicit claim into an
explicit test — *does a validated, deliberately-weighted, parsimonious screen beat
industry-style practice at the actual prediction task?* Every practitioner reader
instinctively trusts this baseline. Beat it and the thesis has teeth; tie it and the
honest finding is "professional conditions indices are re-packaged momentum" (check its
correlation with `trailing_rent_growth` — prediction: high). Either outcome publishes.

Constraints: the replication is approximate (short ZORDI history, omitted paid block) —
document every deviation in the spec *before* running; never tune the replica to lose.

---

## 4. Presentation adoptions (site) — form, not claims

What the Arbor report does better than our site, mapped to concrete adoptions:

1. **Key Findings block** — three plain-language bullets at the top of the landing page
   (feeds the existing "60-second layer" item). Theirs is the first page; ours is buried.
2. **Primary / Secondary Strength columns** in the Top-10 table — derive directly from the
   two largest bucket contributions per metro ("Tight supply", "Strong migration & jobs").
   We already compute these; we just don't surface them as columns.
3. **Change-vs-prior-edition column** — theirs compares Spring vs Fall rankings; our
   frozen registry makes the same column *more* credible (the prior edition provably
   wasn't rewritten). Show alongside rank ranges so six-month noise isn't read as signal —
   the caveat they omit.
4. **Market Spotlight page** for the #1 metro — narrative + a metro-vs-national YoY rent
   growth chart (we have ZORI; the "outperformed the national average for N consecutive
   months" framing is compelling and computable).
5. **Methodology appendix table with a vintage column** — variable, weight, source,
   "through [date]". This *is* the per-measure provenance tagging the provisional edition
   needs (live / proxy / carried-forward + as-of date). One table satisfies both the
   transparency goal and the vintage-honesty rule.
6. **Composite-score diverging bar chart** (score vs universe average = 0). At 110 metros,
   render top 25 / bottom 25 with an expander for all.
7. **Plain-vocabulary discipline** — their prose never uses a statistic it doesn't explain.
   Ours occasionally leads with "weighted Kendall's τ." Adopt the rule: plain sentence
   first, statistic in parentheses, everywhere a lay reader lands.

**Do not import:** unexplained rank swings, vintage silence, absence of uncertainty, the
undefined target. The validation tables, rank ranges, honest-limits list, and frozen
registry are the moat — every adoption above is presentation-layer only and must not
dilute a single caveat.

---

## 5. Build process — phases, gates, deliverables

**Phase 0 — Pre-registration (one evening; do before anything else).**
Dated decision-log entries that freeze: (a) the C1–C6 candidate list, gate definition, and
coverage kill-rule verbatim; (b) the CES nowcast re-run gate, re-committed word-for-word
from v2.1 (≥85% pooled 3-yr τ retention AND ≥7/10 mean top-10 overlap), one attempt, both
outcomes published; (c) the industry-baseline replication spec (§3) including every known
deviation. Deliverable: decision-log entries. *Nothing downstream starts until this is
logged — this is the lesson of the v2.1 gate wobble.*

**Phase 1 — Real-time validity (carried unchanged from v3-plan Tier 1; highest priority).**
P1.1 Pull CES metro employment + wages via FRED SAE series; rebuild nowcast M2/M3; run the
re-committed gate once. P1.2 Vintage-honest reporting: every surface showing finalized-data
τ (0.444) co-reports the real-time pseudo-nowcast figure (0.332) with vintage labels; add
the elapsed-window clause to the 2023 ranking. P1.3 Temporal uncertainty: per-window ranges
promoted to the primary uncertainty statement; jackknife-over-windows; region-cluster
bootstrap sensitivity. Deliverables: gate verdict entry, updated site copy, updated
findings doc. *P1.1's outcome decides the provisional edition's fate and half the
publication narrative — start here.*

**Phase 2 — Data acquisition & coverage audit (no accuracy computed).**
Download CREMI (all three MF sub-indices), ZORDI, ACS insurance measures; map each to the
CBSA universe; produce a coverage-and-history table (metros covered, first usable year,
lag). Apply the coverage kill-rule. Deliverable: `data/candidate_coverage.md` + raw caches.
*Kept strictly separate from Phase 3 so coverage decisions can't be contaminated by
peeking at predictive power.*

**Phase 3 — Candidate gates.**
Run the standard three-part gate on each surviving candidate (C4 evaluated in the nowcast
layer, not the annual model). Log adopt / context / reject per candidate with CIs.
Deliverables: `tier3_gates.csv`, decision-log entries, findings-doc section. Expected
result: 0–2 adoptions; C2 (NOI growth) is the one to watch.

**Phase 4 — Industry baseline backtest.**
Build the §3 replica; walk-forward vs 3-yr forward rent growth; add to the P1 baseline
table with bootstrap CI on the gap vs the composite; compute its correlation with
`trailing_rent_growth`. Deliverables: baseline row + one paper subsection ("versus
industry practice"). Depends on Phase 2 data; independent of Phase 3 verdicts.

**Phase 5 — Value-claim analyses (carried from v3-plan Tier 2).**
P5.1 Momentum orthogonality (per-window model-vs-momentum in τ *and* pp; partial rank
correlation controlling trailing rent growth; 50/50 blend baseline). P5.2 Economic effect
size: top-10 mean 3-yr forward rent growth vs universe median, in percentage points, per
window, for the model and every baseline — adopt as a headline metric next to
precision@10. P5.3 Ex-ante regime flag: define from scoring-date-available data, backtest
2015–2025, publish rule + false-positive rate; the site flag switches to current-conditions
evaluation. Deliverables: findings-doc sections; the pp table feeds Phase 6's Key Findings.

**Phase 6 — Product rebuild.**
The §4 adoptions (Key Findings block, strength columns, change-vs-edition column,
spotlight, methodology/vintage table, diverging bars, plain-vocabulary pass) merged with
the carried v3-plan Tier-3 fixes: edition renames ("Validated" / "Provisional —
experimental") sitewide including the sidebar toggle; gate-failure numbers inline on the
provisional banner (75% retention; 6.1/10 mean top-10 overlap; 3/10 in 2023); metro-detail
history chart truncated or dash-marked at the edition vintage; rank-stability explanation;
baselines and uncertainty added to Track Record; frozen-ledger scoring dates
pre-announced; custom domain + final name across site/repo/paper. Deliverable: shipped
site update. *Uses the design-system skill file; every new chart follows the existing
tokens.*

**Phase 7 — Publication.**
Paper updates: vintage-honest headline (real-time first), industry-baseline subsection,
pp effect sizes, gate outcomes from Phases 1 and 3 (positive or negative), the ~90%-free
observation from §1 in the introduction. Then the LinkedIn piece. Repo hardening (pinned
env, one-command reproduce, CI smoke test, data-license audit — add Atlanta Fed and
Zillow ZORDI terms to the audit) lands before the link goes public.

**Dependency sketch:** Phase 0 → everything. Phase 1 independent of 2–4 (start
immediately). Phase 2 → 3 and 4. Phase 5 independent (start anytime after Phase 0).
Phase 6 consumes 1, 3, 4, 5. Phase 7 last. Rough effort: Phase 0 an evening; Phase 1 the
big analytical lift; Phases 2–4 a focused week combined; Phase 5 a few sessions; Phase 6
the big product lift; Phase 7 short once inputs exist.

---

## 6. Guardrails (updated for v3)

- **No equal weights, no free-fitting** — P4 stands; the Arbor replica uses equal weights
  *only* as a baseline to beat, never as a scheme to adopt.
- **No target drift.** The target remains 3-yr forward rent growth. Investor-conditions
  material (taxes, insurance, capital markets) lives in the context layer unless it passes
  the gate into the score.
- **No gate-shopping.** Candidate list, gate wording, and attempt counts frozen in
  Phase 0; amendments only by dated log entry written *before* the affected run.
- **Vintage rule.** Every published accuracy number and every displayed measure states its
  data vintage; the methodology table's "through [date]" column is mandatory, not
  decorative.
- **Presentation borrows form, never claims.** Nothing adopted from the benchmark may
  remove a caveat, an uncertainty range, or a limitation from any surface.
- **Negative results publish.** Phase 1 and Phase 3 outcomes are written up whichever way
  they land.
