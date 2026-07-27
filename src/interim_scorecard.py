"""
interim_scorecard.py — grade the outstanding frozen calls at every horizon
already resolvable (spec: decision-log 2026-07-27; descriptive, no gate).

Three reads, each on the LATEST frozen registry run for its scoring year:
  2023 vintage   at h=1 (2023->2024) and h=2 (2023->2025), annual ZORI
  2024 vintage   at h=1 (2024->2025), annual ZORI
  2025 current   partial first year: same-months Jan-May rent growth,
                 2025 -> 2026, monthly ZORI (noisiest read, labeled)

Interim tracking only: the pre-committed full-window resolutions (mid-2027,
2028, early 2029) remain the real grades. Short horizons favor momentum and
are not the model's design target.

    .venv/Scripts/python.exe src/interim_scorecard.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import backtest            # noqa: E402

OUT = config.PROCESSED_DIR / "interim_scorecard.csv"


def _latest_run(score_year: int) -> Path | None:
    runs = []
    for p in sorted(config.PREDICTIONS_DIR.iterdir()):
        mf = p / "manifest.json"
        if p.is_dir() and mf.exists() and (p / "ranking.csv").exists():
            m = json.loads(mf.read_text())
            if int(m.get("score_year", -1)) == score_year:
                runs.append(p)
    return runs[-1] if runs else None


def _grade(pred: pd.DataFrame, realized: pd.Series) -> dict:
    df = (pred.set_index("cbsa_code")[["score"]]
          .join(realized.rename("realized"), how="inner").dropna())
    df = df.sort_index().reset_index()
    tau = backtest._weighted_tau_by_realized(df["score"].to_numpy(),
                                             df["realized"].to_numpy())
    p10 = backtest._precision_at_k(df["score"].to_numpy(),
                                   df["realized"].to_numpy(), config.PRECISION_K)
    top10 = df.nlargest(10, "score")
    pp = float((top10["realized"].mean() - df["realized"].median()) * 100)
    return {"n_metros": len(df), "tau": tau, "precision_at_10": p10,
            "top10_pp_edge": pp}


def _annual_growth(zori: pd.DataFrame, t0: int, t1: int) -> pd.Series:
    a = zori[zori.year == t0].set_index("cbsa_code")["zori"]
    b = zori[zori.year == t1].set_index("cbsa_code")["zori"]
    g = (b / a - 1.0).dropna()
    return backtest._winsorize(g)


def main() -> None:
    zori = backtest._zori_lookup()
    rows = []

    for year, horizons in ((2023, (1, 2)), (2024, (1,))):
        run = _latest_run(year)
        if run is None:
            continue
        pred = pd.read_csv(run / "ranking.csv", dtype={"cbsa_code": str})
        for h in horizons:
            g = _grade(pred[["cbsa_code", "score"]],
                       _annual_growth(zori, year, year + h))
            rows.append({"run": run.name, "screen": f"{year} vintage",
                         "window": f"{year}->{year + h}",
                         "read": f"{h}-year interim (of 3)", **g})

    run25 = _latest_run(2025)
    if run25 is not None:
        from src.nowcast.midyear_qa import monthly_zori_by_cbsa, same_months_yoy
        pred = pd.read_csv(run25 / "ranking.csv", dtype={"cbsa_code": str})
        g_my = same_months_yoy(monthly_zori_by_cbsa(), "zori", 2026)
        g = _grade(pred[["cbsa_code", "score"]], backtest._winsorize(g_my))
        rows.append({"run": run25.name, "screen": "2025 current",
                     "window": "2025->May 2026",
                     "read": "partial first year (of 3)", **g})

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print("=== Interim scorecard (NOT the pre-committed resolutions) ===\n")
    print(f"{'screen':<14}{'window':<16}{'read':<26}{'tau':>7}{'p@10':>7}"
          f"{'pp edge':>9}")
    for _, r in out.iterrows():
        print(f"{r['screen']:<14}{r['window']:<16}{r['read']:<26}"
              f"{r['tau']:>7.3f}{r['precision_at_10']:>7.2f}"
              f"{r['top10_pp_edge']:>+9.1f}")
    print("\nShort horizons favor momentum and are not the design target; the "
          "full-window resolutions (mid-2027, 2028, early 2029) remain the "
          "real grades.")
    print(f"Written: {OUT.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
