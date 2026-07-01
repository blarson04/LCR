"""
ablation.py — what actually carries the signal? (V2 P2)

Two diagnostics, both on existing data via the shared walk-forward harness:

  (a) LEAVE-ONE-OUT. Rebuild the composite with one indicator (or one whole
      bucket) removed and measure the change in 3-yr tau vs the full model.
        delta_tau > 0  -> dropping it HELPED (dead weight or actively harmful)
        delta_tau < 0  -> it was contributing positively
      Because tau is rank-based (scale-invariant), dropping an indicator's
      weighted contribution is a clean ablation without needing to renormalize.

  (b) CORRELATION. Correlation matrix of the (directional, normalized)
      indicators, flagging redundant pairs — hand-set weights on correlated
      indicators silently double-count whatever they share.

    .venv/Scripts/python.exe src/ablation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config                       # noqa: E402
from src import normalize           # noqa: E402
from src import score as score_mod  # noqa: E402
from src import backtest            # noqa: E402
from src import baselines           # noqa: E402  (reuse _metrics)

INDICATORS = list(config.INDICATORS)
W = {k: v["weight"] for k, v in config.INDICATORS.items()}
BUCKET = {k: v["bucket"] for k, v in config.INDICATORS.items()}
BUCKETS = list(dict.fromkeys(BUCKET.values()))


def _build_variants(norm: pd.DataFrame):
    """Return (key_df, {variant_name: score_series}) — full model plus every
    leave-one-indicator-out and leave-one-bucket-out composite."""
    keys = norm[["cbsa_code", "year"]].copy()
    z = norm[INDICATORS].fillna(0.0)
    full = sum(W[k] * z[k] for k in INDICATORS)

    variants = {"Full model": full}
    for k in INDICATORS:
        variants[f"- {k}"] = full - W[k] * z[k]
    for b in BUCKETS:
        cols = [k for k in INDICATORS if BUCKET[k] == b]
        variants[f"- bucket: {b}"] = full - sum(W[k] * z[k] for k in cols)
    return keys, variants


def run():
    norm = normalize.normalize()
    scored = score_mod.score()
    pred_years = backtest.usable_pred_years(scored)
    zori = backtest._zori_lookup()

    keys, variants = _build_variants(norm)
    rows = []
    for name, series in variants.items():
        pred = keys.copy()
        pred["score"] = series.to_numpy()
        summ = backtest.summarize(backtest.evaluate_predictions(pred, pred_years, (3, 1), zori))
        rows.append({"variant": name, **baselines._metrics(summ)})
    abl = pd.DataFrame(rows)
    full_tau = abl.loc[abl.variant == "Full model", "tau_3y"].iloc[0]
    abl["delta_tau_3y"] = abl["tau_3y"] - full_tau   # >0 => dropping it helped

    corr = norm[INDICATORS].corr()
    return abl, corr, full_tau


def _high_corr_pairs(corr: pd.DataFrame, thresh: float = 0.5) -> pd.DataFrame:
    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if abs(r) >= thresh:
                pairs.append({"a": cols[i], "b": cols[j], "corr": r})
    return pd.DataFrame(pairs).sort_values("corr", key=lambda s: s.abs(), ascending=False)


def main() -> None:
    abl, corr, full_tau = run()
    abl.to_csv(config.PROCESSED_DIR / "ablation.csv", index=False)
    corr.to_csv(config.PROCESSED_DIR / "indicator_correlation.csv")

    ind = abl[abl.variant.str.startswith("- ") & ~abl.variant.str.contains("bucket")]
    buc = abl[abl.variant.str.contains("bucket")]
    ind = ind.sort_values("delta_tau_3y", ascending=False)
    buc = buc.sort_values("delta_tau_3y", ascending=False)

    print(f"=== P2 leave-one-out ablation (full-model 3y tau = {full_tau:.3f}) ===")
    print("delta_tau_3y > 0  =>  dropping it RAISED tau (dead weight / harmful)\n")
    print(f"{'Drop indicator':<26}{'3y tau':>8}{'delta':>9}{'1y tau':>8}")
    print("  " + "-" * 51)
    for _, r in ind.iterrows():
        print(f"{r['variant']:<26}{r['tau_3y']:>8.3f}{r['delta_tau_3y']:>+9.3f}{r['tau_1y']:>8.3f}")

    print(f"\n{'Drop whole bucket':<26}{'3y tau':>8}{'delta':>9}{'1y tau':>8}")
    print("  " + "-" * 51)
    for _, r in buc.iterrows():
        print(f"{r['variant']:<26}{r['tau_3y']:>8.3f}{r['delta_tau_3y']:>+9.3f}{r['tau_1y']:>8.3f}")

    pairs = _high_corr_pairs(corr, 0.5)
    print("\n=== P2 redundancy: indicator pairs with |correlation| >= 0.5 ===\n")
    if len(pairs):
        for _, r in pairs.iterrows():
            print(f"  {r['corr']:+.2f}   {r['a']}  <->  {r['b']}")
    else:
        print("  (none — indicators are reasonably independent)")

    print("\nReading it: indicators with delta > 0 are candidates to drop (they hurt the")
    print("3y ranking on this sample); highly-correlated pairs are double-counting candidates.")
    print("Caveat: point estimates, few windows — P3 will add confidence intervals.")


if __name__ == "__main__":
    main()
