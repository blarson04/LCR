"""
proxy_map.py — the single source of truth for how each v2 indicator is nowcast.

For every indicator in the frozen v2 (8-indicator) model, this records its
publication lag and, when slow, the fast proxy used by the v2.1 nowcast layer.
build_nowcast_panel.py (M2) and nowcast_backtest.py (M3) both read this so the
proxy definitions live in exactly one place.

strategy:
  fast          — already current; use the finalized source as-is
  proxy         — replace the slow finalized input with a fast-publishing proxy
  carry_forward — highly persistent year to year; reuse the prior year's value

NB: the v2 model dropped population_growth and mf_pipeline (de-duplication), so
only the 8 scored indicators appear here.
"""

from __future__ import annotations

PROXY_MAP_VERSION = "0.4"   # 2026-07-08: state-chained income adopted (gate PASSED)

PROXY_MAP = {
    "net_migration": {
        "strategy": "proxy", "proxy_source": "census_pep",
        "finalized": "IRS SOI county flows (~2y lag)",
        "proxy": "Census PEP net domestic migration (~6mo lag)",
        "validated": "M1: level r~0.99, rank ~0.90/yr; ranking-substitution Spearman ~0.98"},
    "job_growth": {
        "strategy": "proxy", "proxy_source": "bls_ces",
        "finalized": "BLS QCEW (~6-9mo)",
        "proxy": "BLS CES monthly metro employment via FRED (~2mo); carry-forward "
                 "fallback for the few metros without a current series",
        "validated": "P1 QA: 110/110 mapped; growth rank-agreement vs QCEW 0.90-0.96 every year"},
    "income_growth": {
        "strategy": "proxy", "proxy_source": "bea_state_chain",
        "finalized": "BEA regional income (~1.5y)",
        "proxy": "prior finalized metro income chained by the primary state's BEA "
                 "per-capita income growth (states publish about a year ahead of "
                 "metros; the earlier hourly-earnings proxy stays rejected)",
        "validated": "v0.4 QA: rank agreement vs finalized metro income growth "
                     "0.51-0.66 every year (mean 0.60) vs 0.11 for the flat carry; "
                     "gate PASSED 2026-07-08 at 96.56% retention"},
    "permits_to_stock": {
        "strategy": "proxy", "proxy_source": "bps_monthly",
        "finalized": "Census BPS annual + ACS stock (~1y)",
        "proxy": "BPS monthly YTD permits annualized; housing stock carried forward",
        "validated": "stock carry-forward YoY rank corr 1.00 (M1)"},
    "rent_to_income": {
        "strategy": "proxy", "proxy_source": "zori+state_chained_income",
        "finalized": "ZORI + BEA income (~1.5y via income)",
        "proxy": "current ZORI over the state-chained income level (same chain as "
                 "income_growth)",
        "validated": "covered by the v0.4 gate (2026-07-08)"},
    "cost_to_own_vs_rent": {
        "strategy": "fast",
        "finalized": "ZHVI + ZORI + FRED mortgage (~weeks)", "proxy": "same — already fast"},
    "trailing_rent_growth": {
        "strategy": "fast",
        "finalized": "ZORI (~weeks)", "proxy": "same — already fast"},
    "employment_diversity": {
        "strategy": "carry_forward",
        "finalized": "QCEW industry HHI (~6-9mo)",
        "proxy": "carry forward prior-year HHI",
        "validated": "YoY rank corr 0.84 (M1)"},
}

# Provenance tags used on every nowcast panel value.
PROVENANCE = ("finalized", "proxy", "carried_forward")
