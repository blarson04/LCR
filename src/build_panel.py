"""
build_panel.py — assemble the clean metro x year panel (the M2 finale).

This is where the eight ingest sources come together. It does three things:

  1. FREEZE THE UNIVERSE. Apply both gates from the decision log:
       - population >= 500k (Census ACS 2023), AND
       - gap-free ZORI rent coverage through the latest year, starting <= 2016.
     Census names metros by full CBSA title ("Austin-Round Rock-San Marcos, TX")
     while Zillow names them by principal city ("Austin, TX"), so we match on
     any principal city + state. Every metro that fails a gate is written to a
     dropped-metros log with the reason (transparency is part of the method).

  2. MERGE. Left-join every source onto the universe x year grid, keyed by CBSA
     code (and year). Zillow series are mapped from their region id to CBSA via
     the frozen universe; the FRED mortgage rate is national, broadcast by year.

  3. WRITE. Save the panel to data/processed/panel.parquet (+ .csv to eyeball)
     and the drop log to data/processed/dropped_metros.csv.

Columns in the final panel are the RAW inputs (one per source measure), not the
indicators — indicators.py (M3) computes those from this panel.

    .venv/Scripts/python.exe src/build_panel.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src.ingest import census, zillow, irs_migration, permits, bls, bea, fred  # noqa: E402

PANEL_START = config.RENT_HISTORY_START   # 2015


# --------------------------------------------------------------------------
# 1. Freeze the universe
# --------------------------------------------------------------------------
def _cbsa_city_state_keys(title: str) -> set[tuple[str, str]]:
    """'Austin-Round Rock-San Marcos, TX' -> {('austin','tx'),('round rock','tx'),...}."""
    title = title.replace(" Metro Area", "")
    place, _, st = title.rpartition(",")
    cities = [c.strip().lower() for c in re.split(r"[-/]", place)]
    states = [s.strip().lower() for s in st.split("-")]
    return {(c, s) for c in cities for s in states}


def _zillow_key(region_name: str) -> tuple[str, str]:
    """'Austin, TX' -> ('austin','tx') (first state if multi-state)."""
    place, _, st = region_name.rpartition(",")
    return place.strip().lower(), st.strip().split("-")[0].strip().lower()


def build_universe() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return (universe, dropped).
    universe : [cbsa_code, cbsa_title, region_id, population] for metros passing
               BOTH gates. region_id is Zillow's id (for joining rent/home value).
    dropped  : [cbsa_code, cbsa_title, population, reason] for metros that cleared
               the population floor but failed the rent gate.
    """
    # Population gate.
    pop = census.fetch_population(2023)
    pop = pop[pop["population"] >= config.POP_FLOOR].copy()

    # Rent gate (relaxed: start <= 2016, gap-free through latest).
    annual_zori = zillow.to_long_annual()
    covered = zillow.metros_with_full_coverage(
        annual_zori, latest_start=config.RENT_GATE_LATEST_START)
    covered_lookup = {_zillow_key(n): rid
                      for n, rid in zip(covered["region_name"], covered["region_id"])}
    any_zori_keys = {_zillow_key(n) for n in annual_zori["region_name"].unique()}

    universe_rows, dropped_rows = [], []
    for _, m in pop.iterrows():
        title = m["name"].replace(" Metro Area", "")
        keys = _cbsa_city_state_keys(m["name"])
        region_id = next((covered_lookup[k] for k in keys if k in covered_lookup), None)
        if region_id is not None:
            universe_rows.append({"cbsa_code": m["cbsa_code"], "cbsa_title": title,
                                  "region_id": int(region_id), "population": m["population"]})
        else:
            has_any = any(k in any_zori_keys for k in keys)
            reason = ("ZORI coverage too short (starts after 2016 or has gaps)"
                      if has_any else "no ZORI rent coverage")
            dropped_rows.append({"cbsa_code": m["cbsa_code"], "cbsa_title": title,
                                 "population": m["population"], "reason": reason})

    universe = pd.DataFrame(universe_rows).sort_values("population", ascending=False).reset_index(drop=True)
    dropped = pd.DataFrame(dropped_rows).sort_values("population", ascending=False).reset_index(drop=True)
    return universe, dropped


