"""
tier3_gates.py — v3 build-spec Phase 3: the five pre-registered candidate gates.

Runs the frozen v2 three-part gate (see tier2_gate.gate) on each candidate that
survived the Phase 2 coverage audit, using the constructions fixed in the
2026-07-07 Phase 3 execution-spec decision-log entry:

    C1  CREMI MF Absorption.Units  annual sub-index value (level)
    C2  CREMI MF NOI.Index         annual sub-index value (level)
    C3  CREMI MF Asset.Value       annual sub-index value (level)
    C6a 1-yr delta of panel rental_vacancy (consecutive-year guard: no 2020 ACS)
    C6b 1-yr delta of CREMI MSAUR (same guard)

ONE attempt per candidate — this script is the attempt. Output: tier3_gates.csv.

    .venv/Scripts/python.exe src/tier3_gates.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                            # noqa: E402
from src import indicators, tier2_gate   # noqa: E402
from src.ingest import cremi             # noqa: E402


def _delta_1yr(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """[cbsa_code, year, cand] = 1-yr change in col, only across consecutive
    years (an ACS gap year must not silently become a 2-yr delta)."""
    d = df[["cbsa_code", "year", col]].dropna().sort_values(["cbsa_code", "year"])
    g = d.groupby("cbsa_code")
    d["cand"] = g[col].diff()
    d.loc[g["year"].diff() != 1, "cand"] = pd.NA
    return d[["cbsa_code", "year", "cand"]].dropna()


def candidate_frames() -> dict[str, tuple[pd.DataFrame, bool]]:
    """name -> (frame[cbsa_code, year, cand], inverse) per the execution spec."""
    mf = cremi.build_mf_annual()
    panel = indicators.load_panel()
    frames: dict[str, tuple[pd.DataFrame, bool]] = {}
    for key, var in [("C1 CREMI MF absorption", "Absorption.Units"),
                     ("C2 CREMI MF NOI", "NOI.Index"),
                     ("C3 CREMI MF asset price", "Asset.Value")]:
        f = mf[["cbsa_code", "year", var]].rename(columns={var: "cand"}).dropna()
        frames[key] = (f, False)                      # higher = better
    frames["C6a delta rental_vacancy"] = (_delta_1yr(panel, "rental_vacancy"), True)
    frames["C6b delta unemployment (MSAUR)"] = (_delta_1yr(mf, "MSAUR"), True)
    return frames


def main() -> None:
    results = []
    for name, (frame, inverse) in candidate_frames().items():
        r = tier2_gate.gate(name, frame=frame, inverse=inverse)
        tier2_gate._report(r)
        if r["flipped"]:
            print("  NOTE: auto_orient FLIPPED this candidate (disclosed).")
        print()
        results.append(r)
    out = pd.DataFrame([{
        "candidate": x["name"],
        "standalone_tau_3y": round(x["standalone_tau"], 3),
        "max_abs_corr": round(abs(x["top_corr"][0][1]), 3),
        "top_corr_indicator": x["top_corr"][0][0],
        "value_add_delta_tau": round(x["delta_tau"], 3),
        "ci_lo": round(x["ci"][0], 3), "ci_hi": round(x["ci"][1], 3),
        "auto_orient_flipped": x["flipped"],
        "adopted": x["adopt"]} for x in results])
    out.to_csv(config.PROCESSED_DIR / "tier3_gates.csv", index=False)
    print(f"wrote {config.PROCESSED_DIR / 'tier3_gates.csv'}")
    print(f"adoptions: {int(out.adopted.sum())} of {len(out)}")


if __name__ == "__main__":
    main()
