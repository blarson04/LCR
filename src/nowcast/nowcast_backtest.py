"""
nowcast_backtest.py — the pseudo-nowcast honesty test (M3).

Rebuilds each historical scoring year using ONLY what the nowcast would have had
(PEP for migration, carried-forward slow indicators, live rent/permits — the
same proxy scheme as M2), runs the standard walk-forward evaluation, and asks:
**how much accuracy do the proxies cost vs. the finalized model?**

Reports finalized vs. pseudo-nowcast per regime, a metro-cluster bootstrap CI on
the 3-yr pooled τ gap (P3 machinery), and per-year ranking agreement (Spearman +
top-10 overlap). Then applies the PRE-COMMITTED go/no-go gate from the decision
log. Appends the M3 section to paper/nowcast-validation.md.

    .venv/Scripts/python.exe src/nowcast/nowcast_backtest.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import indicators, normalize  # noqa: E402
from src import score as score_mod  # noqa: E402
from src import backtest, uncertainty  # noqa: E402
from src.ingest import census_pep  # noqa: E402
from src.nowcast import build_nowcast_panel as bnp  # noqa: E402

# Pre-committed gate (decision log, 2026-07-02).
GATE_TAU_RETENTION = 0.85
GATE_MIN_TOP10 = 7.0
B = 800
OUT = config.ROOT / "paper" / "nowcast-validation.md"


def _pseudo_scores(pred_years):
    """Score every metro-year with the pseudo-nowcast panel (target years rebuilt
    from proxies; other years finalized so within-year normalization is fair)."""
    from src.ingest import bls_ces
    panel = indicators.load_panel()
    ind = indicators.compute_indicators(panel)
    pep = census_pep.build_pep_migration_panel()
    ces = bls_ces.build_ces_job_growth_panel()
    rows = [bnp.nowcast_row(y, panel, ind, pep, ces) for y in pred_years]
    ind_ps = pd.concat([ind[~ind["year"].isin(pred_years)], *rows], ignore_index=True)
    return score_mod.score(normalize.normalize(ind_ps))


def run():
    scored_fin = score_mod.score()
    pred_years = backtest.usable_pred_years(scored_fin)
    scored_ps = _pseudo_scores(pred_years)
    zori = backtest._zori_lookup()

    fin = backtest.summarize(backtest.evaluate_predictions(
        scored_fin[["cbsa_code", "year", "score"]], pred_years, (3, 1)))
    ps = backtest.summarize(backtest.evaluate_predictions(
        scored_ps[["cbsa_code", "year", "score"]], pred_years, (3, 1)))

    # bootstrap CI on the 3-yr pooled tau gap (finalized - pseudo)
    cols = {"finalized": scored_fin[["cbsa_code", "year", "score"]],
            "pseudo": scored_ps[["cbsa_code", "year", "score"]]}
    frames = uncertainty._window_frames(cols, pred_years, zori)
    metros = sorted(set().union(*[set(f.index) for f in frames]))
    rng = np.random.default_rng(config.RANDOM_SEED)
    gap_boot = np.empty(B)
    for b in range(B):
        s = rng.choice(metros, size=len(metros), replace=True)
        gap_boot[b] = (uncertainty._pooled_tau(frames, s, "finalized")
                       - uncertainty._pooled_tau(frames, s, "pseudo"))
    gap_lo, gap_hi = np.nanpercentile(gap_boot, [2.5, 97.5])

    # per-year ranking agreement (finalized vs pseudo)
    agree = []
    for y in pred_years:
        a = scored_fin[scored_fin.year == y][["cbsa_code", "score"]].rename(columns={"score": "f"})
        bb = scored_ps[scored_ps.year == y][["cbsa_code", "score"]].rename(columns={"score": "p"})
        m = a.merge(bb, on="cbsa_code")
        if len(m) < 10:
            continue
        overlap = len(set(m.nlargest(10, "f").cbsa_code) & set(m.nlargest(10, "p").cbsa_code))
        agree.append({"year": int(y), "spearman": spearmanr(m.f, m.p)[0], "top10_overlap": overlap})
    agree = pd.DataFrame(agree)

    def pooled_tau(summ):
        return float(summ[(summ.horizon == 3) & (summ.regime == "POOLED")]["mean_tau"].iloc[0])
    fin_tau, ps_tau = pooled_tau(fin), pooled_tau(ps)
    retention = ps_tau / fin_tau if fin_tau else float("nan")
    mean_overlap = agree["top10_overlap"].mean()
    passed = (retention >= GATE_TAU_RETENTION) and (mean_overlap >= GATE_MIN_TOP10)
    return dict(fin=fin, ps=ps, fin_tau=fin_tau, ps_tau=ps_tau, retention=retention,
                gap=fin_tau - ps_tau, gap_ci=(gap_lo, gap_hi), agree=agree,
                mean_overlap=mean_overlap, passed=passed)


def _merge_summ(fin, ps):
    m = fin.merge(ps, on=["horizon", "regime"], suffixes=("_fin", "_ps"))
    m = m[["horizon", "regime", "mean_tau_fin", "mean_tau_ps", "mean_precision@10_fin", "mean_precision@10_ps"]]
    return m


def _tbl(df, fmt):
    d = df.copy()
    for c, f in fmt.items():
        d[c] = d[c].map(f)
    head = "| " + " | ".join(d.columns) + " |"
    sep = "| " + " | ".join("---" for _ in d.columns) + " |"
    rows = ["| " + " | ".join(str(v) for v in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join([head, sep, *rows])


def _write_doc(r):
    m = _merge_summ(r["fin"], r["ps"]).rename(columns={
        "horizon": "h", "regime": "regime", "mean_tau_fin": "τ finalized", "mean_tau_ps": "τ pseudo",
        "mean_precision@10_fin": "P@10 fin", "mean_precision@10_ps": "P@10 pseudo"})
    m["regime"] = m["regime"].str.replace("_", "-")
    verdict = ("PASS — publish provisional nowcast" if r["passed"] else
               "FAIL — published as a negative result; surfaced only as a provisional-"
               "experimental edition under the amended gate taxonomy (decision log 2026-07-06)")
    decomp_path = config.PROCESSED_DIR / "nowcast" / "m3_decomposition.csv"
    decomp_md = ""
    if decomp_path.exists():
        dc = pd.read_csv(decomp_path)
        decomp_md = ("\n**Which proxy causes the loss? (pooled 3-yr τ by variant)**\n\n"
                     + _tbl(dc.rename(columns={"variant": "variant", "pooled_tau_3y": "pooled τ",
                                               "retention": "retention"}),
                            {"pooled τ": "{:.3f}".format, "retention": "{:.0%}".format})
                     + "\n\nThe migration proxy costs almost nothing; carrying forward "
                       "`job_growth`+`income_growth` drives the entire failure.\n")
    if r["passed"]:
        decision_md = (
            "\n### Decision\nGate **PASSED** on the pre-committed one-shot CES re-run "
            "(decision log 2026-07-06): the provisional configuration retains the required signal. "
            "Per the pre-commitment, the current-year screen is promoted to a **validated** "
            "edition — published with its vintage and per-indicator provenance displayed.\n")
    else:
        decision_md = (
            "\n### Decision\nGate **NOT MET on the pre-committed one-shot CES re-run** "
            "(decision log 2026-07-06). Per the binding consequence, the provisional edition is "
            "**pulled from the site**, and no further proxy iterations may run without a new "
            "pre-registered specification. This is published negative result #2.\n")
    sec = f"""

