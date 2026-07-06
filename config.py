"""
Central configuration for the Multifamily Market Screener.

Everything that is a *choice* (which metros, how heavily we weight each
indicator, where regimes start and end, where files live) lives here so the
pipeline code stays generic and these knobs are easy to find and change.

The "why" behind every number is in decision-log.md. Cross-references to that
log are noted inline.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Paths  (everything is relative to this file, so it works on any machine)
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"            # cached source downloads (gitignored)
PROCESSED_DIR = DATA_DIR / "processed"  # cleaned metro x year panel
PREDICTIONS_DIR = ROOT / "predictions"  # frozen, timestamped prediction runs

for _d in (RAW_DIR, PROCESSED_DIR, PREDICTIONS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Metro universe  (decision-log: "Metro universe: 500k population floor")
# --------------------------------------------------------------------------
# A metro must clear BOTH gates to enter the panel:
#   1. population >= POP_FLOOR
#   2. continuous rent-index history back to RENT_HISTORY_START
# Every metro that fails a gate is logged with the reason (transparency is
# part of the methodology).
POP_FLOOR = 500_000
RENT_HISTORY_START = 2015   # ZORI reaches ~2015; Apartment List ~2017
# A metro clears the rent gate if its ZORI is gap-free through the latest year
# and starts no later than this. Set to 2016 (not 2015) so two legitimate ~600k
# metros — Jackson, MS and Syracuse, NY — aren't dropped for missing only the
# 2015 baseline year (decision-log 2026-06-29). They get a blank 2015 cell.
RENT_GATE_LATEST_START = 2016

# --------------------------------------------------------------------------
# Forecast target  (decision-log: "Forecast horizon")
# --------------------------------------------------------------------------
PRIMARY_HORIZON_YEARS = 3   # the real target: 3-year forward rent growth
CONTRAST_HORIZON_YEARS = 1  # reported as a foil, not the target

# --------------------------------------------------------------------------
# Indicator weights
# v2 = the DE-DUPLICATED 8-indicator scheme (see v2-findings.md, P2/P4):
# population_growth was folded into net_migration (r=0.62) and mf_pipeline into
# permits_to_stock (r=0.77) — the bootstrap showed this matches the v1 10-indicator
# model with no reliable accuracy loss, so we prefer the more parsimonious set.
# Bucket totals are unchanged (Demand 40 / Supply 25 / Affordability 20 /
# Momentum 10 / Resilience 5). Weights are HAND-SET (not fitted) and sum to 1.0.
# "inverse": True means higher raw value is WORSE; indicators.py flips it so
# that after flipping, higher = better for every indicator.
# (The v1 weights are preserved in git history + the frozen v1 registry run.)
# --------------------------------------------------------------------------
INDICATORS = {
    # ---- Demand: 40% ----
    "net_migration":        {"weight": 0.20, "inverse": False, "bucket": "Demand"},
    "job_growth":           {"weight": 0.12, "inverse": False, "bucket": "Demand"},
    "income_growth":        {"weight": 0.08, "inverse": False, "bucket": "Demand"},
    # ---- Supply: 25% ----
    "permits_to_stock":     {"weight": 0.25, "inverse": True,  "bucket": "Supply"},
    # ---- Affordability: 20% ----
    "rent_to_income":       {"weight": 0.12, "inverse": True,  "bucket": "Affordability"},
    "cost_to_own_vs_rent":  {"weight": 0.08, "inverse": False, "bucket": "Affordability"},
    # ---- Momentum: 10% (confirmation only) ----
    "trailing_rent_growth": {"weight": 0.10, "inverse": False, "bucket": "Momentum"},
    # ---- Resilience: 5% ----
    "employment_diversity": {"weight": 0.05, "inverse": False, "bucket": "Resilience"},
}

BUCKET_WEIGHTS = {  # derived; handy for charts and sanity checks
    "Demand": 0.40, "Supply": 0.25, "Affordability": 0.20,
    "Momentum": 0.10, "Resilience": 0.05,
}

# --------------------------------------------------------------------------
# Regime windows  (decision-log: "COVID era — segment by regime")
# Each backtest result is reported per regime AND pooled. Windows are tagged
# by the regime(s) they span.
# --------------------------------------------------------------------------
REGIMES = {
    "pre_covid":     (2015, 2019),   # baseline
    "shock":         (2020, 2022),   # stimulus + remote-work spike (anomalous)
    "normalization": (2023, 2099),   # supply thesis playing out; 2099 = "present"
}

# --------------------------------------------------------------------------
# Backtest knobs  (decision-log: "Evaluation metric" / "Winsorize")
# --------------------------------------------------------------------------
# Regime/confidence flag rule (v3-P6): the flag fires when national (median-
# metro) year-over-year asking-rent growth in the SCORING year exceeds this.
# Uses only scoring-date-available data (ZORI is near-live). The 7.5% value
# shipped on 2026-07-02, BEFORE the ex-ante validation in src/regime_flag.py —
# it is validated as-is, not tuned. Known limitation (disclosed): it detects
# rent-spike regimes (the observed failure mode); a novel shock type that
# doesn't move rents may not be flagged.
REGIME_FLAG_THRESHOLD = 0.075

WINSOR_LIMITS = (0.01, 0.99)   # cap rent-growth outliers at 1st / 99th pct
TAU_RANK_BASIS = "realized"    # weightedtau weighting: "realized" | "predicted" | "symmetric"
PRECISION_K = 10               # headline metric: precision@10
RANDOM_SEED = 42               # set wherever randomness enters, for reproducibility

# Model version — bump when weights, indicators, or methodology change. Stamped
# into every frozen prediction run so the track record is unambiguous.
MODEL_VERSION = "2.0.0"

# Whether the provisional (nowcast) edition may be shown on the site. Set by
# gate outcomes ONLY (decision-log entries 2026-07-06): the one-shot CES re-run
# missed the pre-committed gate (τ retention 84.7% < 85%; mean top-10 overlap
# 6.7 < 7), so per the binding consequence the edition is pulled. Do not flip
# this without a new pre-registered gate that passes.
NOWCAST_PUBLISHED = False


def validate_weights() -> None:
    """Fail loudly if the hand-set weights ever stop summing to 1.0."""
    total = sum(spec["weight"] for spec in INDICATORS.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"Indicator weights must sum to 1.0, got {total:.4f}")


if __name__ == "__main__":
    validate_weights()
    print("config.py OK")
    print(f"  root            : {ROOT}")
    print(f"  indicators      : {len(INDICATORS)} (weights sum to 1.0)")
    print(f"  population floor : {POP_FLOOR:,}")
    print(f"  rent history     : {RENT_HISTORY_START}+")
    print(f"  regimes          : {', '.join(REGIMES)}")
