"""
County -> CBSA (metro) crosswalk.

Several sources report data by COUNTY (IRS migration, Census building permits)
but our panel is keyed by METRO (CBSA). This module provides the authoritative
mapping from the Census Bureau's OMB delineation file, plus a helper that rolls
county-level numbers up to the metro that contains them.

The delineation's `CBSA Code` is the same code the ACS API returns for metros,
so everything joins on a single clean key.

No API key needed (flat .xlsx from Census). Used by ingest modules and
build_panel.py — not run on its own, but has a smoke test for sanity.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

CROSSWALK_RAW_DIR = config.RAW_DIR / "crosswalk"
CROSSWALK_RAW_DIR.mkdir(parents=True, exist_ok=True)

# OMB July 2023 delineations, prepared by Census. Re-verify if it 404s.
DELINEATION_URL = (
    "https://www2.census.gov/programs-surveys/metro-micro/geographies/"
    "reference-files/2023/delineation-files/list1_2023.xlsx"
)


def load(*, metro_only: bool = True, refresh: bool = False) -> pd.DataFrame:
    """
    Return the county->CBSA crosswalk with columns:
        county_fips (5-char str), cbsa_code (str), cbsa_title,
        metro_type ('Metropolitan'/'Micropolitan'), central_outlying.

    metro_only=True keeps just Metropolitan Statistical Areas (our universe is
    MSAs, not Micropolitan — see decision-log).
    """
    cache = CROSSWALK_RAW_DIR / "list1_2023.xlsx"
    if cache.exists() and not refresh:
        raw = pd.read_excel(cache, header=2)
    else:
        resp = requests.get(DELINEATION_URL, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Delineation download failed (status {resp.status_code}). "
                f"Check the Census reference-files path and update DELINEATION_URL."
            )
        cache.write_bytes(resp.content)
        raw = pd.read_excel(io.BytesIO(resp.content), header=2)

    # Drop the footnote rows at the bottom. They carry explanatory TEXT in the
    # CBSA Code column (not NaN), so filter to rows with a numeric code.
    raw = raw.copy()
    raw["CBSA Code"] = pd.to_numeric(raw["CBSA Code"], errors="coerce")
    raw = raw.dropna(subset=["CBSA Code"])

    df = pd.DataFrame({
        "cbsa_code": raw["CBSA Code"].astype(int).astype(str),
        "cbsa_title": raw["CBSA Title"].astype(str),
        "metro_type": raw["Metropolitan/Micropolitan Statistical Area"]
                        .str.replace(" Statistical Area", "", regex=False),
        "county_fips": (raw["FIPS State Code"].astype(int).map("{:02d}".format)
                        + raw["FIPS County Code"].astype(int).map("{:03d}".format)),
        "central_outlying": raw["Central/Outlying County"].astype(str),
    })

    if metro_only:
        df = df[df["metro_type"] == "Metropolitan"]
    return df.reset_index(drop=True)


def aggregate_counties_to_cbsa(
    data: pd.DataFrame,
    fips_col: str,
    value_cols: list[str],
    *,
    how: str = "sum",
    metro_only: bool = True,
) -> pd.DataFrame:
    """
    Roll county-level `value_cols` up to the metro that contains each county.

    `data` must have a column `fips_col` of 5-char county FIPS strings. Returns
    one row per (cbsa_code, cbsa_title) with the aggregated values. Counties
    that don't fall in any (metro) CBSA are dropped — that's expected, since
    rural counties aren't part of our universe.
    """
    xwalk = load(metro_only=metro_only)
    merged = data.merge(xwalk[["county_fips", "cbsa_code", "cbsa_title"]],
                        left_on=fips_col, right_on="county_fips", how="inner")
    grp = merged.groupby(["cbsa_code", "cbsa_title"])[value_cols]
    out = getattr(grp, how)().reset_index()
    return out


def _smoke_test() -> None:
    xwalk = load()
    print("County -> CBSA crosswalk (Metropolitan only):")
    print(f"  counties mapped : {xwalk['county_fips'].nunique():,}")
    print(f"  metros (CBSAs)  : {xwalk['cbsa_code'].nunique():,}")
    print(f"  cached to       : {CROSSWALK_RAW_DIR.relative_to(config.ROOT)}\n")
    # Austin should span several counties (Travis, Williamson, Hays, ...).
    aus = xwalk[xwalk["cbsa_title"].str.startswith("Austin")]
    print(f"  Austin CBSA {aus['cbsa_code'].iloc[0]} spans {len(aus)} counties:")
    print("   ", ", ".join(sorted(aus["county_fips"])))
    print("\nOK — ready to roll county-level IRS migration + permits up to metros.")


if __name__ == "__main__":
    _smoke_test()
