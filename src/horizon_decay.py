"""
horizon_decay.py — how far ahead does the screen stay useful? (exploratory)

Evaluates the model at horizons 1–6 years on history: pooled top-weighted τ,
per-window range, precision@10, and the top-10 pp edge vs the universe median.
Also evaluated: rent momentum (the decay benchmark) and the 2024-vintage
configuration (the actual product; PEP-migration substitution), since a 2028
call from today = horizon 4 on the 2024 vintage.

EXPLORATORY, clearly labeled: this measures the decay curve. Publishing any
horizon beyond 3 years as a product claim would require its own pre-registered
gate (per the governance rules). Windows shrink with horizon (h=4: 5 windows,
h=5/6: 4) and overlap heavily — read long horizons as directional.

    .venv/Scripts/python.exe src/horizon_decay.py
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
from src.nowcast import vintage_gate  # noqa: E402

HORIZONS = (1, 2, 3, 4, 5, 6)
K = 10


def _pp_and_tau(pred: pd.DataFrame, zori: pd.DataFrame, pred_years, h: int):
    """Per-window (top-10 pp edge, tau, precision@10) for one ranking source."""
    latest = int(zori["year"].max())
    rows = []
    for T in pred_years:
        if T + h > latest:
            continue
        now = zori[zori.year == T][["cbsa_code", "zori"]].rename(columns={"zori": "z0"})
        fut = zori[zori.year == T + h][["cbsa_code", "zori"]].rename(columns={"zori": "z1"})
        f = now.merge(fut, on="cbsa_code").dropna()
        f = f[f.z0 > 0]
        f["realized"] = backtest._winsorize(f["z1"] / f["z0"] - 1.0)
        p = (pred[pred.year == T].set_index("cbsa_code")["score"]
             .reindex(f.set_index("cbsa_code").index).dropna())
        r = f.set_index("cbsa_code")["realized"].reindex(p.index)
        top = r.loc[p.nlargest(K).index]
        thresh = np.quantile(r, 0.75)
        rows.append({
            "pred_year": T,
            "tau": backtest._weighted_tau_by_realized(p.to_numpy(), r.to_numpy()),
            "pp": (top.mean() - r.median()) * 100,
            "prec": float((top >= thresh).mean()),
        })
    return pd.DataFrame(rows)


def run():
    scored = score_mod.score()
    pred_years = backtest.usable_pred_years(scored)
    zori = backtest._zori_lookup()
    norm = normalize.normalize()

    comp = scored[["cbsa_code", "year", "score"]]
    mom = norm[["cbsa_code", "year"]].copy()
    mom["score"] = norm["trailing_rent_growth"].fillna(0.0).to_numpy()
    vint = vintage_gate._vintage_scores(pred_years)[["cbsa_code", "year", "score"]]

    out = []
    for h in HORIZONS:
        for name, pred in [("Composite (finalized)", comp),
                           ("Composite (2024-vintage config)", vint),
                           ("Momentum", mom)]:
            w = _pp_and_tau(pred, zori, pred_years, h)
            if not len(w):
                continue
            out.append({
                "horizon": h, "strategy": name, "n_windows": len(w),
                "pooled_tau": w["tau"].mean(), "tau_min": w["tau"].min(),
                "tau_max": w["tau"].max(), "mean_pp": w["pp"].mean(),
                "pp_min": w["pp"].min(), "prec10": w["prec"].mean(),
            })
    df = pd.DataFrame(out)
    df.to_csv(config.PROCESSED_DIR / "horizon_decay.csv", index=False)
    return df


def main():
    df = run()
    print("=== Horizon decay (EXPLORATORY — windows shrink & overlap as h grows) ===\n")
    for name in ["Composite (finalized)", "Composite (2024-vintage config)", "Momentum"]:
        sub = df[df.strategy == name]
        print(f"{name}:")
        print(f"  {'h':>2} {'wins':>5} {'pooled tau':>11} {'tau range':>18} "
              f"{'top10 pp':>9} {'worst pp':>9} {'prec@10':>8}")
        for _, r in sub.iterrows():
            print(f"  {int(r.horizon):>2} {int(r.n_windows):>5} {r.pooled_tau:>11.3f} "
                  f"[{r.tau_min:+.2f}, {r.tau_max:+.2f}]".rjust(0)
                  + f" {r.mean_pp:>12.1f} {r.pp_min:>9.1f} {r.prec10:>8.2f}")
        print()
    print("A 2028 call from today's validated product = horizon 4 on the 2024 vintage.")
    print("Publishing any h>3 claim requires its own pre-registered gate.")


if __name__ == "__main__":
    main()
