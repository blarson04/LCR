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
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402
from src import crosswalk  # noqa: E402

BLS_RAW_DIR = config.RAW_DIR / "qcew"
BLS_RAW_DIR.mkdir(parents=True, exist_ok=True)

_AGG_TOTAL = 40   # MSA, all industries, all ownership
_AGG_SECTOR = 44  # MSA, by NAICS sector, by ownership
_AGG_TOTAL_COUNTY = 70   # county equivalents of the two MSA levels
_AGG_SECTOR_COUNTY = 74


# The 2023 OMB delineation renumbered a few CBSAs. QCEW filed them under the
# OLD codes through 2023 and switched to the NEW codes with the 2024 files
# (verified 2026-07-07: C1938/C1746 return 404 for 2024; C1943/C1741 exist).
# Dayton keeps the same three counties across the renumbering, so a year-aware
# area code yields a boundary-consistent series. Cleveland's new definition
# adds Ashtabula County, and Poughkeepsie/28880 has no pre-2024 MSA file at
# all, so both are built from COUNTY files on the current boundary instead
# (data-repair spec, decision-log 2026-07-07 D2/D3).
QCEW_YEAR_AWARE_OVERRIDES = {"19430": ("C1938", "C1943")}   # (<=2023, >=2024)
QCEW_NEW_CODE_FROM = 2024
# Metros whose 2023-delineation composition differs from their pre-2024 QCEW
# area files (verified against current-boundary county sums, decision-log
# 2026-07-08 D6): the area files would splice two boundaries mid-series, so
# these are built from county files on the current boundary for ALL years.
QCEW_COUNTY_ROLLUP = {
    "17410",   # Cleveland OH        (D3: new definition adds Ashtabula)
    "28880",   # Poughkeepsie NY     (D2: no pre-2024 MSA file)
    "35380",   # New Orleans LA      (D6: 2024 file -16.9% fake growth)
    "23420",   # Fresno CA           (D6: +15.6% fake growth; Madera absorbed)
    "49340",   # Worcester MA        (D6: -9.8% fake; lost CT portion)
    "36260",   # Ogden UT            (D6: -7.3% fake)
    "27140",   # Jackson MS          (D6: +7.2% fake)
    "39900",   # Reno NV             (D6: +6.1% fake)
}


def qcew_area_code(cbsa_code: str, year: int | None = None) -> str:
    """CBSA code (5-digit string) -> QCEW area code, e.g. '12420' -> 'C1242'."""
    cbsa_code = str(cbsa_code)
    if cbsa_code in QCEW_YEAR_AWARE_OVERRIDES:
        old, new = QCEW_YEAR_AWARE_OVERRIDES[cbsa_code]
        return new if (year is not None and year >= QCEW_NEW_CODE_FROM) else old
    return "C" + cbsa_code[:4]


# Politeness + resilience: BLS resets the connection if hit too fast (we fetch
# ~1,100 files to build the panel). Pause briefly between live downloads and
# retry transient network errors with backoff.
_DOWNLOAD_PAUSE = 0.2   # seconds between live downloads
_MAX_RETRIES = 4


def fetch_metro_year(cbsa_code: str, year: int, *, refresh: bool = False) -> pd.DataFrame:
    """Download one metro-year QCEW area file, caching raw CSV to data/raw/qcew/."""
    return _fetch_area_year(qcew_area_code(cbsa_code, year), year, refresh=refresh)


def _fetch_area_year(area: str, year: int, *, refresh: bool = False) -> pd.DataFrame:
    """Download one QCEW area-year file (MSA 'C####' or county FIPS), cached."""
    cache = BLS_RAW_DIR / f"{area}_{year}.csv"
    if cache.exists() and not refresh:
        return pd.read_csv(cache)

    url = f"https://data.bls.gov/cew/data/api/{year}/a/area/{area}.csv"
    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=60,
                                headers={"User-Agent": "multifamily-screener research"})
        except requests.exceptions.RequestException as e:
            last_err = e                          # transient (reset/timeout): back off + retry
            time.sleep(1.5 * (attempt + 1))
            continue
        if resp.status_code == 404:               # this metro genuinely has no QCEW area
            raise RuntimeError(f"QCEW has no area file for {area} {year} (404).")
        if resp.status_code != 200:
            last_err = RuntimeError(f"status {resp.status_code}")
            time.sleep(1.5 * (attempt + 1))
            continue
        cache.write_bytes(resp.content)
        time.sleep(_DOWNLOAD_PAUSE)
        return pd.read_csv(io.BytesIO(resp.content))

    raise RuntimeError(f"QCEW download failed for {area} {year} after "
                       f"{_MAX_RETRIES} tries: {last_err}")


def _member_counties(cbsa_code: str) -> list[str]:
    xw = crosswalk.load()
    return xw[xw["cbsa_code"] == str(cbsa_code)]["county_fips"].tolist()


