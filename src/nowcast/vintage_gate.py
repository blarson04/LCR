"""
vintage_gate.py — one-shot gate for the lagged-vintage screen (v3.1 spec,
decision log 2026-07-07).

Configuration under test: score year T with ALL finalized inputs except
net_migration, which uses the Census PEP proxy (over ACS population T).
Pseudo-test on every usable historical scoring year; gate thresholds are the
originals, verbatim: >=85% retention of pooled 3-yr weighted tau AND mean
top-10 overlap >= 7/10. One attempt; both outcomes published.

    .venv/Scripts/python.exe src/nowcast/vintage_gate.py
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
from src.ingest import census_pep   # noqa: E402

GATE_TAU_RETENTION = 0.85
GATE_MIN_TOP10 = 7.0
B = 800
OUT = config.ROOT / "paper" / "nowcast-validation.md"


def _vintage_scores(pred_years):
    """Indicators with net_migration replaced by PEP/ACS-population for the
    tested years; everything else finalized. Scored through the unchanged v2 path."""
    panel = indicators.load_panel()
    ind = indicators.compute_indicators(panel)
    pep = census_pep.build_pep_migration_panel()[["cbsa_code", "year", "pep_net_migration"]]

    m = (panel[["cbsa_code", "year", "population"]]
         .merge(pep, on=["cbsa_code", "year"], how="left"))
    m["pep_rate"] = m["pep_net_migration"] / m["population"]
    rate = m.set_index(["cbsa_code", "year"])["pep_rate"]

    iv = ind.set_index(["cbsa_code", "year"])
    mask = iv.index.get_level_values("year").isin(pred_years)
    sub = rate.reindex(iv.index)
    iv.loc[mask, "net_migration"] = sub[mask].where(
        sub[mask].notna(), iv.loc[mask, "net_migration"])
    return score_mod.score(normalize.normalize(iv.reset_index()))


def run():
    scored_fin = score_mod.score()
    pred_years = backtest.usable_pred_years(scored_fin)
    scored_v = _vintage_scores(pred_years)
    zori = backtest._zori_lookup()

    fin = backtest.summarize(backtest.evaluate_predictions(
        scored_fin[["cbsa_code", "year", "score"]], pred_years, (3, 1)))
    vs = backtest.summarize(backtest.evaluate_predictions(
        scored_v[["cbsa_code", "year", "score"]], pred_years, (3, 1)))

    cols = {"finalized": scored_fin[["cbsa_code", "year", "score"]],
            "vintage": scored_v[["cbsa_code", "year", "score"]]}
    frames = uncertainty._window_frames(cols, pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    rng = np.random.default_rng(config.RANDOM_SEED)
    gap_b = np.empty(B)
    for b in range(B):
        s = rng.choice(metros, size=len(metros), replace=True)
        gap_b[b] = (uncertainty._pooled_tau(frames, s, "finalized")
                    - uncertainty._pooled_tau(frames, s, "vintage"))
    gap_lo, gap_hi = np.nanpercentile(gap_b, [2.5, 97.5])

    agree = []
    for y in pred_years:
        a = scored_fin[scored_fin.year == y][["cbsa_code", "score"]].rename(columns={"score": "f"})
        bb = scored_v[scored_v.year == y][["cbsa_code", "score"]].rename(columns={"score": "v"})
        mm = a.merge(bb, on="cbsa_code")
        overlap = len(set(mm.nlargest(10, "f").cbsa_code) & set(mm.nlargest(10, "v").cbsa_code))
        agree.append({"year": int(y), "spearman": spearmanr(mm.f, mm.v)[0],
                      "top10_overlap": overlap})
    agree = pd.DataFrame(agree)

    def pooled(s):
        return float(s[(s.horizon == 3) & (s.regime == "POOLED")]["mean_tau"].iloc[0])
    fin_tau, v_tau = pooled(fin), pooled(vs)
    retention = v_tau / fin_tau
    mean_overlap = float(agree["top10_overlap"].mean())
    passed = (retention >= GATE_TAU_RETENTION) and (mean_overlap >= GATE_MIN_TOP10)

    agree.to_csv(config.PROCESSED_DIR / "nowcast" / "vintage_gate_agreement.csv", index=False)
    m = fin.merge(vs, on=["horizon", "regime"], suffixes=("_fin", "_vint"))
    m.to_csv(config.PROCESSED_DIR / "nowcast" / "vintage_gate_summary.csv", index=False)
    return dict(fin_tau=fin_tau, v_tau=v_tau, retention=retention, gap_ci=(gap_lo, gap_hi),
                mean_overlap=mean_overlap, passed=passed, agree=agree)


def main():
    r = run()
    print("=== v3.1 lagged-vintage gate (one shot; spec of 2026-07-07) ===\n")
    print(f"  3y pooled tau: finalized {r['fin_tau']:.3f}  vintage {r['v_tau']:.3f}  "
          f"retention {r['retention']*100:.2f}%")
    print(f"  gap 95% CI [{r['gap_ci'][0]:+.3f}, {r['gap_ci'][1]:+.3f}]")
    per_year = ", ".join(f"{int(a.year)}:{int(a.top10_overlap)}"
                         for a in r["agree"].itertuples())
    print(f"  per-year top-10 overlap: {per_year}")
    print(f"  mean top-10 overlap {r['mean_overlap']:.2f}/10")
    print(f"\n  GATE (>= {GATE_TAU_RETENTION:.0%} retention AND >= {GATE_MIN_TOP10:.0f}/10): "
          f"{'PASS' if r['passed'] else 'FAIL'}")
    print("  -> " + ("publish the 2024-vintage screen as VALIDATED (vintage-labeled)"
                     if r['passed'] else "negative result #3; nothing ships"))

    sec = f"""

---

## V — Lagged-vintage gate (v3.1 spec, 2026-07-07; one shot)

Configuration: all-finalized inputs, single substitution (PEP migration / ACS population).
Result: pooled 3-yr τ **{r['v_tau']:.3f}** vs finalized **{r['fin_tau']:.3f}** → retention
**{r['retention']*100:.2f}%** (gate ≥ 85%); mean top-10 overlap **{r['mean_overlap']:.2f}/10**
(gate ≥ 7). Gap 95% CI [{r['gap_ci'][0]:+.3f}, {r['gap_ci'][1]:+.3f}].
**{'PASS — the 2024-vintage screen publishes as a VALIDATED current screen (2024→2027), vintage-labeled and registry-frozen.' if r['passed'] else 'FAIL — negative result #3; nothing ships.'}**
"""
    OUT.write_text(OUT.read_text(encoding="utf-8") + sec, encoding="utf-8")


if __name__ == "__main__":
    main()
