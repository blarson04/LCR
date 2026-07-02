"""
census_pep.py — Census Population Estimates net domestic migration (v2.1 proxy).

The v2 model's most important indicator (net_migration) comes from IRS county
flows, which publish ~2 years late. The Census Population Estimates Program
(PEP) publishes a county-level *net domestic migration* component of change
annually, far sooner. This module ingests it as the fast PROXY for IRS
migration — the linchpin of the v2.1 nowcast (M1).

County-level, so it rolls up to metros through the same crosswalk IRS uses.

PEP "year Y" = the July Y-1 → July Y estimate. We use the 2010s vintage file
for years <= 2020 and the 2020s vintage for years >= 2021 (avoids the partial
2020 double-count between the two vintages).

No API key needed (flat CSVs, Latin-1).

    .venv/Scripts/python.exe src/ingest/census_pep.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config            # noqa: E402
from src import crosswalk  # noqa: E402

PEP_RAW_DIR = config.RAW_DIR / "pep"
PEP_RAW_DIR.mkdir(parents=True, exist_ok=True)

# (url, years-to-take) — 2010s vintage for <=2020, 2020s vintage for >=2021.
_BASE = "https://www2.census.gov/programs-surveys/popest/datasets"
PEP_FILES = [
    (f"{_BASE}/2010-2020/counties/totals/co-est2020-alldata.csv",
     "co-est2020-alldata.csv", range(2011, 2021)),
    (f"{_BASE}/2020-2024/counties/totals/co-est2024-alldata.csv",
     "co-est2024-alldata.csv", range(2021, 2025)),
]


def _fetch(url: str, name: str, *, refresh: bool = False) -> pd.DataFrame:
    cache = PEP_RAW_DIR / name
    if cache.exists() and not refresh:
        return pd.read_csv(cache, encoding="latin-1", dtype={"STATE": str, "COUNTY": str})
    resp = requests.get(url, timeout=120, headers={"User-Agent": "multifamily-screener research"})
    if resp.status_code != 200:
        raise RuntimeError(f"PEP download failed for {name} (status {resp.status_code}).")
    cache.write_bytes(resp.content)
    return pd.read_csv(cache, encoding="latin-1", dtype={"STATE": str, "COUNTY": str})


def _long_from_file(df: pd.DataFrame, years) -> pd.DataFrame:
    """Melt DOMESTICMIG<year> columns into long [county_fips, year, net_domestic_mig]."""
    df = df[df["COUNTY"].str.zfill(3) != "000"].copy()          # drop state rows
    df["county_fips"] = df["STATE"].str.zfill(2) + df["COUNTY"].str.zfill(3)
    keep = {}
    for y in years:
        col = f"DOMESTICMIG{y}"
        if col in df.columns:
            keep[y] = pd.to_numeric(df[col], errors="coerce")
    out = pd.DataFrame({"county_fips": df["county_fips"]})
    long = pd.concat([out.assign(year=y, net_domestic_mig=v) for y, v in keep.items()],
                     ignore_index=True)
    return long[["county_fips", "year", "net_domestic_mig"]]


def build_pep_migration_panel(*, refresh: bool = False) -> pd.DataFrame:
    """Metro-level PEP net domestic migration: [cbsa_code, cbsa_title, year, pep_net_migration]."""
    parts = [_long_from_file(_fetch(url, name, refresh=refresh), yrs)
             for url, name, yrs in PEP_FILES]
    county = pd.concat(parts, ignore_index=True)
    frames = []
    for yr, g in county.groupby("year"):
        metro = crosswalk.aggregate_counties_to_cbsa(g, "county_fips", ["net_domestic_mig"], how="sum")
        metro["year"] = yr
        frames.append(metro)
    panel = pd.concat(frames, ignore_index=True).rename(columns={"net_domestic_mig": "pep_net_migration"})
    return (panel[["cbsa_code", "cbsa_title", "year", "pep_net_migration"]]
            .sort_values(["cbsa_code", "year"]).reset_index(drop=True))


def _smoke_test() -> None:
    print("Census PEP net domestic migration smoke test.\n")
    panel = build_pep_migration_panel()
    print(f"  metro-years: {len(panel):,}  ({panel['cbsa_code'].nunique()} metros, "
          f"{panel['year'].min()}-{panel['year'].max()})")
    print(f"  cached to: {PEP_RAW_DIR.relative_to(config.ROOT)}\n")
    latest = panel["year"].max()
    recent = panel[panel["year"] == latest]
    print(f"  Top 6 metros by PEP net domestic in-migration, {latest}:")
    for _, r in recent.nlargest(6, "pep_net_migration").iterrows():
        print(f"    {r['pep_net_migration']:>+9,.0f}  {r['cbsa_title']}")
    print("\nOK — PEP migration ready; M1 tests it against IRS (the linchpin).")


if __name__ == "__main__":
    _smoke_test()
