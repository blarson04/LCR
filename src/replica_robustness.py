"""
replica_robustness.py — P5: the industry-replica robustness pair (descriptive).

Runs the two exhibits frozen in the 2026-07-08 P5 spec entry, once, and
publishes both outcomes whichever way they land:

  1. TOP-50 SUBUNIVERSE — the composite-vs-replica comparison restricted to
     the 50 largest universe metros (Arbor's universe is the largest 50).
     Answers the strongest hostile objection: "different universe."
  2. ALTERNATE-TASK FAIRNESS — both rankings scored at two tasks closer to
     the replica's implied one: (a) 1-yr-forward rent growth; (b) a blended
     target = the within-year z-score mean of 3-yr forward rent growth and
     3-yr forward CREMI MF Asset.Value change (equal blend, winsorized like
     the primary target).

Framing rule, welded here and everywhere these numbers appear: the claim is
"equal-weight conditions indices are not rent-growth predictors," never "we
beat Arbor" — and the four omitted categories (capital markets, taxes, ZORDI,
insurance) are plausibly their strongest. First results are final.

    .venv/Scripts/python.exe src/replica_robustness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                        # noqa: E402
from src import backtest, industry_baseline  # noqa: E402
from src import score as score_mod  # noqa: E402
from src.ingest import cremi         # noqa: E402
from src.tier2_gate import _zwithin  # noqa: E402

B_BOOT = 800
OUT_CSV = config.PROCESSED_DIR / "replica_robustness.csv"


def _window_frames(score_cols: dict[str, pd.DataFrame], pred_years,
                   realized_fn) -> list[pd.DataFrame]:
    """One frame per prediction year: realized target + each ranking's score,
    inner-joined so both rankings cover the same metros."""
    frames = []
    for T in pred_years:
        base = realized_fn(T)
        if base is None or len(base) < config.PRECISION_K:
            continue
        f = base
        for name, df in score_cols.items():
            f = f.merge(df[df.year == T][["cbsa_code", "score"]]
                        .rename(columns={"score": name}), on="cbsa_code", how="inner")
        if len(f) >= config.PRECISION_K:
            frames.append(f.set_index("cbsa_code"))
    return frames


def _pooled_tau(frames, sample, col) -> float:
    taus = []
    for f in frames:
        sub = f.reindex(sample).dropna(subset=[col, "realized"])
        if len(sub) >= config.PRECISION_K:
            taus.append(backtest._weighted_tau_by_realized(
                sub[col].to_numpy(), sub["realized"].to_numpy()))
    return float(np.mean(taus)) if taus else np.nan


def _gap_ci(frames) -> tuple[float, float, float, float, float]:
    """(tau_full, tau_replica, gap, lo, hi) with a metro-cluster bootstrap."""
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    t_full = _pooled_tau(frames, metros, "full")
    t_rep = _pooled_tau(frames, metros, "replica")
    rng = np.random.default_rng(config.RANDOM_SEED)
    boot = np.empty(B_BOOT)
    for b in range(B_BOOT):
        s = rng.choice(metros, size=len(metros), replace=True)
        boot[b] = _pooled_tau(frames, s, "full") - _pooled_tau(frames, s, "replica")
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    return t_full, t_rep, t_full - t_rep, float(lo), float(hi)


def main() -> None:
    replica = industry_baseline.build_replica()
    scored = score_mod.score()[["cbsa_code", "year", "score"]]
    zori = backtest._zori_lookup()
    pred_years = backtest.usable_pred_years(score_mod.score())
    cols = {"full": scored, "replica": replica}
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")

    def rent_target(h):
        def fn(T):
            if T + h > int(zori["year"].max()):
                return None
            now = zori[zori.year == T][["cbsa_code", "zori"]].rename(columns={"zori": "z0"})
            fut = zori[zori.year == T + h][["cbsa_code", "zori"]].rename(columns={"zori": "z1"})
            base = now.merge(fut, on="cbsa_code")
            base = base[base.z0 > 0].copy()
            base["realized"] = backtest._winsorize(base["z1"] / base["z0"] - 1.0)
            return base[["cbsa_code", "realized"]]
        return fn

    rows = []

    # ---- Exhibit 1: top-50 subuniverse, primary 3-yr task -------------------
    latest_pop = (panel.dropna(subset=["population"])
                  .sort_values("year").groupby("cbsa_code").tail(1))
    top50 = set(latest_pop.nlargest(50, "population")["cbsa_code"])
    cols50 = {n: df[df["cbsa_code"].isin(top50)] for n, df in cols.items()}
    frames50 = _window_frames(cols50, pred_years, rent_target(3))
    tf, tr, gap, lo, hi = _gap_ci(frames50)
    rows.append({"exhibit": "top50_subuniverse", "task": "3y rent growth",
                 "tau_full": tf, "tau_replica": tr, "gap": gap,
                 "ci_lo": lo, "ci_hi": hi, "n_windows": len(frames50)})

    # ---- Exhibit 2a: full universe, 1-yr task --------------------------------
    frames1 = _window_frames(cols, pred_years, rent_target(1))
    tf, tr, gap, lo, hi = _gap_ci(frames1)
    rows.append({"exhibit": "alternate_task", "task": "1y rent growth",
                 "tau_full": tf, "tau_replica": tr, "gap": gap,
                 "ci_lo": lo, "ci_hi": hi, "n_windows": len(frames1)})

    # ---- Exhibit 2b: blended rent + asset-value target -----------------------
    mf = cremi.build_mf_annual()[["cbsa_code", "year", "Asset.Value"]].dropna()

    def blend_target(T):
        rent = rent_target(3)(T)
        if rent is None:
            return None
        now = mf[mf.year == T].rename(columns={"Asset.Value": "a0"})
        fut = mf[mf.year == T + 3].rename(columns={"Asset.Value": "a1"})
        av = now.merge(fut[["cbsa_code", "a1"]], on="cbsa_code")
        av["d_asset"] = backtest._winsorize(av["a1"] - av["a0"])
        m = rent.merge(av[["cbsa_code", "d_asset"]], on="cbsa_code", how="inner")
        if len(m) < config.PRECISION_K:
            return None
        yr = pd.Series(T, index=m.index)
        z_rent = _zwithin(pd.Series(m["realized"].to_numpy(), index=m.index), yr)
        z_asset = _zwithin(pd.Series(m["d_asset"].to_numpy(), index=m.index), yr)
        m["realized"] = (z_rent.to_numpy() + z_asset.to_numpy()) / 2.0
        return m[["cbsa_code", "realized"]]

    framesb = _window_frames(cols, pred_years, blend_target)
    tf, tr, gap, lo, hi = _gap_ci(framesb)
    rows.append({"exhibit": "alternate_task", "task": "3y rent + asset-value blend",
                 "tau_full": tf, "tau_replica": tr, "gap": gap,
                 "ci_lo": lo, "ci_hi": hi, "n_windows": len(framesb)})

    out = pd.DataFrame(rows).round(3)
    out.to_csv(OUT_CSV, index=False)

    print("=== P5: industry-replica robustness pair (descriptive; first results final) ===\n")
    for _, r in out.iterrows():
        verdict = ("composite reliably ahead" if r["ci_lo"] > 0
                   else ("replica reliably ahead" if r["ci_hi"] < 0 else "within noise"))
        print(f"  {r['exhibit']:<20} {r['task']:<28} "
              f"composite {r['tau_full']:+.3f}  replica {r['tau_replica']:+.3f}  "
              f"gap {r['gap']:+.3f} [{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}]  "
              f"({int(r['n_windows'])} windows) -> {verdict}")
    print(f"\nwrote {OUT_CSV.relative_to(config.ROOT)}")
    print("Framing (welded): equal-weight conditions indices are not rent-growth "
          "predictors; the omitted paid categories are plausibly Arbor's strongest.")


if __name__ == "__main__":
    main()
