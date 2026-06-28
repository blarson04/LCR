"""
Zillow ingest — the target variable (rent).

ZORI (Zillow Observed Rent Index) is our anchor rent series and the thing the
whole model tries to predict: 3-year forward rent growth. It also drives two
indicators (trailing rent growth = Momentum; and it's the numerator of the
rent-to-income affordability ratio) and the second universe gate (a metro must
have continuous ZORI history back to RENT_HISTORY_START to enter the panel).

Series choice: `Metro_zori_uc_sfrcondomfr_sm_sa_month` — the all-homes-plus-
multifamily ZORI, smoothed and seasonally adjusted. Seasonal adjustment keeps
month-of-year effects out of the growth math; we annualize anyway.
Limitation (carry to the paper): ZORI is *asking* rent, not executed rent.

No API key needed — Zillow Research publishes flat CSVs. The download path
changes periodically, so it lives in one constant below; re-verify if it 404s.

    .venv/Scripts/python.exe src/ingest/zillow.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config  # noqa: E402

ZILLOW_RAW_DIR = config.RAW_DIR / "zillow"
ZILLOW_RAW_DIR.mkdir(parents=True, exist_ok=True)

# All-homes+multifamily ZORI, smoothed + seasonally adjusted, metro level.
ZORI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zori/"
    "Metro_zori_uc_sfrcondomfr_sm_sa_month.csv"
)
# ZHVI = Zillow Home Value Index (all homes, smoothed + SA). Home values drive
# the cost-to-own-vs-rent affordability indicator (with the FRED mortgage rate).
ZHVI_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
_ID_COLS = ["RegionID", "SizeRank", "RegionName", "RegionType", "StateName"]
MIN_MONTHS_PER_YEAR = 6   # a year needs >= this many monthly obs to count


def _download(url: str, cache_name: str, *, refresh: bool = False) -> pd.DataFrame:
    """Download a wide Zillow metro CSV, caching the raw file to data/raw/zillow/."""
    cache = ZILLOW_RAW_DIR / cache_name
    if cache.exists() and not refresh:
        return pd.read_csv(cache)
    resp = requests.get(url, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(
            f"Zillow download failed (status {resp.status_code}). The path may have "
            f"changed — check https://www.zillow.com/research/data/ .\nURL tried: {url}"
        )
    cache.write_bytes(resp.content)
    return pd.read_csv(io.BytesIO(resp.content))


def fetch_zori(*, refresh: bool = False) -> pd.DataFrame:
    return _download(ZORI_URL, "Metro_zori_sfrcondomfr_sm_sa_month.csv", refresh=refresh)


def fetch_zhvi(*, refresh: bool = False) -> pd.DataFrame:
    return _download(ZHVI_URL, "Metro_zhvi_sfrcondo_sm_sa_month.csv", refresh=refresh)


def _annualize(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    """
    Shared logic: wide monthly metro series -> tidy annual panel with columns
    [region_id, region_name, state, year, <value_name>]. A year's value is the
    mean of its monthly observations, kept only if the year has enough months.
    Metro (msa) rows only, from RENT_HISTORY_START onward.
    """
    df = df[df["RegionType"] == "msa"].copy()
    date_cols = [c for c in df.columns if c not in _ID_COLS]

    long = df.melt(
        id_vars=["RegionID", "RegionName", "StateName"],
        value_vars=date_cols, var_name="date", value_name=value_name,
    )
    long["date"] = pd.to_datetime(long["date"])
    long["year"] = long["date"].dt.year
    long = long.dropna(subset=[value_name])

    grp = long.groupby(["RegionID", "RegionName", "StateName", "year"])
    annual = grp[value_name].agg(["mean", "count"]).reset_index()
    annual = annual[annual["count"] >= MIN_MONTHS_PER_YEAR]
    annual = annual[annual["year"] >= config.RENT_HISTORY_START]
    annual = annual.rename(columns={"RegionID": "region_id", "RegionName": "region_name",
                                    "StateName": "state", "mean": value_name})
    return (annual[["region_id", "region_name", "state", "year", value_name]]
            .sort_values(["region_id", "year"]).reset_index(drop=True))


def to_long_annual(df: pd.DataFrame | None = None, *, refresh: bool = False) -> pd.DataFrame:
    """Annual ZORI panel: [region_id, region_name, state, year, zori]."""
    if df is None:
        df = fetch_zori(refresh=refresh)
    return _annualize(df, "zori")


def zhvi_long_annual(df: pd.DataFrame | None = None, *, refresh: bool = False) -> pd.DataFrame:
    """Annual ZHVI (home value) panel: [region_id, region_name, state, year, zhvi]."""
    if df is None:
        df = fetch_zhvi(refresh=refresh)
    return _annualize(df, "zhvi")


def metros_with_full_coverage(annual: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Metros whose ZORI history is continuous from RENT_HISTORY_START to the
    latest available year (no gaps). This is the rent-coverage gate; metros
    failing it get dropped from the universe (and logged) in build_panel.py.
    Returns the id columns + first_year / last_year / n_years.
    """
    if annual is None:
        annual = to_long_annual()
    latest = annual["year"].max()
    expected = set(range(config.RENT_HISTORY_START, latest + 1))

    rows = []
    for rid, g in annual.groupby("region_id"):
        years = set(g["year"])
        if expected.issubset(years):
            rows.append({
                "region_id": rid,
                "region_name": g["region_name"].iloc[0],
                "state": g["state"].iloc[0],
                "first_year": min(years), "last_year": max(years),
                "n_years": len(years),
            })
    return pd.DataFrame(rows).sort_values("region_name").reset_index(drop=True)


def _smoke_test() -> None:
    print("Zillow ZORI smoke test — downloading + annualizing the rent series.\n")
    annual = to_long_annual()
    latest = annual["year"].max()
    covered = metros_with_full_coverage(annual)
    print(f"  metros with any ZORI data: {annual['region_id'].nunique()}")
    print(f"  continuous coverage {config.RENT_HISTORY_START}-{latest} (rent gate): {len(covered)}")
    print(f"  cached to: {ZILLOW_RAW_DIR.relative_to(config.ROOT)}\n")

    aus = annual[annual["region_name"] == "Austin, TX"]
    print("  Austin, TX annual ZORI ($/mo):")
    for _, r in aus.iterrows():
        print(f"    {r['year']}: {r['zori']:,.0f}")
    if len(aus) >= 4:
        first, last = aus.iloc[0], aus.iloc[-1]
        g = (last["zori"] / first["zori"]) ** (1 / (last["year"] - first["year"])) - 1
        print(f"    -> {first['year']}-{last['year']} CAGR: {g*100:.1f}%/yr")
    print("\nOK — annual rent panel ready; the coverage list is the rent-coverage gate.")


if __name__ == "__main__":
    _smoke_test()
