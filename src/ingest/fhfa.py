"""
fhfa.py — FHFA all-transactions metro house-price index (data-QA sister series).

NOT a model input. The P0 data-QA regime (decision-log 2026-07-08) cross-checks
every measure that has an independent sister series; FHFA's repeat-sales HPI is
the independent check on Zillow ZHVI (different instrument: repeat-sales on
mortgage transactions vs Zillow's hedonic model, different boundary handling).
A large ZHVI-vs-FHFA growth divergence is a data-bug tripwire, exactly like
the QCEW-vs-CES diff that caught the D6 boundary breaks.

Source: the free quarterly CSV (no key, no registration), one row per
metro-quarter: name, CBSA code, year, quarter, index (NSA), standard error.
Index history reaches back to the 1970s and runs ~1 quarter behind.

    .venv/Scripts/python.exe src/ingest/fhfa.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402

FHFA_RAW_DIR = config.RAW_DIR / "fhfa"
FHFA_RAW_DIR.mkdir(parents=True, exist_ok=True)

# Verified 2026-07-08 (the pre-2026 /DataTools/ and hyphenated paths now 404).
HPI_METRO_URL = "https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_at_metro.csv"

_COLS = ["metro_name", "cbsa_code", "year", "quarter", "hpi", "hpi_se"]


def fetch_hpi_metro(*, refresh: bool = False) -> pd.DataFrame:
    """Raw quarterly metro HPI: [metro_name, cbsa_code, year, quarter, hpi]."""
    cache = FHFA_RAW_DIR / "hpi_at_metro.csv"
    if not cache.exists() or refresh:
        resp = requests.get(HPI_METRO_URL, timeout=120,
                            headers={"User-Agent": "multifamily-screener research"})
        if resp.status_code != 200:
            raise RuntimeError(f"FHFA HPI download failed (status {resp.status_code}). "
                               f"Check HPI_METRO_URL against fhfa.gov/data/hpi/datasets.")
        cache.write_bytes(resp.content)
    df = pd.read_csv(cache, header=None, names=_COLS, dtype={"cbsa_code": str})
    df["hpi"] = pd.to_numeric(df["hpi"], errors="coerce")   # early years are '-'
    return df.dropna(subset=["hpi"])


def build_hpi_annual_panel(*, refresh: bool = False) -> pd.DataFrame:
    """Annual (calendar-mean of quarters) metro HPI: [cbsa_code, year, fhfa_hpi].

    Years with fewer than 4 quarters published (the current partial year) are
    dropped so annual growth never compares a full year to a partial one.
    """
    q = fetch_hpi_metro(refresh=refresh)
    n = q.groupby(["cbsa_code", "year"])["hpi"].count().rename("n_q")
    annual = q.groupby(["cbsa_code", "year"], as_index=False)["hpi"].mean()
    annual = annual.merge(n.reset_index(), on=["cbsa_code", "year"])
    annual = annual[annual["n_q"] == 4].drop(columns="n_q")
    return (annual.rename(columns={"hpi": "fhfa_hpi"})
            .sort_values(["cbsa_code", "year"]).reset_index(drop=True))


def _smoke_test() -> None:
    panel = build_hpi_annual_panel()
    print("FHFA all-transactions metro HPI smoke test.\n")
    print(f"  metro-years : {len(panel):,}  ({panel['cbsa_code'].nunique()} CBSAs, "
          f"{panel['year'].min()}-{panel['year'].max()})")
    fres = panel[panel["cbsa_code"] == "23420"].tail(3)
    print("  Fresno tail:")
    for _, r in fres.iterrows():
        print(f"    {int(r['year'])}: {r['fhfa_hpi']:.2f}")
    print(f"\n  cached to: {FHFA_RAW_DIR.relative_to(config.ROOT)}")
    print("OK — QA sister series for ZHVI ready (never a model input).")


if __name__ == "__main__":
    _smoke_test()