def _totals_and_sectors(cbsa_code: str, year: int, *,
                        refresh: bool = False) -> tuple[float, float, pd.DataFrame]:
    """(total_emp, avg_annual_pay, sector cells) for one metro-year.

    MSA path: read the metro area file (agglvl 40/44). County-rollup path
    (QCEW_COUNTY_ROLLUP): read each member county's file (agglvl 70/74) and
    aggregate on the current boundary — identical cell semantics, so HHI and
    the AI-exposure share mean the same thing on both paths.
    """
    if str(cbsa_code) in QCEW_COUNTY_ROLLUP:
        tot_emp, tot_wages = 0.0, 0.0
        any_total, cells = False, []
        for fips in _member_counties(cbsa_code):
            df = _fetch_area_year(fips, year, refresh=refresh)
            t = df[(df["agglvl_code"] == _AGG_TOTAL_COUNTY) & (df["own_code"] == 0)]
            if len(t) and float(t["annual_avg_emplvl"].iloc[0]) > 0:
                e = float(t["annual_avg_emplvl"].iloc[0])
                tot_emp += e
                tot_wages += e * float(t["avg_annual_pay"].iloc[0])
                any_total = True
            cells.append(df[df["agglvl_code"] == _AGG_SECTOR_COUNTY]
                         [["own_code", "industry_code", "annual_avg_emplvl"]])
        sectors = (pd.concat(cells, ignore_index=True)
                   .groupby(["own_code", "industry_code"], as_index=False)
                   ["annual_avg_emplvl"].sum()) if cells else pd.DataFrame(
                       columns=["own_code", "industry_code", "annual_avg_emplvl"])
        total_emp = tot_emp if any_total else np.nan
        avg_pay = (tot_wages / tot_emp) if tot_emp > 0 else np.nan
        return total_emp, avg_pay, sectors

    df = fetch_metro_year(cbsa_code, year, refresh=refresh)
    total = df[df["agglvl_code"] == _AGG_TOTAL]
    total_emp = float(total["annual_avg_emplvl"].iloc[0]) if len(total) else np.nan
    avg_pay = float(total["avg_annual_pay"].iloc[0]) if len(total) else np.nan
    sectors = df[df["agglvl_code"] == _AGG_SECTOR][
        ["own_code", "industry_code", "annual_avg_emplvl"]]
    return total_emp, avg_pay, sectors


def summarize_metro_year(cbsa_code: str, year: int, *, refresh: bool = False) -> dict:
    """
    Reduce one metro-year QCEW file to the three scalars the panel needs:
    total_emp, avg_annual_pay, emp_hhi.
    """
    total_emp, avg_pay, sectors = _totals_and_sectors(cbsa_code, year, refresh=refresh)

    emp = pd.to_numeric(sectors["annual_avg_emplvl"], errors="coerce")
    emp = emp[emp > 0]                       # drop suppressed/zero sectors
    if emp.sum() > 0:
        shares = emp / emp.sum()
        emp_hhi = float((shares ** 2).sum())  # 1/N (diverse) .. 1 (single sector)
    else:
        emp_hhi = np.nan

    return {"cbsa_code": str(cbsa_code), "year": year,
            "total_emp": total_emp, "avg_annual_pay": avg_pay, "emp_hhi": emp_hhi}


# Highest gen-AI-exposure NAICS sectors (Information, Finance & Insurance,
# Professional/Scientific/Technical, Management of companies). An industry-level
# PROXY for occupational AI exposure — occupation-level OEWS blocks bot downloads
# (HTTP 403), so this uses the QCEW sector data already cached. (P7)
_AI_EXPOSED_SECTORS = {"51", "52", "54", "55"}


def ai_exposure_share(cbsa_code: str, year: int, *, refresh: bool = False) -> float:
    """Metro employment share in high-AI-exposure white-collar sectors (0..1)."""
    _, _, sec = _totals_and_sectors(cbsa_code, year, refresh=refresh)
    sec = sec[["industry_code", "annual_avg_emplvl"]].copy()
    sec["emp"] = pd.to_numeric(sec["annual_avg_emplvl"], errors="coerce")
    total = sec["emp"].sum()
    exposed = sec[sec["industry_code"].astype(str).isin(_AI_EXPOSED_SECTORS)]["emp"].sum()
    # A metro with literally zero Info/Finance/Prof/Mgmt employment is implausible,
    # so treat a hard 0 as QCEW disclosure suppression (missing), not a true zero.
    if not total or total <= 0 or exposed <= 0:
        return np.nan
    return float(exposed / total)


def build_ai_exposure_panel(cbsa_codes, years=range(2015, 2025), *,
                            refresh: bool = False) -> pd.DataFrame:
    """[cbsa_code, year, ai_exposure] for the given metros (reads cached QCEW)."""
    rows = []
    for cbsa in cbsa_codes:
        for yr in years:
            try:
                rows.append({"cbsa_code": str(cbsa), "year": yr,
                             "ai_exposure": ai_exposure_share(cbsa, yr, refresh=refresh)})
            except RuntimeError:
                pass
    return pd.DataFrame(rows)


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
                # Always surface skips: a missing metro-year becomes a NaN gap.
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
