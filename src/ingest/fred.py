"""
FRED ingest — the first source wired up end to end.

FRED (Federal Reserve Economic Data, from the St. Louis Fed) is the gentlest
source to start with: one well-documented API, one Python wrapper (`fredapi`),
and clean time series. We use it in M1 to get the whole pipeline shape right
(fetch -> cache -> clean) before adding the messier sources.

What this module gives the rest of the project:
  - get_client()            : a ready-to-use FRED client (reads your API key)
  - fetch_series(series_id) : raw series, cached to data/raw/fred/ so we only
                              hit the network once per series
  - to_annual(series, how)  : collapse a monthly/daily series to one value per
                              calendar year (the panel's grain is metro x YEAR)

Run it directly to prove your key works:
    .venv/Scripts/python.exe src/ingest/fred.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

# Make "import config" work no matter where the script is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402

FRED_RAW_DIR = config.RAW_DIR / "fred"
FRED_RAW_DIR.mkdir(parents=True, exist_ok=True)


def get_client():
    """Return a fredapi.Fred client, or raise a clear error if the key is missing."""
    load_dotenv(config.ROOT / ".env")          # load FRED_API_KEY from .env
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "No FRED_API_KEY found.\n"
            "  1. Get a free key (instant): https://fred.stlouisfed.org/docs/api/api_key.html\n"
            "  2. Copy .env.example to .env and paste the key after FRED_API_KEY=\n"
        )
    from fredapi import Fred  # imported here so the module loads even without the dep
    return Fred(api_key=key)


def fetch_series(series_id: str, *, refresh: bool = False) -> pd.Series:
    """
    Fetch one FRED series, caching the raw result to data/raw/fred/<id>.csv.

    The cache is what makes the pipeline reproducible and fast: the network is
    hit only the first time (or when refresh=True). Returns a date-indexed
    pandas Series named after the series_id.
    """
    cache = FRED_RAW_DIR / f"{series_id}.csv"

    if cache.exists() and not refresh:
        s = pd.read_csv(cache, index_col=0, parse_dates=True).iloc[:, 0]
        s.name = series_id
        return s

    client = get_client()
    s = client.get_series(series_id)
    s.name = series_id
    s.index.name = "date"
    s.to_frame().to_csv(cache)   # cache raw download
    return s


def to_annual(series: pd.Series, how: str = "mean") -> pd.Series:
    """
    Collapse a higher-frequency series to one value per calendar year.

      how="mean" : average over the year   (levels: rates, indexes)
      how="last" : December / year-end value (stocks measured at a point in time)

    Returns a series indexed by integer year.
    """
    if how == "mean":
        annual = series.groupby(series.index.year).mean()
    elif how == "last":
        annual = series.groupby(series.index.year).last()
    else:
        raise ValueError(f"how must be 'mean' or 'last', got {how!r}")
    annual.index.name = "year"
    annual.name = series.name
    return annual


# A couple of national series used purely to prove the plumbing in M1.
# (Metro-level FRED series get mapped to our universe in M2 / build_panel.py.)
_SMOKE_TEST_SERIES = {
    "MORTGAGE30US": "30-yr fixed mortgage rate (%)",
    "CPIAUCSL": "CPI, all urban consumers (index)",
}


def _smoke_test() -> None:
    print("FRED smoke test — fetching a couple of national series to prove the key + cache work.\n")
    for sid, label in _SMOKE_TEST_SERIES.items():
        s = fetch_series(sid)
        annual = to_annual(s, how="mean")
        recent = annual[annual.index >= config.RENT_HISTORY_START]
        print(f"  {sid}  ({label})")
        print(f"    raw points : {len(s):,}  ({s.index.min().date()} -> {s.index.max().date()})")
        print(f"    cached to  : {(FRED_RAW_DIR / (sid + '.csv')).relative_to(config.ROOT)}")
        print(f"    annual {config.RENT_HISTORY_START}+ :")
        for yr, val in recent.round(2).items():
            print(f"        {yr}: {val}")
        print()
    print("OK — fetch -> cache -> clean works. Cached CSVs are reused on the next run.")


if __name__ == "__main__":
    _smoke_test()
