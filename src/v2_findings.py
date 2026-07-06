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
    wsch = pd.read_csv(PROC / "weight_schemes.csv")
    pr_red = pd.read_csv(PROC / "price_return_redundancy.csv")
    pr_appr = pd.read_csv(PROC / "price_return_appreciation.csv")
    gates_path = PROC / "tier2_gates.csv"
    gates = pd.read_csv(gates_path) if gates_path.exists() else pd.DataFrame()

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

    # P4 weight schemes
    ws = wsch.copy()
    ws["95% CI"] = ws.apply(lambda r: f"[{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]", axis=1)
    ws["gap vs best"] = ws.apply(lambda r: f"{r['gap_vs_best']:+.3f} [{r['gap_lo']:+.3f}, {r['gap_hi']:+.3f}]", axis=1)
    ws["reliably worse?"] = ws["reliably_worse"].map({True: "yes", False: "no"})
    ws["tau_3y"] = ws["tau_3y"].map(lambda v: f"{v:.3f}")
    ws = ws.rename(columns={"scheme": "Scheme", "n_ind": "#ind", "tau_3y": "3y tau"})
    ws = ws[["Scheme", "#ind", "3y tau", "95% CI", "gap vs best", "reliably worse?"]]
    best_scheme = wsch.sort_values("tau_3y", ascending=False).iloc[0]["scheme"]
    ok = wsch[~wsch["reliably_worse"]].sort_values(["n_ind", "gap_vs_best"])
    rec_scheme = ok.iloc[0]["scheme"] if len(ok) else best_scheme

    # P5 price/return
    pr_top = (pr_red.reindex(pr_red["corr"].abs().sort_values(ascending=False).index)
              .groupby("new_measure").head(2))
    pr_top["corr"] = pr_top["corr"].map(lambda v: f"{v:+.2f}")
    pr_top = pr_top.rename(columns={"new_measure": "New measure", "indicator": "Existing indicator", "corr": "corr"})
    appr = pr_appr.copy()
    for c in ["appr_tau_3y", "appr_tau_1y"]:
        appr[c] = appr[c].map(lambda v: f"{v:.3f}")
    appr["appr_p@10_3y"] = appr["appr_p@10_3y"].map(lambda v: f"{v:.2f}")
    appr = appr.rename(columns={"predictor": "Predictor of forward appreciation",
                                "appr_tau_3y": "3y τ", "appr_p@10_3y": "3y P@10", "appr_tau_1y": "1y τ"})

    # P6/P7 Tier-2 gates
    if len(gates):
        gt = gates.rename(columns={
            "candidate": "Candidate", "standalone_tau_3y": "standalone 3y τ",
            "max_abs_corr": "max |corr|", "value_add_delta_tau": "value-add Δτ",
            "adopted": "adopted?"})
        gt["95% CI"] = gt.apply(lambda r: f"[{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]", axis=1)
        gt["adopted?"] = gt["adopted?"].map({True: "yes", False: "no"})
        gt = gt[["Candidate", "standalone 3y τ", "max |corr|", "value-add Δτ", "95% CI", "adopted?"]]
        gates_tbl = _tbl(gt)
    else:
        gates_tbl = "_(run src/tier2_gate.py to generate)_"

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

*(Vintage note, v3-P2: every τ in this document is a **finalized-data ceiling** — computed on
revisions no real-time user could have held. The real-time-achievable pooled 3-yr τ is ≈0.38;
see `paper-brief.md` and `nowcast-validation.md`.)*

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

**P4 recommendation:** adopt the **{rec_scheme}** scheme — the simplest weighting not reliably
worse than the best. It drops the two redundant indicators with no reliable accuracy loss.

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

## P4 — Weight robustness (3y τ, bootstrap B=1000)

Best point estimate: **{best_scheme}**. Recommendation (simplest not reliably worse than best):
**{rec_scheme}**.

{_tbl(ws)}

Only equal-weight is *reliably* worse than the best — so a thoughtful scheme beats naive
equal-weighting, but among thoughtful schemes the differences are within noise (don't over-tune).
The **de-duplicated 8-indicator** scheme matches the 10-indicator hand-set with no reliable loss:
a free parsimony win. `demand-tilted` has the top point estimate but its edge is not reliable —
noted as a hypothesis, not adopted.

---

## P5 — Price/return dimension (gated)

Tests whether adding home-price/return signals is worthwhile. **Redundancy** (top correlations
with existing indicators):

{_tbl(pr_top)}

`price_to_rent` is the same as the existing `cost_to_own_vs_rent`; `home_appreciation` tracks
`trailing_rent_growth`. **Predicting forward home-price appreciation:**

{_tbl(appr)}

Valuation/yield "return screens" have ~no predictive signal, while the **rent-growth composite
predicts appreciation too** (τ ≈ 0.32). **Decision:** do NOT add a yield indicator or a separate
valuation screen; instead report the model's appreciation skill as a validated secondary
total-return outcome (addresses W5, the narrow-target critique).

---

## P6 & P7 — Tier-2 candidate indicators (gated)

Each candidate was tested before adoption: standalone predictive τ, redundancy with existing
indicators, and whether augmenting the composite at 10% *reliably* improves 3-yr τ (bootstrap CI).

{gates_tbl}

- **Vacancy (P6)** — ACS rental vacancy (chosen over Apartment List for reproducibility). Has
  standalone signal but is partly redundant with `cost_to_own_vs_rent` and doesn't reliably help.
- **AI-exposure (P7)** — an industry-level proxy (metro employment share in the highest
  gen-AI-exposure NAICS sectors) built from cached QCEW, since BLS OEWS occupation files block bot
  downloads (403). Genuinely non-redundant but weak, with zero reliable value-add.

**Neither is adopted as a scored indicator** — both are kept as panel *context* columns. The
recurring Tier-2 result: **no new free signal reliably improved the model**, reinforcing that it's
a parsimonious, honestly-bounded framework (the gate is doing its job).

---

## Status → what's next

- **Done:** v2 model = de-duplicated 8-indicator scheme (P4); honest framing (real signal,
  comparable to momentum, beats equal-weight/persistence); CIs reported; price/return (P5),
  vacancy (P6), and AI-exposure (P7) all gated out with the model held parsimonious; UI upgraded
  (track record, rank-range uncertainty, why-this-rank, compare, regime flag, context measures).
- **Future refinements (data-gated):** occupation-level AI exposure if accessible OEWS data is
  found; executed-rent / capital-markets data (paid).
"""
    OUT.write_text(md, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    p = build()
    print(f"Wrote {p.relative_to(config.ROOT)} ({p.stat().st_size/1024:.1f} KB)")
