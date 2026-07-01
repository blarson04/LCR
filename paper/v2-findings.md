# V2 Tier-1 Findings — Rigor Pass (P1-P3)

*Auto-generated 2026-07-01 from the committed analysis outputs
(`baseline_comparison.csv`, `ablation.csv`, `indicator_correlation.csv`, `uncertainty_*.csv`).
Regenerate with `python src/v2_findings.py`. Companion to `v2-plan.md`.*

## Bottom line (honest)

The full model has **real, statistically reliable signal** at the 3-year horizon
(τ = **0.444**, 95% CI **[0.357, 0.502]** — excludes 0). It reliably beats
equal-weight and a persistence rule. But with error bars, two comfortable v1 stories do **not**
survive:

1. **It does not reliably beat a momentum one-liner at 3y** — the edge over ranking by trailing
   rent growth is within noise. Honest framing: *comparable to momentum, with the added value of
   interpretability and diversification.*
2. **No indicator can be cut on accuracy grounds.** Every ablation "improvement" from dropping an
   indicator has a CI that straddles 0. Only **`net_migration`** is individually indispensable.

Implication for v2: **de-duplicate on parsimony/collinearity grounds, not accuracy; do not
free-fit weights** (the accuracy landscape is too flat to fit without overfitting).

---

## P1 — Baselines (walk-forward, same years/metros)

| Model | 3y tau | 3y P@10 | 1y tau | uplift vs full (3y) |
| --- | --- | --- | --- | --- |
| Full model (composite) | 0.444 | 0.667 | 0.485 | 0.000 |
| Equal weight (10 ind.) | 0.405 | 0.617 | 0.448 | 0.039 |
| Momentum only (trailing rent) | 0.391 | 0.650 | 0.621 | 0.053 |
| Best single indicator [trailing_rent_growth] | 0.391 | 0.650 | 0.621 | 0.053 |
| Persistence (trailing h-yr) | 0.216 | 0.375 | 0.621 | 0.229 |
| Random (avg of seeds) | -0.012 | 0.257 | 0.001 | 0.456 |

Full model clears random, persistence, best-single, and equal-weight on 3y point estimates — but
see P3 for which gaps are real. At **1 year, momentum alone (τ 0.621) beats the full model
(τ 0.485)**: this is a longer-horizon framework.

---

## P2 — Ablation & de-duplication

**Leave-one-out (delta > 0 ⇒ dropping RAISED point-estimate τ):**

| Drop indicator | 3y tau | delta |
| --- | --- | --- |
| cost_to_own_vs_rent | 0.470 | +0.025 |
| income_growth | 0.459 | +0.015 |
| employment_diversity | 0.452 | +0.007 |
| population_growth | 0.432 | -0.013 |
| mf_pipeline | 0.430 | -0.014 |
| rent_to_income | 0.422 | -0.022 |
| permits_to_stock | 0.410 | -0.035 |
| trailing_rent_growth | 0.397 | -0.047 |
| job_growth | 0.379 | -0.065 |
| net_migration | 0.294 | -0.150 |

**Leave-one-bucket-out:**

| Drop bucket | 3y tau | delta |
| --- | --- | --- |
| Affordability | 0.469 | +0.024 |
| Resilience | 0.452 | +0.007 |
| Momentum | 0.397 | -0.047 |
| Supply | 0.380 | -0.065 |
| Demand | 0.052 | -0.393 |

The model is overwhelmingly a **Demand** engine (dropping Demand collapses τ). Note the reversal:
`permits_to_stock` is anti-predictive alone but contributes in combination (dropping it lowers τ).

**Redundant indicator pairs (|correlation| ≥ 0.5):**

| pair | corr |
| --- | --- |
| permits_to_stock <-> mf_pipeline | +0.77 |
| population_growth <-> permits_to_stock | -0.64 |
| job_growth <-> permits_to_stock | -0.64 |
| net_migration <-> population_growth | +0.62 |
| net_migration <-> permits_to_stock | -0.61 |

De-duplication candidates: fold `mf_pipeline` into `permits_to_stock`, and `population_growth`
into `net_migration`.

---

## P3 — Uncertainty (metro-cluster bootstrap, B=1000, 3y)

Full model τ = **0.444**, 95% CI **[0.357, 0.502]**.

**Gaps — a gap is only trustworthy if its CI excludes 0:**

| comparison | delta | 95% CI | reliable? |
| --- | --- | --- | --- |
| full - equal_weight | +0.039 | [+0.008, +0.069] | yes |
| full - best_single (momentum) | +0.053 | [-0.034, +0.140] | no |
| full - persistence | +0.229 | [+0.138, +0.339] | yes |
| drop:cost_to_own_vs_rent (drop helps if >0) | +0.025 | [-0.002, +0.056] | no |
| drop:income_growth (drop helps if >0) | +0.015 | [-0.018, +0.044] | no |
| drop:employment_diversity (drop helps if >0) | +0.007 | [-0.012, +0.022] | no |
| drop:permits_to_stock (drop helps if >0) | -0.035 | [-0.097, +0.013] | no |
| drop:net_migration (drop helps if >0) | -0.150 | [-0.209, -0.072] | yes |

Reliable: beats equal-weight and persistence; `net_migration` removal reliably hurts. NOT reliable:
the edge over momentum, and every indicator-cut delta.

---

## What P4 should (and shouldn't) do

- **Should:** compare a few *hypothesis-driven* schemes (hand-set vs. equal-weight vs. a
  de-duplicated scheme vs. a Demand-tilted scheme) with bootstrap CIs; pick the **simplest scheme
  not reliably worse than the best**.
- **Shouldn't:** run an unconstrained optimizer — the flat, noisy landscape guarantees overfitting.

## Open items
- **P4** — weight robustness (above).  **Tier 2** — price/return dimension, vacancy, AI-exposure
  (each gated by the redundancy/ablation test).  **Tier 3** — surface track record + uncertainty in the UI.
