"""
backtest.py — does the screening framework actually predict rent growth?

This is the validation milestone. For each prediction year T we already have a
composite score (score.py). We compare that score against what ACTUALLY
happened to rents over the following window, ranked across metros.

Method (all per the decision log / build spec):
  - TARGET: forward rent growth from ZORI, ranked cross-sectionally. Primary
    horizon = 3 years (T -> T+3); 1 year reported as a contrast (if 3y beats
    1y, that's evidence the model captures fundamentals, not momentum).
  - WALK-FORWARD: score on year T only, test against the future, roll T forward.
    The model never sees the future.
  - WINSORIZE realized growth at the 1st/99th percentile within each window so a
    couple of blow-ups don't dominate.
  - REGIMES: tag each window by its start year's regime (pre_covid / shock /
    normalization) and report per-regime AND pooled.
  - METRICS:
      * top-weighted Kendall's tau (scipy.stats.weightedtau), weighted by
        REALIZED rank — concentrates reward on getting the true top markets right.
      * precision@10 — how many of the model's top 10 landed in the top quartile
        of realized rent growth.

CAVEAT (reported, not hidden): rent history starts ~2015, so there are only a
handful of overlapping windows. These are DIRECTIONAL evidence, not significance.

    .venv/Scripts/python.exe src/backtest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import weightedtau

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import score as score_mod  # noqa: E402

MIN_INDICATOR_COVERAGE = 8   # only predict from years where metros average >=8/10 indicators
PRECISION_TOP_QUANTILE = 0.75  # "top quartile" of realized growth


def _regime_of(year: int) -> str:
    for name, (lo, hi) in config.REGIMES.items():
        if lo <= year <= hi:
            return name
    return "unknown"


def _winsorize(s: pd.Series) -> pd.Series:
    lo, hi = s.quantile(config.WINSOR_LIMITS[0]), s.quantile(config.WINSOR_LIMITS[1])
    return s.clip(lo, hi)


def _weighted_tau_by_realized(pred: np.ndarray, realized: np.ndarray) -> float:
    """Top-weighted Kendall's tau, weighting by realized rank (rank 0 = the metro
    with the highest realized growth)."""
    order = np.argsort(-realized)                 # indices, best realized first
    ranks = np.empty(len(order), dtype=int)
    ranks[order] = np.arange(len(order))
    tau, _ = weightedtau(pred, realized, rank=ranks)
    return float(tau)


def _precision_at_k(pred: np.ndarray, realized: np.ndarray, k: int) -> float:
    """Fraction of the model's top-k metros that landed in the top quartile of
    realized growth."""
    if len(pred) < k:
        return np.nan
    threshold = np.quantile(realized, PRECISION_TOP_QUANTILE)
    top_k_idx = np.argsort(-pred)[:k]
    return float(np.mean(realized[top_k_idx] >= threshold))


def _zori_lookup() -> pd.DataFrame:
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    return panel[["cbsa_code", "year", "zori"]]


def run_backtest(horizons=(3, 1)) -> pd.DataFrame:
    """Return one row per (horizon, prediction year T) with tau, precision@10,
    n_metros, and regime."""
    scored = score_mod.score()
    zori = _zori_lookup()

    # Prediction years with enough indicator coverage to trust the score.
    cov = scored.groupby("year")["n_indicators"].median()
    usable_years = sorted(cov[cov >= MIN_INDICATOR_COVERAGE].index)
    latest_zori = int(zori["year"].max())

    rows = []
    for h in horizons:
        for T in usable_years:
            if T + h > latest_zori:
                continue
            pred = scored[scored["year"] == T][["cbsa_code", "score"]]
            now = zori[zori["year"] == T][["cbsa_code", "zori"]].rename(columns={"zori": "z0"})
            fut = zori[zori["year"] == T + h][["cbsa_code", "zori"]].rename(columns={"zori": "z1"})

            df = pred.merge(now, on="cbsa_code").merge(fut, on="cbsa_code").dropna()
            df = df[df["z0"] > 0]
            if len(df) < config.PRECISION_K:
                continue
            df["realized"] = _winsorize(df["z1"] / df["z0"] - 1.0)

            rows.append({
                "horizon": h, "pred_year": T, "regime": _regime_of(T),
                "n_metros": len(df),
                "weighted_tau": _weighted_tau_by_realized(df["score"].to_numpy(),
                                                          df["realized"].to_numpy()),
                "precision_at_10": _precision_at_k(df["score"].to_numpy(),
                                                   df["realized"].to_numpy(), config.PRECISION_K),
            })
    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    """Average the per-window metrics by horizon x regime, plus a pooled row."""
    out = []
    for h in sorted(results["horizon"].unique()):
        sub = results[results["horizon"] == h]
        for regime in list(config.REGIMES) :
            g = sub[sub["regime"] == regime]
            if len(g):
                out.append({"horizon": h, "regime": regime, "n_windows": len(g),
                            "mean_tau": g["weighted_tau"].mean(),
                            "mean_precision@10": g["precision_at_10"].mean()})
        out.append({"horizon": h, "regime": "POOLED", "n_windows": len(sub),
                    "mean_tau": sub["weighted_tau"].mean(),
                    "mean_precision@10": sub["precision_at_10"].mean()})
    return pd.DataFrame(out)


def main() -> None:
    results = run_backtest()
    summary = summarize(results)
    results.to_csv(config.PROCESSED_DIR / "backtest_windows.csv", index=False)
    summary.to_csv(config.PROCESSED_DIR / "backtest_summary.csv", index=False)

    print("=== Per-window results (walk-forward) ===\n")
    print(f"{'h':>2} {'T':>5} {'regime':<14}{'n':>4}{'w.tau':>8}{'prec@10':>9}")
    print("  " + "-" * 42)
    for _, r in results.iterrows():
        print(f"{r['horizon']:>2} {r['pred_year']:>5} {r['regime']:<14}{r['n_metros']:>4}"
              f"{r['weighted_tau']:>8.3f}{r['precision_at_10']:>9.2f}")

    print("\n=== Summary by horizon x regime ===\n")
    print(f"{'h':>2} {'regime':<14}{'windows':>8}{'mean tau':>10}{'mean prec@10':>14}")
    print("  " + "-" * 46)
    for _, r in summary.iterrows():
        tag = "*" if r["regime"] == "POOLED" else " "
        print(f"{r['horizon']:>2} {r['regime']:<14}{r['n_windows']:>8}"
              f"{r['mean_tau']:>10.3f}{r['mean_precision@10']:>14.2f} {tag}")

    print("\nReading it: weighted tau > 0 means the ranking is positively associated")
    print("with realized rent growth (top-weighted toward the true winners);")
    print("precision@10 is the share of the top 10 that hit the realized top quartile.")
    print("Few overlapping windows -> DIRECTIONAL evidence, not statistical proof.")


if __name__ == "__main__":
    main()
