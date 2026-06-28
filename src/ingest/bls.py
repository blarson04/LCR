"""
BLS ingest — jobs, wages, and employment diversity (Demand 12% + 8%, Resilience 5%).

Source: QCEW (Quarterly Census of Employment and Wages), the BLS near-census of
employer-reported jobs and wages. We use the QCEW *open-data* CSV files, one per
metro-year, which require no API key and carry everything we need in one place:

  - total_emp      : metro total employment (agglvl 40)  -> job growth (YoY in indicators.py)
  - avg_annual_pay : metro average annual pay (agglvl 40) -> wage growth (YoY)
  - emp_hhi        : Herfindahl index of employment across the 20 private NAICS
                     sectors (agglvl 44). HIGHER hhi = MORE concentrated = LESS
                     resilient; indicators.py flips it so higher = better.

Why QCEW over the BLS time-series API: near-census accuracy (vs the CES sample),
all three measures in one file, no metro code crosswalk, no rate limits. QCEW
lags ~6-9 months, which is fine for our annual panel and 3-year horizon.
(The BLS_API_KEY in .env is kept for optional cross-checks; v1 doesn't need it.)

QCEW metro area code = "C" + the first four digits of the 5-digit CBSA code.

    .venv/Scripts/python.exe src/ingest/bls.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402

BLS_RAW_DIR = config.RAW_DIR / "qcew"
BLS_RAW_DIR.mkdir(parents=True, exist_ok=True)

_AGG_TOTAL = 40   # MSA, all industries, all ownership
_AGG_SECTOR = 44  # MSA, by NAICS sector (private, own_code 5)


def qcew_area_code(cbsa_code: str) -> str:
    """CBSA code (5-digit string) -> QCEW area code, e.g. '12420' -> 'C1242'."""
    return "C" + str(cbsa_code)[:4]


def fetch_metro_year(cbsa_code: str, year: int, *, refresh: bool = False) -> pd.DataFrame:
    """Download one metro-year QCEW area file, caching raw CSV to data/raw/qcew/."""
    area = qcew_area_code(cbsa_code)
    cache = BLS_RAW_DIR / f"{area}_{year}.csv"
    if cache.exists() and not refresh:
        return pd.read_csv(cache)
    url = f"https://data.bls.gov/cew/data/api/{year}/a/area/{area}.csv"
    resp = requests.get(url, timeout=60, headers={"User-Agent": "multifamily-screener research"})
    if resp.status_code != 200:
        raise RuntimeError(f"QCEW download failed for {area} {year} (status {resp.status_code}).")
    cache.write_bytes(resp.content)
    return pd.read_csv(io.BytesIO(resp.content))


def summarize_metro_year(cbsa_code: str, year: int, *, refresh: bool = False) -> dict:
    """
    Reduce one metro-year QCEW file to the three scalars the panel needs:
    total_emp, avg_annual_pay, emp_hhi.
    """
    df = fetch_metro_year(cbsa_code, year, refresh=refresh)

    total = df[df["agglvl_code"] == _AGG_TOTAL]
    total_emp = float(total["annual_avg_emplvl"].iloc[0]) if len(total) else np.nan
    avg_pay = float(total["avg_annual_pay"].iloc[0]) if len(total) else np.nan

    sectors = df[df["agglvl_code"] == _AGG_SECTOR]
    emp = sectors["annual_avg_emplvl"]
    emp = emp[emp > 0]                       # drop suppressed/zero sectors
    if emp.sum() > 0:
        shares = emp / emp.sum()
        emp_hhi = float((shares ** 2).sum())  # 1/N (diverse) .. 1 (single sector)
    else:
        emp_hhi = np.nan

    return {"cbsa_code": str(cbsa_code), "year": year,
            "total_emp": total_emp, "avg_annual_pay": avg_pay, "emp_hhi": emp_hhi}


def build_employment_panel(cbsa_codes, years=range(2015, 2025), *,
                           refresh: bool = False, verbose: bool = False) -> pd.DataFrame:
    """
    Employment panel for the given metros. build_panel.py passes the frozen
    universe (~111 metros) so we don't fetch all 393. Returns long panel
    [cbsa_code, year, total_emp, avg_annual_pay, emp_hhi].
    """
    rows = []
    for cbsa in cbsa_codes:
        for yr in years:
            try:
                rows.append(summarize_metro_year(cbsa, yr, refresh=refresh))
            except RuntimeError as e:
                if verbose:
                    print(f"  [skip] {cbsa} {yr}: {str(e).splitlines()[0]}")
    return pd.DataFrame(rows).sort_values(["cbsa_code", "year"]).reset_index(drop=True)


def _smoke_test() -> None:
    # A few metros that contrast diversified vs concentrated economies.
    sample = {"12420": "Austin, TX", "35620": "New York, NY", "41940": "San Jose, CA",
              "39580": "Raleigh, NC", "26420": "Houston, TX"}
    print("BLS/QCEW smoke test — jobs, pay, and employment HHI (latest available year).\n")
    for cbsa, label in sample.items():
        # try the most recent year that exists, walking back if needed
        for yr in (2024, 2023):
            try:
                s = summarize_metro_year(cbsa, yr)
                print(f"  {label:<14} {yr}: emp={s['total_emp']:>10,.0f}  "
                      f"avg_pay=${s['avg_annual_pay']:>7,.0f}  HHI={s['emp_hhi']:.3f}")
                break
            except RuntimeError:
                continue
    print(f"\n  cached to: {BLS_RAW_DIR.relative_to(config.ROOT)}")
    print("OK — higher HHI = more concentrated economy; indicators.py flips it to 'diversity'.")


if __name__ == "__main__":
    _smoke_test()
