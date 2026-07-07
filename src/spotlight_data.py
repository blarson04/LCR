"""
spotlight_data.py — committed monthly rent-trend extract for the site's
Market spotlight page (v3 build-spec §4.4).

The deployed site has no data/raw (gitignored), so the monthly ZORI series it
needs is pre-extracted here into a small committed CSV: year-over-year rent
growth by month for every universe metro, plus a 'US' row per month holding
the universe median (the "national" comparison line). Regenerate whenever the
Zillow cache is refreshed (each vintage refresh is enough).

    .venv/Scripts/python.exe src/spotlight_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                    # noqa: E402
from src import build_panel      # noqa: E402
from src.ingest import zillow    # noqa: E402

START_MONTH = "2018-01"   # keep the file small; the chart shows recent history


def build() -> pd.DataFrame:
    universe, _ = build_panel.build_universe()
    rid_to_cbsa = dict(zip(universe["region_id"], universe["cbsa_code"]))

    wide = zillow.fetch_zori()
    month_cols = [c for c in wide.columns if c[:2] == "20"]
    long = wide.melt(id_vars=["RegionID"], value_vars=month_cols,
                     var_name="month", value_name="zori").dropna()
    long["cbsa_code"] = long["RegionID"].map(rid_to_cbsa)
    long = long.dropna(subset=["cbsa_code"])
    long["month"] = long["month"].str[:7]

    prev = long.copy()
    prev["month"] = (pd.PeriodIndex(prev["month"], freq="M") + 12).astype(str)
    m = long.merge(prev.rename(columns={"zori": "zori_prev"})[
        ["cbsa_code", "month", "zori_prev"]], on=["cbsa_code", "month"])
    m["yoy"] = (m["zori"] / m["zori_prev"] - 1).round(4)
    m = m[m["month"] >= START_MONTH][["month", "cbsa_code", "yoy"]]

    nat = (m.groupby("month", as_index=False)["yoy"].median().round(4)
           .assign(cbsa_code="US"))
    out = (pd.concat([m, nat[["month", "cbsa_code", "yoy"]]], ignore_index=True)
           .sort_values(["cbsa_code", "month"]).reset_index(drop=True))
    return out


def main() -> None:
    out = build()
    path = config.PROCESSED_DIR / "spotlight_rent_trend.csv"
    out.to_csv(path, index=False)
    metros = out[out.cbsa_code != "US"]["cbsa_code"].nunique()
    print(f"wrote {path}: {len(out):,} rows, {metros} metros + US median, "
          f"{out.month.min()} to {out.month.max()}")


if __name__ == "__main__":
    main()
