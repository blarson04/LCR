# Multifamily Screener — V2 Plan & V1 Critique

*Companion to `decision-log.md` (the why), `v1-build-spec.md` (the v1 how), and the v1 results brief.
This document critiques v1 honestly and lays out a prioritized plan to improve it. The guiding
principle: v1's strength is transparency and honesty; v2 should make it **more rigorous and more
honest**, not more opaque. Measure before building.*

---

## 1. Honest assessment of v1

### What is solid
- **Transparent, reproducible, free-data** pipeline — the core differentiator versus paid tools.
- **Honest validation** — walk-forward, regime-segmented, with the shock breakdown reported rather than hidden.
- **Pre-registration registry** — an auditable track record almost no one else offers.
- **Genuine signal in normal conditions** — pre-COVID 3-yr τ ≈ 0.61, precision@10 ≈ 0.88.

### What is weak (the critique)
- **W1 — No baseline.** τ ≈ 0.61 is reported with nothing to compare it to. We never tested the full
  ten-indicator model against naive alternatives (momentum-only, persistence, single-best-indicator,
  equal-weight, random). Without that, we cannot claim the composite adds value over a one-line rule.
  *This is the highest-priority gap and the first question a reviewer will ask.*
- **W2 — Indicator redundancy.** Ten indicators, but fewer independent signals. `per_capita_income`
  and `avg_annual_pay` overlap; `population_growth` is largely driven by `net_migration`. Hand-set
  weights on correlated indicators silently over-weight whatever they share.
- **W3 — The 3-yr ≈ 1-yr finding is under-investigated.** The thesis was that fundamentals express
  themselves over longer horizons; they did not outperform the short horizon. This may indicate the
  model is riding *persistence/momentum* more than durable fundamentals. Cannot be resolved without
  W1 (baselines) and W2 (ablation).
- **W4 — No uncertainty quantification.** Every τ is a point estimate from few overlapping windows.
  A reader cannot distinguish 0.61 ± 0.05 from 0.61 ± 0.30.
- **W5 — Narrow target.** The outcome is asking-rent growth only (ZORI), a proxy for profitability
  that ignores price appreciation and yield. ZORI is asking rent, not executed rent.
- **W6 — Untested weights.** Weights are hand-set and were never compared against alternative schemes.
- **W7 — Current ranking unvalidated and stability unknown.** The 2023 ranking has no out-of-sample
  check yet, and we have not measured how much the ranking whipsaws year to year.
- **W8 — Passive shock handling.** The model reports that it fails in shocks but gives the user no
  live signal that current conditions are abnormal and confidence should be lower.

---

## 2. V2 priorities (tiered)

### Tier 1 — Rigor (do first; mostly analysis, little/no new data)

- **P1 — Baseline benchmarking.** Re-run the walk-forward backtest for: random ranking, momentum-only,
  persistence (rank by trailing rent growth), each single indicator alone, and equal weights. Report
  the full model's τ and precision@10 **as uplift over these baselines**, per regime. This reframes
  every existing result and directly addresses W1 and W3.
- **P2 — Ablation & de-duplication.** (a) Compute the indicator correlation matrix; merge or drop
  redundant indicators (income vs. wage; migration vs. population growth). (b) Leave-one-out ablation:
  drop each indicator/bucket, measure the change in τ, to see what actually carries the signal.
  Likely outcome: a leaner indicator set with the dead weight removed.
- **P3 — Uncertainty quantification.** Block-bootstrap the backtest to put confidence intervals on τ
  and precision@10. Report ranges, not point estimates. Addresses W4 and is a credibility upgrade.
- **P4 — Weight robustness (not free-fitting).** Test a small, hypothesis-driven set of alternative
  weightings (including an ablation-informed one), selected on held-out calm-regime performance.
  **Do not** run an unconstrained optimizer: with ~110 metros and a handful of overlapping windows,
  a free fit will overfit badly. If any fitting is done, constrain it (e.g., ridge toward the
  hand-set weights as a prior) and never fit on the shock regime.

### Tier 2 — Broaden the signal (new data; each addition gated by the P2 redundancy check)

- **P5 — Price/return dimension (low-hanging fruit).** Zillow home values (`zhvi`) are *already in the
  panel*; add FHFA's free house-price index as a cross-check. Construct price-to-rent / gross-yield
  and appreciation measures. This moves the target from rent-growth-only toward a total-return proxy
  (W5). Decide whether this becomes a second screen or a blended score (see open questions).
- **P6 — Vacancy signal.** Add the free Apartment List vacancy index — a direct read on the
  supply/demand balance that complements the permits-based supply measures.
- **P7 — AI/automation exposure indicator.** Score each metro by its occupational mix's exposure to
  AI-driven displacement. Models a forward-looking employment risk the current indicators capture only
  indirectly; novel and timely. (Parked from the original decision log.)

*Gate: no new indicator enters the score until it passes the redundancy/ablation test — does it add
independent predictive signal, or just noise and collinearity?*

### Tier 3 — Product / website

- **Surface the track record and methodology.** The regime-by-regime performance and the prediction
  registry are the credibility differentiator, and v1 hides them. Make them front-and-center pages.
- **Show uncertainty in the UI.** Present scores as a screen, not a guarantee; show rank ranges /
  confidence rather than false-precision point ranks.
- **"Why this rank" panel.** Use the per-bucket z-score contributions already computed to explain each
  metro's score in plain language.
- **Metro trajectory view.** Show a market's indicators and rank over time, not just the latest snapshot.
- **Multi-metro comparison.** Compare two or three markets side by side.
- **Confidence / regime flag.** Detect when current conditions resemble a shock regime and warn that
  model reliability is lower (addresses W8).
- **Sensitivity explorer (with a caution).** Let users adjust weights and watch the ranking move —
  framed as transparency, with explicit warning against cherry-picking a flattering configuration.
- **Polish.** Mobile responsiveness, load performance, accessibility.

---

## 3. Sequencing

1. **Tier 1 before anything else.** The rigor work may change what v2 should even be. If ablation shows
   three indicators are dead weight, you remove them rather than adding more. If baselines show
   momentum-only nearly matches the full model, that reframes the whole project. Do not add data or
   features until you know what is actually working.
2. **Tier 2 next**, each new indicator passing the P2 gate before it joins the score.
3. **Tier 3 in parallel**, except that the "surface the track record" pages depend on Tier 1 outputs.

---

## 4. Guardrails (what NOT to do)

- **No black-box ML.** Transparency is the entire competitive edge, and the data cannot support a
  complex free-fit model honestly.
- **No new indicator without a passed redundancy/ablation test.**
- **Never optimize weights on the full history or the shock regime.**
- **Don't let the sensitivity explorer become a cherry-picking tool** — log/disclose the default weights
  as the canonical screen.

---

## 5. Open questions for V2

- **Combining rent growth and price/return:** two separate screens (a "rent-growth" screen and a
  "yield/return" screen) or one blended score? Two screens is more honest and more flexible; a blend is
  simpler for a lay reader.
- **Frequency:** move to quarterly/monthly data to get more (still overlapping) windows and stronger
  uncertainty estimates, versus the current annual panel?
- **Universe:** keep it frozen (current, mild survivorship bias) or make it time-varying?
