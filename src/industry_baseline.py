"""
industry_baseline.py — v3 build-spec Phase 4: the free-Arbor replica.

Builds an Arbor-Chandan-style "opportunity matrix" on our 110-metro universe —
their scheme (equal-weighted categories, variables equal-weighted within), our
free components — and runs it through the standard walk-forward against 3-yr
forward rent growth. Construction is fixed by the 2026-07-07 Phase 4 execution
spec (decision-log): 6 of their 10 categories are replicable for free; the
orientations below are Arbor's a-priori directions and are NEVER auto-oriented.

The question this answers (build-spec §3): does the validated, deliberately
weighted screen beat industry-style practice at the actual prediction task —
and is the industry index re-packaged rent momentum? (Phase 0 logged the
prediction: its correlation with trailing_rent_growth will be high.)

First results are final — no tuning in either direction after this runs.

    .venv/Scripts/python.exe src/industry_baseline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                        # noqa: E402
from src import indicators, normalize, backtest, uncertainty  # noqa: E402
from src import score as score_mod   # noqa: E402
from src.ingest import cremi, census  # noqa: E402
from src.tier2_gate import _zwithin   # noqa: E402

ROW_NAME = "Industry-style index (equal weight)"
B_BOOT = 800


def _guarded_yoy(df: pd.DataFrame, col: str, out: str) -> pd.DataFrame:
    """YoY growth of a level column, only across consecutive years (the 2020
    ACS gap must not silently become a 2-yr growth rate)."""
    d = df[["cbsa_code", "year", col]].dropna().sort_values(["cbsa_code", "year"])
    g = d.groupby("cbsa_code")
    d[out] = d[col] / g[col].shift(1) - 1.0
    d.loc[g["year"].diff() != 1, out] = np.nan
    return d[["cbsa_code", "year", out]].dropna()


def _guarded_diff(df: pd.DataFrame, col: str, out: str) -> pd.DataFrame:
    """1-yr change of a column, consecutive years only."""
    d = df[["cbsa_code", "year", col]].dropna().sort_values(["cbsa_code", "year"])
    g = d.groupby("cbsa_code")
    d[out] = g[col].diff()
    d.loc[g["year"].diff() != 1, out] = np.nan
    return d[["cbsa_code", "year", out]].dropna()


def build_replica() -> pd.DataFrame:
    """The replica composite: [cbsa_code, year, score], higher = better."""
    panel = indicators.load_panel().sort_values(["cbsa_code", "year"]).reset_index(drop=True)
    norm = normalize.normalize()
    mf = cremi.build_mf_annual()
    demo = census.build_renter_demographics_panel()
    keys = panel[["cbsa_code", "year"]].copy()

    def z_of(frame: pd.DataFrame, col: str, sign: int = 1) -> pd.Series:
        """Within-year z across our universe, oriented a priori, neutral-filled."""
        vals = keys.merge(frame[["cbsa_code", "year", col]],
                          on=["cbsa_code", "year"], how="left")[col]
        z = _zwithin(pd.Series(vals.to_numpy(), index=keys.index), keys["year"])
        return (sign * z).fillna(0.0)

    def from_norm(col: str) -> pd.Series:
        """A model-normalized indicator (already oriented higher=better),
        aligned to the panel keys."""
        vals = keys.merge(norm[["cbsa_code", "year", col]],
                          on=["cbsa_code", "year"], how="left")[col]
        return pd.Series(vals.to_numpy(), index=keys.index).fillna(0.0)

    categories = {
        # 2. Performance fundamentals: CREMI NOI / asset price / absorption
        "performance": pd.concat([z_of(mf, "NOI.Index"),
                                  z_of(mf, "Asset.Value"),
                                  z_of(mf, "Absorption.Units")], axis=1).mean(axis=1),
        # 4. Labor market: growth, wages, unemployment level + 1-yr change
        "labor": pd.concat([from_norm("job_growth"),
                            from_norm("income_growth"),
                            z_of(mf, "MSAUR", sign=-1),
                            z_of(_guarded_diff(mf, "MSAUR", "d"), "d", sign=-1)],
                           axis=1).mean(axis=1),
        # 5. Population growth
        "population": z_of(_guarded_yoy(panel, "population", "g"), "g"),
        # 6. Demographics: renter spending power + young householder share
        "demographics": pd.concat([z_of(demo, "renter_income"),
                                   z_of(demo, "renter_under35_share")], axis=1).mean(axis=1),
        # 7. Rental vacancy (tightness: lower is better)
        "vacancy": z_of(panel, "rental_vacancy", sign=-1),
        # 9. Affordability (WWJ-equivalent; normalize already orients it)
        "affordability": from_norm("rent_to_income"),
    }
    out = keys.copy()
    out["score"] = pd.concat(categories.values(), axis=1).mean(axis=1)
    return out


def _metrics(summary: pd.DataFrame) -> dict:
    def g(h, reg, col):
        m = summary[(summary.horizon == h) & (summary.regime == reg)]
        return float(m[col].iloc[0]) if len(m) else float("nan")
    return {"tau_3y": g(3, "POOLED", "mean_tau"),
            "prec_3y": g(3, "POOLED", "mean_precision@10"),
            "tau_3y_preCOVID": g(3, "pre_covid", "mean_tau"),
            "tau_1y": g(1, "POOLED", "mean_tau")}


def main() -> None:
    replica = build_replica()
    scored = score_mod.score()
    norm = normalize.normalize()
    zori = backtest._zori_lookup()
    py = backtest.usable_pred_years(scored)

    def evalp(pred):
        return backtest.evaluate_predictions(pred, py, (3, 1), zori)

    rep_m = _metrics(backtest.summarize(evalp(replica)))
    full_m = _metrics(backtest.summarize(evalp(scored[["cbsa_code", "year", "score"]])))

    # bootstrap CI on the gap (composite tau minus replica tau), metro clusters
    cols = {"full": scored[["cbsa_code", "year", "score"]],
            "replica": replica}
    frames = uncertainty._window_frames(cols, py, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    rng = np.random.default_rng(config.RANDOM_SEED)
    gap_point = (uncertainty._pooled_tau(frames, metros, "full")
                 - uncertainty._pooled_tau(frames, metros, "replica"))
    boot = np.empty(B_BOOT)
    for b in range(B_BOOT):
        s = rng.choice(metros, size=len(metros), replace=True)
        boot[b] = (uncertainty._pooled_tau(frames, s, "full")
                   - uncertainty._pooled_tau(frames, s, "replica"))
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])

    # is the industry index re-packaged momentum? (Phase 0 prediction: high)
    m = replica.merge(norm[["cbsa_code", "year", "trailing_rent_growth"]],
                      on=["cbsa_code", "year"], how="inner").dropna()
    pooled_corr = float(m["score"].corr(m["trailing_rent_growth"]))
    per_year = m.groupby("year").apply(
        lambda d: d["score"].corr(d["trailing_rent_growth"], method="spearman"),
        include_groups=False)
    mean_rank_corr = float(per_year.mean())

    # ---- persist: detail file + a row in the baseline table ----
    detail = pd.DataFrame([{
        "model": ROW_NAME,
        **{k: round(v, 3) for k, v in rep_m.items()},
        "full_tau_3y": round(full_m["tau_3y"], 3),
        "gap_tau_3y": round(gap_point, 3),
        "gap_ci_lo": round(lo, 3), "gap_ci_hi": round(hi, 3),
        "corr_trailing_pooled": round(pooled_corr, 3),
        "rank_corr_trailing_mean": round(mean_rank_corr, 3),
        "categories_included": 6, "categories_total": 10,
    }])
    detail.to_csv(config.PROCESSED_DIR / "industry_baseline.csv", index=False)

    bl_path = config.PROCESSED_DIR / "baseline_comparison.csv"
    comp = pd.read_csv(bl_path)
    comp = comp[comp.model != ROW_NAME]
    row = {"model": ROW_NAME, **rep_m, "best_single_name": "",
           "uplift_tau_3y_vs_full":
               float(comp.loc[comp.model == "Full model (composite)", "tau_3y"].iloc[0])
               - rep_m["tau_3y"]}
    comp = (pd.concat([comp, pd.DataFrame([row])], ignore_index=True)
            .sort_values("tau_3y", ascending=False).reset_index(drop=True))
    comp.to_csv(bl_path, index=False)

    print("=== Phase 4: industry-style equal-weight index vs the composite ===\n")
    print(f"  replica  : 3y tau {rep_m['tau_3y']:+.3f}  P@10 {rep_m['prec_3y']:.2f}  "
          f"preCOVID {rep_m['tau_3y_preCOVID']:+.3f}  1y {rep_m['tau_1y']:+.3f}")
    print(f"  composite: 3y tau {full_m['tau_3y']:+.3f}  P@10 {full_m['prec_3y']:.2f}  "
          f"preCOVID {full_m['tau_3y_preCOVID']:+.3f}  1y {full_m['tau_1y']:+.3f}")
    print(f"\n  gap (composite - replica) pooled 3y tau: {gap_point:+.3f}  "
          f"95% CI [{lo:+.3f}, {hi:+.3f}]"
          f"  -> {'RELIABLE edge' if lo > 0 else ('reliably WORSE' if hi < 0 else 'within noise')}")
    print(f"\n  replica vs trailing rent growth: pooled corr {pooled_corr:+.3f}, "
          f"mean per-year rank corr {mean_rank_corr:+.3f}")
    print(f"  (Phase 0 logged prediction: high -> "
          f"{'confirmed' if mean_rank_corr > 0.5 else 'NOT confirmed'})")
    print(f"\nwrote {config.PROCESSED_DIR / 'industry_baseline.csv'}")
    print(f"updated {bl_path} with row: {ROW_NAME}")


if __name__ == "__main__":
    main()
