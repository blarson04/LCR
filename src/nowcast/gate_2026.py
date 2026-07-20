"""
gate_2026.py — the ONE-SHOT gate for the v0.5 mid-year 2026 screen
(spec: decision-log 2026-07-20; cooling-off: may run NO EARLIER than
2026-07-21; first results are final).

Pseudo-test: the identical mid-year scheme applied to every usable historical
scoring year with a closed 3-yr window; each pseudo row is scored through the
unchanged v2 path against the finalized model.

Gate (both prongs to earn the "validated" label):
  A) retention: pooled 3-yr weighted tau >= 85% of the finalized model's
  B) mean top-10 overlap vs the finalized model >= 7/10

Consequence, pre-committed BOTH ways (author direction): the measured
accuracy publishes whichever way it lands, and the 2026->2029 screen ships in
both branches — PASS makes it a validated current screen; FAIL ships it only
as a clearly-labeled speculative outlook carrying the failed numbers as a
warning. See the spec entry for the full wording.

    .venv/Scripts/python.exe src/nowcast/gate_2026.py --verify   # construction only
    .venv/Scripts/python.exe src/nowcast/gate_2026.py            # THE run
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import backtest, normalize  # noqa: E402
from src import score as score_mod  # noqa: E402
from src.nowcast import midyear     # noqa: E402

RETENTION_BAR = 0.85
OVERLAP_BAR = 7.0
EARLIEST_RUN = date(2026, 7, 21)    # cooling-off (P6 rule 1)
OUT_DIR = config.PROCESSED_DIR / "nowcast"


def pseudo_scores(shared: dict, years: list[int]) -> pd.DataFrame:
    """[cbsa_code, year, score] for the mid-year pseudo rows, each scored in
    a frame where year T's finalized row is replaced by the pseudo row."""
    ind = shared["ind"]
    frames = []
    for T in years:
        row = midyear.midyear_row(T, shared)
        full = pd.concat([ind[ind["year"] != T], row], ignore_index=True)
        scored = score_mod.score(normalize.normalize(full))
        frames.append(scored[scored["year"] == T][["cbsa_code", "year", "score"]])
    return pd.concat(frames, ignore_index=True)


def verify() -> None:
    """Construction checks only — coverage and scale sanity. NO accuracy
    metric of any kind is computed here."""
    shared = midyear.load_shared()
    for T in (2018, 2022, 2026):
        pep_override = None
        if T == 2026:
            from src.ingest import census_pep
            pep_override = census_pep.pep_migration_estimate_2025()
        row = midyear.midyear_row(T, shared, pep_override=pep_override)
        n = len(row)
        print(f"[{T}] row: {n} metros")
        assert n == 110, n
        for c in ("trailing_rent_growth", "job_growth", "permits_to_stock",
                  "net_migration", "rent_to_income", "cost_to_own_vs_rent",
                  "employment_diversity"):
            nn = int(row[c].notna().sum())
            print(f"    {c:<22} {nn:>3}/110 non-null")
            assert nn >= 100, (T, c, nn)
        assert row["income_growth"].isna().all(), "income must be neutral-filled"
        tg = row["trailing_rent_growth"].dropna()
        # 2022's real Jan-May YoY asking-rent growth exceeded +30% in several
        # Sun Belt metros; the bound only needs to catch unit errors.
        assert tg.abs().max() < 0.40, "rent growth out of plausible range"
        jg = row["job_growth"].dropna()
        assert jg.abs().max() < 0.20, "job growth out of plausible range"
    print("\nConstruction checks PASS. No accuracy was computed.")


def main() -> None:
    if "--verify" in sys.argv:
        verify()
        return
    if date.today() < EARLIEST_RUN:
        sys.exit(f"COOLING-OFF: the spec was logged 2026-07-20; this gate may "
                 f"not run before {EARLIEST_RUN}. (--verify is allowed.)")

    print("=== v0.5 MID-YEAR GATE — one pre-registered attempt "
          "(spec 2026-07-20) ===\n")
    shared = midyear.load_shared()
    fin_scored = score_mod.score()
    pred_years = backtest.usable_pred_years(fin_scored)
    zori = backtest._zori_lookup()
    latest = int(zori["year"].max())
    years = [T for T in pred_years if T + 3 <= latest]

    ps = pseudo_scores(shared, years)
    res_ps = backtest.evaluate_predictions(ps, years, horizons=(3,))
    res_fin = backtest.evaluate_predictions(
        fin_scored[["cbsa_code", "year", "score"]], years, horizons=(3,))
    tau_ps = float(res_ps["weighted_tau"].mean())
    tau_fin = float(res_fin["weighted_tau"].mean())
    retention = tau_ps / tau_fin

    overlaps = []
    for T in years:
        top_ps = set(ps[ps.year == T].nlargest(10, "score")["cbsa_code"])
        f = fin_scored[fin_scored.year == T]
        top_fin = set(f.nlargest(10, "score")["cbsa_code"])
        overlaps.append({"year": T, "top10_overlap": len(top_ps & top_fin)})
    ov = pd.DataFrame(overlaps)
    mean_ov = float(ov["top10_overlap"].mean())

    a_pass = retention >= RETENTION_BAR
    b_pass = mean_ov >= OVERLAP_BAR
    verdict = "PASS" if (a_pass and b_pass) else "FAIL"

    print(f"Windows: {years}")
    print(f"Pooled 3-yr weighted tau: mid-year {tau_ps:.3f} vs finalized "
          f"{tau_fin:.3f}  ->  retention {retention:.2%} "
          f"({'PASS' if a_pass else 'FAIL'} vs >= {RETENTION_BAR:.0%})")
    print("Top-10 overlap by year: "
          + ", ".join(f"{r.year}: {r.top10_overlap}" for r in ov.itertuples())
          + f"  ->  mean {mean_ov:.2f} ({'PASS' if b_pass else 'FAIL'} vs >= "
            f"{OVERLAP_BAR:.0f}/10)")
    print(f"\nVERDICT: {verdict}")
    print("PASS -> validated current screen (pending green data QA), default "
          "edition, accuracy displayed." if verdict == "PASS" else
          "FAIL -> ships ONLY as a labeled speculative outlook carrying these "
          "numbers as a warning; negative result to Track record.")

    ov.to_csv(OUT_DIR / "gate2026_agreement.csv", index=False)
    pd.DataFrame([{
        "tau_pseudo": tau_ps, "tau_finalized": tau_fin, "retention": retention,
        "retention_bar": RETENTION_BAR, "prong_a_pass": a_pass,
        "mean_top10_overlap": mean_ov, "overlap_bar": OVERLAP_BAR,
        "prong_b_pass": b_pass, "verdict": verdict,
        "windows": " ".join(map(str, years)),
    }]).to_csv(OUT_DIR / "gate2026_summary.csv", index=False)
    print(f"\nWritten: {(OUT_DIR / 'gate2026_summary.csv').relative_to(config.ROOT)}, "
          f"gate2026_agreement.csv")
    print("First results are final. Log the outcome entry in decision-log.md.")


if __name__ == "__main__":
    main()
