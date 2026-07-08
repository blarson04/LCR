"""
registry.py — freeze and timestamp each prediction run (pre-registration).

Every production run is frozen to predictions/<timestamp>/ and never edited:
the scores, the ranking, the input-data snapshot, and a manifest recording the
model version, git commit, weights, and the (locked) evaluation metric. As
real outcomes mature, these frozen calls can be scored against what actually
happened — a checkable, hindsight-proof public track record, which is the
project's core credibility differentiator.

Each run also appends one line to predictions/registry_index.csv so the history
is easy to browse.

    .venv/Scripts/python.exe src/registry.py            # freeze a run now
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import score as score_mod  # noqa: E402

INDEX_PATH = config.PREDICTIONS_DIR / "registry_index.csv"


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=config.ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def freeze_run(score_year: int = score_mod.SCORE_YEAR) -> Path:
    """Freeze the current model output to a new timestamped, immutable folder.
    Returns the run directory."""
    # P0 data-QA regime (decision-log 2026-07-08): nothing freezes for
    # publication without a green (or fully dispositioned) QA report that
    # matches the current panel build.
    from src import data_qa
    data_qa.assert_publication_clear()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = config.PREDICTIONS_DIR / stamp
    run_dir.mkdir(parents=True, exist_ok=False)   # never overwrite an existing run

    # Compute the run fresh and write the outputs.
    scored = score_mod.score()
    ranking = score_mod.ranking_for_year(score_year, scored)
    scored.to_parquet(run_dir / "scores.parquet", index=False)
    ranking.to_csv(run_dir / "ranking.csv", index=False)

    # Snapshot the exact inputs this run was built from.
    panel_src = config.PROCESSED_DIR / "panel.parquet"
    shutil.copy(panel_src, run_dir / "panel_snapshot.parquet")
    bt = config.PROCESSED_DIR / "backtest_summary.csv"
    if bt.exists():
        shutil.copy(bt, run_dir / "backtest_summary.csv")

    files = sorted(p.name for p in run_dir.iterdir())
    top = ranking.iloc[0]
    manifest = {
        "timestamp_utc": stamp,
        "model_version": config.MODEL_VERSION,
        "git_commit": _git_commit(),
        "score_year": score_year,
        "n_metros": int(ranking["cbsa_code"].nunique()),
        "top_metro": top["cbsa_title"],
        "top_score": float(top["score"]),
        # Lock the methodology into the record.
        "weights": {k: v["weight"] for k, v in config.INDICATORS.items()},
        "regimes": {k: list(v) for k, v in config.REGIMES.items()},
        "evaluation_metric": {
            "primary": "top-weighted Kendall's tau (scipy.stats.weightedtau)",
            "tau_rank_basis": config.TAU_RANK_BASIS,
            "headline": f"precision@{config.PRECISION_K} (top-quartile hit-rate)",
            "primary_horizon_years": config.PRIMARY_HORIZON_YEARS,
            "winsor_limits": list(config.WINSOR_LIMITS),
        },
        "files": {f: _sha256(run_dir / f) for f in files},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Append to the running index.
    idx_row = pd.DataFrame([{
        "timestamp_utc": stamp, "model_version": config.MODEL_VERSION,
        "git_commit": manifest["git_commit"], "score_year": score_year,
        "n_metros": manifest["n_metros"], "top_metro": manifest["top_metro"],
    }])
    idx_row.to_csv(INDEX_PATH, mode="a", header=not INDEX_PATH.exists(), index=False)

    return run_dir


def main() -> None:
    run_dir = freeze_run()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    print("Prediction run frozen (immutable, pre-registered):\n")
    print(f"  folder        : {run_dir.relative_to(config.ROOT)}")
    print(f"  model version : {manifest['model_version']}  (commit {manifest['git_commit']})")
    print(f"  score year    : {manifest['score_year']}")
    print(f"  metros        : {manifest['n_metros']}")
    print(f"  top metro     : {manifest['top_metro']}  (score {manifest['top_score']:+.3f})")
    print(f"  files         : {', '.join(manifest['files'])}")
    print(f"\n  index updated : {INDEX_PATH.relative_to(config.ROOT)}")
    print("\nOK — this run is now part of the auditable track record.")


if __name__ == "__main__":
    main()
