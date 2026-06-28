"""
score.py — weighted composite score + ranking (the first real output).

Composite = weighted sum of the directional z-scores from normalize.py, using
the hand-set v1 weights in config.py. Metros are then ranked within each year.

Missing-indicator rule: if a metro lacks an indicator in a year, its normalized
value is treated as 0 (the cross-metro average = neutral) so the metro is
neither rewarded nor penalized for missing data. We also report how many of the
10 indicators each metro actually had, so thinly-covered metros are visible.

Bucket subscores (Demand / Supply / Affordability / Momentum / Resilience) are
reported too, so a metro's score is explainable.

    .venv/Scripts/python.exe src/score.py            # prints the latest ranking
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import normalize           # noqa: E402

INDICATOR_COLS = normalize.INDICATOR_COLS
WEIGHTS = {k: v["weight"] for k, v in config.INDICATORS.items()}
BUCKETS = {k: v["bucket"] for k, v in config.INDICATORS.items()}
SCORE_YEAR = 2023   # latest year with broad coverage across all sources


def score(norm: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Return [cbsa_code, cbsa_title, year, score, rank, n_indicators, <bucket
    subscores>] for every metro-year. `rank` is within each year (1 = best).
    """
    if norm is None:
        norm = normalize.normalize()
    out = norm[["cbsa_code", "cbsa_title", "year"]].copy()

    # How many of the 10 indicators the metro actually has (data coverage).
    out["n_indicators"] = norm[INDICATOR_COLS].notna().sum(axis=1)

    # Weighted composite; missing indicators contribute 0 (neutral).
    z = norm[INDICATOR_COLS].fillna(0.0)
    out["score"] = sum(z[c] * WEIGHTS[c] for c in INDICATOR_COLS)

    # Bucket subscores (sum of weighted z within each bucket).
    for bucket in dict.fromkeys(BUCKETS.values()):
        cols = [c for c in INDICATOR_COLS if BUCKETS[c] == bucket]
        out[f"bucket_{bucket}"] = sum(z[c] * WEIGHTS[c] for c in cols)

    out["rank"] = out.groupby("year")["score"].rank(ascending=False, method="min").astype(int)
    return out.sort_values(["year", "rank"]).reset_index(drop=True)


def ranking_for_year(year: int = SCORE_YEAR, scored: pd.DataFrame | None = None) -> pd.DataFrame:
    if scored is None:
        scored = score()
    return scored[scored["year"] == year].sort_values("rank").reset_index(drop=True)


def save_scores() -> pd.DataFrame:
    """Compute scores for all years and write them to data/processed/ for the
    app to read. (M6's registry.py is the separate, frozen/timestamped record.)"""
    scored = score()
    scored.to_parquet(config.PROCESSED_DIR / "scores.parquet", index=False)
    ranking_for_year(SCORE_YEAR, scored).to_csv(
        config.PROCESSED_DIR / f"ranking_{SCORE_YEAR}.csv", index=False)
    return scored


def _print_ranking() -> None:
    scored = save_scores()
    rk = ranking_for_year(SCORE_YEAR, scored)
    bcols = [c for c in rk.columns if c.startswith("bucket_")]
    print(f"=== Metro screening ranking — {SCORE_YEAR} cross-section "
          f"({len(rk)} metros) ===\n")
    print(f"{'#':>3}  {'Metro':<42}{'score':>7}  {'cov':>3}")
    print("  " + "-" * 58)
    for _, r in rk.head(15).iterrows():
        title = r["cbsa_title"][:40]
        print(f"{r['rank']:>3}  {title:<42}{r['score']:>7.3f}  {r['n_indicators']:>2}/10")
    print("   ...")
    for _, r in rk.tail(5).iterrows():
        title = r["cbsa_title"][:40]
        print(f"{r['rank']:>3}  {title:<42}{r['score']:>7.3f}  {r['n_indicators']:>2}/10")

    print("\n  Top metro bucket breakdown (weighted z contribution):")
    top = rk.iloc[0]
    print(f"    {top['cbsa_title']}:")
    for c in bcols:
        print(f"      {c.replace('bucket_',''):<14} {top[c]:+.3f}")
    print("\nOK — first ranking produced. M4 backtests whether it actually predicts.")


if __name__ == "__main__":
    _print_ranking()
