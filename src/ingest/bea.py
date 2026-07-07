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

    frames = []
    for yr, g in county.groupby("year"):
        metro = crosswalk.aggregate_counties_to_cbsa(
            g, "county_fips", ["personal_income", "population_bea"], how="sum")
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
