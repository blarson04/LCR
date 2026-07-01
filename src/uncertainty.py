"""
uncertainty.py — confidence intervals on tau and on the P1/P2 gaps (V2 P3).

Every tau so far is a point estimate from ~7 overlapping windows. This puts
error bars on them with a **metro-cluster bootstrap**: resample the ~110 metros
with replacement (a metro is the unit of dependence — it recurs across windows),
recompute the pooled 3-yr tau, repeat B times, take percentile CIs.

Crucially it does this **paired**, on the same resample, for competing rankings,
so we get CIs on:
  - the full model's tau,
  - baseline gaps (full - equal-weight / - best-single / - persistence),  [P1]
  - ablation deltas (drop-one - full; >0 means dropping helped).             [P2]

A gap whose CI straddles 0 is not distinguishable from noise — that's the
decision rule for what to actually cut in a leaner v2.

    .venv/Scripts/python.exe src/uncertainty.py
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
from src import backtest            # noqa: E402

HORIZON = 3          # CIs on the primary target
B = 1000             # bootstrap replicates
SEED = config.RANDOM_SEED
INDICATORS = list(config.INDICATORS)
W = {k: v["weight"] for k, v in config.INDICATORS.items()}


def _score_columns(norm: pd.DataFrame, zori: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return {name: DataFrame[cbsa_code, year, score]} for every ranking we compare."""
    z = norm[INDICATORS].fillna(0.0)
    full = sum(W[k] * z[k] for k in INDICATORS)
    keys = norm[["cbsa_code", "year"]]

    def mk(series):
        d = keys.copy(); d["score"] = np.asarray(series); return d

    cols = {
        "full": mk(full),
        "equal_weight": mk(z.mean(axis=1)),
        "best_single (momentum)": mk(z["trailing_rent_growth"]),
    }
    for k in ["cost_to_own_vs_rent", "income_growth", "employment_diversity",
              "permits_to_stock", "net_migration"]:
        cols[f"drop:{k}"] = mk(full - W[k] * z[k])

    # persistence = trailing HORIZON-yr rent growth
    prev = zori.rename(columns={"zori": "z_prev"}).copy(); prev["year"] += HORIZON
    pers = zori.merge(prev, on=["cbsa_code", "year"], how="left")
    pers["score"] = pers["zori"] / pers["z_prev"] - 1.0
    cols["persistence"] = pers[["cbsa_code", "year", "score"]]
    return cols


def _window_frames(score_cols, pred_years, zori):
    """One frame per 3-yr window, indexed by cbsa_code, holding realized growth +
    every ranking's score (inner-joined so all rankings cover the same metros)."""
    latest = int(zori["year"].max())
    frames = []
    for T in pred_years:
        if T + HORIZON > latest:
            continue
        now = zori[zori.year == T][["cbsa_code", "zori"]].rename(columns={"zori": "z0"})
        fut = zori[zori.year == T + HORIZON][["cbsa_code", "zori"]].rename(columns={"zori": "z1"})
        base = now.merge(fut, on="cbsa_code")
        base = base[base.z0 > 0].copy()
        base["realized"] = backtest._winsorize(base["z1"] / base["z0"] - 1.0)
        f = base[["cbsa_code", "realized"]]
        for name, df in score_cols.items():
            f = f.merge(df[df.year == T][["cbsa_code", "score"]].rename(columns={"score": name}),
                        on="cbsa_code", how="inner")
        frames.append(f.set_index("cbsa_code"))
    return frames


def _pooled_tau(frames, sample, col):
    taus = []
    for f in frames:
        sub = f.reindex(sample).dropna(subset=[col, "realized"])
        if len(sub) >= config.PRECISION_K:
            taus.append(backtest._weighted_tau_by_realized(
                sub[col].to_numpy(), sub["realized"].to_numpy()))
    return float(np.mean(taus)) if taus else np.nan


def run():
    norm = normalize.normalize()
    scored = score_mod.score()
    zori = backtest._zori_lookup()
    pred_years = backtest.usable_pred_years(scored)
    cols = _score_columns(norm, zori)
    frames = _window_frames(cols, pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    names = list(cols)

    rng = np.random.default_rng(SEED)
    point = {n: _pooled_tau(frames, metros, n) for n in names}          # full-sample estimate
    boot = {n: np.empty(B) for n in names}
    for b in range(B):
        s = rng.choice(metros, size=len(metros), replace=True)
        for n in names:
            boot[n][b] = _pooled_tau(frames, s, n)

    def ci(arr):
        return float(np.nanpercentile(arr, 2.5)), float(np.nanpercentile(arr, 97.5))

    # full-model tau + CI
    full_ci = ci(boot["full"])
    tau_rows = [{"ranking": n, "tau": point[n], "lo": ci(boot[n])[0], "hi": ci(boot[n])[1]}
                for n in names]

    # paired gaps
    gaps = []
    for n in ["equal_weight", "best_single (momentum)", "persistence"]:
        d = boot["full"] - boot[n]
        gaps.append({"comparison": f"full - {n}", "kind": "baseline uplift",
                     "delta": point["full"] - point[n], "lo": ci(d)[0], "hi": ci(d)[1],
                     "excludes_0": ci(d)[0] > 0 or ci(d)[1] < 0})
    for n in [c for c in names if c.startswith("drop:")]:
        d = boot[n] - boot["full"]      # >0 => dropping helps
        gaps.append({"comparison": f"{n} (drop helps if >0)", "kind": "ablation delta",
                     "delta": point[n] - point["full"], "lo": ci(d)[0], "hi": ci(d)[1],
                     "excludes_0": ci(d)[0] > 0 or ci(d)[1] < 0})
    return point, full_ci, pd.DataFrame(tau_rows), pd.DataFrame(gaps)


def main() -> None:
    point, full_ci, tau_df, gaps = run()
    tau_df.to_csv(config.PROCESSED_DIR / "uncertainty_tau.csv", index=False)
    gaps.to_csv(config.PROCESSED_DIR / "uncertainty_gaps.csv", index=False)

    print(f"=== P3 uncertainty ({HORIZON}-yr tau, metro-cluster bootstrap, B={B}) ===\n")
    print(f"Full model 3y tau = {point['full']:.3f}   95% CI [{full_ci[0]:.3f}, {full_ci[1]:.3f}]\n")

    print("Ranking tau with 95% CI:")
    print(f"  {'ranking':<26}{'tau':>7}{'  95% CI':>18}")
    for _, r in tau_df.sort_values("tau", ascending=False).iterrows():
        print(f"  {r['ranking']:<26}{r['tau']:>7.3f}   [{r['lo']:+.3f}, {r['hi']:+.3f}]")

    print("\nGaps (95% CI); 'yes' = CI excludes 0 => distinguishable from noise:")
    print(f"  {'comparison':<40}{'delta':>8}{'  95% CI':>18}{'  sig?':>6}")
    for _, r in gaps.iterrows():
        sig = "yes" if r["excludes_0"] else "no"
        print(f"  {r['comparison']:<40}{r['delta']:>+8.3f}   [{r['lo']:+.3f}, {r['hi']:+.3f}]  {sig:>4}")

    print("\nReading it: with only ~6 windows and ~110 metros, CIs are wide. A gap whose")
    print("CI straddles 0 is NOT reliable evidence — don't cut/keep on it alone (V2 W4).")


if __name__ == "__main__":
    main()
