"""
bls_ces.py — CES/SAE metro total-nonfarm employment via FRED (v3 P1 proxy).

Supplies the fast job-growth proxy for the nowcast: monthly metro employment,
annual-averaged, as year-over-year growth. Series ids are the name-based
legacy FRED ids discovered and QA'd by src/nowcast/ces_qa.py (110/110 metros,
rank agreement 0.90–0.96 vs finalized QCEW growth in every overlap year); the
mapping is read from data/processed/nowcast/ces_qa_coverage.csv.

Vintage caveat (carried to the docs): FRED serves the *current* CES vintage;
true real-time CES was unrevised and noisier. Same limitation as the PEP
migration proxy, disclosed rather than modeled.

    .venv/Scripts/python.exe src/ingest/bls_ces.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config              # noqa: E402
from src.ingest import fred  # noqa: E402

MAPPING_CSV = config.PROCESSED_DIR / "nowcast" / "ces_qa_coverage.csv"


def build_ces_job_growth_panel(*, refresh: bool = False) -> pd.DataFrame:
    """[cbsa_code, year, ces_job_growth] — YoY growth of annual-average CES
    total-nonfarm employment, for every universe metro with a mapped series."""
    mapping = pd.read_csv(MAPPING_CSV, dtype={"cbsa_code": str})
    mapping = mapping[mapping["emp_found"] & (mapping["emp_series"] != "")]

    frames = []
    for _, r in mapping.iterrows():
        try:
            s = fred.fetch_series(r["emp_series"], refresh=refresh)
        except Exception:
            continue
        annual = s.groupby(s.index.year).mean()
        growth = annual.pct_change().dropna()
        frames.append(pd.DataFrame({"cbsa_code": r["cbsa_code"],
                                    "year": growth.index.astype(int),
                                    "ces_job_growth": growth.values}))
    panel = pd.concat(frames, ignore_index=True)
    return panel.sort_values(["cbsa_code", "year"]).reset_index(drop=True)


if __name__ == "__main__":
    p = build_ces_job_growth_panel()
    print(f"CES job-growth panel: {len(p):,} metro-years, "
          f"{p['cbsa_code'].nunique()} metros, {p['year'].min()}–{p['year'].max()}")
    y25 = p[p["year"] == 2025]
    print(f"  2025 coverage: {len(y25)}/110 metros")
