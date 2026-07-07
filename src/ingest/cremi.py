"""
cremi.py — Atlanta Fed CREMI (Commercial Real Estate Market Index) ingest.

Source of the Phase-3 candidate inputs (v3-build-spec §2): quarterly, by CBSA
and asset type, 1995Q1–present, free CSV downloads:
    atlantafed.org/research/data-and-tools/commercial-real-estate-market-index

We use the **Multifamily** asset type. Variables of interest (frozen list):
    Absorption.Units (C1) · NOI.Index (C2) · Asset.Value (C3) · MSAUR (C6b)
(Multifamily absorption is published as "Absorption.Units"; "Net.Absorption"
exists only for the commercial asset types.)
(The file also carries Market.Cap.Rate and Occupancy.Rate — noted in the
coverage audit; any candidacy would require a new dated decision-log entry.)

CBSA mapping: CREMI splits four large metros into METRO DIVISIONS; we map the
principal division to its parent CBSA (disclosed): Los Angeles 31084→31080,
Miami 33124→33100, New York 35614→35620, San Francisco 41884→41860.
Cleveland (OH) and Dayton (OH) are absent from CREMI multifamily entirely.

The raw file is ~165 MB and lives in data/raw/cremi/ (gitignored); re-download
with refresh=True. Requires a browser User-Agent (the site soft-blocks bots).

    .venv/Scripts/python.exe src/ingest/cremi.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402

CREMI_RAW_DIR = config.RAW_DIR / "cremi"
CREMI_RAW_DIR.mkdir(parents=True, exist_ok=True)

_BASE = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/"
         "research/housing-and-policy/cremi/")
_RESULTS = "CREMI_CBSA_Results.csv"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research"}

# Principal metro division -> parent CBSA (disclosed mapping).
DIVISION_TO_CBSA = {"31084": "31080", "33124": "33100",
                    "35614": "35620", "41884": "41860"}

MF_VARIABLES = ["Absorption.Units", "NOI.Index", "Asset.Value", "MSAUR",
                "Occupancy.Rate", "Market.Cap.Rate", "CREMI"]


def fetch_results(*, refresh: bool = False) -> pd.DataFrame:
    cache = CREMI_RAW_DIR / _RESULTS
    if not cache.exists() or refresh:
        r = requests.get(_BASE + _RESULTS, timeout=300, headers=_UA)
        if r.status_code != 200 or not r.content[:20].strip().startswith(b'"'):
            if r.status_code != 200:
                raise RuntimeError(f"CREMI download failed (status {r.status_code}).")
        cache.write_bytes(r.content)
    return pd.read_csv(cache)


def build_mf_annual(*, refresh: bool = False) -> pd.DataFrame:
    """Annual (calendar-mean of quarterly) Multifamily panel:
    [cbsa_code, year, <MF_VARIABLES...>] mapped to our CBSA codes."""
    df = fetch_results(refresh=refresh)
    mf = df[(df["Asset_Type"] == "Multifamily") & df["variable"].isin(MF_VARIABLES)].copy()
    mf["cbsa_code"] = mf["CBSA.Code"].astype(int).astype(str)
    mf["cbsa_code"] = mf["cbsa_code"].replace(DIVISION_TO_CBSA)
    mf["year"] = (mf["DT"] // 10000).astype(int)
    annual = (mf.groupby(["cbsa_code", "year", "variable"])["value"].mean()
              .unstack("variable").reset_index())
    annual.columns.name = None
    return annual.sort_values(["cbsa_code", "year"]).reset_index(drop=True)


def _smoke_test() -> None:
    a = build_mf_annual()
    uni = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")[["cbsa_code"]].drop_duplicates()
    cov = uni["cbsa_code"].isin(set(a["cbsa_code"])).sum()
    print(f"CREMI multifamily annual panel: {len(a):,} metro-years, "
          f"{a['year'].min()}–{a['year'].max()}")
    print(f"universe coverage: {cov}/110 (missing: Cleveland OH, Dayton OH)")
    aus = a[(a.cbsa_code == "12420") & (a.year.isin([2019, 2022, 2024]))]
    print("\nAustin sample:")
    print(aus[["year", "Absorption.Units", "NOI.Index", "Occupancy.Rate"]].to_string(index=False))


if __name__ == "__main__":
    _smoke_test()
