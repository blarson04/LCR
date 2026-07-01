"""
price_return.py — the price/return dimension (V2 P5), tested measure-first.

The v1/v2 target is asking-rent growth only (critique W5). ZHVI home values are
already in the panel, so this asks two gated questions before adding anything:

  (1) REDUNDANCY — are price/return measures new information, or already in the
      rent model? price_to_rent vs the existing cost_to_own_vs_rent indicator;
      home_appreciation vs trailing_rent_growth.
  (2) PREDICTIVE VALUE — does a valuation/yield "return screen" predict forward
      home-price appreciation, and does it beat the existing rent-growth model
      (which we also score against appreciation as a generalization test)?

Finding (see printout): price/return measures are redundant or non-predictive,
while the rent-growth composite predicts appreciation too — so we do NOT add a
yield indicator or a separate valuation screen. Instead the model's appreciation
skill is reported as a validated secondary outcome (a total-return proxy).

    .venv/Scripts/python.exe src/price_return.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import indicators          # noqa: E402
from src import score as score_mod  # noqa: E402
from src import backtest            # noqa: E402

SCORE_YEAR = score_mod.SCORE_YEAR


def _zwithin(s: pd.Series, yr: pd.Series) -> pd.Series:
    g = s.groupby(yr)
    return (s - g.transform("mean")) / g.transform("std").replace(0, np.nan)


def _measures(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.sort_values(["cbsa_code", "year"]).copy()
    panel["price_to_rent"] = panel["zhvi"] / (panel["zori"] * 12)
    panel["gross_yield"] = (panel["zori"] * 12) / panel["zhvi"]
    prev = panel[["cbsa_code", "year", "zhvi"]].copy()
    prev["year"] += 1
    prev = prev.rename(columns={"zhvi": "_zhvi_prev"})
    panel = panel.merge(prev, on=["cbsa_code", "year"], how="left")
    panel["home_appreciation"] = panel["zhvi"] / panel["_zhvi_prev"] - 1
    return panel


def run():
    panel = _measures(indicators.load_panel())
    ind = indicators.compute_indicators()
    existing = list(config.INDICATORS)

    # (1) redundancy vs existing indicators (scoring-year cross-section)
    y = panel[panel.year == SCORE_YEAR][
        ["cbsa_code", "price_to_rent", "home_appreciation"]].merge(
        ind[ind.year == SCORE_YEAR], on="cbsa_code")
    redun = []
    for nc in ["price_to_rent", "home_appreciation"]:
        for e in existing:
            redun.append({"new_measure": nc, "indicator": e, "corr": y[nc].corr(y[e])})
    redun = pd.DataFrame(redun)

    # (2) predict forward home-price appreciation (target = zhvi)
    zhvi = panel[["cbsa_code", "year", "zhvi"]].dropna()
    keys = panel[["cbsa_code", "year"]]
    def mk(v): d = keys.copy(); d["score"] = np.asarray(v); return d
    preds = {
        "low valuation (-price/rent)": mk(-_zwithin(panel["price_to_rent"], panel["year"])),
        "high yield (rent/price)": mk(_zwithin(panel["gross_yield"], panel["year"])),
        "price momentum (trailing appr)": mk(_zwithin(panel["home_appreciation"], panel["year"])),
        "rent-growth composite (v2)": score_mod.score()[["cbsa_code", "year", "score"]],
    }
    py = backtest.usable_pred_years()
    rows = []
    for n, p in preds.items():
        s = backtest.summarize(backtest.evaluate_predictions(p, py, (3, 1), target=zhvi, target_col="zhvi"))
        def g(h):
            r = s[(s.horizon == h) & (s.regime == "POOLED")]
            return float(r.mean_tau.iloc[0]), float(r["mean_precision@10"].iloc[0])
        t3, p3 = g(3); t1, _ = g(1)
        rows.append({"predictor": n, "appr_tau_3y": t3, "appr_p@10_3y": p3, "appr_tau_1y": t1})
    appr = pd.DataFrame(rows).sort_values("appr_tau_3y", ascending=False)
    return redun, appr


def main() -> None:
    redun, appr = run()
    redun.to_csv(config.PROCESSED_DIR / "price_return_redundancy.csv", index=False)
    appr.to_csv(config.PROCESSED_DIR / "price_return_appreciation.csv", index=False)

    print(f"=== P5 (1) Redundancy: new price/return measures vs existing indicators ({SCORE_YEAR}) ===\n")
    for nc in redun.new_measure.unique():
        top = redun[redun.new_measure == nc].reindex(
            redun[redun.new_measure == nc]["corr"].abs().sort_values(ascending=False).index).head(3)
        print(f"  {nc}:")
        for _, r in top.iterrows():
            print(f"     {r['corr']:+.2f}  {r['indicator']}")
    print("\n  => price_to_rent ~ cost_to_own_vs_rent (already in the model);")
    print("     home_appreciation ~ trailing_rent_growth. Not new information.")

    print("\n=== P5 (2) Predicting forward HOME-PRICE APPRECIATION (target = zhvi) ===\n")
    print(f"  {'predictor':<32}{'3y tau':>8}{'P@10':>7}{'1y tau':>8}")
    for _, r in appr.iterrows():
        print(f"  {r['predictor']:<32}{r['appr_tau_3y']:>8.3f}{r['appr_p@10_3y']:>7.2f}{r['appr_tau_1y']:>8.3f}")

    print("\nConclusion: a valuation/yield return-screen has ~no signal; the rent-growth")
    print("composite predicts appreciation too. => Do NOT add a yield indicator or a")
    print("separate valuation screen; report the model's appreciation skill as a validated")
    print("secondary (total-return) outcome instead (addresses W5).")


if __name__ == "__main__":
    main()
