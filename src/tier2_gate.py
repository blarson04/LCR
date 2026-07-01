"""
tier2_gate.py — should a candidate indicator join the model? (V2 Tier-2 gate)

The plan's rule: no new indicator enters the score until it passes a
redundancy/ablation test. This runs three checks on a candidate (a raw panel
column), reusing the shared harness + the P3 metro-cluster bootstrap:

  1. STANDALONE — does the candidate alone predict forward 3-yr rent growth?
  2. REDUNDANCY — how correlated is it with the existing scored indicators?
  3. VALUE-ADD — augment the composite with the candidate at a modest weight;
     does 3-yr tau RELIABLY improve (bootstrap CI on delta-tau excludes 0)?

Verdict = adopt only if it has standalone signal, isn't largely redundant, AND
reliably improves the model. Otherwise keep it as context, not a scored input.

    .venv/Scripts/python.exe src/tier2_gate.py            # gates rental_vacancy (P6)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import indicators, normalize  # noqa: E402
from src import score as score_mod  # noqa: E402
from src import backtest, uncertainty  # noqa: E402

INDICATORS = list(config.INDICATORS)


def _zwithin(s: pd.Series, yr: pd.Series) -> pd.Series:
    g = s.groupby(yr)
    return (s - g.transform("mean")) / g.transform("std").replace(0, np.nan)


def _standalone_tau(cand, py, zori):
    st = backtest.summarize(backtest.evaluate_predictions(
        cand.rename(columns={"cand": "score"}).dropna(), py, (3,), target=zori))
    return float(st[(st.horizon == 3) & (st.regime == "POOLED")]["mean_tau"].iloc[0])


def gate(name: str, panel_col: str, *, inverse: bool, weight: float = 0.10,
         B: int = 800, auto_orient: bool = True):
    panel = indicators.load_panel().sort_values(["cbsa_code", "year"])
    norm = normalize.normalize()
    scored = score_mod.score()
    zori = backtest._zori_lookup()
    py = backtest.usable_pred_years(scored)

    cz = _zwithin(panel[panel_col], panel["year"])
    if inverse:
        cz = -cz                                      # flip so higher = better
    cand = panel[["cbsa_code", "year"]].copy()
    cand["cand"] = cz.to_numpy()

    # 1. standalone 3y tau — auto-orient so the candidate gets its fairest shot
    standalone = _standalone_tau(cand, py, zori)
    flipped = False
    if auto_orient and standalone < 0:
        cand["cand"] = -cand["cand"]
        standalone = -standalone
        flipped = True

    # 2. redundancy vs existing indicators (pooled across metro-years)
    merged = norm.merge(cand, on=["cbsa_code", "year"], how="inner")
    corrs = {k: merged["cand"].corr(merged[k]) for k in INDICATORS}
    top = sorted(corrs.items(), key=lambda kv: -abs(kv[1]))[:3]
    max_abs_corr = max(abs(v) for v in corrs.values())

    # 3. value-add: augment composite at `weight`, bootstrap CI on delta-tau
    full = scored[["cbsa_code", "year", "score"]].copy()
    aug = full.merge(cand, on=["cbsa_code", "year"], how="left")
    aug["cand"] = aug["cand"].fillna(0.0)
    aug["score"] = (1 - weight) * aug["score"] + weight * aug["cand"]
    cols = {"full": full, "augmented": aug[["cbsa_code", "year", "score"]]}
    frames = uncertainty._window_frames(cols, py, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    rng = np.random.default_rng(config.RANDOM_SEED)
    d_point = (uncertainty._pooled_tau(frames, metros, "augmented")
               - uncertainty._pooled_tau(frames, metros, "full"))
    boot = np.empty(B)
    for b in range(B):
        s = rng.choice(metros, size=len(metros), replace=True)
        boot[b] = (uncertainty._pooled_tau(frames, s, "augmented")
                   - uncertainty._pooled_tau(frames, s, "full"))
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])

    reliable = lo > 0
    adopt = (standalone > 0.10) and (max_abs_corr < 0.70) and reliable
    return {"name": name, "standalone_tau": standalone, "top_corr": top,
            "delta_tau": d_point, "ci": (lo, hi), "reliable": reliable, "adopt": adopt,
            "flipped": flipped}


def _report(r):
    print(f"=== Tier-2 gate: {r['name']} ===\n")
    print(f"  1. standalone 3y tau     : {r['standalone_tau']:+.3f}  "
          f"({'has signal' if r['standalone_tau'] > 0.10 else 'weak/none'})")
    print(f"  2. top correlations with existing indicators:")
    for k, v in r["top_corr"]:
        print(f"        {v:+.2f}  {k}")
    print(f"  3. value-add (augment @10%): delta-tau {r['delta_tau']:+.3f}  "
          f"95% CI [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}]  "
          f"({'RELIABLE' if r['reliable'] else 'within noise'})")
    print(f"\n  VERDICT: {'ADOPT as scored indicator' if r['adopt'] else 'DO NOT adopt — keep as context'}")
    print("  (adopt requires standalone signal + low redundancy + reliably improves tau)")


if __name__ == "__main__":
    import sys as _sys
    which = _sys.argv[1] if len(_sys.argv) > 1 else "all"
    results = []
    if which in ("all", "p6"):
        r = gate("rental_vacancy (P6)", "rental_vacancy", inverse=True)
        _report(r); results.append(r); print()
    if which in ("all", "p7"):
        r = gate("ai_exposure (P7)", "ai_exposure", inverse=True)
        _report(r); results.append(r)
    if results:
        pd.DataFrame([{
            "candidate": x["name"], "standalone_tau_3y": round(x["standalone_tau"], 3),
            "max_abs_corr": round(abs(x["top_corr"][0][1]), 3),
            "value_add_delta_tau": round(x["delta_tau"], 3),
            "ci_lo": round(x["ci"][0], 3), "ci_hi": round(x["ci"][1], 3),
            "adopted": x["adopt"]} for x in results]).to_csv(
            config.PROCESSED_DIR / "tier2_gates.csv", index=False)
