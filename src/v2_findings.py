"""
v2_findings.py — consolidate the Tier-1 rigor results (P1-P3) into one brief.

Reads the committed analysis outputs and writes paper/v2-findings.md: baselines,
ablation, correlation, and bootstrap CIs, with the honest corrected narrative.
Regenerate after re-running baselines/ablation/uncertainty.

    .venv/Scripts/python.exe src/v2_findings.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

PROC = config.PROCESSED_DIR
OUT = config.ROOT / "paper" / "v2-findings.md"


def _tbl(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *rows])


def build() -> Path:
    comp = pd.read_csv(PROC / "baseline_comparison.csv")
    singles = pd.read_csv(PROC / "baseline_singles.csv")
    abl = pd.read_csv(PROC / "ablation.csv")
    corr = pd.read_csv(PROC / "indicator_correlation.csv", index_col=0)
    tau = pd.read_csv(PROC / "uncertainty_tau.csv")
    gaps = pd.read_csv(PROC / "uncertainty_gaps.csv")

    full_tau = float(abl.loc[abl.variant == "Full model", "tau_3y"].iloc[0])
    ft = tau[tau.ranking == "full"].iloc[0]

    # P1 baseline table
    p1 = comp.copy()
    p1["Model"] = p1.apply(lambda r: r["model"] + (f" [{r['best_single_name']}]"
                           if isinstance(r["best_single_name"], str) and r["best_single_name"] else ""), axis=1)
    p1 = p1[["Model", "tau_3y", "prec_3y", "tau_1y", "uplift_tau_3y_vs_full"]]
    p1.columns = ["Model", "3y tau", "3y P@10", "1y tau", "uplift vs full (3y)"]
    for c in ["3y tau", "3y P@10", "1y tau", "uplift vs full (3y)"]:
        p1[c] = p1[c].map(lambda v: f"{v:.3f}")

    # P2 leave-one-out (indicators)
    loo = abl[abl.variant.str.startswith("- ") & ~abl.variant.str.contains("bucket")].copy()
    loo = loo.sort_values("delta_tau_3y", ascending=False)[["variant", "tau_3y", "delta_tau_3y"]]
    loo.columns = ["Drop indicator", "3y tau", "delta"]
    loo["Drop indicator"] = loo["Drop indicator"].str.replace("- ", "", regex=False)
    loo["3y tau"] = loo["3y tau"].map(lambda v: f"{v:.3f}")
    loo["delta"] = loo["delta"].map(lambda v: f"{v:+.3f}")

    # P2 buckets
    buc = abl[abl.variant.str.contains("bucket")].copy().sort_values("delta_tau_3y", ascending=False)
    buc = buc[["variant", "tau_3y", "delta_tau_3y"]]
    buc.columns = ["Drop bucket", "3y tau", "delta"]
    buc["Drop bucket"] = buc["Drop bucket"].str.replace("- bucket: ", "", regex=False)
    buc["3y tau"] = buc["3y tau"].map(lambda v: f"{v:.3f}")
    buc["delta"] = buc["delta"].map(lambda v: f"{v:+.3f}")

    # P2 correlations (|r|>=0.5)
    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if abs(r) >= 0.5:
                pairs.append({"pair": f"{cols[i]} <-> {cols[j]}", "corr": f"{r:+.2f}"})
    pairs_df = pd.DataFrame(pairs).sort_values("corr", key=lambda s: s.str.replace("+", "").astype(float).abs(),
                                               ascending=False) if pairs else pd.DataFrame({"pair": ["(none)"], "corr": [""]})

    # P3 gaps
    g = gaps.copy()
    g["95% CI"] = g.apply(lambda r: f"[{r['lo']:+.3f}, {r['hi']:+.3f}]", axis=1)
    g["reliable?"] = g["excludes_0"].map({True: "yes", False: "no"})
    g["delta"] = g["delta"].map(lambda v: f"{v:+.3f}")
    g = g[["comparison", "delta", "95% CI", "reliable?"]]

    md = f"""# V2 Tier-1 Findings — Rigor Pass (P1-P3)

*Auto-generated {datetime.now(timezone.utc):%Y-%m-%d} from the committed analysis outputs
(`baseline_comparison.csv`, `ablation.csv`, `indicator_correlation.csv`, `uncertainty_*.csv`).
Regenerate with `python src/v2_findings.py`. Companion to `v2-plan.md`.*

## Bottom line (honest)

The full model has **real, statistically reliable signal** at the 3-year horizon
(τ = **{full_tau:.3f}**, 95% CI **[{ft.lo:.3f}, {ft.hi:.3f}]** — excludes 0). It reliably beats
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

{_tbl(p1)}

Full model clears random, persistence, best-single, and equal-weight on 3y point estimates — but
see P3 for which gaps are real. At **1 year, momentum alone (τ {comp[comp.model.str.contains('Momentum')]['tau_1y'].iloc[0]:.3f}) beats the full model
(τ {comp[comp.model.str.contains('Full')]['tau_1y'].iloc[0]:.3f})**: this is a longer-horizon framework.

---

## P2 — Ablation & de-duplication

**Leave-one-out (delta > 0 ⇒ dropping RAISED point-estimate τ):**

{_tbl(loo)}

**Leave-one-bucket-out:**

{_tbl(buc)}

The model is overwhelmingly a **Demand** engine (dropping Demand collapses τ). Note the reversal:
`permits_to_stock` is anti-predictive alone but contributes in combination (dropping it lowers τ).

**Redundant indicator pairs (|correlation| ≥ 0.5):**

{_tbl(pairs_df)}

De-duplication candidates: fold `mf_pipeline` into `permits_to_stock`, and `population_growth`
into `net_migration`.

---

## P3 — Uncertainty (metro-cluster bootstrap, B=1000, 3y)

Full model τ = **{full_tau:.3f}**, 95% CI **[{ft.lo:.3f}, {ft.hi:.3f}]**.

**Gaps — a gap is only trustworthy if its CI excludes 0:**

{_tbl(g)}

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
"""
    OUT.write_text(md, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    p = build()
    print(f"Wrote {p.relative_to(config.ROOT)} ({p.stat().st_size/1024:.1f} KB)")
