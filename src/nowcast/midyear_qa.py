"""
midyear_qa.py — input-level QA for the proposed MID-YEAR proxy scheme (v0.5).

Author request 2026-07-20: a 2026->2029 screen built mid-year from
year-to-date data. Per the governance precedent (the v0.4 income-proxy QA),
instrument-level agreement may be measured BEFORE the spec entry; NO gate
metrics (no tau against realized rent growth, no retention, no overlap) are
computed here. Each QA asks one question: how well does the mid-year
instrument rank-agree with the finalized full-year input it would stand in
for, per overlap year?

  QA-R  ZORI Jan-May same-months YoY            vs finalized trailing_rent_growth
  QA-J  CES Jan-May same-months YoY             vs finalized job_growth (QCEW)
  QA-P  BPS county May-YTD units (real vintage-shaped files) vs annual units
  QA-I  income options for the scoring year:
          (a) primary-state annual growth, one year stale (T-1)
          (b) flat carry of the metro's T-2 finalized growth
        each vs finalized metro income growth at T
        (context: the same-year state chain scored 0.60 in the v0.4 QA)
  QA-M  PEP migration staleness: estimate-year T-1 rate vs T rate

Output: data/processed/nowcast/midyear_qa.csv + printed summary.

    .venv/Scripts/python.exe src/nowcast/midyear_qa.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import indicators          # noqa: E402
from src.build_panel import build_universe  # noqa: E402
from src.ingest import bea, census_pep, fred, permits  # noqa: E402

OUT = config.PROCESSED_DIR / "nowcast" / "midyear_qa.csv"
YTD_MONTH = 5   # Jan-May: the months reliably closed by a July build


# ---------------------------------------------------------------------------
# Mid-year instruments
# ---------------------------------------------------------------------------

def monthly_zori_by_cbsa() -> pd.DataFrame:
    """[cbsa_code, date, zori] monthly, mapped region->CBSA via the universe."""
    universe, _ = build_universe()
    rid_to_cbsa = dict(zip(universe["region_id"], universe["cbsa_code"]))
    raw = pd.read_csv(config.RAW_DIR / "zillow" / "Metro_zori_sfrcondomfr_sm_sa_month.csv")
    date_cols = [c for c in raw.columns if c[:2] == "20"]
    long = raw.melt(id_vars=["RegionID"], value_vars=date_cols,
                    var_name="date", value_name="zori").dropna()
    long["cbsa_code"] = long["RegionID"].map(rid_to_cbsa)
    long = long.dropna(subset=["cbsa_code"])
    long["date"] = pd.to_datetime(long["date"])
    return long[["cbsa_code", "date", "zori"]]


def same_months_yoy(monthly: pd.DataFrame, value_col: str, year: int,
                    upto_month: int = YTD_MONTH) -> pd.Series:
    """mean(Jan..M of `year`) / mean(Jan..M of year-1) - 1, per cbsa."""
    m = monthly[monthly["date"].dt.month <= upto_month]
    cur = (m[m["date"].dt.year == year].groupby("cbsa_code")[value_col].mean())
    prev = (m[m["date"].dt.year == year - 1].groupby("cbsa_code")[value_col].mean())
    return (cur / prev - 1.0).dropna()


def monthly_ces_by_cbsa() -> pd.DataFrame:
    """[cbsa_code, date, emp] monthly CES from the cached FRED series."""
    mapping = pd.read_csv(config.PROCESSED_DIR / "nowcast" / "ces_qa_coverage.csv",
                          dtype={"cbsa_code": str})
    mapping = mapping[mapping["emp_found"] & (mapping["emp_series"] != "")]
    frames = []
    for _, r in mapping.iterrows():
        try:
            s = fred.fetch_series(r["emp_series"])
        except Exception:
            continue
        frames.append(pd.DataFrame({"cbsa_code": r["cbsa_code"],
                                    "date": s.index, "emp": s.values}))
    return pd.concat(frames, ignore_index=True)


def bps_ytd_units(year: int, month: int = YTD_MONTH, *,
                  refresh: bool = False) -> pd.Series:
    """County May-YTD permitted units rolled to CBSA (the real vintage-shaped
    monthly files, same layout as the annual files)."""
    from src import crosswalk
    name = f"co{str(year)[2:]}{month:02d}y.txt"
    cache = permits.BPS_RAW_DIR / name
    if cache.exists() and not refresh:
        text = cache.read_text()
    else:
        import requests
        resp = requests.get(f"https://www2.census.gov/econ/bps/County/{name}",
                            timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"BPS YTD download failed for {name} "
                               f"(status {resp.status_code}).")
        text = resp.text
        cache.write_text(text)
    raw = pd.read_csv(io.StringIO(text), header=None, skiprows=3)
    C = permits._COL
    out = pd.DataFrame({
        "county_fips": (raw[C["state"]].astype(int).map("{:02d}".format)
                        + raw[C["county"]].astype(int).map("{:03d}".format)),
        "total_units": sum(pd.to_numeric(raw[C[k]], errors="coerce").fillna(0)
                           for k in ("units_1u", "units_2u", "units_34", "units_5p")),
    })
    metro = crosswalk.aggregate_counties_to_cbsa(
        out, "county_fips", ["total_units"], how="sum")
    return metro.set_index("cbsa_code")["total_units"]


# ---------------------------------------------------------------------------
# QA driver
# ---------------------------------------------------------------------------

def _rho(a: pd.Series, b: pd.Series) -> tuple[float, int]:
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(j) < 30:
        return float("nan"), len(j)
    return float(spearmanr(j["a"], j["b"]).statistic), len(j)


def main() -> None:
    ind = indicators.compute_indicators()
    fin = {c: ind.pivot_table(index="cbsa_code", columns="year", values=c,
                              aggfunc="first")
           for c in ("trailing_rent_growth", "job_growth", "income_growth",
                     "permits_to_stock")}
    rows = []

    print("QA-R: ZORI Jan-May same-months YoY vs finalized full-year rent growth")
    zori_m = monthly_zori_by_cbsa()
    for y in range(2016, 2026):
        rho, n = _rho(same_months_yoy(zori_m, "zori", y),
                      fin["trailing_rent_growth"].get(y, pd.Series(dtype=float)))
        rows.append({"qa": "R_rent_ytd", "year": y, "rho": rho, "n": n})
        print(f"    {y}: rho {rho: .3f} (n={n})")

    print("QA-J: CES Jan-May same-months YoY vs finalized QCEW job growth")
    ces_m = monthly_ces_by_cbsa()
    for y in range(2016, 2025):
        rho, n = _rho(same_months_yoy(ces_m, "emp", y),
                      fin["job_growth"].get(y, pd.Series(dtype=float)))
        rows.append({"qa": "J_jobs_ytd", "year": y, "rho": rho, "n": n})
        print(f"    {y}: rho {rho: .3f} (n={n})")

    print("QA-P: BPS May-YTD county units vs finalized annual units (rank)")
    ann = permits.build_permits_panel()
    ann_p = ann.pivot_table(index="cbsa_code", columns="year",
                            values="total_units", aggfunc="first")
    for y in range(2015, 2026):
        try:
            ytd = bps_ytd_units(y)
        except RuntimeError as e:
            print(f"    {y}: skip ({str(e)[:60]})")
            continue
        rho, n = _rho(ytd, ann_p.get(y, pd.Series(dtype=float)))
        rows.append({"qa": "P_permits_ytd", "year": y, "rho": rho, "n": n})
        print(f"    {y}: rho {rho: .3f} (n={n})")

    print("QA-I: income proxies vs finalized metro income growth")
    sg = bea.state_pc_income_growth_panel()
    states = (ind[["cbsa_code", "cbsa_title"]].drop_duplicates("cbsa_code")
              .set_index("cbsa_code")["cbsa_title"]
              .str.split(",").str[1].str.strip().str.split("-").str[0])
    for y in range(2016, 2025):
        stale_chain = states.map(lambda s: sg.get((s, y - 1), float("nan")))
        rho_a, n_a = _rho(stale_chain, fin["income_growth"].get(y, pd.Series(dtype=float)))
        carry = fin["income_growth"].get(y - 2, pd.Series(dtype=float))
        rho_b, n_b = _rho(carry, fin["income_growth"].get(y, pd.Series(dtype=float)))
        rows.append({"qa": "I_state_chain_stale", "year": y, "rho": rho_a, "n": n_a})
        rows.append({"qa": "I_flat_carry_T2", "year": y, "rho": rho_b, "n": n_b})
        print(f"    {y}: state chain T-1 {rho_a: .3f} (n={n_a}) | "
              f"flat carry T-2 {rho_b: .3f} (n={n_b})")

    print("QA-M: PEP migration staleness (estimate-year T-1 rate vs T rate)")
    pep = census_pep.build_pep_migration_panel()
    pep_p = pep.pivot_table(index="cbsa_code", columns="year",
                            values="pep_net_migration", aggfunc="first")
    for y in range(2013, 2025):
        if y in pep_p.columns and (y - 1) in pep_p.columns:
            rho, n = _rho(pep_p[y - 1], pep_p[y])
            rows.append({"qa": "M_pep_stale", "year": y, "rho": rho, "n": n})
            print(f"    {y}: rho {rho: .3f} (n={n})")

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print("\nMeans by QA:")
    for qa, g in out.groupby("qa"):
        print(f"  {qa:<22} mean rho {g['rho'].mean(): .3f}  "
              f"(range {g['rho'].min(): .3f} to {g['rho'].max(): .3f}, "
              f"{len(g)} years)")
    print(f"\nWritten: {OUT.relative_to(config.ROOT)}")
    print("No gate metrics were computed (instrument agreement only).")


if __name__ == "__main__":
    main()
