"""
build_midyear_screen.py — staging outputs for the v0.5 mid-year 2026 screen.

The gate FAILED (2026-07-21: retention 82.74%, overlap 4.83/10), so per the
pre-committed consequence these outputs feed ONLY the labeled "Speculative
outlook" page. They are working CSVs, NOT registry runs: a failed
configuration never freezes and never carries the validated label.

    .venv/Scripts/python.exe src/nowcast/build_midyear_screen.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import normalize           # noqa: E402
from src import score as score_mod  # noqa: E402
from src.ingest import census_pep   # noqa: E402
from src.nowcast import midyear     # noqa: E402

YEAR = 2026
OUT = config.PROCESSED_DIR / "nowcast"


def main() -> None:
    gate = pd.read_csv(OUT / "gate2026_summary.csv")
    assert len(gate) == 1, "gate summary missing; the gate must run first"
    shared = midyear.load_shared()
    row = midyear.midyear_row(
        YEAR, shared, pep_override=census_pep.pep_migration_estimate_2025())
    full = pd.concat([shared["ind"][shared["ind"]["year"] != YEAR], row],
                     ignore_index=True)
    norm = normalize.normalize(full)
    scored = score_mod.score(norm)
    rank = (scored[scored["year"] == YEAR].sort_values("rank")
            .reset_index(drop=True))
    assert rank["cbsa_code"].nunique() == 110

    row.to_csv(OUT / f"midyear_{YEAR}_raw.csv", index=False)
    norm[norm["year"] == YEAR].to_csv(OUT / f"midyear_{YEAR}_norm.csv", index=False)
    rank.to_csv(OUT / f"midyear_{YEAR}_ranking.csv", index=False)

    v = gate.iloc[0]
    print(f"Mid-year {YEAR} staging outputs written (SPECULATIVE; gate "
          f"{v['verdict']}: retention {v['retention']:.2%}, overlap "
          f"{v['mean_top10_overlap']:.2f}/10).")
    print("\n  Top 10 (speculative 2026->2029 outlook):")
    for _, r in rank.head(10).iterrows():
        print(f"   {int(r['rank']):>3}  {r['cbsa_title'][:44]:<46}{r['score']:+.3f}")


if __name__ == "__main__":
    main()
