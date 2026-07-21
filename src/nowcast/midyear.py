"""
midyear.py — shared row construction for the v0.5 MID-YEAR scheme
(decision-log 2026-07-20 spec). One function builds the scoring row for any
year T from data through May of T, so the gate pseudo-test and the real 2026
build use identical logic (the nowcast_row precedent).

Scheme (frozen in the spec):
  trailing_rent_growth  ZORI same-months YoY (mean Jan-May T over Jan-May T-1)
  cost_to_own_vs_rent   payment on Jan-May-mean ZHVI at Jan-May-mean 30y rate,
                        over Jan-May-mean ZORI
  permits_to_stock      BPS county May-YTD units x 12/5 over ACS stock <= T-2
  net_migration         PEP net domestic migration, estimate-year T-1,
                        over population <= T-2
  job_growth            CES same-months YoY; carry fallback (latest < T)
  income_growth         v0.6 (decision-log 2026-07-21): primary-state
                        Q1-over-Q1 total personal income growth of T (BEA
                        SQINC1, QA 0.464); neutral fill where missing
  rent_to_income        (Jan-May-mean ZORI x 12) over metro T-2 income level
                        chained by state T-1 annual growth AND state Q1
                        growth of T (the v0.4 consistency pattern)
  employment_diversity  carry (latest < T)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import indicators          # noqa: E402
from src.ingest import fred         # noqa: E402
from src.nowcast.midyear_qa import (  # noqa: E402
    YTD_MONTH, bps_ytd_units, monthly_ces_by_cbsa, monthly_zori_by_cbsa)

ANNUALIZE = 12.0 / YTD_MONTH   # readable units; cancels in the within-year z


def monthly_zhvi_by_cbsa() -> pd.DataFrame:
    """[cbsa_code, date, zhvi] monthly, region->CBSA via the universe."""
    from src.build_panel import build_universe
    universe, _ = build_universe()
    rid_to_cbsa = dict(zip(universe["region_id"], universe["cbsa_code"]))
    raw = pd.read_csv(config.RAW_DIR / "zillow" / "Metro_zhvi_sfrcondo_sm_sa_month.csv")
    date_cols = [c for c in raw.columns if c[:2] == "20"]
    long = raw.melt(id_vars=["RegionID"], value_vars=date_cols,
                    var_name="date", value_name="zhvi").dropna()
    long["cbsa_code"] = long["RegionID"].map(rid_to_cbsa)
    long = long.dropna(subset=["cbsa_code"])
    long["date"] = pd.to_datetime(long["date"])
    return long[["cbsa_code", "date", "zhvi"]]


def _ytd_mean(monthly: pd.DataFrame, col: str, year: int) -> pd.Series:
    m = monthly[(monthly["date"].dt.year == year)
                & (monthly["date"].dt.month <= YTD_MONTH)]
    return m.groupby("cbsa_code")[col].mean()


def _ytd_rate(year: int) -> float:
    s = fred.fetch_series("MORTGAGE30US")
    m = s[(s.index.year == year) & (s.index.month <= YTD_MONTH)]
    return float(m.mean())


def _latest_leq(df: pd.DataFrame, col: str, upto: int) -> pd.Series:
    """Latest non-null value of `col` per metro among years <= `upto`."""
    d = df[(df["year"] <= upto) & df[col].notna()].sort_values("year")
    return d.groupby("cbsa_code")[col].last()


def load_shared() -> dict:
    """The data every mid-year row needs, loaded once."""
    panel = indicators.load_panel()
    ind = indicators.compute_indicators(panel)
    from src.ingest import bea, census_pep, permits
    from src.nowcast.income_quarterly_qa import state_q1_income_growth
    return dict(
        panel=panel, ind=ind,
        zori_m=monthly_zori_by_cbsa(), zhvi_m=monthly_zhvi_by_cbsa(),
        ces_m=monthly_ces_by_cbsa(),
        pep=census_pep.build_pep_migration_panel(),
        sg=bea.state_pc_income_growth_panel(),
        q1=state_q1_income_growth(),
        permits_annual=permits.build_permits_panel())


def midyear_row(T: int, shared: dict,
                pep_override: pd.Series | None = None) -> pd.DataFrame:
    """The v0.5 scoring row for year T (columns match compute_indicators).
    `pep_override` supplies the estimate-year T-1 migration when it is not in
    the historical PEP panel (the 2026 build passes the vintage-2025 series)."""
    panel, ind = shared["panel"], shared["ind"]
    metros = (ind[["cbsa_code", "cbsa_title"]].drop_duplicates("cbsa_code")
              .set_index("cbsa_code"))

    zori_t = _ytd_mean(shared["zori_m"], "zori", T).reindex(metros.index)
    zori_p = _ytd_mean(shared["zori_m"], "zori", T - 1).reindex(metros.index)
    zhvi_t = _ytd_mean(shared["zhvi_m"], "zhvi", T).reindex(metros.index)
    ces_t = _ytd_mean(shared["ces_m"], "emp", T).reindex(metros.index)
    ces_p = _ytd_mean(shared["ces_m"], "emp", T - 1).reindex(metros.index)

    stock = _latest_leq(panel, "housing_units", T - 2).reindex(metros.index)
    pop = _latest_leq(panel, "population", T - 2).reindex(metros.index)
    inc_t2 = _latest_leq(panel, "per_capita_income", T - 2).reindex(metros.index)

    if pep_override is not None:
        mig = pep_override.reindex(metros.index)
    else:
        pep = shared["pep"]
        mig = (pep[pep["year"] == T - 1].set_index("cbsa_code")
               ["pep_net_migration"].reindex(metros.index))

    st = (metros["cbsa_title"].str.split(",").str[1].str.strip()
          .str.split("-").str[0])
    sg = shared["sg"]
    g_state = st.map(lambda s: sg.get((s, T - 1), float("nan")))
    income = (inc_t2 * (1.0 + g_state)).where(g_state.notna(), inc_t2)
    # v0.6: chain one further step by the same-year Q1 state growth, and use
    # that growth as the income_growth estimate (decision-log 2026-07-21).
    g_q1 = st.map(lambda s: shared["q1"].get((s, T), float("nan")))
    income = (income * (1.0 + g_q1)).where(g_q1.notna(), income)

    try:
        permits_ytd = bps_ytd_units(T).reindex(metros.index)
    except RuntimeError:
        permits_ytd = pd.Series(float("nan"), index=metros.index)
    # Spec amendment 2026-07-20: pre-2022 YTD files are reported-only, so a
    # metro absent from the file carries its PRIOR-year annual pace x 5/12
    # (published before mid-year; vintage-clean).
    if "permits_annual" in shared:
        pa = shared["permits_annual"]
        prior = (pa[pa["year"] == T - 1].set_index("cbsa_code")["total_units"]
                 .reindex(metros.index))
        permits_ytd = permits_ytd.where(permits_ytd.notna(),
                                        prior * (YTD_MONTH / 12.0))

    rate = _ytd_rate(T)
    own = indicators._monthly_mortgage_payment(zhvi_t, pd.Series(rate, index=zhvi_t.index))

    nc = pd.DataFrame(index=metros.index)
    nc["cbsa_title"] = metros["cbsa_title"]
    nc["trailing_rent_growth"] = zori_t / zori_p - 1.0
    nc["cost_to_own_vs_rent"] = own / zori_t
    nc["permits_to_stock"] = permits_ytd * ANNUALIZE / stock
    nc["net_migration"] = mig / pop
    jg_carry = _latest_leq(ind, "job_growth", T - 1).reindex(metros.index)
    jg = ces_t / ces_p - 1.0
    nc["job_growth"] = jg.where(jg.notna(), jg_carry)
    nc["income_growth"] = g_q1.to_numpy()         # v0.6 Q1 state chain; NaN=neutral
    nc["rent_to_income"] = (zori_t * 12.0) / income
    nc["employment_diversity"] = _latest_leq(ind, "employment_diversity",
                                             T - 1).reindex(metros.index)
    nc = nc.reset_index()
    nc["year"] = T
    return nc[ind.columns]
