"""
p3_gate.py — the P3 multi-year growth-input gate (spec: decision-log 2026-07-08).

ONE pre-registered attempt at the churn defect. Candidate, frozen in the spec:
replace the two single-year growth inputs with 3-year mean growth — job_growth
and income_growth switch TOGETHER as one candidate. Definition: for scoring
year T, the mean of the exact-prior-year YoY growths at T, T-1, T-2; a
component exists only if both its endpoint years exist (panel gaps yield
missing components, never multi-year jumps); at least 2 of 3 components
required, else NaN (standard neutral fill downstream).

Gate (replacement shape), both prongs required to adopt:
  (A) Not reliably worse: 95% metro-cluster bootstrap CI (B=800, seed 42) on
      the pooled 3-yr weighted-tau gap (multi-year minus current) does NOT lie
      entirely below zero. Same paired-resample machinery as uncertainty.py.
  (B) Reliably calmer: edition-to-edition score correlation (Spearman, both
      published editions rebuilt under the variant with proxy scheme v0.4
      otherwise unchanged) >= 0.80. Corrected-panel baseline for the current
      inputs: 0.683 (D7/D8 outcome entry).

For the 2025 edition, the year-T component of each multi-year mean is the same
v0.4 proxy that supplied the single-year value (CES job growth; the primary-
state BEA income chain); where the proxy is unavailable for a metro, that
component is missing and the frozen >=2-of-3 rule applies (the carry fallback
would double-count the T-1 component inside a mean).

Adopted -> model 3.0.0, full regeneration, registry re-freeze. Rejected ->
negative result published; tiers + rank intervals remain the churn answer.
First results are final.

    .venv/Scripts/python.exe src/p3_gate.py --verify   # machinery checks only
    .venv/Scripts/python.exe src/p3_gate.py            # THE one-shot gate run
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import backtest, indicators, normalize  # noqa: E402
from src import score as score_mod  # noqa: E402

B = 800
SEED = config.RANDOM_SEED
HORIZON = 3
MULTI_COLS = {"job_growth": "total_emp", "income_growth": "per_capita_income"}
MIN_COMPONENTS = 2
PRONG_B_THRESHOLD = 0.80
VINTAGE_YEAR = 2024
NOWCAST_YEAR = 2025

OUT_SUMMARY = config.PROCESSED_DIR / "p3_gate_summary.csv"
OUT_WINDOWS = config.PROCESSED_DIR / "p3_gate_windows.csv"


# ---------------------------------------------------------------------------
# The candidate transform
# ---------------------------------------------------------------------------

def _yoy_frame(panel: pd.DataFrame, level_col: str) -> pd.DataFrame:
    """[cbsa_code, year, yoy] using the EXACT prior year (indicators._yoy rule)."""
    out = panel[["cbsa_code", "year"]].copy()
    out["yoy"] = indicators._yoy(panel, level_col)
    return out


def _multi_year_mean(yoy: pd.DataFrame) -> pd.Series:
    """3-yr mean of the YoY components at T, T-1, T-2; >=2 of 3 required.
    Indexed like yoy (one row per metro-year)."""
    m = yoy.copy()
    for lag in (1, 2):
        prev = yoy.rename(columns={"yoy": f"yoy_l{lag}"}).copy()
        prev["year"] += lag
        m = m.merge(prev, on=["cbsa_code", "year"], how="left")
    comps = m[["yoy", "yoy_l1", "yoy_l2"]]
    mean = comps.mean(axis=1, skipna=True)
    return mean.where(comps.notna().sum(axis=1) >= MIN_COMPONENTS)


def variant_indicators(panel: pd.DataFrame | None = None) -> pd.DataFrame:
    """The finalized indicator table with job_growth and income_growth replaced
    by their 3-yr mean versions. Everything else untouched."""
    if panel is None:
        panel = indicators.load_panel()
    panel = panel.sort_values(["cbsa_code", "year"]).reset_index(drop=True)
    ind = indicators.compute_indicators(panel)
    for ind_col, level_col in MULTI_COLS.items():
        mean = _multi_year_mean(_yoy_frame(panel, level_col))
        ind[ind_col] = mean.to_numpy()
    return ind


# ---------------------------------------------------------------------------
# Prong A — paired walk-forward + metro-cluster bootstrap on the tau gap
# ---------------------------------------------------------------------------

def _window_frames(rankings: dict[str, pd.DataFrame], pred_years: list[int],
                   zori: pd.DataFrame) -> list[pd.DataFrame]:
    """One frame per 3-yr window: realized growth + every ranking's score,
    inner-joined (the uncertainty.py convention)."""
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
        for name, df in rankings.items():
            f = f.merge(df[df.year == T][["cbsa_code", "score"]]
                        .rename(columns={"score": name}), on="cbsa_code", how="inner")
        f["pred_year"] = T
        frames.append(f.set_index("cbsa_code"))
    return frames


def _pooled_tau(frames: list[pd.DataFrame], sample, col: str) -> float:
    taus = []
    for f in frames:
        sub = f.reindex(sample).dropna(subset=[col, "realized"])
        if len(sub) >= config.PRECISION_K:
            taus.append(backtest._weighted_tau_by_realized(
                sub[col].to_numpy(), sub["realized"].to_numpy()))
    return float(np.mean(taus)) if taus else np.nan


def prong_a(panel: pd.DataFrame) -> dict:
    cur_scores = score_mod.score(normalize.normalize(indicators.compute_indicators(panel)))
    var_scores = score_mod.score(normalize.normalize(variant_indicators(panel)))
    pred_years = backtest.usable_pred_years(cur_scores)
    zori = backtest._zori_lookup()
    rankings = {"current": cur_scores[["cbsa_code", "year", "score"]],
                "multi_year": var_scores[["cbsa_code", "year", "score"]]}
    frames = _window_frames(rankings, pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))

    point_cur = _pooled_tau(frames, metros, "current")
    point_var = _pooled_tau(frames, metros, "multi_year")

    rng = np.random.default_rng(SEED)
    gap = np.empty(B)
    for b in range(B):
        s = rng.choice(metros, size=len(metros), replace=True)
        gap[b] = _pooled_tau(frames, s, "multi_year") - _pooled_tau(frames, s, "current")
    lo, hi = (float(np.nanpercentile(gap, 2.5)), float(np.nanpercentile(gap, 97.5)))

    windows = pd.DataFrame([
        {"pred_year": int(f["pred_year"].iloc[0]), "n_metros": len(f),
         "tau_current": backtest._weighted_tau_by_realized(
             f["current"].to_numpy(), f["realized"].to_numpy()),
         "tau_multi_year": backtest._weighted_tau_by_realized(
             f["multi_year"].to_numpy(), f["realized"].to_numpy())}
        for f in frames])
    return {"tau_current": point_cur, "tau_multi_year": point_var,
            "gap": point_var - point_cur, "gap_lo": lo, "gap_hi": hi,
            "pass": not (hi < 0), "windows": windows}


# ---------------------------------------------------------------------------
# Prong B — both editions rebuilt under the variant; Spearman >= 0.80
# ---------------------------------------------------------------------------

def _vintage_edition_scores(ind: pd.DataFrame, panel: pd.DataFrame) -> pd.Series:
    """The 2024-vintage edition built from `ind` (build_vintage_screen logic:
    PEP migration substitution at 2024; QCEW-gap metros carry their 2023
    indicator values where 2024 is missing). Returns scores indexed by cbsa."""
    from src.ingest import census_pep
    from src.nowcast.build_vintage_screen import QCEW_GAP_CARRY
    pep = census_pep.build_pep_migration_panel()[["cbsa_code", "year", "pep_net_migration"]]
    m = (panel[["cbsa_code", "year", "population"]]
         .merge(pep, on=["cbsa_code", "year"], how="left"))
    m["pep_rate"] = m["pep_net_migration"] / m["population"]
    rate = m.set_index(["cbsa_code", "year"])["pep_rate"]

    iv = ind.set_index(["cbsa_code", "year"])
    ymask = iv.index.get_level_values("year") == VINTAGE_YEAR
    sub = rate.reindex(iv.index)
    iv.loc[ymask, "net_migration"] = sub[ymask].where(
        sub[ymask].notna(), iv.loc[ymask, "net_migration"])
    prev = iv.xs(VINTAGE_YEAR - 1, level="year")
    for k in QCEW_GAP_CARRY:
        cur = iv.loc[ymask, k]
        fill = prev[k].reindex(cur.index.get_level_values("cbsa_code")).to_numpy()
        iv.loc[ymask, k] = cur.where(cur.notna(), fill)

    scored = score_mod.score(normalize.normalize(iv.reset_index()))
    return (scored[scored["year"] == VINTAGE_YEAR]
            .set_index("cbsa_code")["score"])


def _nowcast_components_2025(panel: pd.DataFrame, ind: pd.DataFrame):
    """The year-T (2025) proxy components per metro: CES job growth and the
    primary-state income chain growth — NaN where the proxy is unavailable."""
    from src.ingest import bea, bls_ces
    ces = bls_ces.build_ces_job_growth_panel()
    sg_panel = bea.state_pc_income_growth_panel()
    i_y = ind[ind["year"] == NOWCAST_YEAR]
    if i_y.empty:   # finalized table has no 2025 row; use the metro list from 2024
        i_y = ind[ind["year"] == VINTAGE_YEAR]
    i_y = i_y.set_index("cbsa_code")
    ces_y = (ces[ces["year"] == NOWCAST_YEAR].set_index("cbsa_code")["ces_job_growth"]
             .reindex(i_y.index))
    st = (i_y["cbsa_title"].str.split(",").str[1].str.strip().str.split("-").str[0])
    sg = st.map(lambda s: sg_panel.get((s, NOWCAST_YEAR), float("nan")))
    return ces_y, sg


def _nowcast_edition_scores(hist_ind: pd.DataFrame, panel: pd.DataFrame,
                            multi_year: bool) -> pd.Series:
    """The 2025 current edition (proxy scheme v0.4) built on `hist_ind`.
    multi_year=True replaces the two growth inputs on the 2025 row with the
    3-yr mean whose year-T component is the proxy growth itself (missing proxy
    = missing component, >=2-of-3 rule); the finalized T-1/T-2 components come
    from the single-year YoY at 2024/2023."""
    from src.ingest import bea, bls_ces, census_pep
    from src.nowcast import build_nowcast_panel as bnp
    fin_ind = indicators.compute_indicators(panel)
    pep = census_pep.build_pep_migration_panel()
    ces = bls_ces.build_ces_job_growth_panel()
    sg_panel = bea.state_pc_income_growth_panel()
    nc = bnp.nowcast_row(NOWCAST_YEAR, panel, fin_ind, pep, ces, state_growth=sg_panel)

    if multi_year:
        ces_y, sg = _nowcast_components_2025(panel, fin_ind)
        nc = nc.set_index("cbsa_code")
        for ind_col, comp_t in (("job_growth", ces_y), ("income_growth", sg)):
            fin = fin_ind.pivot_table(index="cbsa_code", columns="year",
                                      values=ind_col, aggfunc="first")
            comps = pd.DataFrame({
                "t": comp_t,
                "t1": fin.get(NOWCAST_YEAR - 1).reindex(nc.index),
                "t2": fin.get(NOWCAST_YEAR - 2).reindex(nc.index)})
            mean = comps.mean(axis=1, skipna=True).where(
                comps.notna().sum(axis=1) >= MIN_COMPONENTS)
            nc[ind_col] = mean
        nc = nc.reset_index()[hist_ind.columns]

    full = pd.concat([hist_ind[hist_ind["year"] != NOWCAST_YEAR], nc], ignore_index=True)
    scored = score_mod.score(normalize.normalize(full))
    return (scored[scored["year"] == NOWCAST_YEAR]
            .set_index("cbsa_code")["score"])


def edition_spearman(panel: pd.DataFrame, multi_year: bool) -> tuple[float, pd.DataFrame]:
    ind = variant_indicators(panel) if multi_year else indicators.compute_indicators(panel)
    v = _vintage_edition_scores(ind, panel)
    n = _nowcast_edition_scores(ind, panel, multi_year=multi_year)
    both = pd.DataFrame({"vintage": v, "current": n}).dropna()
    rho = float(spearmanr(both["vintage"], both["current"]).statistic)
    return rho, both


# ---------------------------------------------------------------------------
# Verification mode — machinery checks only, NO candidate accuracy computed
# ---------------------------------------------------------------------------

def verify() -> None:
    panel = indicators.load_panel().sort_values(["cbsa_code", "year"]).reset_index(drop=True)

    print("[1/4] Transform check (hand-computed 3-yr means, one metro) ...")
    ind = indicators.compute_indicators(panel)
    var = variant_indicators(panel)
    code = "10580"   # Albany
    for col in MULTI_COLS:
        s = ind[ind.cbsa_code == code].set_index("year")[col]
        got = var[(var.cbsa_code == code) & (var.year == 2024)][col].iloc[0]
        want = np.nanmean([s.get(2024), s.get(2023), s.get(2022)])
        assert abs(got - want) < 1e-12, (col, got, want)
        print(f"    {col}: 2024 variant {got:+.4f} == mean(YoY 2022-24) OK")
    y16 = var[(var.cbsa_code == code) & (var.year == 2016)]["job_growth"].iloc[0]
    assert np.isnan(y16), "2016 should be NaN (only 1 component)"
    print("    2016 -> NaN (1 of 3 components) OK")

    print("[2/4] Current-model pooled tau reproduces the published 0.431 ...")
    cur_scores = score_mod.score(normalize.normalize(ind))
    pred_years = backtest.usable_pred_years(cur_scores)
    zori = backtest._zori_lookup()
    frames = _window_frames({"current": cur_scores[["cbsa_code", "year", "score"]]},
                            pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    tau = _pooled_tau(frames, metros, "current")
    print(f"    pooled 3-yr weighted tau = {tau:.3f} (published 0.431)")
    assert abs(tau - 0.431) < 0.005, tau

    print("[3/4] Edition rebuild path reproduces the published edition scores ...")
    v = _vintage_edition_scores(ind, panel)
    pub_v = pd.read_csv(config.PROCESSED_DIR / "vintage" / "vintage_2024_ranking.csv",
                        dtype={"cbsa_code": str}).set_index("cbsa_code")["score"]
    dv = (v - pub_v.reindex(v.index)).abs().max()
    n = _nowcast_edition_scores(ind, panel, multi_year=False)
    pub_n = pd.read_csv(config.PROCESSED_DIR / "nowcast" /
                        f"provisional_{NOWCAST_YEAR}_ranking.csv",
                        dtype={"cbsa_code": str}).set_index("cbsa_code")["score"]
    dn = (n - pub_n.reindex(n.index)).abs().max()
    print(f"    vintage max |diff| = {dv:.2e}; current max |diff| = {dn:.2e}")
    assert dv < 1e-9 and dn < 1e-9, (dv, dn)

    print("[4/4] Current-inputs edition Spearman reproduces the 0.683 baseline ...")
    rho, _ = edition_spearman(panel, multi_year=False)
    print(f"    Spearman(vintage 2024, current 2025) = {rho:.3f} (published 0.683)")
    assert abs(rho - 0.683) < 0.005, rho
    print("\nAll machinery checks PASS. No candidate accuracy was computed.")


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def main() -> None:
    if "--verify" in sys.argv:
        verify()
        return

    panel = indicators.load_panel().sort_values(["cbsa_code", "year"]).reset_index(drop=True)

    print("=== P3 GATE — one pre-registered attempt (spec 2026-07-08) ===\n")
    a = prong_a(panel)
    print(f"Prong A: pooled 3-yr weighted tau current {a['tau_current']:.3f} vs "
          f"multi-year {a['tau_multi_year']:.3f}")
    print(f"         gap (multi - current) {a['gap']:+.3f}, "
          f"95% CI [{a['gap_lo']:+.3f}, {a['gap_hi']:+.3f}]  "
          f"(B={B}, seed {SEED})")
    print(f"         -> {'PASS (not reliably worse)' if a['pass'] else 'FAIL (reliably worse)'}\n")

    rho, both = edition_spearman(panel, multi_year=True)
    b_pass = rho >= PRONG_B_THRESHOLD
    print(f"Prong B: edition-to-edition score Spearman under the variant = {rho:.3f} "
          f"(threshold >= {PRONG_B_THRESHOLD:.2f}; current-inputs baseline 0.683)")
    print(f"         -> {'PASS (reliably calmer)' if b_pass else 'FAIL'}\n")

    verdict = "ADOPT" if (a["pass"] and b_pass) else "REJECT"
    print(f"VERDICT: {verdict}")

    a["windows"].to_csv(OUT_WINDOWS, index=False)
    pd.DataFrame([{
        "tau_current": a["tau_current"], "tau_multi_year": a["tau_multi_year"],
        "gap": a["gap"], "gap_ci_lo": a["gap_lo"], "gap_ci_hi": a["gap_hi"],
        "prong_a_pass": a["pass"], "edition_spearman_variant": rho,
        "edition_spearman_baseline": 0.683, "prong_b_threshold": PRONG_B_THRESHOLD,
        "prong_b_pass": b_pass, "verdict": verdict,
        "bootstrap_B": B, "seed": SEED, "n_metros_editions": len(both),
    }]).to_csv(OUT_SUMMARY, index=False)
    print(f"\nWritten: {OUT_SUMMARY.relative_to(config.ROOT)}, "
          f"{OUT_WINDOWS.relative_to(config.ROOT)}")
    print("First results are final. Log the outcome entry in decision-log.md.")


if __name__ == "__main__":
    main()
