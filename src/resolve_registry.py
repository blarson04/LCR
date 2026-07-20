"""
resolve_registry.py — push-button scoring of frozen registry runs against
realized rent growth (v4 A5; the machinery behind the binding 2028
pre-commitment, decision-log 2026-07-08 governance rule 4).

For every frozen run in the registry (or one named via --stamp), this grades
the run's ranking against the ZORI rent growth that actually followed over the
primary 3-year horizon:

  - realized weighted tau (the standard harness metric, identical winsorize
    and tie-break rules),
  - precision@10 against the realized top quartile,
  - top-10 percentage-point edge vs the median market,
  - retention vs the finalized model recomputed on the then-current panel
    (the same ratio the gates promised), and the top-10 overlap with it.

Runs whose outcome window has not closed yet are reported as unresolvable
with the year they are waiting for — so in early 2029 (2028 ZORI closed) the
2025 screen's resolution is one command, not archaeology:

    .venv/Scripts/python.exe src/resolve_registry.py

Output: data/processed/resolutions.csv (one row per resolvable run) and a
printed report. Publishing a resolution remains a decision-log event; this
script computes, it does not publish.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import backtest            # noqa: E402
from src import score as score_mod  # noqa: E402

HORIZON = config.PRIMARY_HORIZON_YEARS
OUT = config.PROCESSED_DIR / "resolutions.csv"


def _runs() -> list[Path]:
    return sorted(p for p in config.PREDICTIONS_DIR.iterdir()
                  if p.is_dir() and (p / "manifest.json").exists()
                  and (p / "ranking.csv").exists())


def resolve_run(run_dir: Path, zori: pd.DataFrame,
                fin_scored: pd.DataFrame) -> dict:
    manifest = json.loads((run_dir / "manifest.json").read_text())
    T = int(manifest["score_year"])
    latest = int(zori["year"].max())
    base = {"run": run_dir.name, "score_year": T,
            "model_version": manifest.get("model_version", "?"),
            "window": f"{T}->{T + HORIZON}"}
    if T + HORIZON > latest:
        return base | {"resolvable": False,
                       "waiting_for": f"ZORI {T + HORIZON} (panel has {latest})"}

    rank = pd.read_csv(run_dir / "ranking.csv", dtype={"cbsa_code": str})
    pred = rank[["cbsa_code", "score"]]
    now = zori[zori.year == T][["cbsa_code", "zori"]].rename(columns={"zori": "z0"})
    fut = zori[zori.year == T + HORIZON][["cbsa_code", "zori"]].rename(columns={"zori": "z1"})
    df = pred.merge(now, on="cbsa_code").merge(fut, on="cbsa_code").dropna()
    df = df[df["z0"] > 0]
    df["realized"] = backtest._winsorize(df["z1"] / df["z0"] - 1.0)
    df = df.sort_values("cbsa_code").reset_index(drop=True)

    tau = backtest._weighted_tau_by_realized(df["score"].to_numpy(),
                                             df["realized"].to_numpy())
    p10 = backtest._precision_at_k(df["score"].to_numpy(),
                                   df["realized"].to_numpy(), config.PRECISION_K)
    top10 = df.nlargest(10, "score")
    pp_edge = float((top10["realized"].mean() - df["realized"].median()) * 100)

    # Finalized-model comparison on the then-current panel (the gates' ratio).
    fin = fin_scored[fin_scored["year"] == T][["cbsa_code", "score"]].rename(
        columns={"score": "fin_score"})
    m = df.merge(fin, on="cbsa_code", how="inner")
    tau_fin, retention, overlap = float("nan"), float("nan"), float("nan")
    if len(m) >= config.PRECISION_K:
        tau_fin = backtest._weighted_tau_by_realized(m["fin_score"].to_numpy(),
                                                     m["realized"].to_numpy())
        retention = tau / tau_fin if tau_fin else float("nan")
        overlap = len(set(m.nlargest(10, "score")["cbsa_code"])
                      & set(m.nlargest(10, "fin_score")["cbsa_code"]))
    return base | {"resolvable": True, "n_metros": len(df),
                   "realized_tau": tau, "precision_at_10": p10,
                   "top10_pp_edge_vs_median": pp_edge,
                   "finalized_model_tau": tau_fin, "retention": retention,
                   "top10_overlap_vs_finalized": overlap,
                   "zori_vintage": f"panel through {int(zori['year'].max())}"}


def main() -> None:
    zori = backtest._zori_lookup()
    fin_scored = score_mod.score()
    rows = [resolve_run(r, zori, fin_scored) for r in _runs()]
    out = pd.DataFrame(rows)
    resolved = out[out["resolvable"]]
    if len(resolved):
        resolved.to_csv(OUT, index=False)

    print(f"=== Frozen-run resolution report (target: {HORIZON}-yr ZORI growth) ===\n")
    for _, r in out.iterrows():
        if not r["resolvable"]:
            print(f"  {r['run']}  {r['window']}  NOT YET — waiting for {r['waiting_for']}")
        else:
            print(f"  {r['run']}  {r['window']}  tau {r['realized_tau']:+.3f}  "
                  f"p@10 {r['precision_at_10']:.2f}  top-10 edge "
                  f"{r['top10_pp_edge_vs_median']:+.1f}pp  "
                  f"retention {r['retention']:.1%}  overlap "
                  f"{r['top10_overlap_vs_finalized']:.0f}/10")
    if len(resolved):
        print(f"\nWritten: {OUT.relative_to(config.ROOT)}")
    print("\nA resolution publishes only via a dated decision-log entry "
          "(governance rule 4: whatever it shows).")


if __name__ == "__main__":
    main()
