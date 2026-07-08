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


def _pop_long_from_file(df: pd.DataFrame, years) -> pd.DataFrame:
    """Melt POPESTIMATE<year> columns into long [county_fips, year, pep_pop]."""
    df = df[df["COUNTY"].str.zfill(3) != "000"].copy()          # drop state rows
    df["county_fips"] = df["STATE"].str.zfill(2) + df["COUNTY"].str.zfill(3)
    keep = {y: pd.to_numeric(df[f"POPESTIMATE{y}"], errors="coerce")
            for y in years if f"POPESTIMATE{y}" in df.columns}
    out = pd.DataFrame({"county_fips": df["county_fips"]})
    long = pd.concat([out.assign(year=y, pep_pop=v) for y, v in keep.items()],
                     ignore_index=True)
    return long[["county_fips", "year", "pep_pop"]]


def build_pep_population_panel(*, refresh: bool = False) -> pd.DataFrame:
    """Metro-level PEP population estimates: [cbsa_code, cbsa_title, year, pep_pop].

    Used ONLY by the data-QA regime as the independent sister series for ACS
    population (decision-log 2026-07-08, P0) — never a model input.
    """
    parts = [_pop_long_from_file(_fetch(url, name, refresh=refresh), yrs)
             for url, name, yrs in PEP_FILES]
    county = pd.concat(parts, ignore_index=True)
    frames = []
    for yr, g in county.groupby("year"):
        metro = crosswalk.aggregate_counties_to_cbsa(g, "county_fips", ["pep_pop"], how="sum")
        metro["year"] = yr
        frames.append(metro)
    panel = pd.concat(frames, ignore_index=True)
    return (panel[["cbsa_code", "cbsa_title", "year", "pep_pop"]]
            .sort_values(["cbsa_code", "year"]).reset_index(drop=True))


# --------------------------------------------------------------------------
# D8 boundary-consistent population + housing (decision-log 2026-07-08 D7/D8)
#
# The ACS1 metro API returns each survey year under the delineation current at
# release, silently mixing boundaries for every metro whose county membership
# changed. These builders reconstruct population and housing-unit series from
# COUNTY-level Census estimates rolled up on the CURRENT boundary (county FIPS
# are stable across delineations), the same pattern as the QCEW county rollup.
# --------------------------------------------------------------------------
HU_2010S_URL = (f"{_BASE}/2010-2020/housing/HU-EST2020_ALL.csv")
HU_2020S_URL = ("https://www2.census.gov/programs-surveys/popest/tables/"
                "2020-2024/housing/totals/CO-EST2024-HU.xlsx")


def _fetch_bytes(url: str, name: str, *, refresh: bool = False) -> Path:
    cache = PEP_RAW_DIR / name
    if not cache.exists() or refresh:
        resp = requests.get(url, timeout=120,
                            headers={"User-Agent": "multifamily-screener research"})
        if resp.status_code != 200:
            raise RuntimeError(f"download failed for {name} (status {resp.status_code})")
        cache.write_bytes(resp.content)
    return cache


def _county_name_to_fips() -> dict[str, str]:
    """'Autauga County, Alabama' -> '01001', from the cached delineation file
    (covers every county that belongs to a CBSA — all we ever roll up)."""
    raw = pd.read_excel(crosswalk.CROSSWALK_RAW_DIR / "list1_2023.xlsx", header=2)
    raw["CBSA Code"] = pd.to_numeric(raw["CBSA Code"], errors="coerce")
    raw = raw.dropna(subset=["CBSA Code"])
    fips = (raw["FIPS State Code"].astype(int).map("{:02d}".format)
            + raw["FIPS County Code"].astype(int).map("{:03d}".format))
    key = (raw["County/County Equivalent"].astype(str).str.strip() + ", "
           + raw["State Name"].astype(str).str.strip())
    return dict(zip(key, fips))


def build_county_pop_panel(*, refresh: bool = False) -> pd.DataFrame:
    """County population estimates, FIPS-keyed: [county_fips, year, pep_pop],
    2011-2020 from the 2010s vintage (legacy CT counties), 2020-2024 from the
    2020s vintage (CT planning regions). The overlap year 2020 keeps BOTH rows,
    tagged by `vintage`, so callers can chain across the CT seam."""
    frames = []
    for (url, name, _), years, vint in [
            (PEP_FILES[0], range(2011, 2021), "2010s"),
            (PEP_FILES[1], range(2020, 2025), "2020s")]:
        df = _fetch(url, name, refresh=refresh)
        df = df[df["COUNTY"].str.zfill(3) != "000"].copy()
        df["county_fips"] = df["STATE"].str.zfill(2) + df["COUNTY"].str.zfill(3)
        for y in years:
            col = f"POPESTIMATE{y}"
            if col in df.columns:
                frames.append(pd.DataFrame({
                    "county_fips": df["county_fips"], "year": y, "vintage": vint,
                    "pep_pop": pd.to_numeric(df[col], errors="coerce")}))
    return pd.concat(frames, ignore_index=True)


