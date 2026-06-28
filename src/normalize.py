"""
normalize.py — make indicators comparable, and orient them so higher = better.

Two jobs, both essential and easy to get wrong:

  1. NORMALIZE WITHIN EACH YEAR. Z-score every indicator across metros, separately
     for each calendar year. This is the decision-log's core rule: normalize per
     period, NOT over the whole panel — so a common national shock (every metro's
     rent jumps in 2021) cancels out and only the metro-to-metro spread survives.

  2. APPLY DIRECTION. For "inverse" indicators (permits_to_stock, mf_pipeline,
     rent_to_income), a higher raw value is WORSE, so we flip the sign of the
     z-score. After this step, for EVERY indicator, a higher z-score = better.

Output: same [cbsa_code, cbsa_title, year] keys with each indicator replaced by
its directional z-score. NaNs stay NaN (handled at scoring).

    .venv/Scripts/python.exe src/normalize.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import indicators          # noqa: E402

INDICATOR_COLS = indicators.INDICATOR_COLS


def _zscore_within_year(s: pd.Series, year: pd.Series) -> pd.Series:
    """Z-score `s` across metros within each year. std uses ddof=0; if a year has
    no spread (std=0) the z-scores are 0 (all equal)."""
    grp = s.groupby(year)
    mean = grp.transform("mean")
    std = grp.transform("std", ddof=0)
    z = (s - mean) / std
    return z.where(std != 0, 0.0)


def normalize(ind: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return the indicator table with each indicator as a directional z-score
    (higher = better for all)."""
    if ind is None:
        ind = indicators.compute_indicators()

    out = ind[["cbsa_code", "cbsa_title", "year"]].copy()
    for col in INDICATOR_COLS:
        z = _zscore_within_year(ind[col], ind["year"])
        if config.INDICATORS[col]["inverse"]:
            z = -z                  # higher raw was worse -> flip so higher = better
        out[col] = z
    return out


def _smoke_test() -> None:
    norm = normalize()
    latest = 2023
    y = norm[norm["year"] == latest]
    print("normalize.py — directional z-scores within each year (higher = better).\n")
    # A correct z-score column has mean ~0 and std ~1 within the year.
    print(f"  {latest} sanity (each indicator should be ~mean 0, ~std 1):")
    for c in INDICATOR_COLS[:4]:
        print(f"    {c:<22} mean={y[c].mean():+.2f}  std={y[c].std(ddof=0):.2f}")
    print("\n  Direction check — Austin vs an oversupplied metro on permits_to_stock")
    print("  (inverse: LOW supply should give a POSITIVE z):")
    for name in ("Austin", "Cleveland"):
        r = y[y["cbsa_title"].str.startswith(name)]
        if len(r):
            print(f"    {name:<10} permits_to_stock z = {r.iloc[0]['permits_to_stock']:+.2f}")
    print("\nOK — normalized scores ready; score.py applies the weights.")


if __name__ == "__main__":
    _smoke_test()
