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

PROXY_MAP_VERSION = "0.1"

PROXY_MAP = {
    "net_migration": {
        "strategy": "proxy", "proxy_source": "census_pep",
        "finalized": "IRS SOI county flows (~2y lag)",
        "proxy": "Census PEP net domestic migration (~6mo lag)",
        "validated": "M1: level r~0.99, rank ~0.90/yr; ranking-substitution Spearman ~0.98"},
    "job_growth": {
        "strategy": "proxy", "proxy_source": "bls_ces",
        "finalized": "BLS QCEW (~6-9mo)",
        "proxy": "BLS CES/SAE monthly metro employment (~2mo)",
        "validated": "pending M1 CES build"},
    "income_growth": {
        "strategy": "proxy", "proxy_source": "bls_ces_wages",
        "finalized": "BEA regional income (~1.5y)",
        "proxy": "CES/QCEW wage growth as income-growth proxy",
        "validated": "pending"},
    "permits_to_stock": {
        "strategy": "proxy", "proxy_source": "bps_monthly",
        "finalized": "Census BPS annual + ACS stock (~1y)",
        "proxy": "BPS monthly YTD permits annualized; housing stock carried forward",
        "validated": "stock carry-forward YoY rank corr 1.00 (M1)"},
    "rent_to_income": {
        "strategy": "proxy", "proxy_source": "zori+projected_income",
        "finalized": "ZORI + BEA income (~1.5y via income)",
        "proxy": "current ZORI over wage-growth-projected income",
        "validated": "pending"},
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