# --------------------------------------------------------------------------
# 2. Merge all sources onto the universe x year grid
# --------------------------------------------------------------------------
def assemble_panel(universe: pd.DataFrame) -> pd.DataFrame:
    """Left-join every source onto (universe CBSA) x (year) and return the panel."""
    cbsa_codes = universe["cbsa_code"].tolist()
    rid_to_cbsa = dict(zip(universe["region_id"], universe["cbsa_code"]))

    # Pull each source (cached, so this is fast after the first run).
    print("  pulling sources ...")
    pop_panel = census.build_population_panel()[["cbsa_code", "year", "population"]]
    hu_panel = census.build_housing_panel()[["cbsa_code", "year", "housing_units"]]
    vac = census.build_vacancy_panel()[["cbsa_code", "year", "rental_vacancy"]]
    mig = irs_migration.build_migration_panel()[["cbsa_code", "year", "net_migration"]]
    perm = (permits.build_permits_panel()[["cbsa_code", "year", "total_units", "mf_units"]]
            .rename(columns={"total_units": "permits_total", "mf_units": "permits_mf"}))
    inc = bea.build_income_panel()[["cbsa_code", "year", "per_capita_income"]]
    print("  pulling QCEW employment for the universe (slow on first run) ...")
    emp = bls.build_employment_panel(cbsa_codes)[
        ["cbsa_code", "year", "total_emp", "avg_annual_pay", "emp_hhi"]]

    zori = zillow.to_long_annual()
    zori = zori.assign(cbsa_code=zori["region_id"].map(rid_to_cbsa))
    zori = zori[zori["cbsa_code"].notna()][["cbsa_code", "year", "zori"]]
    zhvi = zillow.zhvi_long_annual()
    zhvi = zhvi.assign(cbsa_code=zhvi["region_id"].map(rid_to_cbsa))
    zhvi = zhvi[zhvi["cbsa_code"].notna()][["cbsa_code", "year", "zhvi"]]

    mtg = (fred.to_annual(fred.fetch_series("MORTGAGE30US"), how="mean")
           .rename("mortgage_rate_30y").reset_index())   # [year, mortgage_rate_30y]

    # Grid = universe x years.
    latest = int(zori["year"].max())
    years = range(PANEL_START, latest + 1)
    grid = pd.MultiIndex.from_product(
        [universe["cbsa_code"], years], names=["cbsa_code", "year"]).to_frame(index=False)
    panel = grid.merge(universe[["cbsa_code", "cbsa_title"]], on="cbsa_code", how="left")

    for src in (pop_panel, hu_panel, vac, mig, perm, inc, emp, zori, zhvi):
        panel = panel.merge(src, on=["cbsa_code", "year"], how="left")
    panel = panel.merge(mtg, on="year", how="left")  # national rate, broadcast

    ordered = ["cbsa_code", "cbsa_title", "year", "population", "housing_units",
               "rental_vacancy", "net_migration", "permits_total", "permits_mf", "total_emp",
               "avg_annual_pay", "emp_hhi", "per_capita_income", "zori", "zhvi",
               "mortgage_rate_30y"]
    return panel[ordered].sort_values(["cbsa_code", "year"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# 3. Build + write
# --------------------------------------------------------------------------
def main() -> None:
    print("Building the metro x year panel.\n")
    universe, dropped = build_universe()
    print(f"Universe frozen: {len(universe)} metros pass both gates "
          f"(population >= {config.POP_FLOOR:,} AND rent coverage).")
    print(f"Dropped {len(dropped)} metro(s) that cleared population but failed the rent gate:")
    for _, r in dropped.iterrows():
        print(f"    - {r['cbsa_title']}  ({r['population']:,}) — {r['reason']}")

    panel = assemble_panel(universe)

    # Write outputs.
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = config.PROCESSED_DIR / "panel.parquet"
    panel.to_parquet(panel_path, index=False)
    panel.to_csv(config.PROCESSED_DIR / "panel.csv", index=False)
    dropped.to_csv(config.PROCESSED_DIR / "dropped_metros.csv", index=False)

    print(f"\nPanel written: {panel_path.relative_to(config.ROOT)}")
    print(f"  shape: {panel.shape[0]} rows ({panel['cbsa_code'].nunique()} metros x "
          f"{panel['year'].nunique()} years), {panel.shape[1]} columns")
    print(f"  years: {panel['year'].min()}-{panel['year'].max()}")
    print("\n  non-null coverage by column (latest year may lag for some sources):")
    for col in panel.columns:
        if col in ("cbsa_code", "cbsa_title", "year"):
            continue
        pct = panel[col].notna().mean() * 100
        print(f"    {col:<18} {pct:5.1f}%")
    print("\nOK — clean panel ready. M3 (indicators + score) reads this file.")


if __name__ == "__main__":
    main()
