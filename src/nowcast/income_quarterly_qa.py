"""
income_quarterly_qa.py — can a SAME-YEAR quarterly state chain stand in for
metro income growth mid-year?

Input-level QA only (the permitted pre-spec pattern; NO gate metrics). The
v0.5 spec neutral-filled income because the instruments available mid-year
QA'd near noise (stale annual state chain 0.133, flat carry -0.04) while the
same-year ANNUAL state chain that v0.4 uses scored 0.60 - but annual state
data for year T publishes in March T+1, too late for a mid-year build.

BEA also publishes QUARTERLY state personal income (~3 months after each
quarter; Q1 of T lands in late June of T). This QA asks: how well does the
state's Q1-over-Q1 total personal income growth rank-agree with the FINALIZED
metro per-capita income growth of the same year T, per overlap year? For
context it re-states the annual same-year chain and the stale chain on the
identical year set.

Output: data/processed/nowcast/income_quarterly_qa.csv

    .venv/Scripts/python.exe src/nowcast/income_quarterly_qa.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import requests
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import indicators          # noqa: E402
from src.ingest import bea          # noqa: E402

OUT = config.PROCESSED_DIR / "nowcast" / "income_quarterly_qa.csv"
CACHE = config.RAW_DIR / "bea" / "sqinc1_states_quarterly.json"


def state_q1_income_growth(*, refresh: bool = False) -> pd.Series:
    """(state_abbr, year) -> Q1-over-Q1 total personal income growth."""
    if CACHE.exists() and not refresh:
        raw = json.loads(CACHE.read_text())
    else:
        params = {
            "UserID": bea.get_key(), "method": "GetData",
            "datasetname": "Regional", "TableName": "SQINC1",
            "GeoFips": "STATE", "LineCode": 1,
            "Year": ",".join(str(y) for y in range(2014, 2027)),
            "ResultFormat": "json",
        }
        resp = requests.get(bea._BEA_URL, params=params, timeout=180)
        results = resp.json().get("BEAAPI", {}).get("Results", {})
        if "Data" not in results:
            raise RuntimeError(f"BEA SQINC1 failed: {str(results)[:300]}")
        raw = results["Data"]
        CACHE.write_text(json.dumps(raw))
    df = pd.DataFrame(raw)
    df = df[df["TimePeriod"].str.endswith("Q1")].copy()
    df["year"] = df["TimePeriod"].str[:4].astype(int)
    df["v"] = pd.to_numeric(df["DataValue"].astype(str).str.replace(",", ""),
                            errors="coerce")
    df["abbr"] = (df["GeoName"].str.replace(" *", "", regex=False).str.strip()
                  .map(bea._STATE_ABBR))
    df = df.dropna(subset=["abbr"]).sort_values(["abbr", "year"])
    df["g"] = df.groupby("abbr")["v"].pct_change()
    return df.dropna(subset=["g"]).set_index(["abbr", "year"])["g"]


def _rho(a: pd.Series, b: pd.Series) -> tuple[float, int]:
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(j) < 30:
        return float("nan"), len(j)
    return float(spearmanr(j["a"], j["b"]).statistic), len(j)


def main() -> None:
    ind = indicators.compute_indicators()
    fin = ind.pivot_table(index="cbsa_code", columns="year",
                          values="income_growth", aggfunc="first")
    states = (ind[["cbsa_code", "cbsa_title"]].drop_duplicates("cbsa_code")
              .set_index("cbsa_code")["cbsa_title"]
              .str.split(",").str[1].str.strip().str.split("-").str[0])

    q1 = state_q1_income_growth()
    sg_annual = bea.state_pc_income_growth_panel()

    rows = []
    print("Same-year instruments vs finalized metro income growth (Spearman):")
    print(f"  {'year':>5} {'Q1 chain':>9} {'annual chain':>13} {'stale chain':>12}")
    for y in range(2016, 2025):
        v_q1 = states.map(lambda s: q1.get((s, y), float("nan")))
        v_ann = states.map(lambda s: sg_annual.get((s, y), float("nan")))
        v_stale = states.map(lambda s: sg_annual.get((s, y - 1), float("nan")))
        r_q1, n = _rho(v_q1, fin.get(y, pd.Series(dtype=float)))
        r_ann, _ = _rho(v_ann, fin.get(y, pd.Series(dtype=float)))
        r_st, _ = _rho(v_stale, fin.get(y, pd.Series(dtype=float)))
        rows.append({"year": y, "rho_q1_chain": r_q1, "rho_annual_chain": r_ann,
                     "rho_stale_chain": r_st, "n": n})
        print(f"  {y:>5} {r_q1:>9.3f} {r_ann:>13.3f} {r_st:>12.3f}")

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print("\nMeans: "
          f"Q1 chain {out['rho_q1_chain'].mean():.3f} | "
          f"annual same-year chain {out['rho_annual_chain'].mean():.3f} "
          f"(the v0.4 instrument, bar 0.60) | "
          f"stale chain {out['rho_stale_chain'].mean():.3f}")
    print(f"Written: {OUT.relative_to(config.ROOT)}")
    print("No gate metrics were computed (instrument agreement only).")


if __name__ == "__main__":
    main()
