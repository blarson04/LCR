"""
v4_momentum_gate.py — the V4-6 permit-momentum gates (spec: decision-log
2026-08-16). One pre-registered attempt per candidate; both outcomes publish.

Two gate shapes, exactly as pre-registered:

  AUGMENTATION (P6 rule 5, one attempt per measure, precedence order
  M1a -> M1b -> M2a -> M2b): standalone pooled 3-yr weighted tau > 0.10
  AND max |corr| vs the 8 scored indicators < 0.70 AND value-add bootstrap
  CI (B=800, seed 42) excludes 0 at BOTH overlay weights 5% and 10%.

  REPLACEMENT R (M1a at the v1 supply split 17% level / 8% momentum):
  (A) reliably better — pooled 3-yr weighted-tau gap CI entirely above zero;
  (B) reliably calm — edition-to-edition Spearman >= 0.80 (baseline 0.683).

  Precedence: R first if it passes, else the first augmentation passer;
  at most one adoption. Coverage kill-rule (>=100/110) runs before any
  accuracy computation.

    .venv/Scripts/python.exe src/v4_momentum_gate.py --verify   # machinery only
    .venv/Scripts/python.exe src/v4_momentum_gate.py            # THE one-shot run
                                                                # (no earlier than
                                                                #  2026-08-17)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                                    # noqa: E402
from src import backtest, indicators, normalize, p3_gate, tier2_gate  # noqa: E402
from src import score as score_mod               # noqa: E402
from src.v4_permit_momentum import MEASURES, OUT_MOMENTUM  # noqa: E402

B = 800
SEED = config.RANDOM_SEED
EARLIEST_RUN = date(2026, 8, 17)        # cooling-off: spec logged 2026-08-16
COVERAGE_FLOOR = 100                     # of 110, the Phase-0 kill-rule
REPLACEMENT_MEASURE = "permit_momentum_total"     # M1a, frozen in the spec
REPLACEMENT_SPLIT = {"permits_to_stock": 0.17, "permit_momentum": 0.08}
AUG_WEIGHTS = (0.05, 0.10)               # conjunctive, P6 rule 5
PRONG_B_THRESHOLD = 0.80

OUT_SUMMARY = config.PROCESSED_DIR / "v4_momentum_gate_summary.csv"
OUT_WINDOWS = config.PROCESSED_DIR / "v4_momentum_gate_windows.csv"

W8 = {k: v["weight"] for k, v in config.INDICATORS.items()}
INV8 = {k: v["inverse"] for k, v in config.INDICATORS.items()}
W_VAR = {**W8, **REPLACEMENT_SPLIT}      # sums to 1.0: 25% supply -> 17 + 8
INV_VAR = {**INV8, "permit_momentum": True}
assert abs(sum(W_VAR.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Candidate data
# ---------------------------------------------------------------------------

def momentum_table() -> pd.DataFrame:
    return pd.read_csv(OUT_MOMENTUM, dtype={"cbsa_code": str})


def candidate_frame(measure: str) -> pd.DataFrame:
    """[cbsa_code, year, cand] for one measure (winsorized values; the gate
    z-scores within year)."""
    mom = momentum_table()
    return (mom[["cbsa_code", "year", measure]]
            .rename(columns={measure: "cand"}))


def variant_indicators(panel: pd.DataFrame | None = None) -> pd.DataFrame:
    """The finalized 8-indicator table + the momentum column for variant R."""
    if panel is None:
        panel = indicators.load_panel()
    ind = indicators.compute_indicators(panel)
    mom = momentum_table()[["cbsa_code", "year", REPLACEMENT_MEASURE]]
    return ind.merge(mom.rename(columns={REPLACEMENT_MEASURE: "permit_momentum"}),
                     on=["cbsa_code", "year"], how="left")


# ---------------------------------------------------------------------------
# Local scorer — the score.py path generalized to an arbitrary weight map.
# Verified in --verify to reproduce the published scores to machine precision
# when given the standard 8 weights.
# ---------------------------------------------------------------------------

def score_frame(ind: pd.DataFrame, weights: dict[str, float],
                inverse: dict[str, bool]) -> pd.DataFrame:
    out = ind[["cbsa_code", "year"]].copy()
    total = 0.0
    for col, w in weights.items():
        z = normalize._zscore_within_year(ind[col], ind["year"])
        if inverse[col]:
            z = -z
        total = total + w * z.fillna(0.0)
    out["score"] = total.to_numpy()
    return out


# ---------------------------------------------------------------------------
# Coverage kill-rule — BEFORE any accuracy computation
# ---------------------------------------------------------------------------

def coverage_report() -> pd.DataFrame:
    """Per measure: metro coverage in each usable prediction year. A measure
    fails if any pred year WITH data covers < 100 metros; pred years with no
    data at all (the ACS-gap years for the rate variants) drop their windows,
    the C6a precedent, and are reported."""
    mom = momentum_table()
    pred_years = backtest.usable_pred_years()
    n_universe = mom["cbsa_code"].nunique()
    rows = []
    for m in MEASURES:
        cov = {y: int(mom[mom["year"] == y][m].notna().sum()) for y in pred_years}
        with_data = {y: c for y, c in cov.items() if c > 0}
        rows.append({
            "measure": m, "universe": n_universe,
            "min_coverage_years_with_data": min(with_data.values()) if with_data else 0,
            "pred_years_with_data": len(with_data),
            "pred_years_total": len(pred_years),
            "coverage_by_year": "; ".join(f"{y}:{c}" for y, c in cov.items()),
            "coverage_ok": bool(with_data) and min(with_data.values()) >= COVERAGE_FLOOR,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Replacement variant R — prong A (paired walk-forward + bootstrap on the gap)
# ---------------------------------------------------------------------------

def prong_a(panel: pd.DataFrame) -> dict:
    cur = score_mod.score()[["cbsa_code", "year", "score"]]
    var = score_frame(variant_indicators(panel), W_VAR, INV_VAR)
    pred_years = backtest.usable_pred_years()
    zori = backtest._zori_lookup()
    frames = p3_gate._window_frames(
        {"current": cur, "variant": var}, pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))

    point_cur = p3_gate._pooled_tau(frames, metros, "current")
    point_var = p3_gate._pooled_tau(frames, metros, "variant")

    rng = np.random.default_rng(SEED)
    gap = np.empty(B)
    for b in range(B):
        s = rng.choice(metros, size=len(metros), replace=True)
        gap[b] = (p3_gate._pooled_tau(frames, s, "variant")
                  - p3_gate._pooled_tau(frames, s, "current"))
    lo, hi = float(np.nanpercentile(gap, 2.5)), float(np.nanpercentile(gap, 97.5))

    windows = pd.DataFrame([
        {"pred_year": int(f["pred_year"].iloc[0]), "n_metros": len(f),
         "tau_current": backtest._weighted_tau_by_realized(
             f["current"].to_numpy(), f["realized"].to_numpy()),
         "tau_variant": backtest._weighted_tau_by_realized(
             f["variant"].to_numpy(), f["realized"].to_numpy())}
        for f in frames])
    return {"tau_current": point_cur, "tau_variant": point_var,
            "gap": point_var - point_cur, "gap_lo": lo, "gap_hi": hi,
            "pass": lo > 0, "windows": windows}    # reliably BETTER (spec)


# ---------------------------------------------------------------------------
# Replacement variant R — prong B (edition-to-edition Spearman)
# The p3_gate edition rebuilds, re-expressed over the local scorer so the
# variant's extra column can ride along. --verify proves the re-expression
# reproduces both published edition score sets under the standard weights.
# ---------------------------------------------------------------------------

def _vintage_scores(ind: pd.DataFrame, panel: pd.DataFrame,
                    weights: dict, inverse: dict) -> pd.Series:
    from src.ingest import census_pep
    from src.nowcast.build_vintage_screen import QCEW_GAP_CARRY
    pep = census_pep.build_pep_migration_panel()[["cbsa_code", "year", "pep_net_migration"]]
    m = (panel[["cbsa_code", "year", "population"]]
         .merge(pep, on=["cbsa_code", "year"], how="left"))
    m["pep_rate"] = m["pep_net_migration"] / m["population"]
    rate = m.set_index(["cbsa_code", "year"])["pep_rate"]

    iv = ind.set_index(["cbsa_code", "year"])
    ymask = iv.index.get_level_values("year") == p3_gate.VINTAGE_YEAR
    sub = rate.reindex(iv.index)
    iv.loc[ymask, "net_migration"] = sub[ymask].where(
        sub[ymask].notna(), iv.loc[ymask, "net_migration"])
    prev = iv.xs(p3_gate.VINTAGE_YEAR - 1, level="year")
    for k in QCEW_GAP_CARRY:
        cur = iv.loc[ymask, k]
        fill = prev[k].reindex(cur.index.get_level_values("cbsa_code")).to_numpy()
        iv.loc[ymask, k] = cur.where(cur.notna(), fill)

    scored = score_frame(iv.reset_index(), weights, inverse)
    return (scored[scored["year"] == p3_gate.VINTAGE_YEAR]
            .set_index("cbsa_code")["score"])


def _nowcast_scores(ind: pd.DataFrame, panel: pd.DataFrame,
                    weights: dict, inverse: dict) -> pd.Series:
    from src.ingest import bea, bls_ces, census_pep
    from src.nowcast import build_nowcast_panel as bnp
    fin_ind = indicators.compute_indicators(panel)
    pep = census_pep.build_pep_migration_panel()
    ces = bls_ces.build_ces_job_growth_panel()
    sg = bea.state_pc_income_growth_panel()
    nc = bnp.nowcast_row(p3_gate.NOWCAST_YEAR, panel, fin_ind, pep, ces,
                         state_growth=sg)
    if "permit_momentum" in ind.columns:
        mom = momentum_table()
        m25 = (mom[mom["year"] == p3_gate.NOWCAST_YEAR]
               [["cbsa_code", REPLACEMENT_MEASURE]]
               .rename(columns={REPLACEMENT_MEASURE: "permit_momentum"}))
        nc = nc.merge(m25, on="cbsa_code", how="left")
    full = pd.concat([ind[ind["year"] != p3_gate.NOWCAST_YEAR],
                      nc[list(ind.columns)]], ignore_index=True)
    scored = score_frame(full, weights, inverse)
    return (scored[scored["year"] == p3_gate.NOWCAST_YEAR]
            .set_index("cbsa_code")["score"])


def prong_b(panel: pd.DataFrame) -> dict:
    ind = variant_indicators(panel)
    v = _vintage_scores(ind, panel, W_VAR, INV_VAR)
    n = _nowcast_scores(ind, panel, W_VAR, INV_VAR)
    both = pd.DataFrame({"vintage": v, "current": n}).dropna()
    rho = float(spearmanr(both["vintage"], both["current"]).statistic)
    return {"spearman": rho, "pass": rho >= PRONG_B_THRESHOLD, "n": len(both)}


# ---------------------------------------------------------------------------
# Verification mode — machinery checks only, NO candidate accuracy computed
# ---------------------------------------------------------------------------

def verify() -> None:
    panel = indicators.load_panel().sort_values(["cbsa_code", "year"]).reset_index(drop=True)

    print("[1/5] Local scorer reproduces score.py to machine precision ...")
    mine = score_frame(indicators.compute_indicators(panel), W8, INV8)
    theirs = score_mod.score()[["cbsa_code", "year", "score"]]
    m = mine.merge(theirs, on=["cbsa_code", "year"], suffixes=("_mine", "_pub"))
    d = (m["score_mine"] - m["score_pub"]).abs().max()
    assert d < 1e-9, d
    print(f"    max |score diff| over {len(m):,} metro-years = {d:.2e} OK")

    print("[2/5] Current-model pooled tau reproduces the published 0.431 ...")
    pred_years = backtest.usable_pred_years()
    zori = backtest._zori_lookup()
    frames = p3_gate._window_frames({"current": theirs}, pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    tau = p3_gate._pooled_tau(frames, metros, "current")
    assert abs(tau - 0.431) < 0.005, tau
    print(f"    pooled 3-yr weighted tau = {tau:.3f} (published 0.431) OK")

    print("[3/5] Edition rebuild path reproduces both published score sets ...")
    ind8 = indicators.compute_indicators(panel)
    v = _vintage_scores(ind8, panel, W8, INV8)
    pub_v = pd.read_csv(config.PROCESSED_DIR / "vintage" / "vintage_2024_ranking.csv",
                        dtype={"cbsa_code": str}).set_index("cbsa_code")["score"]
    dv = (v - pub_v.reindex(v.index)).abs().max()
    n = _nowcast_scores(ind8, panel, W8, INV8)
    pub_n = pd.read_csv(config.PROCESSED_DIR / "nowcast" /
                        f"provisional_{p3_gate.NOWCAST_YEAR}_ranking.csv",
                        dtype={"cbsa_code": str}).set_index("cbsa_code")["score"]
    dn = (n - pub_n.reindex(n.index)).abs().max()
    assert dv < 1e-9 and dn < 1e-9, (dv, dn)
    print(f"    vintage max |diff| = {dv:.2e}; current max |diff| = {dn:.2e} OK")
    both = pd.DataFrame({"v": v, "n": n}).dropna()
    rho = float(spearmanr(both["v"], both["n"]).statistic)
    assert abs(rho - 0.683) < 0.005, rho
    print(f"    current-inputs edition Spearman = {rho:.3f} (published 0.683) OK")

    print("[4/5] tier2 frame path == panel-column path (plumbing identity) ...")
    frame = panel[["cbsa_code", "year", "rental_vacancy"]].rename(
        columns={"rental_vacancy": "cand"})
    a = tier2_gate.gate("plumbing (col)", "rental_vacancy", inverse=True, B=80)
    b = tier2_gate.gate("plumbing (frame)", frame=frame, inverse=True, B=80)
    assert abs(a["standalone_tau"] - b["standalone_tau"]) < 1e-12
    assert abs(a["delta_tau"] - b["delta_tau"]) < 1e-12
    print(f"    identical standalone tau and delta-tau across both paths OK")

    print("[5/5] Transform check (hand-computed momentum, one metro) + coverage ...")
    mom = momentum_table()
    permits = pd.read_csv(config.PROCESSED_DIR / "v4_permit_panel.csv",
                          dtype={"cbsa_code": str}).set_index(["cbsa_code", "year"])
    got = mom[(mom.cbsa_code == "12420") & (mom.year == 2024)][
        "permit_momentum_total_raw"].iloc[0]
    want = (permits.loc[("12420", 2024), "total_units"]
            / permits.loc[("12420", 2023), "total_units"] - 1.0)
    assert abs(got - want) < 1e-12, (got, want)
    print(f"    Austin 2024 raw momentum {got:+.4f} == units ratio OK")
    from src.v4_permit_momentum import _winsorize_within_year
    for m_ in MEASURES:   # stored measure must equal the recomputed clip
        recomputed = _winsorize_within_year(mom[f"{m_}_raw"], mom["year"])
        d_ = (mom[m_] - recomputed).abs().max()
        assert d_ < 1e-12, (m_, d_)
    print("    winsorized columns == recomputed within-year clip OK")
    cov = coverage_report()
    for _, r in cov.iterrows():
        print(f"    {r['measure']:<28} min coverage {r['min_coverage_years_with_data']:>3}"
              f"/110 in {r['pred_years_with_data']}/{r['pred_years_total']} pred years"
              f"  -> {'OK' if r['coverage_ok'] else 'KILL'}")

    print("\nAll machinery checks PASS. No candidate accuracy was computed.")


# ---------------------------------------------------------------------------
# The one-shot gates
# ---------------------------------------------------------------------------

def main() -> None:
    if "--verify" in sys.argv:
        verify()
        return
    if date.today() < EARLIEST_RUN:
        print(f"REFUSING TO RUN: the cooling-off rule sets the earliest gate run "
              f"at {EARLIEST_RUN} (spec logged 2026-08-16). Run --verify instead.")
        sys.exit(1)

    panel = indicators.load_panel().sort_values(["cbsa_code", "year"]).reset_index(drop=True)
    print("=== V4-6 GATES — one pre-registered attempt per candidate "
          "(spec 2026-08-16) ===\n")

    print("[coverage kill-rule]")
    cov = coverage_report()
    for _, r in cov.iterrows():
        print(f"  {r['measure']:<28} min {r['min_coverage_years_with_data']:>3}/110 "
              f"({r['pred_years_with_data']}/{r['pred_years_total']} pred years)"
              f" -> {'ok' if r['coverage_ok'] else 'KILLED ON COVERAGE'}")
    alive = [m for m in MEASURES
             if cov.set_index("measure").loc[m, "coverage_ok"]]

    print("\n[augmentation gates — P6 rule 5, conjunctive at 5% and 10%]")
    aug_rows = []
    for m_ in alive:
        frame = candidate_frame(m_)
        r5 = tier2_gate.gate(f"{m_} @5%", frame=frame, inverse=True, weight=0.05, B=B)
        r10 = tier2_gate.gate(f"{m_} @10%", frame=frame, inverse=True, weight=0.10, B=B)
        passed = (r5["standalone_tau"] > 0.10 and abs(r5["top_corr"][0][1]) < 0.70
                  and r5["ci"][0] > 0 and r10["ci"][0] > 0)
        aug_rows.append({
            "measure": m_, "standalone_tau": r5["standalone_tau"],
            "auto_orient_flipped": r5["flipped"],
            "max_abs_corr": abs(r5["top_corr"][0][1]),
            "top_corr_with": r5["top_corr"][0][0],
            "delta_tau_5": r5["delta_tau"], "ci5_lo": r5["ci"][0], "ci5_hi": r5["ci"][1],
            "delta_tau_10": r10["delta_tau"], "ci10_lo": r10["ci"][0], "ci10_hi": r10["ci"][1],
            "pass": passed})
        r = aug_rows[-1]
        print(f"  {m_:<28} tau {r['standalone_tau']:+.3f}"
              f"{' (flipped)' if r['auto_orient_flipped'] else ''}"
              f"  |corr| {r['max_abs_corr']:.2f} ({r['top_corr_with']})"
              f"  d5 {r['delta_tau_5']:+.3f} [{r['ci5_lo']:+.3f},{r['ci5_hi']:+.3f}]"
              f"  d10 {r['delta_tau_10']:+.3f} [{r['ci10_lo']:+.3f},{r['ci10_hi']:+.3f}]"
              f"  -> {'PASS' if r['pass'] else 'fail'}")

    print("\n[replacement variant R — M1a at the 17/8 supply split]")
    a = prong_a(panel)
    print(f"  Prong A: tau current {a['tau_current']:.3f} vs variant "
          f"{a['tau_variant']:.3f}; gap {a['gap']:+.3f}, "
          f"95% CI [{a['gap_lo']:+.3f}, {a['gap_hi']:+.3f}] "
          f"-> {'PASS (reliably better)' if a['pass'] else 'FAIL'}")
    b_res = prong_b(panel)
    print(f"  Prong B: edition Spearman {b_res['spearman']:.3f} "
          f"(threshold >= {PRONG_B_THRESHOLD}; baseline 0.683; n={b_res['n']}) "
          f"-> {'PASS' if b_res['pass'] else 'FAIL'}")
    r_pass = a["pass"] and b_res["pass"]

    # Precedence, pre-committed: R first, else first augmentation passer.
    verdict = "REJECT ALL"
    if r_pass:
        verdict = "ADOPT R (replacement, 17/8 split)"
    else:
        for r in aug_rows:
            if r["pass"]:
                verdict = f"ADOPT {r['measure']} (augmentation @5%)"
                break
    print(f"\nVERDICT: {verdict}")

    a["windows"].to_csv(OUT_WINDOWS, index=False)
    summary = pd.DataFrame(aug_rows)
    summary["leg"] = "augmentation"
    r_row = pd.DataFrame([{
        "measure": REPLACEMENT_MEASURE, "leg": "replacement",
        "standalone_tau": np.nan,
        "tau_current": a["tau_current"], "tau_variant": a["tau_variant"],
        "gap": a["gap"], "gap_ci_lo": a["gap_lo"], "gap_ci_hi": a["gap_hi"],
        "prong_a_pass": a["pass"], "edition_spearman": b_res["spearman"],
        "prong_b_pass": b_res["pass"], "pass": r_pass}])
    out = pd.concat([summary, r_row], ignore_index=True)
    out["verdict"] = verdict
    out["bootstrap_B"] = B
    out["seed"] = SEED
    out.to_csv(OUT_SUMMARY, index=False)
    print(f"\nWritten: {OUT_SUMMARY.relative_to(config.ROOT)}, "
          f"{OUT_WINDOWS.relative_to(config.ROOT)}")
    print("First results are final. Log the outcome entry in decision-log.md.")


if __name__ == "__main__":
    main()
