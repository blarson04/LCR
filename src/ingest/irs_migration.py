"""
IRS migration ingest — net domestic migration (the 14% indicator, highest weight).

The IRS publishes county-to-county migration derived from where tax filers
lived in consecutive years. It's one of the highest-signal free datasets: a
leading demand indicator, less revision-prone than payroll data, and it
captures cost-of-living / tax / lifestyle moves that job numbers miss
(decision-log: "Migration ranked above job growth").

How we turn it into a metro number, per year:
  net_county = (US inflow to county) - (US outflow from county)
  net_metro  = sum of net_county over the counties in the metro
Intra-metro moves cancel in that sum, so this is true net migration into the
metro from the rest of the country. We use the "Total Migration-US" aggregate
rows (origin/destination code 97/0), which exclude foreign migration.

Counts: n2 = exemptions ~ persons (our headcount); n1 = returns ~ households.
We keep persons as the headline and households alongside.

File suffix YYZZ compares returns filed in 20YY and 20ZZ; we label the metro
year as the later year (e.g. countyinflow2223 -> migration year 2023).

No API key needed (flat CSVs, Latin-1 encoded).

    .venv/Scripts/python.exe src/ingest/irs_migration.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config            # noqa: E402
from src import crosswalk  # noqa: E402

IRS_RAW_DIR = config.RAW_DIR / "irs"
IRS_RAW_DIR.mkdir(parents=True, exist_ok=True)

_BASE = "https://www.irs.gov/pub/irs-soi"
# file suffix -> migration year (the later year of the compared pair)
FILE_YEARS = {
    "1516": 2016, "1617": 2017, "1718": 2018, "1819": 2019,
    "1920": 2020, "2021": 2021, "2122": 2022, "2223": 2023,
}
_US_TOTAL = (97, 0)   # statefips/countyfips code for "Total Migration-US"


def _fetch_csv(name: str, *, refresh: bool = False) -> pd.DataFrame:
    """Download one IRS CSV (Latin-1), caching the raw file to data/raw/irs/."""
    cache = IRS_RAW_DIR / name
    if cache.exists() and not refresh:
        return pd.read_csv(cache, encoding="latin-1")
    resp = requests.get(f"{_BASE}/{name}", timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"IRS download failed for {name} (status {resp.status_code}).")
    cache.write_bytes(resp.content)
    return pd.read_csv(cache, encoding="latin-1")


def _fips(state: pd.Series, county: pd.Series) -> pd.Series:
    """Combine numeric state + county codes into a 5-char FIPS string."""
    return (state.astype(int).map("{:02d}".format)
            + county.astype(int).map("{:03d}".format))


def net_migration_for_year(suffix: str, *, refresh: bool = False) -> pd.DataFrame:
    """
    County-level net domestic migration for one file pair.
    Returns columns [county_fips, in_persons, out_persons, net_persons,
    net_households, year].
    """
    inflow = _fetch_csv(f"countyinflow{suffix}.csv", refresh=refresh)
    outflow = _fetch_csv(f"countyoutflow{suffix}.csv", refresh=refresh)

    # Inflow "Total Migration-US": keyed by DESTINATION county (y2).
    inflow_us = inflow[(inflow["y1_statefips"] == _US_TOTAL[0])
                       & (inflow["y1_countyfips"] == _US_TOTAL[1])].copy()
    inflow_us["county_fips"] = _fips(inflow_us["y2_statefips"], inflow_us["y2_countyfips"])

    # Outflow "Total Migration-US": keyed by ORIGIN county (y1).
    outflow_us = outflow[(outflow["y2_statefips"] == _US_TOTAL[0])
                         & (outflow["y2_countyfips"] == _US_TOTAL[1])].copy()
    outflow_us["county_fips"] = _fips(outflow_us["y1_statefips"], outflow_us["y1_countyfips"])

    # IRS marks disclosure-suppressed counts as -1; treat those as 0.
    for d in (inflow_us, outflow_us):
        for c in ("n1", "n2"):
            d.loc[d[c] < 0, c] = 0

    df = (inflow_us[["county_fips", "n1", "n2"]]
          .rename(columns={"n1": "in_hh", "n2": "in_persons"})
          .merge(outflow_us[["county_fips", "n1", "n2"]]
                 .rename(columns={"n1": "out_hh", "n2": "out_persons"}),
                 on="county_fips", how="outer")
          .fillna(0))

    df["net_persons"] = df["in_persons"] - df["out_persons"]
    df["net_households"] = df["in_hh"] - df["out_hh"]
    df["year"] = FILE_YEARS[suffix]
    return df[["county_fips", "in_persons", "out_persons",
               "net_persons", "net_households", "year"]]


def build_migration_panel(*, refresh: bool = False) -> pd.DataFrame:
    """
    Metro-level net domestic migration across all years.
    Returns long panel [cbsa_code, cbsa_title, year, net_migration,
    net_migration_hh] — net_migration is persons.
    """
    frames = []
    for suffix in FILE_YEARS:
        county = net_migration_for_year(suffix, refresh=refresh)
        metro = crosswalk.aggregate_counties_to_cbsa(
            county, "county_fips", ["net_persons", "net_households"], how="sum")
        metro["year"] = FILE_YEARS[suffix]
        frames.append(metro)
    panel = pd.concat(frames, ignore_index=True)
    panel = panel.rename(columns={"net_persons": "net_migration",
                                  "net_households": "net_migration_hh"})
    return (panel[["cbsa_code", "cbsa_title", "year", "net_migration", "net_migration_hh"]]
            .sort_values(["cbsa_code", "year"]).reset_index(drop=True))


def _smoke_test() -> None:
    print("IRS migration smoke test — building metro net domestic migration.\n")
    panel = build_migration_panel()
    print(f"  metro-years: {len(panel):,}  ({panel['cbsa_code'].nunique()} metros, "
          f"{panel['year'].min()}-{panel['year'].max()})")
    print(f"  cached to: {IRS_RAW_DIR.relative_to(config.ROOT)}\n")

    latest = panel["year"].max()
    recent = panel[panel["year"] == latest].copy()
    print(f"  Top 8 metros by net domestic in-migration, {latest}:")
    for _, r in recent.nlargest(8, "net_migration").iterrows():
        print(f"    {r['net_migration']:>+9,.0f}  {r['cbsa_title']}")
    print(f"\n  Bottom 5 (net out-migration), {latest}:")
    for _, r in recent.nsmallest(5, "net_migration").iterrows():
        print(f"    {r['net_migration']:>+9,.0f}  {r['cbsa_title']}")
    print("\nOK — metro net migration ready (becomes a per-capita rate in indicators.py).")


if __name__ == "__main__":
    _smoke_test()
