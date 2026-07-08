"""
qcew_wage_qa.py — P4 proxy QA: can QCEW average-pay growth restore the
within-state income differentiation the state-chain proxy erases?

QA ONLY, exactly like the state-chain precedent (decision-log 2026-07-08 v0.4
entry): rank agreement of QCEW average-annual-pay growth against finalized BEA
metro per-capita income growth, every overlap year, NO gate metrics computed.
Context on record: CES average hourly earnings was rejected at 0.0-0.26
agreement; QCEW pay is a different instrument (near-census vs sample, annual
pay vs hourly earnings) and merits its own look. The D7 county rollup makes
the pay series boundary-consistent for every affected metro.

Adoption bar (frozen in the v4 handoff): mean rank agreement must BEAT the
state chain's 0.60 to justify a proxy_map v0.5 spec entry. Per the P6
friction rules, any resulting gate attempt waits for the next federal data
release and runs no sooner than the day after its spec entry.

    .venv/Scripts/python.exe src/nowcast/qcew_wage_qa.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402

OUT = config.PROCESSED_DIR / "nowcast" / "qcew_wage_qa.csv"
STATE_CHAIN_BAR = 0.60   # the incumbent proxy's mean agreement (v0.4 QA)


def run() -> pd.DataFrame:
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")

    def yoy(col):
        prev = panel[["cbsa_code", "year", col]].copy()
        prev["year"] += 1
        m = panel[["cbsa_code", "year", col]].merge(
            prev.rename(columns={col: "_p"}), on=["cbsa_code", "year"])
        m["g"] = m[col] / m["_p"] - 1.0
        return m[["cbsa_code", "year", "g"]].dropna()

    pay = yoy("avg_annual_pay").rename(columns={"g": "pay_growth"})
    inc = yoy("per_capita_income").rename(columns={"g": "income_growth"})
    m = pay.merge(inc, on=["cbsa_code", "year"])

    rows = []
    for y, g in m.groupby("year"):
        if len(g) >= 60:
            rho = spearmanr(g["pay_growth"], g["income_growth"])[0]
            rows.append({"year": int(y), "n": len(g), "spearman": round(float(rho), 3)})
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    return out


def main() -> None:
    out = run()
    mean = out["spearman"].mean()
    print("=== P4 QA: QCEW pay growth vs finalized BEA income growth (rank agreement) ===\n")
    print(out.to_string(index=False))
    print(f"\n  mean agreement: {mean:.3f}   adoption bar (state chain): {STATE_CHAIN_BAR:.2f}")
    print(f"  -> {'CLEARS the bar; a proxy_map v0.5 spec entry is justified'
          if mean > STATE_CHAIN_BAR else
          'does NOT clear the bar; the state chain stays, negative result recorded'}")
    print("\nQA only — no gate metrics were computed. Any gate attempt is subject to "
          "the P6 cooling-off and attempt-cap rules.")


if __name__ == "__main__":
    main()
