"""
precision_k.py — co-report precision@20 beside precision@10 (v4 A5, analysis only).

precision@10 moves in lumps of 0.1 with n=110 metros, so a single top-10 miss
swings a window by 10 points. This one-off appendix analysis computes the
composite's per-window precision@10 AND precision@20 (share of the model's
top-k landing in the realized top quartile) on the 3-yr target, plus pooled
means. Descriptive; no gate, no claims change; the headline metric stays
precision@10 as pre-registered.

Output: data/processed/precision_k.csv (consumed by paper_brief's appendix).

    .venv/Scripts/python.exe src/precision_k.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import backtest            # noqa: E402
from src import score as score_mod  # noqa: E402

OUT = config.PROCESSED_DIR / "precision_k.csv"
KS = (10, 20)


def main() -> None:
    scored = score_mod.score()
    pred_years = backtest.usable_pred_years(scored)
    zori = backtest._zori_lookup()
    latest = int(zori["year"].max())

    rows = []
    for T in pred_years:
        if T + 3 > latest:
            continue
        pred = scored[scored["year"] == T][["cbsa_code", "score"]]
        now = zori[zori.year == T][["cbsa_code", "zori"]].rename(columns={"zori": "z0"})
        fut = zori[zori.year == T + 3][["cbsa_code", "zori"]].rename(columns={"zori": "z1"})
        df = pred.merge(now, on="cbsa_code").merge(fut, on="cbsa_code").dropna()
        df = df[df["z0"] > 0]
        df["realized"] = backtest._winsorize(df["z1"] / df["z0"] - 1.0)
        df = df.sort_values("cbsa_code").reset_index(drop=True)
        row = {"pred_year": T, "n_metros": len(df)}
        for k in KS:
            row[f"precision_at_{k}"] = backtest._precision_at_k(
                df["score"].to_numpy(), df["realized"].to_numpy(), k)
        rows.append(row)

    out = pd.DataFrame(rows)
    pooled = {"pred_year": "POOLED", "n_metros": int(out["n_metros"].mean())}
    for k in KS:
        pooled[f"precision_at_{k}"] = float(out[f"precision_at_{k}"].mean())
    out = pd.concat([out, pd.DataFrame([pooled])], ignore_index=True)
    out.to_csv(OUT, index=False)

    print("precision@k co-report (3-yr target, composite):")
    print(f"  {'window':>7} {'n':>4} {'p@10':>6} {'p@20':>6}")
    for _, r in out.iterrows():
        print(f"  {str(r['pred_year']):>7} {r['n_metros']:>4.0f} "
              f"{r['precision_at_10']:>6.2f} {r['precision_at_20']:>6.2f}")
    print(f"\nWritten: {OUT.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
