"""
indicators.py — turn the raw panel into the 10 model indicators.

The panel (build_panel.py) holds raw inputs (employment levels, rent dollars,
permit counts, ...). This module converts them into the 10 comparable
indicators the model scores. Values here are kept in their natural, readable
units (e.g. rent_to_income is an actual ratio) so the metro drill-down can show
real numbers. Direction (which way is "good") is applied later, in normalize.py.

Indicator definitions (see decision-log for the weights/rationale):
  net_migration        net domestic migrants / population        (per-capita rate)
  job_growth           YoY change in total employment
  income_growth        YoY change in per-capita personal income
  population_growth    YoY change in population
  permits_to_stock     total permitted units / existing housing stock   [inverse]
  mf_pipeline          5+ unit permits / existing housing stock         [inverse]
  rent_to_income       annual rent (ZORI x 12) / per-capita income      [inverse]
  cost_to_own_vs_rent  monthly mortgage payment on ZHVI / monthly rent
  trailing_rent_growth YoY change in ZORI
  employment_diversity 1 - employment HHI (higher = more diversified)

YoY growth uses the true prior calendar year (via a year-shift join), so the
gaps in the panel (e.g. no ACS 2020) never produce a spurious multi-year jump.

    .venv/Scripts/python.exe src/indicators.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

INDICATOR_COLS = list(config.INDICATORS.keys())
_MORTGAGE_TERM_MONTHS = 360   # 30-year amortization for the ownership-cost proxy


def load_panel() -> pd.DataFrame:
    return pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")


def _yoy(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Year-over-year growth of `col` within each metro, using the EXACT prior
    year. Returns NaN when year t-1 is absent (so panel gaps don't create
    fake one-year jumps). Index-aligned to df.
    """
    prev = df[["cbsa_code", "year", col]].copy()
    prev["year"] += 1
    prev = prev.rename(columns={col: "_prev"})
    merged = df.merge(prev, on=["cbsa_code", "year"], how="left")
    return (merged[col] / merged["_prev"] - 1.0).to_numpy()


def _monthly_mortgage_payment(home_value: pd.Series, annual_rate_pct: pd.Series) -> pd.Series:
    """Standard amortizing monthly payment on the full home value at the 30y rate.
    Used as a relative cost-of-ownership proxy (down-payment/LTV is a constant
    scalar that doesn't affect cross-metro ranking)."""
    r = annual_rate_pct / 100.0 / 12.0
    n = _MORTGAGE_TERM_MONTHS
    return home_value * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def compute_indicators(panel: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return [cbsa_code, cbsa_title, year, <10 indicator columns>] with raw values."""
    if panel is None:
        panel = load_panel()
    panel = panel.sort_values(["cbsa_code", "year"]).reset_index(drop=True)

    out = panel[["cbsa_code", "cbsa_title", "year"]].copy()

    # Levels / rates
    # v2 = de-duplicated 8-indicator set: population_growth (folded into
    # net_migration) and mf_pipeline (folded into permits_to_stock) are no longer
    # scored. The panel still carries `population` (migration denominator) and
    # `permits_mf` for reference/context.
    out["net_migration"] = panel["net_migration"] / panel["population"]
    out["permits_to_stock"] = panel["permits_total"] / panel["housing_units"]
    out["rent_to_income"] = (panel["zori"] * 12.0) / panel["per_capita_income"]
    own = _monthly_mortgage_payment(panel["zhvi"], panel["mortgage_rate_30y"])
    out["cost_to_own_vs_rent"] = own / panel["zori"]
    out["employment_diversity"] = 1.0 - panel["emp_hhi"]

    # Year-over-year growth
    out["job_growth"] = _yoy(panel, "total_emp")
    out["income_growth"] = _yoy(panel, "per_capita_income")
    out["trailing_rent_growth"] = _yoy(panel, "zori")

    return out[["cbsa_code", "cbsa_title", "year"] + INDICATOR_COLS]


def _smoke_test() -> None:
    ind = compute_indicators()
    latest = 2023   # scoring year (broad coverage)
    y = ind[ind["year"] == latest]
    print(f"Indicators computed: {ind.shape[0]} metro-years, {len(INDICATOR_COLS)} indicators.\n")
    print(f"  non-null per indicator in {latest}:")
    for c in INDICATOR_COLS:
        print(f"    {c:<22} {y[c].notna().sum():>3}/110")
    aus = y[y["cbsa_title"].str.startswith("Austin")].iloc[0]
    print(f"\n  Austin {latest} sample values:")
    print(f"    net_migration rate     {aus['net_migration']*100:+.2f}% of pop")
    print(f"    job_growth             {aus['job_growth']*100:+.2f}%")
    print(f"    permits_to_stock       {aus['permits_to_stock']*100:.2f}% of stock")
    print(f"    rent_to_income         {aus['rent_to_income']*100:.1f}% (annual rent / income)")
    print(f"    cost_to_own_vs_rent    {aus['cost_to_own_vs_rent']:.2f}x rent")
    print(f"    employment_diversity   {aus['employment_diversity']:.3f}")
    print("\nOK — raw indicators ready; normalize.py z-scores them within each year.")


if __name__ == "__main__":
    _smoke_test()