---

## M3 — Pseudo-nowcast backtest (accuracy cost)

Rebuilding history with the nowcast's proxies (PEP migration, carried-forward slow
indicators, live rent/permits) and running the standard walk-forward evaluation:

{_tbl(m, {"τ finalized": "{:.3f}".format, "τ pseudo": "{:.3f}".format,
          "P@10 fin": "{:.2f}".format, "P@10 pseudo": "{:.2f}".format, "h": "{:.0f}".format})}

**3-yr pooled τ:** finalized **{r['fin_tau']:.3f}** vs pseudo-nowcast **{r['ps_tau']:.3f}** →
retention **{r['retention']*100:.1f}%**. Gap **{r['gap']:+.3f}**, 95% CI
[{r['gap_ci'][0]:+.3f}, {r['gap_ci'][1]:+.3f}] (metro-cluster bootstrap).

**Ranking agreement (pseudo vs finalized), per year:**

{_tbl(r['agree'], {"spearman": "{:.3f}".format, "top10_overlap": "{:.0f}/10".format})}

Mean top-10 overlap **{r['mean_overlap']:.1f}/10**.

**Gate (pre-committed):** retain ≥ {GATE_TAU_RETENTION*100:.0f}% of pooled 3-yr τ AND mean top-10
overlap ≥ {GATE_MIN_TOP10:.0f}/10 → **{verdict}**.
{decomp_md}{decision_md}"""
    doc = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
    if "## M3 — Pseudo-nowcast" in doc:
        doc = doc.split("\n\n---\n\n## M3 — Pseudo-nowcast")[0]
    OUT.write_text(doc + sec, encoding="utf-8")


def decompose() -> pd.DataFrame:
    """Isolate which proxy drives the accuracy loss (pooled 3y τ per variant)."""
    from src.ingest import bls_ces
    panel = indicators.load_panel()
    ind = indicators.compute_indicators(panel)
    pep = census_pep.build_pep_migration_panel()
    ces = bls_ces.build_ces_job_growth_panel()
    py = backtest.usable_pred_years(score_mod.score())

    def pooled(frame):
        sc = score_mod.score(normalize.normalize(frame))
        s = backtest.summarize(backtest.evaluate_predictions(
            sc[["cbsa_code", "year", "score"]], py, (3,)))
        return float(s[(s.horizon == 3) & (s.regime == "POOLED")].mean_tau.iloc[0])

    rows = [bnp.nowcast_row(y, panel, ind, pep, ces) for y in py]
    pseudo = pd.concat([ind[~ind["year"].isin(py)], *rows], ignore_index=True)
    ps_idx = pseudo.set_index(["cbsa_code", "year"])

    mig = ind.copy().set_index(["cbsa_code", "year"])
    mig.loc[ps_idx.index, "net_migration"] = ps_idx["net_migration"]
    jobs_final = pseudo.copy().set_index(["cbsa_code", "year"])
    finx = ind.set_index(["cbsa_code", "year"])
    for k in ("job_growth", "income_growth"):
        repl = finx[k].reindex(jobs_final.index)
        jobs_final[k] = repl.where(repl.notna(), jobs_final[k])

    out = pd.DataFrame([
        {"variant": "finalized (all real)", "pooled_tau_3y": pooled(ind)},
        {"variant": "only migration proxied", "pooled_tau_3y": pooled(mig.reset_index())},
        {"variant": "pseudo but jobs+income finalized", "pooled_tau_3y": pooled(jobs_final.reset_index())},
        {"variant": "full pseudo-nowcast", "pooled_tau_3y": pooled(pseudo)},
    ])
    fin = out.iloc[0]["pooled_tau_3y"]
    out["retention"] = out["pooled_tau_3y"] / fin
    out.to_csv(config.PROCESSED_DIR / "nowcast" / "m3_decomposition.csv", index=False)
    return out


def main() -> None:
    r = run()
    (config.PROCESSED_DIR / "nowcast").mkdir(parents=True, exist_ok=True)
    _merge_summ(r["fin"], r["ps"]).to_csv(config.PROCESSED_DIR / "nowcast" / "m3_summary.csv", index=False)
    r["agree"].to_csv(config.PROCESSED_DIR / "nowcast" / "m3_agreement.csv", index=False)
    _write_doc(r)

    print("=== M3 pseudo-nowcast vs finalized ===\n")
    print(f"  3y pooled tau: finalized {r['fin_tau']:.3f}  pseudo {r['ps_tau']:.3f}  "
          f"retention {r['retention']*100:.1f}%")
    print(f"  gap {r['gap']:+.3f}  95% CI [{r['gap_ci'][0]:+.3f}, {r['gap_ci'][1]:+.3f}]")
    print(f"  mean top-10 overlap {r['mean_overlap']:.1f}/10")
    print(f"\n  GATE (>= {GATE_TAU_RETENTION*100:.0f}% tau retained AND >= {GATE_MIN_TOP10:.0f}/10 overlap): "
          f"{'PASS' if r['passed'] else 'FAIL'}")
    print(f"  -> {'publish provisional nowcast' if r['passed'] else 'ship as internal experiment (documented)'}")


if __name__ == "__main__":
    main()
