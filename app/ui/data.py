"""
data.py: shared, cached data access for every site page.

Loads the model outputs once (cached), prepares both editions (accurate /
finalized 2023 and speculative / provisional 2025), and holds the plain-
language dictionaries the skill requires (no raw column names or z-scores in
default views).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config                        # noqa: E402
from src import indicators, normalize  # noqa: E402
from src import score as score_mod  # noqa: E402

SCORE_YEAR = score_mod.SCORE_YEAR
SPEC_YEAR = 2025
VINTAGE_YEAR = 2024   # gate-passed lagged-vintage screen (decision log 2026-07-07)
INDICATORS = config.INDICATORS
N_IND = len(INDICATORS)
BUCKETS = ["Demand", "Supply", "Affordability", "Momentum", "Resilience"]

EDITION_KEY = "edition"
FINAL_LABEL = "Validated (finalized 2023)"
SPEC_LABEL = "Provisional (experimental 2025)"

# ---- Plain-language dictionaries -------------------------------------------
PRETTY = {
    "net_migration": "Net domestic migration",
    "job_growth": "Job growth",
    "income_growth": "Income growth",
    "permits_to_stock": "New building permits vs housing stock",
    "rent_to_income": "Rent as a share of income",
    "cost_to_own_vs_rent": "Cost to own vs rent",
    "trailing_rent_growth": "Recent rent growth",
    "employment_diversity": "Employment diversity",
}
# per-indicator human formats for raw values
FMT = {
    "net_migration": lambda v: f"{v*100:+.2f}% of population",
    "job_growth": lambda v: f"{v*100:+.1f}% a year",
    "income_growth": lambda v: f"{v*100:+.1f}% a year",
    "permits_to_stock": lambda v: f"{v*100:.1f}% of stock",
    "rent_to_income": lambda v: f"{v*100:.0f}% of income",
    "cost_to_own_vs_rent": lambda v: f"{v:.1f}× rent",
    "trailing_rent_growth": lambda v: f"{v*100:+.1f}% a year",
    "employment_diversity": lambda v: f"{v:.2f} (0–1)",
}
OUTLOOK = {
    "net_migration": ("People are moving in faster than most metros",
                      "More residents are leaving than arriving"),
    "job_growth": ("Jobs are growing faster than most metros",
                   "Job growth is lagging the pack"),
    "income_growth": ("Local incomes are rising quickly",
                      "Income growth is sluggish"),
    "permits_to_stock": ("Very little new building, so tight supply supports rents",
                         "Heavy homebuilding raises oversupply risk"),
    "rent_to_income": ("Rents are affordable vs local incomes, leaving room to grow",
                       "Rents already stretch local incomes"),
    "cost_to_own_vs_rent": ("Buying is far pricier than renting, keeping demand in rentals",
                            "Buying is relatively cheap, which can pull renters into ownership"),
    "trailing_rent_growth": ("Rents have been climbing lately",
                             "Recent rent growth has been weak"),
    "employment_diversity": ("A diverse job base makes it more resilient",
                             "The economy leans on just a few industries"),
}
BUCKET_GOOD = {"Demand": "Strong migration & jobs", "Supply": "Little new building",
               "Affordability": "Room for rents to grow", "Momentum": "Rents climbing",
               "Resilience": "Diverse economy"}
BUCKET_BAD = {"Demand": "Weak demand", "Supply": "Heavy construction",
              "Affordability": "Rents already stretched", "Momentum": "Rents cooling",
              "Resilience": "Concentrated economy"}
BUCKET_LABEL = {"Demand": "demand (migration & jobs)", "Supply": "limited new supply",
                "Affordability": "affordability", "Momentum": "rent momentum",
                "Resilience": "a diversified economy"}
CTX = {"rental_vacancy": ("Rental vacancy", "lower = healthier"),
       "ai_exposure": ("AI-exposure (white-collar share)", "higher = more AI-exposed")}

# Per-measure source + vintage ledger for the current (2024-vintage) screen
# (build-spec §4.5; the vintage-honesty rule made visible). The starred QCEW
# note is the disclosed Cleveland/Dayton 2024 transition gap.
VINTAGE_SOURCES = {
    "net_migration": ("Census population estimates, net domestic migration (a validated "
                      "substitute for the slower IRS data)", "2024"),
    "job_growth": ("BLS employment census (QCEW)", "2024 *"),
    "income_growth": ("BEA county personal income, rolled up to metros", "2024"),
    "permits_to_stock": ("Census building permits over ACS housing stock", "2024"),
    "rent_to_income": ("Zillow rent index vs BEA income", "2024"),
    "cost_to_own_vs_rent": ("Zillow home values vs rents, with mortgage rates (FRED)", "2024"),
    "trailing_rent_growth": ("Zillow rent index (ZORI)", "2024"),
    "employment_diversity": ("BLS employment census (QCEW), industry mix", "2024 *"),
}

STATE_CENTROIDS = {
    "AL": (32.8, -86.8), "AZ": (34.2, -111.7), "AR": (34.8, -92.4), "CA": (37.2, -119.5),
    "CO": (39.0, -105.5), "CT": (41.6, -72.7), "DE": (39.0, -75.5), "DC": (38.9, -77.0),
    "FL": (28.6, -81.7), "GA": (32.9, -83.4), "HI": (20.8, -156.3), "ID": (44.2, -114.5),
    "IL": (40.0, -89.2), "IN": (39.9, -86.3), "IA": (42.0, -93.5), "KS": (38.5, -98.4),
    "KY": (37.5, -85.3), "LA": (31.0, -92.0), "ME": (45.4, -69.2), "MD": (39.0, -76.8),
    "MA": (42.3, -71.9), "MI": (44.3, -85.0), "MN": (46.3, -94.3), "MS": (32.7, -89.7),
    "MO": (38.4, -92.5), "MT": (47.0, -109.6), "NE": (41.5, -99.8), "NV": (39.3, -116.6),
    "NH": (43.7, -71.6), "NJ": (40.1, -74.7), "NM": (34.4, -106.1), "NY": (42.9, -75.5),
    "NC": (35.5, -79.4), "ND": (47.5, -100.5), "OH": (40.3, -82.8), "OK": (35.6, -97.5),
    "OR": (43.9, -120.6), "PA": (40.9, -77.8), "RI": (41.7, -71.5), "SC": (33.9, -80.9),
    "SD": (44.4, -100.2), "TN": (35.8, -86.4), "TX": (31.3, -99.3), "UT": (39.3, -111.7),
    "VT": (44.1, -72.7), "VA": (37.6, -78.8), "WA": (47.4, -120.5), "WV": (38.6, -80.6),
    "WI": (44.6, -89.9), "WY": (43.0, -107.5),
}

# Rank-range machinery (uncertainty display): rank span across a few reasonable
# alternative weightings.
SCHEME_FACTORS = {"current": {}, "equal": None, "demand-tilt": {"Demand": 1.5},
                  "supply-tilt": {"Supply": 1.6}, "affordability-light": {"Affordability": 0.4}}


def _scheme_weights(factor):
    if factor is None:
        return {k: 1.0 / N_IND for k in INDICATORS}
    w = {k: INDICATORS[k]["weight"] * factor.get(INDICATORS[k]["bucket"], 1.0) for k in INDICATORS}
    tot = sum(w.values())
    return {k: v / tot for k, v in w.items()}


def rank_ranges(norm_df: pd.DataFrame, year: int) -> pd.DataFrame:
    z = norm_df[norm_df.year == year].set_index("cbsa_code")[list(INDICATORS)].fillna(0.0)
    ranks = {}
    for name, fac in SCHEME_FACTORS.items():
        w = _scheme_weights(fac)
        ranks[name] = sum(w[k] * z[k] for k in INDICATORS).rank(ascending=False, method="min")
    rk = pd.DataFrame(ranks)
    return pd.DataFrame({"rank_lo": rk.min(axis=1).astype(int),
                         "rank_hi": rk.max(axis=1).astype(int)})


def why_sentence(row) -> str:
    contribs = {b: row.get(f"bucket_{b}", 0.0) for b in BUCKETS}
    pos = max(contribs, key=contribs.get)
    neg = min(contribs, key=contribs.get)
    txt = (f"Ranks <b>#{int(row['rank'])}</b> chiefly on strong "
           f"<b>{BUCKET_LABEL[pos]}</b> ({contribs[pos]:+.2f})")
    if contribs[neg] < 0:
        txt += f", held back by weak <b>{BUCKET_LABEL[neg]}</b> ({contribs[neg]:+.2f})."
    else:
        txt += ", with no bucket dragging it down."
    return txt


def strength_drag(row) -> tuple[str, str]:
    """Largest positive / negative bucket contribution, as plain words."""
    c = {b: row.get(f"bucket_{b}", 0.0) for b in BUCKETS}
    bmax, bmin = max(c, key=c.get), min(c, key=c.get)
    strength = BUCKET_GOOD[bmax] if c[bmax] > 0.02 else "–"
    drag = BUCKET_BAD[bmin] if c[bmin] < -0.02 else "–"
    return strength, drag


def top_strengths(row) -> tuple[str, str]:
    """The two largest positive bucket contributions, as plain words
    (build-spec §4.2: primary / secondary strength). '' where nothing clears
    the same materiality floor strength_drag uses."""
    c = {b: row.get(f"bucket_{b}", 0.0) for b in BUCKETS}
    first, second = sorted(c, key=c.get, reverse=True)[:2]
    primary = BUCKET_GOOD[first] if c[first] > 0.02 else ""
    secondary = BUCKET_GOOD[second] if c[second] > 0.02 else ""
    return primary, secondary


def national_rent_growth(panel_df: pd.DataFrame, year: int) -> float:
    now = panel_df[panel_df.year == year][["cbsa_code", "zori"]]
    prev = panel_df[panel_df.year == year - 1][["cbsa_code", "zori"]].rename(columns={"zori": "p"})
    m = now.merge(prev, on="cbsa_code").dropna()
    return float((m["zori"] / m["p"] - 1).median()) if len(m) else float("nan")


def regime_of(year: int) -> str:
    for name, (lo, hi) in config.REGIMES.items():
        if lo <= year <= hi:
            return name
    return "unknown"


@st.cache_data(show_spinner=False)
def load() -> dict:
    scored = score_mod.score()
    raw = indicators.compute_indicators()
    norm = normalize.normalize()
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    coords = pd.read_csv(config.PROCESSED_DIR / "metro_coords.csv", dtype={"cbsa_code": str})
    backtest = pd.read_csv(config.PROCESSED_DIR / "backtest_summary.csv")
    reg_path = config.PREDICTIONS_DIR / "registry_index.csv"
    registry = pd.read_csv(reg_path) if reg_path.exists() else pd.DataFrame()

    # Prior edition's frozen ranks (change-vs-edition column) + the committed
    # monthly rent-trend extract (Market spotlight chart).
    prior_path = config.PROCESSED_DIR / "ranking_2023.csv"
    prior_rank = (pd.read_csv(prior_path, dtype={"cbsa_code": str})
                  [["cbsa_code", "rank"]].rename(columns={"rank": "prior_rank"})
                  if prior_path.exists() else pd.DataFrame())
    trend_path = config.PROCESSED_DIR / "spotlight_rent_trend.csv"
    rent_trend = (pd.read_csv(trend_path, dtype={"cbsa_code": str})
                  if trend_path.exists() else pd.DataFrame())

    nc_dir = config.PROCESSED_DIR / "nowcast"
    def _csv(name):
        p = nc_dir / name
        return pd.read_csv(p, dtype={"cbsa_code": str}) if p.exists() else pd.DataFrame()
    nowcast, nc_prov = _csv("provisional_2025_ranking.csv"), _csv("provenance.csv")
    nc_raw, nc_norm = _csv("nowcast_2025_raw.csv"), _csv("nowcast_2025_norm.csv")
    # Gate outcome controls publication (config.NOWCAST_PUBLISHED): the one-shot
    # CES re-run missed the pre-committed gate, so the edition is pulled.
    has_spec = (config.NOWCAST_PUBLISHED
                and len(nowcast) > 0 and len(nc_raw) > 0 and len(nc_norm) > 0)

    acc_rank = scored[scored["year"] == SCORE_YEAR].merge(
        rank_ranges(norm, SCORE_YEAR), on="cbsa_code", how="left")
    acc_raw = raw[raw["year"] == SCORE_YEAR].set_index("cbsa_code")
    acc_pct = (norm[norm["year"] == SCORE_YEAR].set_index("cbsa_code")[list(INDICATORS)]
               .rank(pct=True) * 100)

    if has_spec:
        spec_rank = nowcast.merge(rank_ranges(nc_norm, SPEC_YEAR), on="cbsa_code", how="left")
        spec_raw = nc_raw.set_index("cbsa_code")
        spec_pct = nc_norm.set_index("cbsa_code")[list(INDICATORS)].rank(pct=True) * 100
    else:
        spec_rank, spec_raw, spec_pct = acc_rank, acc_raw, acc_pct

    # Validated lagged-vintage screen (gate PASSED 2026-07-07): primary edition.
    vdir = config.PROCESSED_DIR / "vintage"
    def _vcsv(name):
        p = vdir / name
        return pd.read_csv(p, dtype={"cbsa_code": str}) if p.exists() else pd.DataFrame()
    v_rank_raw = _vcsv(f"vintage_{VINTAGE_YEAR}_ranking.csv")
    v_raw = _vcsv(f"vintage_{VINTAGE_YEAR}_raw.csv")
    v_norm = _vcsv(f"vintage_{VINTAGE_YEAR}_norm.csv")
    has_vintage = len(v_rank_raw) > 0 and len(v_raw) > 0 and len(v_norm) > 0
    if has_vintage:
        vint_rank = v_rank_raw.merge(rank_ranges(v_norm, VINTAGE_YEAR), on="cbsa_code", how="left")
        vint_raw = v_raw.set_index("cbsa_code")
        vint_pct = v_norm.set_index("cbsa_code")[list(INDICATORS)].rank(pct=True) * 100
    else:
        vint_rank, vint_raw, vint_pct = acc_rank, acc_raw, acc_pct

    primary_year = VINTAGE_YEAR if has_vintage else SCORE_YEAR
    ctx_year = panel[panel["year"] == primary_year].set_index("cbsa_code")
    ctx_pct = ctx_year[list(CTX)].rank(pct=True) * 100

    pc = backtest[(backtest["horizon"] == 3) & (backtest["regime"] == "pre_covid")]
    pc_tau = float(pc["mean_tau"].iloc[0]) if len(pc) else float("nan")
    spec_tau = float("nan")
    m3 = config.PROCESSED_DIR / "nowcast" / "m3_summary.csv"
    if m3.exists():
        m3d = pd.read_csv(m3)
        m3r = m3d[(m3d["horizon"] == 3) & (m3d["regime"] == "pre_covid")]
        if len(m3r):
            spec_tau = float(m3r["mean_tau_ps"].iloc[0])
    # Provisional-vs-finalized ranking divergence (shown on every provisional
    # disclosure per the amended gate taxonomy, decision-log 2026-07-06).
    overlap_mean, overlap_last = float("nan"), float("nan")
    agree = config.PROCESSED_DIR / "nowcast" / "m3_agreement.csv"
    if agree.exists():
        ag = pd.read_csv(agree)
        if len(ag):
            overlap_mean = float(ag["top10_overlap"].mean())
            overlap_last = float(ag.sort_values("year")["top10_overlap"].iloc[-1])

    return dict(scored=scored, panel=panel, coords=coords, backtest=backtest,
                registry=registry, prior_rank=prior_rank, rent_trend=rent_trend,
                nowcast=nowcast, nc_prov=nc_prov,
                has_spec=has_spec, acc_rank=acc_rank, acc_raw=acc_raw, acc_pct=acc_pct,
                spec_rank=spec_rank, spec_raw=spec_raw, spec_pct=spec_pct,
                has_vintage=has_vintage, vint_rank=vint_rank, vint_raw=vint_raw,
                vint_pct=vint_pct, primary_year=primary_year,
                ctx_year=ctx_year, ctx_pct=ctx_pct, pc_tau=pc_tau, spec_tau=spec_tau,
                overlap_mean=overlap_mean, overlap_last=overlap_last,
                nat_growth=national_rent_growth(panel, primary_year),
                regime=regime_of(primary_year))


def is_spec(d: dict | None = None) -> bool:
    """Current edition from the global sidebar toggle."""
    choice = st.session_state.get(EDITION_KEY, FINAL_LABEL)
    spec = str(choice).startswith("Provisional")
    if d is not None and not d["has_spec"]:
        return False
    return spec


def edition(d: dict) -> dict:
    """The active edition's frames + labels, in one place. Primary = the
    gate-passed 2024-vintage screen when its outputs exist."""
    if is_spec(d):
        return dict(rank=d["spec_rank"], raw=d["spec_raw"], pct=d["spec_pct"],
                    year=SPEC_YEAR, provisional=True, vintage=False,
                    badge_label=None, horizon=f"{SPEC_YEAR}→{SPEC_YEAR+3}")
    if d.get("has_vintage"):
        return dict(rank=d["vint_rank"], raw=d["vint_raw"], pct=d["vint_pct"],
                    year=VINTAGE_YEAR, provisional=False, vintage=True,
                    badge_label=f"Validated · {VINTAGE_YEAR} vintage",
                    horizon=f"{VINTAGE_YEAR}→{VINTAGE_YEAR+3}")
    return dict(rank=d["acc_rank"], raw=d["acc_raw"], pct=d["acc_pct"],
                year=SCORE_YEAR, provisional=False, vintage=False,
                badge_label=None, horizon=f"{SCORE_YEAR}→{SCORE_YEAR+3}")
