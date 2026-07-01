"""
weights.py — weight robustness, honestly (V2 P4).

P3 showed the accuracy landscape is flat and noisy, so we do NOT free-fit
weights (that would overfit). Instead we compare a small set of hypothesis-driven
weighting schemes through the same metro-cluster bootstrap, and choose by the
rule: **the simplest scheme that is not RELIABLY worse than the best** (its gap
to the best-point scheme has a 95% CI that includes 0).

Schemes:
  - hand-set (v1)     : the current config weights
  - equal-weight      : all 10 indicators equal
  - de-duplicated     : fold mf_pipeline -> permits, population_growth ->
                        net_migration (8 indicators; addresses the r=0.77 / 0.62
                        redundancy from P2)
  - demand-tilted     : boost Demand (which carries the signal), shrink the
                        net-harmful Affordability bucket

    .venv/Scripts/python.exe src/weights.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import normalize           # noqa: E402
from src import score as score_mod  # noqa: E402
from src import backtest            # noqa: E402
from src import uncertainty         # noqa: E402  (reuse frames + bootstrap tau)

INDICATORS = list(config.INDICATORS)
B = 1000
SEED = config.RANDOM_SEED

SCHEMES: dict[str, dict[str, float]] = {
    "hand-set (v1)": {k: v["weight"] for k, v in config.INDICATORS.items()},
    "equal-weight": {k: 0.10 for k in INDICATORS},
    "de-duplicated": {
        "net_migration": 0.20, "job_growth": 0.12, "income_growth": 0.08,
        "population_growth": 0.0, "permits_to_stock": 0.25, "mf_pipeline": 0.0,
        "rent_to_income": 0.12, "cost_to_own_vs_rent": 0.08,
        "trailing_rent_growth": 0.10, "employment_diversity": 0.05,
    },
    "demand-tilted": {
        "net_migration": 0.22, "job_growth": 0.16, "income_growth": 0.08,
        "population_growth": 0.06, "permits_to_stock": 0.17, "mf_pipeline": 0.08,
        "rent_to_income": 0.05, "cost_to_own_vs_rent": 0.03,
        "trailing_rent_growth": 0.10, "employment_diversity": 0.05,
    },
}


def _score_cols(norm: pd.DataFrame) -> dict[str, pd.DataFrame]:
    z = norm[INDICATORS].fillna(0.0)
    keys = norm[["cbsa_code", "year"]]
    cols = {}
    for name, w in SCHEMES.items():
        assert abs(sum(w.values()) - 1.0) < 1e-9, f"{name} weights must sum to 1"
        s = sum(w[k] * z[k] for k in INDICATORS)
        d = keys.copy(); d["score"] = np.asarray(s); cols[name] = d
    return cols


def run():
    norm = normalize.normalize()
    scored = score_mod.score()
    zori = backtest._zori_lookup()
    pred_years = backtest.usable_pred_years(scored)
    cols = _score_cols(norm)
    frames = uncertainty._window_frames(cols, pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    names = list(cols)

    rng = np.random.default_rng(SEED)
    point = {n: uncertainty._pooled_tau(frames, metros, n) for n in names}
    boot = {n: np.empty(B) for n in names}
    for b in range(B):
        s = rng.choice(metros, size=len(metros), replace=True)
        for n in names:
            boot[n][b] = uncertainty._pooled_tau(frames, s, n)

    best = max(names, key=lambda n: point[n])          # best point-estimate scheme
    rows = []
    for n in names:
        lo, hi = np.nanpercentile(boot[n], [2.5, 97.5])
        gap = boot[best] - boot[n]                     # best - scheme (paired)
        glo, ghi = np.nanpercentile(gap, [2.5, 97.5])
        rows.append({
            "scheme": n, "n_ind": sum(1 for v in SCHEMES[n].values() if v > 0),
            "tau_3y": point[n], "ci_lo": lo, "ci_hi": hi,
            "gap_vs_best": point[best] - point[n], "gap_lo": glo, "gap_hi": ghi,
            "reliably_worse": bool(glo > 0),           # CI of (best-scheme) above 0
        })
    return pd.DataFrame(rows), best


def main() -> None:
    df, best = run()
    df.to_csv(config.PROCESSED_DIR / "weight_schemes.csv", index=False)

    print(f"=== P4 weight robustness (3y tau, bootstrap B={B}) ===")
    print(f"Best point estimate: {best}\n")
    print(f"  {'scheme':<18}{'#ind':>5}{'3y tau':>9}{'    95% CI':>18}"
          f"{'gap vs best':>13}{'  reliably worse?':>18}")
    for _, r in df.sort_values("tau_3y", ascending=False).iterrows():
        print(f"  {r['scheme']:<18}{r['n_ind']:>5}{r['tau_3y']:>9.3f}"
              f"   [{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]"
              f"{r['gap_vs_best']:>+13.3f}   [{r['gap_lo']:+.3f},{r['gap_hi']:+.3f}]"
              f"{('  YES' if r['reliably_worse'] else '  no'):>8}")

    # recommendation: simplest scheme not reliably worse than the best
    ok = df[~df["reliably_worse"]].sort_values(["n_ind", "gap_vs_best"])
    rec = ok.iloc[0]["scheme"] if len(ok) else best
    print(f"\nRecommendation (simplest scheme not reliably worse than best): {rec}")
    print("Reading it: no scheme is reliably worse than the best => the weights don't")
    print("robustly matter; prefer the simplest/most-interpretable. Any 'winner' is")
    print("within noise, so do NOT over-tune (V2 guardrail).")


if __name__ == "__main__":
    main()
