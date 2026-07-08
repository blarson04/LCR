"""
rank_intervals.py — input-noise rank intervals + tiers (P2, decision-log 2026-07-08).

The product oversold rank precision: scores correlate 0.72 between editions and
the churn traces to the two single-year growth inputs (edition agreement:
job_growth 0.288, income_growth 0.278; every other input >= 0.83). This module
turns that measured noise into the headline product object — a rank interval
and a tier for every metro — per the frozen perturbation spec:

    z' = rho * z + sqrt(1 - rho^2) * eps,   eps ~ N(0,1) iid per metro

applied to the within-year z-scores of job_growth and income_growth only
(rho = the measured edition agreement), so perturbed editions reproduce the
observed agreement with the actual edition by construction. B=1000 draws,
seed 42, frozen v2.0.0 weights, neutral fill unchanged. A metro's interval is
the [5th, 95th] percentile of its rank across draws; tiers are deterministic
functions of the interval (Leading cluster / Strong / Mid / Weak / Lagging).

Presentation layer only: no score, weight, or claim changes anywhere.

Output: data/processed/rank_intervals.csv (one row per edition x metro),
read by the site.

    .venv/Scripts/python.exe src/rank_intervals.py
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

B = 1000
SEED = config.RANDOM_SEED
# Measured edition agreement (2024-vintage vs 2025-current normalized inputs,
# Spearman, n=110) — the calibration constants frozen in the P2 spec entry.
RHO = {"job_growth": 0.288, "income_growth": 0.278}
INDICATORS = list(config.INDICATORS)
W = {k: v["weight"] for k, v in config.INDICATORS.items()}

OUT_CSV = config.PROCESSED_DIR / "rank_intervals.csv"

TIER_ORDER = ["Leading cluster", "Strong", "Mid", "Weak", "Lagging"]


def tier_of(lo: int, med: float) -> str:
    """Deterministic tier rule (P2 spec): Leading requires a plausible top-10
    seat AND a top-quartile median; the rest band by median rank."""
    if lo <= 10 and med <= 28:
        return "Leading cluster"
    if med <= 40:
        return "Strong"
    if med <= 70:
        return "Mid"
    if med <= 95:
        return "Weak"
    return "Lagging"


def intervals_for(norm_year: pd.DataFrame) -> pd.DataFrame:
    """Rank intervals for one edition's normalized frame (one year's rows).

    Returns [cbsa_code, rank_lo, rank_median, rank_hi, tier], ranks 1..N.
    """
    z = norm_year.set_index("cbsa_code")[INDICATORS].fillna(0.0)
    metros = z.index.to_numpy()
    base = sum(W[k] * z[k].to_numpy() for k in INDICATORS)   # the actual score

    rng = np.random.default_rng(SEED)
    n = len(metros)
    scores = np.tile(base, (B, 1))
    for k, rho in RHO.items():
        zk = z[k].to_numpy()
        eps = rng.standard_normal((B, n))
        zk_pert = rho * zk + np.sqrt(1.0 - rho ** 2) * eps
        scores += W[k] * (zk_pert - zk)

    # rank 1 = highest score, per draw
    order = np.argsort(-scores, axis=1)
    ranks = np.empty_like(order)
    rows = np.arange(B)[:, None]
    ranks[rows, order] = np.arange(1, n + 1)[None, :]

    lo = np.percentile(ranks, 5, axis=0).round().astype(int)
    med = np.median(ranks, axis=0)
    hi = np.percentile(ranks, 95, axis=0).round().astype(int)
    return pd.DataFrame({
        "cbsa_code": metros, "rank_lo": lo, "rank_median": med, "rank_hi": hi,
        "tier": [tier_of(l, m) for l, m in zip(lo, med)]})


def build_all() -> pd.DataFrame:
    """Intervals for every edition the site shows: the frozen-2023 accuracy
    ranking, the validated 2024 vintage, and the validated 2025 current."""
    editions = []

    norm = normalize.normalize()
    editions.append(("2023", norm[norm["year"] == score_mod.SCORE_YEAR]))

    vint = config.PROCESSED_DIR / "vintage" / "vintage_2024_norm.csv"
    if vint.exists():
        editions.append(("vintage_2024",
                         pd.read_csv(vint, dtype={"cbsa_code": str})))
    now = config.PROCESSED_DIR / "nowcast" / "nowcast_2025_norm.csv"
    if now.exists():
        editions.append(("current_2025",
                         pd.read_csv(now, dtype={"cbsa_code": str})))

    frames = []
    for label, frame in editions:
        iv = intervals_for(frame)
        iv.insert(0, "edition", label)
        frames.append(iv)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    out = build_all()
    out.to_csv(OUT_CSV, index=False)
    print(f"Rank intervals written: {OUT_CSV.relative_to(config.ROOT)} "
          f"({out['edition'].nunique()} editions x {out.groupby('edition').size().iloc[0]} metros, "
          f"B={B}, seed {SEED})")
    for ed, g in out.groupby("edition"):
        counts = g["tier"].value_counts().reindex(TIER_ORDER).fillna(0).astype(int)
        print(f"\n  {ed}: " + ", ".join(f"{t} {c}" for t, c in counts.items()))
        top = g.nsmallest(5, "rank_median")
        for _, r in top.iterrows():
            print(f"    {r['cbsa_code']}: median #{r['rank_median']:.0f}, "
                  f"90% interval [{r['rank_lo']}, {r['rank_hi']}] — {r['tier']}")


if __name__ == "__main__":
    main()
