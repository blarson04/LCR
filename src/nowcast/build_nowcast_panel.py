"""
build_nowcast_panel.py — provisional current-year nowcast panel + ranking (M2).

Assembles one indicator row per metro for the most recent scoreable year (2025)
using the proxy_map: fast indicators from live sources, the slow-but-critical
net_migration from the validated Census PEP proxy, and carry-forwards where the
finalized current-year value isn't published yet. Every indicator carries a
provenance tag. The rows are fed through the UNCHANGED v2 scoring path
(indicators are pre-computed here, then normalize + score) to produce a
PROVISIONAL ranking — clearly separate from the finalized one.

CES freshening of job_growth/income_growth is deferred (BLS metro employment
needs an area-code crosswalk from a bot-blocked host); those carry forward the
latest finalized QCEW/BEA growth. M3 measures the accuracy cost of this proxy set.

    .venv/Scripts/python.exe src/nowcast/build_nowcast_panel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import indicators, normalize  # noqa: E402
from src import score as score_mod  # noqa: E402
from src.ingest import census_pep  # noqa: E402

NOWCAST_YEAR = 2025
OUT_DIR = config.PROCESSED_DIR / "nowcast"

# How each indicator's NOWCAST_YEAR value is obtained + its provenance tag.
#   fast          — real current-year value from a live source
#   proxy         — slow input replaced by a fast proxy (PEP) or carried denominator
#   carried_forward — latest finalized value reused (current-year not yet published)
PROVENANCE = {
    "trailing_rent_growth": "fast", "cost_to_own_vs_rent": "fast",
    "permits_to_stock": "proxy",       # live permits / carried housing stock
    "net_migration": "proxy",          # PEP net domestic migration / carried population
    "rent_to_income": "proxy",         # live rent / carried income
    "job_growth": "proxy",             # CES monthly employment via FRED (v3-P1)
    "income_growth": "carried_forward",  # AHE proxy rejected in P1 QA
    "employment_diversity": "carried_forward",
}


def _latest(df: pd.DataFrame, col: str, before: int) -> pd.Series:
    """Latest non-null value of `col` per metro among years < `before` (carry-forward)."""
    d = df[(df["year"] < before) & df[col].notna()].sort_values("year")
    return d.groupby("cbsa_code")[col].last()


def nowcast_row(year: int, panel: pd.DataFrame, ind: pd.DataFrame, pep: pd.DataFrame,
                ces: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build the nowcast/pseudo-nowcast indicator row (one per metro) for `year`
    using the proxy scheme (proxy_map v0.2). Shared by M2 (current year) and M3
    (historical years) so the pseudo-nowcast test uses identical logic.
    - PEP for migration (target year if published, else latest PEP)
    - CES for job_growth (target year; carry-forward fallback where missing)
    - slow inputs carried from before `year`."""
    p_y = panel[panel["year"] == year].set_index("cbsa_code")
    i_y = ind[ind["year"] == year].set_index("cbsa_code")
    pep_y = pep[pep["year"] == min(year, pep["year"].max())].set_index("cbsa_code")["pep_net_migration"]
    stock = _latest(panel, "housing_units", year)
    pop = _latest(panel, "population", year)
    income = _latest(panel, "per_capita_income", year)

    nc = pd.DataFrame(index=i_y.index)
    nc["cbsa_title"] = i_y["cbsa_title"]
    nc["trailing_rent_growth"] = i_y["trailing_rent_growth"]         # fast
    nc["cost_to_own_vs_rent"] = i_y["cost_to_own_vs_rent"]           # fast
    nc["permits_to_stock"] = p_y["permits_total"] / stock           # live permits / carried stock
    nc["net_migration"] = pep_y / pop                               # PEP proxy / carried pop
    nc["rent_to_income"] = (p_y["zori"] * 12.0) / income            # live rent / carried income

    # job_growth: CES proxy for the target year, carry-forward where missing.
    jg_carry = _latest(ind, "job_growth", year)
    if ces is not None:
        ces_y = ces[ces["year"] == year].set_index("cbsa_code")["ces_job_growth"]
        nc["job_growth"] = ces_y.reindex(nc.index).where(
            ces_y.reindex(nc.index).notna(), jg_carry.reindex(nc.index))
    else:
        nc["job_growth"] = jg_carry
    for k in ("income_growth", "employment_diversity"):
        nc[k] = _latest(ind, k, year)                               # carried forward
    nc = nc.reset_index()
    nc["year"] = year
    return nc[ind.columns]


def build_nowcast_indicators(year: int = NOWCAST_YEAR) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (finalized indicators with `year`'s row replaced by the nowcast row,
    provenance summary)."""
    from src.ingest import bls_ces
    panel = indicators.load_panel()
    ind = indicators.compute_indicators(panel)
    pep = census_pep.build_pep_migration_panel()
    ces = bls_ces.build_ces_job_growth_panel()
    nc = nowcast_row(year, panel, ind, pep, ces)
    ind_nc = pd.concat([ind[ind["year"] != year], nc], ignore_index=True)
    prov = pd.DataFrame([{"indicator": k, "provenance": PROVENANCE[k],
                          "weight": config.INDICATORS[k]["weight"]} for k in config.INDICATORS])
    return ind_nc, prov


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    ind_nc, prov = build_nowcast_indicators()
    norm = normalize.normalize(ind_nc)
    scored = score_mod.score(norm)
    ranking = scored[scored["year"] == NOWCAST_YEAR].sort_values("rank").reset_index(drop=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(OUT_DIR / f"provisional_{NOWCAST_YEAR}_ranking.csv", index=False)
    prov.to_csv(OUT_DIR / "provenance.csv", index=False)
    # Save the nowcast-year raw + normalized indicators so the site can render the
    # full speculative forecast (metro detail, percentiles) without recomputing.
    ind_nc[ind_nc["year"] == NOWCAST_YEAR].to_csv(OUT_DIR / f"nowcast_{NOWCAST_YEAR}_raw.csv", index=False)
    norm[norm["year"] == NOWCAST_YEAR].to_csv(OUT_DIR / f"nowcast_{NOWCAST_YEAR}_norm.csv", index=False)
    return ranking, prov


def main() -> None:
    ranking, prov = build()
    by = prov.groupby("provenance")["weight"].sum()
    print(f"=== PROVISIONAL {NOWCAST_YEAR} nowcast ranking (NOT finalized) ===\n")
    print("Score composition by data provenance (share of total weight):")
    for p in ("fast", "proxy", "carried_forward"):
        print(f"  {p:<16} {by.get(p, 0)*100:4.0f}%")
    print(f"\nTop 10 (provisional {NOWCAST_YEAR} -> {NOWCAST_YEAR+3} call):")
    for _, r in ranking.head(10).iterrows():
        print(f"  {int(r['rank']):>3}  {r['cbsa_title'][:44]:<46}{r['score']:+.3f}")
    print(f"\nBottom 5:")
    for _, r in ranking.tail(5).iterrows():
        print(f"  {int(r['rank']):>3}  {r['cbsa_title'][:44]:<46}{r['score']:+.3f}")
    print(f"\nWritten to {(OUT_DIR / f'provisional_{NOWCAST_YEAR}_ranking.csv').relative_to(config.ROOT)}")
    print("PROVISIONAL — based on preliminary/proxy data; reconcile when finalized data lands (M4).")


if __name__ == "__main__":
    main()
