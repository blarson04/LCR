"""
midyear_v06_accuracy.py — descriptive accuracy measurement for the v0.6
mid-year recipe (decision-log 2026-07-21 spec; the P5 descriptive shape).

NOT a gate: no threshold, no pass/fail, no label change. The v0.5 gate is
spent and its FAIL verdict stands. This measures the v0.6 recipe (income via
the same-year Q1 state chain) with the identical pseudo-test machinery so the
speculative page can display the accuracy of the recipe it actually shows.
ONE run; first results final; the numbers publish whichever way they land.

    .venv/Scripts/python.exe src/nowcast/midyear_v06_accuracy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config                       # noqa: E402
from src import backtest            # noqa: E402
from src import score as score_mod  # noqa: E402
from src.nowcast import midyear     # noqa: E402
from src.nowcast.gate_2026 import pseudo_scores  # noqa: E402

OUT = config.PROCESSED_DIR / "nowcast" / "midyear_v06_accuracy.csv"


def main() -> None:
    print("=== v0.6 mid-year recipe: descriptive accuracy measurement ===\n")
    shared = midyear.load_shared()

    # Construction check first (coverage only): income now populated.
    row26 = midyear.midyear_row(2026, shared)
    n_inc = int(row26["income_growth"].notna().sum())
    print(f"[construction] 2026 income_growth coverage: {n_inc}/110 "
          f"(Q1 state chain)")
    assert n_inc >= 100, n_inc

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

    print(f"\nWindows: {years}")
    print(f"Pooled 3-yr weighted tau: v0.6 mid-year {tau_ps:.3f} vs finalized "
          f"{tau_fin:.3f}  ->  retention {retention:.2%}")
    print("Top-10 overlap by year: "
          + ", ".join(f"{r.year}: {r.top10_overlap}" for r in ov.itertuples())
          + f"  ->  mean {mean_ov:.2f}/10")
    print(f"(v0.5 reference, its gate spent: retention 82.74%, overlap 4.83/10; "
          f"the page shows v0.6's own numbers either way.)")

    pd.DataFrame([{
        "recipe": "v0.6 (Q1 state income chain)",
        "tau_pseudo": tau_ps, "tau_finalized": tau_fin, "retention": retention,
        "mean_top10_overlap": mean_ov,
        "windows": " ".join(map(str, years)),
        "note": "descriptive measurement, not a gate; page stays speculative",
    }]).to_csv(OUT, index=False)
    ov.to_csv(config.PROCESSED_DIR / "nowcast" / "midyear_v06_agreement.csv",
              index=False)
    print(f"\nWritten: {OUT.relative_to(config.ROOT)}, midyear_v06_agreement.csv")
    print("First results are final; update the speculative page to display them.")


if __name__ == "__main__":
    main()
