"""
BEA ingest — income (Demand 8% + affordability denominator).

The Bureau of Economic Analysis publishes the most authoritative regional
income data. We use table CAINC1 (personal income, population, per-capita
income). BEA's API serves this at COUNTY level, not MSA, so — exactly like the
IRS and permits sources — we pull counties and roll them up to metros with the
shared crosswalk:

  personal_income (metro) = sum of county personal income
  population_bea  (metro) = sum of county population
  per_capita_income       = personal_income / population_bea

per_capita_income feeds two things: income growth (YoY, the 8% indicator) and
the income denominator of the rent-to-income affordability ratio.

Requires BEA_API_KEY in .env (BEA's API has no key-free path). Income arrives
in thousands of dollars (we convert to dollars).

    .venv/Scripts/python.exe src/ingest/bea.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config            # noqa: E402
from src import crosswalk  # noqa: E402

BEA_RAW_DIR = config.RAW_DIR / "bea"
BEA_RAW_DIR.mkdir(parents=True, exist_ok=True)

_BEA_URL = "https://apps.bea.gov/api/data"
_LINE = {"personal_income": 1, "population": 2}   # CAINC1 line codes
BEA_YEARS = list(range(2015, 2025))               # county vintage Y releases ~Nov Y+1; 2024 added 2026-07-07


def get_key() -> str:
    load_dotenv(config.ROOT / ".env")
    key = os.getenv("BEA_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "No BEA_API_KEY found.\n"
            "  1. Get a free key (instant): https://apps.bea.gov/API/signup/\n"
            "  2. Paste it into .env after BEA_API_KEY=\n"
        )
    return key


def _fetch_county_line(line_code: int, *, refresh: bool = False) -> pd.DataFrame:
    """
    Fetch one CAINC1 line (personal income or population) for all counties and
    all BEA_YEARS, caching the raw JSON. Returns [county_fips, year, value].
    """
    cache = BEA_RAW_DIR / f"cainc1_line{line_code}_to{max(BEA_YEARS)}.json"
    if cache.exists() and not refresh:
        raw = json.loads(cache.read_text())
    else:
        params = {
            "UserID": get_key(), "method": "GetData", "datasetname": "Regional",
            "TableName": "CAINC1", "GeoFips": "COUNTY", "LineCode": line_code,
            "Year": ",".join(str(y) for y in BEA_YEARS), "ResultFormat": "json",
        }
        resp = requests.get(_BEA_URL, params=params, timeout=120)
        results = resp.json().get("BEAAPI", {}).get("Results", {})
        if "Data" not in results:
            raise RuntimeError(f"BEA CAINC1 line {line_code} failed: {str(results)[:200]}")
        raw = results["Data"]
        cache.write_text(json.dumps(raw))

    df = pd.DataFrame(raw)
    df = df[df["GeoFips"].str[2:] != "000"]          # drop state/region aggregates
    df["value"] = pd.to_numeric(df["DataValue"].str.replace(",", ""), errors="coerce")
    df["year"] = df["TimePeriod"].astype(int)
    return df[["GeoFips", "year", "value"]].rename(columns={"GeoFips": "county_fips"})


# Connecticut geography splice (data-repair spec, decision-log 2026-07-07 D4):
# BEA's county table carries the DISCONTINUED CT counties with real values only
# through 2023 and the new planning regions only from 2024, so the standard
# crosswalk (planning regions) finds zeros before 2024. For years <= 2023 the
# old counties are mapped to the new CBSAs via the old OMB metro definitions;
# per-capita ratios damp the boundary difference across the 2023->2024 seam.
_CT_LEGACY_COUNTY_TO_CBSA = {
    "09003": "25540", "09007": "25540", "09013": "25540",   # Hartford+Middlesex+Tolland
    "09009": "35300",                                        # New Haven County
    "09001": "14860",                                        # Fairfield County
}
_CT_SPLICE_LAST_LEGACY_YEAR = 2023


def state_pc_income_growth(state_fips: str, year: int, *, refresh: bool = False) -> float:
    """YoY growth of STATE per-capita personal income (SAINC1 line 3) — the
    boundary-stable series used to chain CT metros across the 2023->2024
    geography seam (D4 QA amendment, decision-log 2026-07-07)."""
    cache = BEA_RAW_DIR / f"sainc1_pc_{state_fips}_{year}.json"
    if cache.exists() and not refresh:
        raw = json.loads(cache.read_text())
    else:
        params = {
            "UserID": get_key(), "method": "GetData", "datasetname": "Regional",
            "TableName": "SAINC1", "GeoFips": state_fips, "LineCode": 3,
            "Year": f"{year - 1},{year}", "ResultFormat": "json",
        }
        resp = requests.get(_BEA_URL, params=params, timeout=120)
        results = resp.json().get("BEAAPI", {}).get("Results", {})
        if "Data" not in results:
            raise RuntimeError(f"BEA SAINC1 {state_fips} failed: {str(results)[:200]}")
        raw = results["Data"]
        cache.write_text(json.dumps(raw))
    vals = {int(x["TimePeriod"]): float(str(x["DataValue"]).replace(",", ""))
            for x in raw}
    return vals[year] / vals[year - 1] - 1.0


_STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}


def state_pc_income_growth_panel(*, refresh: bool = False) -> pd.Series:
    """State per-capita personal income growth (SAINC1 line 3), indexed by
    (state_abbr, year) — the v0.4 income-chaining input (decision-log
    2026-07-08 spec). States publish months ahead of counties/metros."""
    cache = BEA_RAW_DIR / "sainc1_pc_states.json"
    if cache.exists() and not refresh:
        raw = json.loads(cache.read_text())
    else:
        params = {
            "UserID": get_key(), "method": "GetData", "datasetname": "Regional",
            "TableName": "SAINC1", "GeoFips": "STATE", "LineCode": 3,
            "Year": ",".join(str(y) for y in range(2014, 2026)),
            "ResultFormat": "json",
        }
        resp = requests.get(_BEA_URL, params=params, timeout=180)
        results = resp.json().get("BEAAPI", {}).get("Results", {})
        if "Data" not in results:
            raise RuntimeError(f"BEA SAINC1 states failed: {str(results)[:200]}")
        raw = results["Data"]
        cache.write_text(json.dumps(raw))
    df = pd.DataFrame(raw)
    df["pc"] = pd.to_numeric(df["DataValue"].astype(str).str.replace(",", ""),
                             errors="coerce")
    df["year"] = df["TimePeriod"].astype(int)
    df["abbr"] = (df["GeoName"].str.replace(" *", "", regex=False).str.strip()
                  .map(_STATE_ABBR))
    df = df.dropna(subset=["abbr"]).sort_values(["abbr", "year"])
    df["g"] = df.groupby("abbr")["pc"].pct_change()
    return df.dropna(subset=["g"]).set_index(["abbr", "year"])["g"]


def build_income_panel(*, refresh: bool = False) -> pd.DataFrame:
    """
    Metro income panel: [cbsa_code, cbsa_title, year, personal_income,
    population_bea, per_capita_income]. Income in dollars.
    """
    inc = _fetch_county_line(_LINE["personal_income"], refresh=refresh)
    pop = _fetch_county_line(_LINE["population"], refresh=refresh)
    inc["value"] *= 1000                              # thousands -> dollars

    county = (inc.rename(columns={"value": "personal_income"})
              .merge(pop.rename(columns={"value": "population_bea"}),
                     on=["county_fips", "year"], how="inner"))

    xwalk = crosswalk.load()
    titles = dict(zip(xwalk["cbsa_code"], xwalk["cbsa_title"]))
    frames = []
    for yr, g in county.groupby("year"):
        if yr <= _CT_SPLICE_LAST_LEGACY_YEAR:
            # Planning-region rows are zeros in these years; keep them out so
            # they can't overwrite the legacy-county aggregation with 0.
            legacy = g[g["county_fips"].isin(_CT_LEGACY_COUNTY_TO_CBSA)]
            g = g[~g["county_fips"].str.startswith("09")]
        else:
            legacy = g.iloc[0:0]
        metro = crosswalk.aggregate_counties_to_cbsa(
            g, "county_fips", ["personal_income", "population_bea"], how="sum")
        if len(legacy):
            lg = (legacy.assign(cbsa_code=legacy["county_fips"]
                                .map(_CT_LEGACY_COUNTY_TO_CBSA))
                  .groupby("cbsa_code")[["personal_income", "population_bea"]]
                  .sum().reset_index())
            lg["cbsa_title"] = lg["cbsa_code"].map(titles)
            metro = pd.concat([metro, lg], ignore_index=True)
        metro["year"] = yr
        frames.append(metro)
    panel = pd.concat(frames, ignore_index=True)
    panel["per_capita_income"] = panel["personal_income"] / panel["population_bea"]
    return (panel[["cbsa_code", "cbsa_title", "year", "personal_income",
                   "population_bea", "per_capita_income"]]
            .sort_values(["cbsa_code", "year"]).reset_index(drop=True))


def _smoke_test() -> None:
    print("BEA smoke test — metro per-capita personal income (county roll-up).\n")
    panel = build_income_panel()
    latest = panel["year"].max()
    print(f"  metro-years: {len(panel):,}  ({panel['cbsa_code'].nunique()} metros, "
          f"{panel['year'].min()}-{latest})")
    print(f"  cached to: {BEA_RAW_DIR.relative_to(config.ROOT)}\n")

    recent = panel[panel["year"] == latest]
    print(f"  Highest per-capita income metros, {latest}:")
    for _, r in recent.nlargest(6, "per_capita_income").iterrows():
        print(f"    ${r['per_capita_income']:>9,.0f}  {r['cbsa_title']}")
    aus = panel[panel["cbsa_title"].str.startswith("Austin")]
    if len(aus) >= 2:
        g = (aus["per_capita_income"].iloc[-1] / aus["per_capita_income"].iloc[0]) ** (
            1 / (aus["year"].iloc[-1] - aus["year"].iloc[0])) - 1
        print(f"\n  Austin per-capita income CAGR {aus['year'].iloc[0]}-{aus['year'].iloc[-1]}: {g*100:.1f}%/yr")
    print("\nOK — income ready (income-growth indicator + rent-to-income denominator).")


if __name__ == "__main__":
    _smoke_test()
