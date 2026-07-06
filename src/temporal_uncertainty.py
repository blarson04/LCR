"""
temporal_uncertainty.py — honest uncertainty statements (v3 P3).

The metro-cluster bootstrap CI answers only "which metros", conditional on the
six observed, overlapping windows — the dominant uncertainty is which regime a
window lands in. This module produces the honest replacements:

  1. PER-WINDOW RANGE (the primary uncertainty statement): min/max pooled τ
     across the observed 3-yr and 1-yr windows.
  2. JACKKNIFE OVER WINDOWS: drop each window, recompute the pooled mean —
     how much does any single window move the headline?
  3. STATE-CLUSTER BOOTSTRAP (sensitivity): metros co-move within states/regions,
     so resample STATES rather than metros; report the full-model τ CI and
     whether the equal-weight edge (the one 'reliable' model-vs-baseline win)
     survives clustering.

Writes data/processed/temporal_uncertainty.csv and prints a summary.

    .venv/Scripts/python.exe src/temporal_uncertainty.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import normalize           # noqa: E402
from src import score as score_mod  # noqa: E402
from src import backtest, uncertainty  # noqa: E402

B = 800
INDICATORS = list(config.INDICATORS)


def _primary_state(title: str) -> str:
    return title.rsplit(",", 1)[-1].strip().split("-")[0].strip()


def run() -> dict:
    win = pd.read_csv(config.PROCESSED_DIR / "backtest_windows.csv")
    out: dict[str, float | int | bool] = {}

    # 1) per-window ranges
    for h in (3, 1):
        t = win[win.horizon == h]["weighted_tau"]
        out[f"win{h}_min"], out[f"win{h}_max"], out[f"win{h}_n"] = (
            float(t.min()), float(t.max()), int(len(t)))

    # 2) jackknife over windows (3-yr pooled = mean over windows)
    t3 = win[win.horizon == 3]["weighted_tau"].to_numpy()
    jk = [float(np.delete(t3, i).mean()) for i in range(len(t3))]
    out["jk3_min"], out["jk3_max"] = min(jk), max(jk)

    # 3) state-cluster bootstrap (full model + equal-weight gap)
    norm = normalize.normalize()
    scored = score_mod.score()
    zori = backtest._zori_lookup()
    pred_years = backtest.usable_pred_years(scored)

    z = norm[INDICATORS].fillna(0.0)
    eq = norm[["cbsa_code", "year"]].copy()
    eq["score"] = z.mean(axis=1).to_numpy()
    cols = {"full": scored[["cbsa_code", "year", "score"]], "equal": eq}
    frames = uncertainty._window_frames(cols, pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))

    state_of = dict(zip(scored["cbsa_code"], scored["cbsa_title"].map(_primary_state)))
    by_state: dict[str, list[str]] = {}
    for m in metros:
        by_state.setdefault(state_of.get(m, "?"), []).append(m)
    states = sorted(by_state)
    out["n_states"] = len(states)

    rng = np.random.default_rng(config.RANDOM_SEED)
    tau_b, gap_b = np.empty(B), np.empty(B)
    for b in range(B):
        draw = rng.choice(states, size=len(states), replace=True)
        sample = [m for s in draw for m in by_state[s]]   # duplicates intended
        tf = uncertainty._pooled_tau(frames, sample, "full")
        te = uncertainty._pooled_tau(frames, sample, "equal")
        tau_b[b], gap_b[b] = tf, tf - te
    out["state_tau_lo"], out["state_tau_hi"] = map(float, np.nanpercentile(tau_b, [2.5, 97.5]))
    out["state_gap_lo"], out["state_gap_hi"] = map(float, np.nanpercentile(gap_b, [2.5, 97.5]))
    out["eq_edge_survives_state_cluster"] = bool(out["state_gap_lo"] > 0)
    out["B"] = B

    pd.DataFrame([out]).to_csv(config.PROCESSED_DIR / "temporal_uncertainty.csv", index=False)
    return out


def main() -> None:
    r = run()
    print("=== P3 temporal / clustered uncertainty (3-yr unless noted) ===\n")
    print(f"  per-window tau range (PRIMARY): 3y [{r['win3_min']:+.2f}, {r['win3_max']:+.2f}] "
          f"across {r['win3_n']} windows; 1y [{r['win1_min']:+.2f}, {r['win1_max']:+.2f}]")
    print(f"  jackknife over windows (pooled 3y): [{r['jk3_min']:.3f}, {r['jk3_max']:.3f}]")
    print(f"  state-cluster bootstrap ({r['n_states']} states, B={r['B']}):")
    print(f"    full-model pooled tau 95% CI [{r['state_tau_lo']:.3f}, {r['state_tau_hi']:.3f}]")
    print(f"    full - equal-weight gap CI   [{r['state_gap_lo']:+.3f}, {r['state_gap_hi']:+.3f}]"
          f"  -> equal-weight edge {'SURVIVES' if r['eq_edge_survives_state_cluster'] else 'does NOT survive'} clustering")
    print("\n  (Pooled metro-cluster CIs are hereafter labeled 'cross-sectional, conditional")
    print("   on observed windows' — they do not capture regime risk.)")


if __name__ == "__main__":
    main()
