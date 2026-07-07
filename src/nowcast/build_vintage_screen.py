"""
build_vintage_screen.py — produce + freeze the VALIDATED 2024-vintage screen.

Runs only because the v3.1 gate PASSED (decision log 2026-07-07). Builds the
2024 scoring row per the spec — all finalized inputs, single substitution
(PEP migration / ACS population; Cleveland & Dayton carry QCEW-derived
indicator values from 2023) — scores it through the unchanged v2 path, writes
the app-facing outputs, and freezes an immutable registry run.

    .venv/Scripts/python.exe src/nowcast/build_vintage_screen.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import indicators, normalize  # noqa: E402
from src import score as score_mod  # noqa: E402
from src.ingest import census_pep   # noqa: E402

VINTAGE_YEAR = 2024
OUT = config.PROCESSED_DIR / "vintage"
QCEW_GAP_CARRY = ("job_growth", "income_growth", "employment_diversity")


def build_indicators() -> pd.DataFrame:
    panel = indicators.load_panel()
    ind = indicators.compute_indicators(panel)
    pep = census_pep.build_pep_migration_panel()[["cbsa_code", "year", "pep_net_migration"]]

    m = (panel[["cbsa_code", "year", "population"]]
         .merge(pep, on=["cbsa_code", "year"], how="left"))
    m["pep_rate"] = m["pep_net_migration"] / m["population"]
    rate = m.set_index(["cbsa_code", "year"])["pep_rate"]

    iv = ind.set_index(["cbsa_code", "year"])
    ymask = iv.index.get_level_values("year") == VINTAGE_YEAR
    sub = rate.reindex(iv.index)
    iv.loc[ymask, "net_migration"] = sub[ymask].where(
        sub[ymask].notna(), iv.loc[ymask, "net_migration"])

    # Disclosed fallback: metros with the QCEW-2024 transition gap carry their
    # 2023 employment-derived indicator values.
    prev = iv.xs(VINTAGE_YEAR - 1, level="year")
    for k in QCEW_GAP_CARRY:
        cur = iv.loc[ymask, k]
        fill = prev[k].reindex(cur.index.get_level_values("cbsa_code")).to_numpy()
        iv.loc[ymask, k] = cur.where(cur.notna(), fill)
    return iv.reset_index()


def main() -> None:
    ind = build_indicators()
    scored = score_mod.score(normalize.normalize(ind))
    rank = scored[scored["year"] == VINTAGE_YEAR].sort_values("rank").reset_index(drop=True)
    assert rank["cbsa_code"].nunique() == 110
    cov = rank["n_indicators"].median()
    assert cov >= 8, f"unexpected coverage {cov}"

    OUT.mkdir(parents=True, exist_ok=True)
    rank.to_csv(OUT / f"vintage_{VINTAGE_YEAR}_ranking.csv", index=False)
    ind[ind.year == VINTAGE_YEAR].to_csv(OUT / f"vintage_{VINTAGE_YEAR}_raw.csv", index=False)
    normalize.normalize(ind).query("year == @VINTAGE_YEAR").to_csv(
        OUT / f"vintage_{VINTAGE_YEAR}_norm.csv", index=False)

    # ---- freeze to the registry (immutable) --------------------------------
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = config.PREDICTIONS_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    scored.to_parquet(run_dir / "scores.parquet", index=False)
    rank.to_csv(run_dir / "ranking.csv", index=False)
    (config.PROCESSED_DIR / "panel.parquet").rename  # no-op; keep panel where it is
    import shutil
    shutil.copy(config.PROCESSED_DIR / "panel.parquet", run_dir / "panel_snapshot.parquet")

    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.ROOT,
                                capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        commit = "unknown"
    top = rank.iloc[0]
    manifest = {
        "timestamp_utc": stamp, "model_version": config.MODEL_VERSION,
        "git_commit": commit, "score_year": VINTAGE_YEAR,
        "run_type": "validated_lagged_vintage",
        "gate": {"spec": "decision-log 2026-07-07 (v3.1)", "retention": 0.9552,
                 "mean_top10_overlap": 8.29, "result": "PASS"},
        "substitutions": {"net_migration": "Census PEP / ACS population",
                          "qcew_gap_carry": list(QCEW_GAP_CARRY) + ["(Cleveland, Dayton only)"]},
        "n_metros": int(rank["cbsa_code"].nunique()),
        "top_metro": top["cbsa_title"], "top_score": float(top["score"]),
        "weights": {k: v["weight"] for k, v in config.INDICATORS.items()},
        "files": {},
    }
    manifest["files"] = {p.name: sha(p) for p in sorted(run_dir.iterdir())}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    idx = pd.DataFrame([{ "timestamp_utc": stamp, "model_version": config.MODEL_VERSION,
                          "git_commit": commit, "score_year": VINTAGE_YEAR,
                          "n_metros": manifest["n_metros"], "top_metro": manifest["top_metro"]}])
    idx.to_csv(config.PREDICTIONS_DIR / "registry_index.csv", mode="a", header=False, index=False)

    print(f"VALIDATED {VINTAGE_YEAR}-vintage screen ({VINTAGE_YEAR}->{VINTAGE_YEAR+3}):")
    print(f"  frozen to {run_dir.relative_to(config.ROOT)}")
    print(f"  median indicator coverage: {cov:.0f}/8")
    print("\n  Top 10:")
    for _, r in rank.head(10).iterrows():
        print(f"   {int(r['rank']):>3}  {r['cbsa_title'][:44]:<46}{r['score']:+.3f}")
    print("\n  Bottom 5:")
    for _, r in rank.tail(5).iterrows():
        print(f"   {int(r['rank']):>3}  {r['cbsa_title'][:44]:<46}{r['score']:+.3f}")


if __name__ == "__main__":
    main()
