"""
momentum_effect.py — economic effect size + momentum orthogonality (v3 P4+P5).

P5 (effect size, in units people understand): for the model and every baseline,
per 3-yr window: mean realized forward rent growth of the strategy's TOP-10
minus the universe MEDIAN, in percentage points.

P4 (does the composite add anything beyond momentum?):
  - per-window model-vs-momentum in both τ and pp (incl. the shock exhibit:
    momentum's top-10 edge flipped negative in 2021–22 — did the composite's?)
  - partial rank correlation: composite vs realized growth, controlling for
    trailing rent growth (rank-residual method)
  - error correlation: do the two strategies miss on the SAME metros?
  - a 50/50 momentum+composite blend added to the comparison set

Writes data/processed/effect_size_windows.csv, effect_size_summary.csv,
momentum_orthogonality.csv.

    .venv/Scripts/python.exe src/momentum_effect.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import normalize           # noqa: E402
from src import score as score_mod  # noqa: E402
from src import backtest            # noqa: E402

H = 3
K = 10
N_RANDOM = 50
INDICATORS = list(config.INDICATORS)


def _zscore_within_year(df: pd.DataFrame, col: str) -> pd.Series:
    g = df.groupby("year")[col]
    return (df[col] - g.transform("mean")) / g.transform("std").replace(0, np.nan)


def _strategies() -> dict[str, pd.DataFrame]:
    norm = normalize.normalize()
    scored = score_mod.score()
    zori = backtest._zori_lookup()
    keys = norm[["cbsa_code", "year"]]

    def mk(v):
        d = keys.copy(); d["score"] = np.asarray(v); return d

    z = norm[INDICATORS].fillna(0.0)
    comp = scored[["cbsa_code", "year", "score"]]
    momentum = mk(norm["trailing_rent_growth"].fillna(0.0))

    # 50/50 blend of within-year standardized composite + momentum z.
    cz = comp.copy()
    cz["cs"] = _zscore_within_year(cz, "score")
    blend = keys.merge(cz[["cbsa_code", "year", "cs"]], on=["cbsa_code", "year"], how="left")
    blend["score"] = 0.5 * blend["cs"].fillna(0.0) + 0.5 * norm["trailing_rent_growth"].fillna(0.0).to_numpy()
    blend = blend[["cbsa_code", "year", "score"]]

    prev = zori.rename(columns={"zori": "zp"}).copy(); prev["year"] += H
    pers = zori.merge(prev, on=["cbsa_code", "year"], how="left")
    pers["score"] = pers["zori"] / pers["zp"] - 1.0

    return {
        "Composite (model)": comp,
        "Momentum (trailing rent)": momentum,
        "50/50 blend": blend,
        "Equal weight": mk(z.mean(axis=1)),
        "Persistence (3-yr trailing)": pers[["cbsa_code", "year", "score"]],
    }


def _windows(pred_years, zori):
    """Per-window frame: cbsa -> winsorized realized 3-yr growth."""
    latest = int(zori["year"].max())
    out = {}
    for T in pred_years:
        if T + H > latest:
            continue
        now = zori[zori.year == T][["cbsa_code", "zori"]].rename(columns={"zori": "z0"})
        fut = zori[zori.year == T + H][["cbsa_code", "zori"]].rename(columns={"zori": "z1"})
        f = now.merge(fut, on="cbsa_code").dropna()
        f = f[f.z0 > 0]
        f["realized"] = backtest._winsorize(f["z1"] / f["z0"] - 1.0)
        out[T] = f.set_index("cbsa_code")["realized"]
    return out


def run():
    zori = backtest._zori_lookup()
    pred_years = backtest.usable_pred_years()
    wins = _windows(pred_years, zori)
    strats = _strategies()
    rng = np.random.default_rng(config.RANDOM_SEED)

    # ---- P5: per-window top-10 pp edge (+ per-window tau) -------------------
    rows = []
    for name, pred in strats.items():
        for T, realized in wins.items():
            p = pred[pred.year == T].set_index("cbsa_code")["score"].reindex(realized.index).dropna()
            r = realized.reindex(p.index)
            top = r.loc[p.nlargest(K).index]
            rows.append({"strategy": name, "pred_year": T,
                         "regime": backtest._regime_of(T),
                         "top10_pp_vs_median": (top.mean() - r.median()) * 100,
                         "tau": backtest._weighted_tau_by_realized(p.to_numpy(), r.to_numpy())})
    for T, realized in wins.items():   # random reference
        pps = [(realized.sample(K, random_state=int(rng.integers(1e9))).mean()
                - realized.median()) * 100 for _ in range(N_RANDOM)]
        rows.append({"strategy": "Random (50-seed mean)", "pred_year": T,
                     "regime": backtest._regime_of(T),
                     "top10_pp_vs_median": float(np.mean(pps)), "tau": np.nan})
    win_df = pd.DataFrame(rows)
    win_df.to_csv(config.PROCESSED_DIR / "effect_size_windows.csv", index=False)

    summ = (win_df.groupby("strategy")
            .agg(mean_pp=("top10_pp_vs_median", "mean"),
                 min_pp=("top10_pp_vs_median", "min"),
                 max_pp=("top10_pp_vs_median", "max"),
                 mean_tau=("tau", "mean")).reset_index())
    summ.to_csv(config.PROCESSED_DIR / "effect_size_summary.csv", index=False)

    # ---- P4: partial rank corr + error correlation --------------------------
    comp, mom = strats["Composite (model)"], strats["Momentum (trailing rent)"]
    orows = []
    for T, realized in wins.items():
        c = comp[comp.year == T].set_index("cbsa_code")["score"].reindex(realized.index)
        m = mom[mom.year == T].set_index("cbsa_code")["score"].reindex(realized.index)
        ok = c.notna() & m.notna()
        rc, rm, rr = (rankdata(c[ok]), rankdata(m[ok]), rankdata(realized[ok]))
        # partial Spearman: composite vs realized, controlling momentum
        res_c = rc - np.polyval(np.polyfit(rm, rc, 1), rm)
        res_r = rr - np.polyval(np.polyfit(rm, rr, 1), rm)
        partial = float(np.corrcoef(res_c, res_r)[0, 1])
        raw = float(spearmanr(rc, rr)[0])
        # error correlation: do the two strategies miss the same metros?
        err_c, err_m = rr - rc, rr - rm
        errcorr = float(np.corrcoef(err_c, err_m)[0, 1])
        orows.append({"pred_year": T, "regime": backtest._regime_of(T), "n": int(ok.sum()),
                      "spearman_raw": raw, "partial_after_momentum": partial,
                      "error_correlation": errcorr})
    orth = pd.DataFrame(orows)
    orth.to_csv(config.PROCESSED_DIR / "momentum_orthogonality.csv", index=False)
    return win_df, summ, orth


def main():
    win_df, summ, orth = run()
    print("=== P5: top-10 edge vs universe median, percentage points of 3-yr rent growth ===\n")
    piv = win_df.pivot_table(index="pred_year", columns="strategy",
                             values="top10_pp_vs_median")
    cols = ["Composite (model)", "Momentum (trailing rent)", "50/50 blend",
            "Equal weight", "Persistence (3-yr trailing)", "Random (50-seed mean)"]
    print(piv[cols].round(1).to_string())
    print("\npooled means (pp):")
    print(summ.set_index("strategy").loc[cols][["mean_pp", "min_pp", "max_pp", "mean_tau"]]
          .round(2).to_string())
    print("\n=== P4: orthogonality (composite vs momentum) ===\n")
    print(orth.round(3).to_string(index=False))
    print(f"\npooled: partial-after-momentum {orth.partial_after_momentum.mean():+.3f} "
          f"(raw {orth.spearman_raw.mean():+.3f}); error correlation "
          f"{orth.error_correlation.mean():+.3f}")


if __name__ == "__main__":
    main()
