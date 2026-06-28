"""
Building permits ingest — the Supply bucket (permits-to-stock 17% + MF pipeline 8%).

Supply is the model's contrarian edge: heavy permitting is a strong NEGATIVE
near term (the recent Sunbelt oversupply is the case study). The Census
Building Permits Survey (BPS) reports permitted housing units by county and
structure size. We split out:
  - total_units : all permitted units (1-unit + 2 + 3-4 + 5+) -> permits-to-stock
  - mf_units    : 5+ unit structures only            -> multifamily pipeline
The housing-stock denominator (ACS) is joined later in indicators.py; here we
just produce clean permit counts per metro-year.

BPS county flat files have two header rows then data; columns come in
(Bldgs, Units, Value) triples per structure size, followed by "reported-only"
triples we ignore (we want the imputed totals).

No API key needed (flat .txt files).

    .venv/Scripts/python.exe src/ingest/permits.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config            # noqa: E402
from src import crosswalk  # noqa: E402

BPS_RAW_DIR = config.RAW_DIR / "bps"
BPS_RAW_DIR.mkdir(parents=True, exist_ok=True)

_BASE = "https://www2.census.gov/econ/bps/County"
PERMIT_YEARS = range(2015, 2026)   # try these; missing years are skipped

# Column positions in the county BPS file (0-indexed). The "Units" column of
# each structure-size group is what we sum.
_COL = {"state": 1, "county": 2, "units_1u": 7, "units_2u": 10,
        "units_34": 13, "units_5p": 16}


def fetch_year(year: int, *, refresh: bool = False) -> pd.DataFrame:
    """
    One year of county permits. Returns [county_fips, total_units, mf_units, year].
    `mf_units` = 5+ unit structures; `total_units` = all sizes.
    """
    name = f"co{year}a.txt"
    cache = BPS_RAW_DIR / name
    if cache.exists() and not refresh:
        text = cache.read_text()
    else:
        resp = requests.get(f"{_BASE}/{name}", timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"BPS download failed for {name} (status {resp.status_code}).")
        text = resp.text
        cache.write_text(text)

    # Two header rows + one blank line precede the data.
    raw = pd.read_csv(io.StringIO(text), header=None, skiprows=3)

    out = pd.DataFrame({
        "county_fips": (raw[_COL["state"]].astype(int).map("{:02d}".format)
                        + raw[_COL["county"]].astype(int).map("{:03d}".format)),
        "units_1u": pd.to_numeric(raw[_COL["units_1u"]], errors="coerce"),
        "units_2u": pd.to_numeric(raw[_COL["units_2u"]], errors="coerce"),
        "units_34": pd.to_numeric(raw[_COL["units_34"]], errors="coerce"),
        "mf_units": pd.to_numeric(raw[_COL["units_5p"]], errors="coerce"),
    }).fillna(0)
    out["total_units"] = out[["units_1u", "units_2u", "units_34", "mf_units"]].sum(axis=1)
    out["year"] = year
    return out[["county_fips", "total_units", "mf_units", "year"]]


def build_permits_panel(years=PERMIT_YEARS, *, refresh: bool = False) -> pd.DataFrame:
    """
    Metro-level permits across all available years.
    Returns long panel [cbsa_code, cbsa_title, year, total_units, mf_units].
    """
    frames = []
    for yr in years:
        try:
            county = fetch_year(yr, refresh=refresh)
        except RuntimeError as e:
            print(f"  [skip] {yr}: {str(e).splitlines()[0]}")
            continue
        metro = crosswalk.aggregate_counties_to_cbsa(
            county, "county_fips", ["total_units", "mf_units"], how="sum")
        metro["year"] = yr
        frames.append(metro)
    panel = pd.concat(frames, ignore_index=True)
    return (panel[["cbsa_code", "cbsa_title", "year", "total_units", "mf_units"]]
            .sort_values(["cbsa_code", "year"]).reset_index(drop=True))


def _smoke_test() -> None:
    print("Building permits smoke test — metro permitted units by year.\n")
    panel = build_permits_panel()
    print(f"  metro-years: {len(panel):,}  ({panel['cbsa_code'].nunique()} metros, "
          f"{panel['year'].min()}-{panel['year'].max()})")
    print(f"  cached to: {BPS_RAW_DIR.relative_to(config.ROOT)}\n")

    latest = panel["year"].max()
    recent = panel[panel["year"] == latest].copy()
    recent["mf_share"] = recent["mf_units"] / recent["total_units"]
    print(f"  Top 8 metros by total permitted units, {latest}:")
    for _, r in recent.nlargest(8, "total_units").iterrows():
        print(f"    {r['total_units']:>9,.0f} total  ({r['mf_share']*100:4.0f}% multifamily)  {r['cbsa_title']}")
    print("\nOK — permit counts ready; permits-to-stock ratio is built in indicators.py.")


if __name__ == "__main__":
    _smoke_test()
