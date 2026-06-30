"""
baselines.py — does the 10-indicator composite beat naive alternatives? (V2 P1)

τ ≈ 0.61 means little without something to compare it to. This runs the SAME
walk-forward harness (backtest.evaluate_predictions) on a set of naive ranking
rules and reports the full model's accuracy as **uplift** over each:

  - Random ranking            (averaged over many seeds) — the zero-skill floor
  - Equal weight              (all 10 indicators, no hand-set weights)
  - Momentum only             (rank by trailing rent growth as of T)
  - Persistence               (rank by trailing growth over the SAME horizon)
  - Each single indicator      (which one lone signal does best?)
  - Full model                (the 10-indicator composite)

Every rule is scored on the same prediction years and metros, so differences
are apples-to-apples. If the full model doesn't clear these bars, the composite
isn't earning its complexity — exactly the question V2 must answer.

    .venv/Scripts/python.exe src/baselines.py
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

INDICATORS = list(config.INDICATORS)
N_RANDOM_SEEDS = 50


# ---- ranking providers: each returns [cbsa_code, year, score] (higher=better)
def _equal_weight(norm: pd.DataFrame) -> pd.DataFrame:
    df = norm[["cbsa_code", "year"]].copy()
    df["score"] = norm[INDICATORS].fillna(0.0).mean(axis=1)
    return df


def _single(norm: pd.DataFrame, key: str) -> pd.DataFrame:
    df = norm[["cbsa_code", "year"]].copy()
    df["score"] = norm[key].fillna(0.0)
    return df


def _persistence(zori: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Score = trailing rent growth over the SAME length as the forward horizon
    ('what grew over the last h years keeps growing')."""
    prev = zori.rename(columns={"zori": "z_prev"}).copy()
    prev["year"] = prev["year"] + horizon
    m = zori.merge(prev, on=["cbsa_code", "year"], how="left")
    m["score"] = m["zori"] / m["z_prev"] - 1.0
    return m[["cbsa_code", "year", "score"]]


def _random(template: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = template[["cbsa_code", "year"]].copy()
    df["score"] = rng.standard_normal(len(df))
    return df


def _metrics(summary: pd.DataFrame) -> dict:
    """Pull the headline numbers out of a backtest.summarize() table."""
    def g(h, reg, col):
        m = summary[(summary.horizon == h) & (summary.regime == reg)]
        return float(m[col].iloc[0]) if len(m) else float("nan")
    return {"tau_3y": g(3, "POOLED", "mean_tau"),
            "prec_3y": g(3, "POOLED", "mean_precision@10"),
            "tau_3y_preCOVID": g(3, "pre_covid", "mean_tau"),
            "tau_1y": g(1, "POOLED", "mean_tau")}


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    norm = normalize.normalize()
    scored = score_mod.score()
    zori = backtest._zori_lookup()
    pred_years = backtest.usable_pred_years(scored)

    def evalp(pred, horizons=(3, 1)):
        return backtest.evaluate_predictions(pred, pred_years, horizons, zori)

    # --- single indicators (also feeds "best single" + a P2 preview) ---
    singles = {k: _metrics(backtest.summarize(evalp(_single(norm, k)))) for k in INDICATORS}
    singles_df = (pd.DataFrame(singles).T.reset_index().rename(columns={"index": "indicator"})
                  .sort_values("tau_3y", ascending=False).reset_index(drop=True))
    best_key = singles_df.iloc[0]["indicator"]

    # --- persistence (horizon-matched, so evaluate each horizon separately) ---
    pers = pd.concat([evalp(_persistence(zori, h), horizons=(h,)) for h in (3, 1)], ignore_index=True)

    # --- random (average over seeds) ---
    rand = pd.concat([backtest.summarize(evalp(_random(scored, s))) for s in range(N_RANDOM_SEEDS)])
    rand_avg = rand.groupby(["horizon", "regime"], as_index=False)[["mean_tau", "mean_precision@10"]].mean()

    rows = {
        "Random (avg of seeds)": _metrics(rand_avg),
        "Best single indicator": singles[best_key],
        "Momentum only (trailing rent)": singles["trailing_rent_growth"],
        "Persistence (trailing h-yr)": _metrics(backtest.summarize(pers)),
        "Equal weight (10 ind.)": _metrics(backtest.summarize(evalp(_equal_weight(norm)))),
        "Full model (composite)": _metrics(backtest.summarize(evalp(scored[["cbsa_code", "year", "score"]]))),
    }
    comp = pd.DataFrame(rows).T.reset_index().rename(columns={"index": "model"})
    comp["best_single_name"] = ""
    comp.loc[comp.model == "Best single indicator", "best_single_name"] = best_key

    # uplift of the full model over each baseline (on 3-yr pooled τ)
    full_tau = comp.loc[comp.model == "Full model (composite)", "tau_3y"].iloc[0]
    comp["uplift_tau_3y_vs_full"] = full_tau - comp["tau_3y"]
    comp = comp.sort_values("tau_3y", ascending=False).reset_index(drop=True)
    return comp, singles_df


def _fmt(df, cols):
    df = df.copy()
    for c in cols:
        df[c] = df[c].map(lambda v: f"{v:.3f}")
    return df


def main() -> None:
    comp, singles = run()
    comp.to_csv(config.PROCESSED_DIR / "baseline_comparison.csv", index=False)
    singles.to_csv(config.PROCESSED_DIR / "baseline_singles.csv", index=False)

    print("=== P1: Full model vs. naive baselines (walk-forward, same years/metros) ===\n")
    print(f"{'Model':<32}{'3y tau':>8}{'3y P@10':>9}{'3y tau preCOVID':>17}{'1y tau':>8}{'uplift':>9}")
    print("  " + "-" * 83)
    for _, r in comp.iterrows():
        name = r["model"] + (f"  [{r['best_single_name']}]" if r["best_single_name"] else "")
        print(f"{name:<32}{r['tau_3y']:>8.3f}{r['prec_3y']:>9.2f}{r['tau_3y_preCOVID']:>17.3f}"
              f"{r['tau_1y']:>8.3f}{r['uplift_tau_3y_vs_full']:>9.3f}")

    print("\n=== Single indicators alone, by 3-yr pooled tau (P2 preview) ===\n")
    print(f"{'Indicator':<24}{'3y tau':>8}{'3y P@10':>9}{'1y tau':>8}")
    print("  " + "-" * 49)
    for _, r in singles.iterrows():
        print(f"{r['indicator']:<24}{r['tau_3y']:>8.3f}{r['prec_3y']:>9.2f}{r['tau_1y']:>8.3f}")

    print("\nReading it: 'uplift' = full-model 3y tau minus that baseline's. >0 means the")
    print("full model beats it. If the gap over equal-weight / best-single / persistence is")
    print("small, the hand-set composite isn't earning its complexity (V2 W1/W3/W6).")


if __name__ == "__main__":
    main()
