"""
Census ingest — the universe backbone.

The Census Bureau supplies the data that *defines which metros exist* for us:
population (the 500k gate and the population-growth indicator), and later
housing stock (the permits-ratio denominator) and income. M2 starts with
population because every other source joins onto the metro list it produces.

We pull from the American Community Survey 1-year estimates (ACS1), which give
one population value per metro per year. Note ACS1 has **no 2020 release**
(COVID data-collection disruption); the panel builder handles that gap.

Geography note: the Census "metropolitan statistical area/micropolitan
statistical area" universe contains BOTH Metro and Micro areas. We keep only
Metro areas (decision-log: "MSAs, not Micropolitan"), detected by the NAME
ending in "Metro Area".

Mirrors src/ingest/fred.py: key from .env, raw responses cached to
data/raw/census/, clear errors, runnable smoke test.

    .venv/Scripts/python.exe src/ingest/census.py
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
import config  # noqa: E402

CENSUS_RAW_DIR = config.RAW_DIR / "census"
CENSUS_RAW_DIR.mkdir(parents=True, exist_ok=True)

# Census geography keyword for metro/micro areas, and the variables we use.
_CBSA_GEO = "metropolitan statistical area/micropolitan statistical area"
_POP_VAR = "B01003_001E"   # ACS table B01003: total population
_HU_VAR = "B25001_001E"    # ACS table B25001: total housing units (permits denominator)

# ACS1 release years we attempt for the population panel (2020 has no ACS1).
ACS1_YEARS = (2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023)


def get_key() -> str:
    """Return the Census API key, or raise a clear error if it's missing."""
    load_dotenv(config.ROOT / ".env")
    key = os.getenv("CENSUS_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "No CENSUS_API_KEY found.\n"
            "  1. Request a free key (emailed to you): https://api.census.gov/data/key_signup.html\n"
            "  2. Paste it into .env after CENSUS_API_KEY=\n"
        )
    return key


def fetch_acs1(year: int, variables: list[str], *, refresh: bool = False) -> pd.DataFrame:
    """
    Fetch ACS1 `variables` for every CBSA in `year`, caching the raw JSON to
    data/raw/census/acs1_<year>_<vars>.json.

    Returns a tidy DataFrame with one row per CBSA: the requested variables
    plus 'cbsa_code', 'name', and 'year'. Metro/Micro are NOT yet filtered.
    """
    tag = "-".join(variables)
    cache = CENSUS_RAW_DIR / f"acs1_{year}_{tag}.json"

    if cache.exists() and not refresh:
        raw = json.loads(cache.read_text())
    else:
        url = f"https://api.census.gov/data/{year}/acs/acs1"
        params = {
            "get": "NAME," + ",".join(variables),
            "for": f"{_CBSA_GEO}:*",
            "key": get_key(),
        }
        resp = requests.get(url, params=params, timeout=60)
        if resp.status_code != 200 or not resp.text.lstrip().startswith("["):
            raise RuntimeError(
                f"Census ACS1 {year} request failed (status {resp.status_code}). "
                f"First 200 chars of response:\n{resp.text[:200]}"
            )
        raw = resp.json()
        cache.write_text(json.dumps(raw))   # cache raw API response

    # raw[0] is the header row; the rest are data rows.
    header, rows = raw[0], raw[1:]
    df = pd.DataFrame(rows, columns=header)
    df = df.rename(columns={"NAME": "name", _CBSA_GEO: "cbsa_code"})
    for v in variables:
        df[v] = pd.to_numeric(df[v], errors="coerce")
    df["year"] = year
    return df


def fetch_population(year: int, *, refresh: bool = False) -> pd.DataFrame:
    """One year of metro population: columns [cbsa_code, name, population, year]."""
    df = fetch_acs1(year, [_POP_VAR], refresh=refresh)
    df = df[df["name"].str.endswith("Metro Area")]          # drop Micro areas
    df = df.rename(columns={_POP_VAR: "population"})
    return df[["cbsa_code", "name", "population", "year"]].reset_index(drop=True)


def fetch_housing_units(year: int, *, refresh: bool = False) -> pd.DataFrame:
    """One year of metro housing stock: [cbsa_code, name, housing_units, year]."""
    df = fetch_acs1(year, [_HU_VAR], refresh=refresh)
    df = df[df["name"].str.endswith("Metro Area")]          # drop Micro areas
    df = df.rename(columns={_HU_VAR: "housing_units"})
    return df[["cbsa_code", "name", "housing_units", "year"]].reset_index(drop=True)


def build_housing_panel(years=ACS1_YEARS, *, refresh: bool = False) -> pd.DataFrame:
    """
    Stack housing stock across ACS1 years: one row per (cbsa_code, year). This
    is the denominator of the permits-to-stock supply indicator. Years with no
    ACS1 release are skipped.
    """
    frames = []
    for yr in years:
        try:
            frames.append(fetch_housing_units(yr, refresh=refresh))
        except RuntimeError as e:
            print(f"  [skip] {yr}: {e.__class__.__name__} — {str(e).splitlines()[0]}")
    panel = pd.concat(frames, ignore_index=True)
    return panel.sort_values(["cbsa_code", "year"]).reset_index(drop=True)


def build_population_panel(years=ACS1_YEARS, *, refresh: bool = False) -> pd.DataFrame:
    """
    Stack population across all available ACS1 years into a long panel:
    one row per (cbsa_code, year). This feeds both the universe gate and the
    population-growth indicator. Years with no ACS1 release are skipped.
    """
    frames = []
    for yr in years:
        try:
            frames.append(fetch_population(yr, refresh=refresh))
        except RuntimeError as e:
            print(f"  [skip] {yr}: {e.__class__.__name__} — {str(e).splitlines()[0]}")
    panel = pd.concat(frames, ignore_index=True)
    return panel.sort_values(["cbsa_code", "year"]).reset_index(drop=True)


def _smoke_test() -> None:
    print("Census smoke test — pulling the latest ACS1 metro population.\n")
    latest = max(ACS1_YEARS)
    pop = fetch_population(latest)
    qualifying = pop[pop["population"] >= config.POP_FLOOR]
    print(f"  ACS1 {latest}: {len(pop)} Metro areas total")
    print(f"  >= {config.POP_FLOOR:,} population (the 500k gate): {len(qualifying)} metros")
    print(f"  cached to: {CENSUS_RAW_DIR.relative_to(config.ROOT)}\n")
    print("  Top 10 by population:")
    top = qualifying.sort_values("population", ascending=False).head(10)
    for _, r in top.iterrows():
        short = r["name"].replace(" Metro Area", "")
        print(f"    {r['population']:>11,}  {short}")
    print("\nOK — this metro list (gated by 500k) is the universe the panel is built on.")


if __name__ == "__main__":
    _smoke_test()