def build_county_hu_panel(*, refresh: bool = False) -> pd.DataFrame:
    """County housing-unit estimates, FIPS-keyed: [county_fips, year, vintage, hu].
    2015-2019 (+April 2020, stored as year 2020) from the 2010s vintage CSV;
    2020-2024 from the vintage-2024 table (county names -> FIPS via the
    delineation file; CT planning regions included)."""
    frames = []
    p10 = _fetch_bytes(HU_2010S_URL, "HU-EST2020_ALL.csv", refresh=refresh)
    h10 = pd.read_csv(p10, encoding="latin-1", dtype={"STATE": str, "COUNTY": str})
    h10 = h10[h10["SUMLEV"].astype(str).str.zfill(3) == "050"].copy()
    h10["county_fips"] = h10["STATE"].str.zfill(2) + h10["COUNTY"].str.zfill(3)
    for y in range(2015, 2020):
        frames.append(pd.DataFrame({
            "county_fips": h10["county_fips"], "year": y, "vintage": "2010s",
            "hu": pd.to_numeric(h10[f"HUESTIMATE{y}"], errors="coerce")}))
    # April 2020 census-day estimate, used only as the chaining endpoint.
    frames.append(pd.DataFrame({
        "county_fips": h10["county_fips"], "year": 2020, "vintage": "2010s",
        "hu": pd.to_numeric(h10["HUESTIMATE042020"], errors="coerce")}))

    p20 = _fetch_bytes(HU_2020S_URL, "CO-EST2024-HU.xlsx", refresh=refresh)
    h20 = pd.read_excel(p20, header=None, skiprows=4,
                        names=["geo", "base", 2020, 2021, 2022, 2023, 2024])
    h20 = h20[h20["geo"].astype(str).str.startswith(".")].copy()
    h20["key"] = h20["geo"].str.lstrip(".").str.strip()
    name_fips = _county_name_to_fips()
    h20["county_fips"] = h20["key"].map(name_fips)
    h20 = h20.dropna(subset=["county_fips"])
    for y in range(2020, 2025):
        frames.append(pd.DataFrame({
            "county_fips": h20["county_fips"], "year": y, "vintage": "2020s",
            "hu": pd.to_numeric(h20[y], errors="coerce")}))
    return pd.concat(frames, ignore_index=True)


def boundary_consistent_pop_hu(ct_legacy: dict[str, list[str]],
                               *, refresh: bool = False) -> pd.DataFrame:
    """Current-boundary metro population + housing units for every metro CBSA:
    [cbsa_code, year, pep_pop, pep_hu], years 2015-2024.

    Non-CT metros: county sums on the current membership (FIPS are stable).
    CT metros (`ct_legacy` = {cbsa: [legacy county FIPS]}): planning-region
    sums for 2020-2024; 2015-2019 back-cast from the planning-region 2020
    level using the legacy-county rollup's year-over-year growth (D4b/D5
    chaining pattern; decision-log 2026-07-08 D8).
    """
    xw = crosswalk.load()
    members = {c: g["county_fips"].tolist() for c, g in xw.groupby("cbsa_code")}
    pop = build_county_pop_panel(refresh=refresh)
    hu = build_county_hu_panel(refresh=refresh)

    def county_sum(frame, val, fips, year, vintage):
        sub = frame[(frame["county_fips"].isin(fips)) & (frame["year"] == year)
                    & (frame["vintage"] == vintage)]
        if len(sub) < len(fips) or sub[val].isna().any():
            return float("nan")           # incomplete rollup -> no value
        return float(sub[val].sum())

    rows = []
    for cbsa, fips in members.items():
        for year in range(2015, 2025):
            if cbsa in ct_legacy:
                continue                   # chained below
            vint_pop = "2010s" if year < 2020 else "2020s"
            vint_hu = "2010s" if year < 2020 else "2020s"
            rows.append({"cbsa_code": cbsa, "year": year,
                         "pep_pop": county_sum(pop, "pep_pop", fips, year, vint_pop),
                         "pep_hu": county_sum(hu, "hu", fips, year, vint_hu)})

    for cbsa, legacy in ct_legacy.items():
        fips = members[cbsa]               # planning regions (current boundary)
        out = {}
        for year in range(2020, 2025):
            out[year] = {"pep_pop": county_sum(pop, "pep_pop", fips, year, "2020s"),
                         "pep_hu": county_sum(hu, "hu", fips, year, "2020s")}
        # legacy-county growth 2015->2020, applied backward from the 2020 level
        for val, col, frame in (("pep_pop", "pep_pop", pop), ("pep_hu", "hu", hu)):
            levels = {y: county_sum(frame, col, legacy, y, "2010s")
                      for y in range(2015, 2021)}
            cur = out[2020][val]
            for y in range(2019, 2014, -1):
                g = levels[y + 1] / levels[y] - 1.0
                cur = cur / (1.0 + g)
                out.setdefault(y, {})[val] = cur
        for year, vals in out.items():
            rows.append({"cbsa_code": cbsa, "year": year, **vals})

    return (pd.DataFrame(rows).sort_values(["cbsa_code", "year"])
            .reset_index(drop=True))


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
