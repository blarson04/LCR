"""
ces_qa.py — v3 P1 data QA (pre-gate, permitted): can FRED's BLS/SAE metro
series supply CURRENT-year employment and wages for the 110-metro universe?

Checks three things, and ONLY these (no accuracy evaluation against the gate
metrics, per the 2026-07-06 pre-commitment):
  1. COVERAGE — for each universe metro, does a total-nonfarm employment series
     (and an average-hourly-earnings series) exist on FRED, and how fresh is it?
  2. AGREEMENT — historically, does SAE annual employment growth rank-agree
     with the finalized QCEW growth the model actually uses?
  3. WAGE AGREEMENT — does AHE growth rank-agree with BEA income growth?

Series discovery (verified against FRED):
  - avg hourly earnings, total private (NSA) IS constructible:
        SMU{state_fips}{cbsa5}0500000003
  - employment LEVELS are NOT under the SM pattern on FRED (only derived
    series like the 3-month change are); FRED files them under legacy
    name-based ids (e.g. AUST448NA), so employment is found via FRED search
    ("All Employees: Total Nonfarm in <city>") and filtered by state + units.
A few CBSAs were renumbered in 2023; SAE still uses the old codes — handled.

    .venv/Scripts/python.exe src/nowcast/ces_qa.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                    # noqa: E402
from src.ingest import fred      # noqa: E402

OUT = config.PROCESSED_DIR / "nowcast"

STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09",
    "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17",
    "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31",
    "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56",
}
# 2023 OMB renumbered CBSAs; SAE (like QCEW) files them under the OLD codes.
OLD_CBSA = {"17410": "17460", "19430": "19380", "28880": "39100"}


def _primary_state(title: str) -> str:
    return title.rsplit(",", 1)[-1].strip().split("-")[0].strip()


def _first_city(title: str) -> str:
    import re
    place = title.rsplit(",", 1)[0]
    return re.split(r"[-/]", place)[0].strip()


def _try_series(sid: str) -> pd.Series | None:
    try:
        s = fred.fetch_series(sid)
        return s if len(s) else None
    except Exception:
        return None


def _search_employment(client, title: str) -> str:
    """FRED-search the metro's total-nonfarm employment level series; return
    the series id ('' if none). Prefers seasonally adjusted, longest history."""
    city, st = _first_city(title), _primary_state(title)
    try:
        res = client.search(f"All Employees: Total Nonfarm in {city}")
    except Exception:
        return ""
    if res is None or not len(res):
        return ""
    cand = res[res["title"].str.startswith("All Employees: Total Nonfarm in")
               & res["title"].str.contains(f", {st}")
               & (res["frequency_short"] == "M")
               & (res["units_short"] == "Thous. of Persons")]
    if not len(cand):
        return ""
    cand = cand.copy()
    cand["sa"] = (cand["seasonal_adjustment_short"] == "SA").astype(int)
    cand = cand.sort_values(["sa", "observation_start"], ascending=[False, True])
    return str(cand.index[0])


def _annual_growth(s: pd.Series) -> pd.Series:
    annual = s.groupby(s.index.year).mean()
    return annual.pct_change().dropna()


def run() -> None:
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    universe = panel[["cbsa_code", "cbsa_title"]].drop_duplicates().reset_index(drop=True)
    qcew = panel[["cbsa_code", "year", "total_emp", "per_capita_income"]]

    client = fred.get_client()
    rows, emp_growth, ahe_growth = [], {}, {}
    for i, (_, m) in enumerate(universe.iterrows()):
        cbsa, title = m["cbsa_code"], m["cbsa_title"]
        st_fips = STATE_FIPS.get(_primary_state(title), "")
        candidates = [cbsa] + ([OLD_CBSA[cbsa]] if cbsa in OLD_CBSA else [])

        # Wages: constructible id, tried for both new and old CBSA codes.
        ahe, ahe_id = None, ""
        for code in candidates:
            sid_w = f"SMU{st_fips}{code}0500000003"
            ahe = _try_series(sid_w)
            if ahe is not None:
                ahe_id = sid_w
                break

        # Employment: legacy name-based ids -> FRED search.
        emp, emp_id = None, ""
        sid_e = _search_employment(client, title)
        if sid_e:
            emp = _try_series(sid_e)
            emp_id = sid_e if emp is not None else ""

        if emp is not None:
            emp_growth[cbsa] = _annual_growth(emp)
        if ahe is not None:
            ahe_growth[cbsa] = _annual_growth(ahe)

        rows.append({
            "cbsa_code": cbsa, "cbsa_title": title,
            "emp_series": emp_id, "emp_found": emp is not None,
            "emp_last_obs": (str(emp.index.max().date()) if emp is not None else ""),
            "ahe_series": ahe_id, "ahe_found": ahe is not None,
            "ahe_last_obs": (str(ahe.index.max().date()) if ahe is not None else ""),
        })
        if (i + 1) % 20 == 0:
            print(f"  probed {i+1}/{len(universe)} metros", flush=True)
        time.sleep(0.15)   # politeness: stay under FRED rate limits

    cov = pd.DataFrame(rows)
    cov.to_csv(OUT / "ces_qa_coverage.csv", index=False)

    # ---- agreement vs the finalized inputs the model uses -------------------
    def agreement(growth_map, final_col):
        per_year = []
        for y in range(2016, 2024):
            pairs = []
            fin = qcew[qcew.year == y].set_index("cbsa_code")[final_col]
            fin_prev = qcew[qcew.year == y - 1].set_index("cbsa_code")[final_col]
            fin_g = (fin / fin_prev - 1).dropna()
            for cbsa, g in growth_map.items():
                if y in g.index and cbsa in fin_g.index:
                    pairs.append((g.loc[y], fin_g.loc[cbsa]))
            if len(pairs) >= 30:
                a = np.array(pairs)
                per_year.append({"year": y, "n": len(pairs),
                                 "spearman": spearmanr(a[:, 0], a[:, 1])[0]})
        return pd.DataFrame(per_year)

    emp_ag = agreement(emp_growth, "total_emp")
    ahe_ag = agreement(ahe_growth, "per_capita_income")
    emp_ag.to_csv(OUT / "ces_qa_emp_agreement.csv", index=False)
    ahe_ag.to_csv(OUT / "ces_qa_ahe_agreement.csv", index=False)

    fresh_2025 = (cov["emp_last_obs"] >= "2025-12-01").sum()
    print("\n=== P1 data QA: FRED/SAE coverage for the 110-metro universe ===\n")
    print(f"  employment series found : {cov.emp_found.sum():>3}/{len(cov)}")
    print(f"    ...current into 2026  : {(cov['emp_last_obs'] >= '2026-01-01').sum():>3}")
    print(f"    ...through 2025       : {fresh_2025:>3}")
    print(f"  avg-hourly-earnings found: {cov.ahe_found.sum():>3}/{len(cov)}")
    print("\n  SAE employment growth vs finalized QCEW growth (rank agreement, per year):")
    print(emp_ag.to_string(index=False) if len(emp_ag) else "   (insufficient overlap)")
    print("\n  AHE wage growth vs finalized BEA income growth (rank agreement, per year):")
    print(ahe_ag.to_string(index=False) if len(ahe_ag) else "   (insufficient overlap)")
    if len(cov[~cov.emp_found]):
        print("\n  metros with NO employment series:")
        for _, r in cov[~cov.emp_found].iterrows():
            print(f"    {r['cbsa_code']}  {r['cbsa_title']}")
    print("\nQA only — no gate metrics were computed (per the 2026-07-06 pre-commitment).")


if __name__ == "__main__":
    run()
