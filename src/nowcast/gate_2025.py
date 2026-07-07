"""
gate_2025.py — one-shot gate for the v0.4 "state-chained income" 2025 screen.

Spec + gate: decision-log 2026-07-08 (logged before this run). v0.4 changes
exactly one thing from the failed v0.2 configuration: the scoring-year income
level is chained by the primary state's BEA per-capita income growth (QA:
rank agreement 0.51-0.66 every year vs 0.11 for the flat carry it replaces).
The pseudo-test rebuilds every usable historical year with the identical
scheme and must retain >= 85% of the finalized pooled 3-yr weighted tau AND
average >= 7/10 top-10 overlap. ONE attempt - this script is the attempt.

    .venv/Scripts/python.exe src/nowcast/gate_2025.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import indicators, normalize  # noqa: E402
from src import score as score_mod  # noqa: E402
from src import backtest, uncertainty  # noqa: E402
from src.ingest import census_pep, bls_ces, bea  # noqa: E402
from src.nowcast import build_nowcast_panel as bnp  # noqa: E402

GATE_TAU_RETENTION = 0.85
GATE_MIN_TOP10 = 7.0
B = 800
OUT_DIR = config.PROCESSED_DIR / "nowcast"
DOC = config.ROOT / "paper" / "nowcast-validation.md"


def pseudo_scores_v04(pred_years):
    panel = indicators.load_panel()
    ind = indicators.compute_indicators(panel)
    pep = census_pep.build_pep_migration_panel()
    ces = bls_ces.build_ces_job_growth_panel()
    sg = bea.state_pc_income_growth_panel()
    rows = [bnp.nowcast_row(y, panel, ind, pep, ces, state_growth=sg)
            for y in pred_years]
    ind_ps = pd.concat([ind[~ind["year"].isin(pred_years)], *rows], ignore_index=True)
    return score_mod.score(normalize.normalize(ind_ps))


def main() -> None:
    scored_fin = score_mod.score()
    pred_years = backtest.usable_pred_years(scored_fin)
    scored_ps = pseudo_scores_v04(pred_years)
    zori = backtest._zori_lookup()

    fin = backtest.summarize(backtest.evaluate_predictions(
        scored_fin[["cbsa_code", "year", "score"]], pred_years, (3, 1)))
    ps = backtest.summarize(backtest.evaluate_predictions(
        scored_ps[["cbsa_code", "year", "score"]], pred_years, (3, 1)))

    cols = {"finalized": scored_fin[["cbsa_code", "year", "score"]],
            "pseudo": scored_ps[["cbsa_code", "year", "score"]]}
    frames = uncertainty._window_frames(cols, pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    rng = np.random.default_rng(config.RANDOM_SEED)
    boot = np.empty(B)
    for b in range(B):
        s = rng.choice(metros, size=len(metros), replace=True)
        boot[b] = (uncertainty._pooled_tau(frames, s, "finalized")
                   - uncertainty._pooled_tau(frames, s, "pseudo"))
    gap_lo, gap_hi = np.nanpercentile(boot, [2.5, 97.5])

    agree = []
    for y in pred_years:
        a = scored_fin[scored_fin.year == y][["cbsa_code", "score"]].rename(columns={"score": "f"})
        bb = scored_ps[scored_ps.year == y][["cbsa_code", "score"]].rename(columns={"score": "p"})
        m = a.merge(bb, on="cbsa_code")
        if len(m) < 10:
            continue
        overlap = len(set(m.nlargest(10, "f").cbsa_code) & set(m.nlargest(10, "p").cbsa_code))
        agree.append({"year": int(y), "spearman": float(spearmanr(m.f, m.p)[0]),
                      "top10_overlap": overlap})
    agree = pd.DataFrame(agree)

    def pooled(s):
        return float(s[(s.horizon == 3) & (s.regime == "POOLED")]["mean_tau"].iloc[0])
    fin_tau, ps_tau = pooled(fin), pooled(ps)
    retention = ps_tau / fin_tau
    mean_overlap = float(agree["top10_overlap"].mean())
    passed = (retention >= GATE_TAU_RETENTION) and (mean_overlap >= GATE_MIN_TOP10)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    m = fin.merge(ps, on=["horizon", "regime"], suffixes=("_fin", "_ps"))[
        ["horizon", "regime", "mean_tau_fin", "mean_tau_ps",
         "mean_precision@10_fin", "mean_precision@10_ps"]]
    m.to_csv(OUT_DIR / "gate2025_summary.csv", index=False)
    agree.to_csv(OUT_DIR / "gate2025_agreement.csv", index=False)

    verdict = "PASS" if passed else "FAIL"
    sec = f"""

---

## Gate attempt #4 — the v0.4 state-chained-income 2025 screen (2026-07-08)

Spec logged before the run (decision log 2026-07-08): v0.2 with exactly one change —
the scoring-year income level chained by the primary state's BEA per-capita income
growth (proxy QA: rank agreement 0.51–0.66 every year, vs 0.11 for the flat carry).
Run on the data-repaired panel (finalized pooled 3-yr τ baseline {fin_tau:.3f}).

**3-yr pooled τ:** finalized **{fin_tau:.3f}** vs pseudo **{ps_tau:.3f}** → retention
**{retention*100:.2f}%** (gate ≥ 85%). Gap {fin_tau - ps_tau:+.3f}, 95% CI
[{gap_lo:+.3f}, {gap_hi:+.3f}]. **Mean top-10 overlap {mean_overlap:.2f}/10**
(gate ≥ 7). Per-year overlap: {', '.join(f"{int(r.year)}: {int(r.top10_overlap)}/10" for r in agree.itertuples())}.

**Verdict: {verdict}.**
"""
    DOC.write_text(DOC.read_text(encoding="utf-8") + sec, encoding="utf-8")

    print(f"=== v0.4 gate (one shot) ===")
    print(f"  finalized tau {fin_tau:.3f}  pseudo {ps_tau:.3f}  retention {retention*100:.2f}%")
    print(f"  gap CI [{gap_lo:+.3f}, {gap_hi:+.3f}]  mean top-10 overlap {mean_overlap:.2f}/10")
    print(f"  per-year overlap: {agree.top10_overlap.tolist()}")
    print(f"\n  VERDICT: {verdict}")


if __name__ == "__main__":
    main()
