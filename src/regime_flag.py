"""
regime_flag.py — ex-ante validation of the regime/confidence flag (v3 P6).

The site's flag warns when model reliability is likely lower. The critique
(v3-plan R4): a conditional claim ("strong in normal regimes") is only usable
if "normal" is identifiable AT SCORING TIME — hindsight regime labels don't
count. This module validates the shipped rule:

    RULE (config.REGIME_FLAG_THRESHOLD, shipped 2026-07-02, validated as-is):
    flag the scoring year if national (median-metro) YoY asking-rent growth
    exceeds 7.5%. Rent data is near-live, so this is scoring-date-available.

Backtest 2016–2025: which years fire; does it fire in the shock (2020–22) and
stay quiet pre-COVID; false positives on calm years; and the payoff — mean
3-yr τ in flagged vs unflagged windows. Writes
data/processed/regime_flag_validation.csv.

    .venv/Scripts/python.exe src/regime_flag.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

SHOCK_YEARS = set(range(config.REGIMES["shock"][0], config.REGIMES["shock"][1] + 1))


def national_rent_growth_by_year(panel: pd.DataFrame) -> pd.Series:
    """Median metro YoY ZORI growth per year (the flag's input)."""
    z = panel.pivot_table(index="year", columns="cbsa_code", values="zori")
    return z.pct_change().median(axis=1).dropna()


def run() -> pd.DataFrame:
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    growth = national_rent_growth_by_year(panel)
    win = pd.read_csv(config.PROCESSED_DIR / "backtest_windows.csv")
    tau3 = win[win.horizon == 3].set_index("pred_year")["weighted_tau"]
    tau1 = win[win.horizon == 1].set_index("pred_year")["weighted_tau"]

    rows = []
    for y in range(2016, 2026):
        g = growth.get(y, np.nan)
        rows.append({
            "year": y, "national_rent_growth": g,
            "flag_fires": bool(g > config.REGIME_FLAG_THRESHOLD) if pd.notna(g) else None,
            "hindsight_regime": ("shock" if y in SHOCK_YEARS else
                                 "pre_covid" if y <= 2019 else "normalization"),
            "tau_3y_window": float(tau3.get(y, np.nan)),
            "tau_1y_window": float(tau1.get(y, np.nan)),
        })
    df = pd.DataFrame(rows)
    df.to_csv(config.PROCESSED_DIR / "regime_flag_validation.csv", index=False)
    return df


def main() -> None:
    df = run()
    thr = config.REGIME_FLAG_THRESHOLD
    print(f"=== P6: regime-flag validation (rule: national rent growth > {thr:.1%}, "
          f"shipped before this test) ===\n")
    show = df.copy()
    show["national_rent_growth"] = show["national_rent_growth"].map(
        lambda v: f"{v:+.1%}" if pd.notna(v) else "—")
    for c in ("tau_3y_window", "tau_1y_window"):
        show[c] = show[c].map(lambda v: f"{v:+.2f}" if pd.notna(v) else "—")
    print(show.to_string(index=False))

    fired = df[df.flag_fires == True]           # noqa: E712
    quiet = df[df.flag_fires == False]          # noqa: E712
    fp = fired[~fired.year.isin(SHOCK_YEARS)]
    fn = quiet[quiet.year.isin(SHOCK_YEARS)]
    print(f"\n  fires in: {sorted(fired.year.tolist())}")
    print(f"  false positives (fires in calm years): {len(fp)} -> {sorted(fp.year.tolist())}")
    print(f"  missed shock years: {sorted(fn.year.tolist())} "
          f"(2020's demand shock did NOT spike rents — disclosed limitation; "
          f"2020 is also not a scoreable 3-yr window)")
    t_f = df[df.flag_fires == True]["tau_3y_window"].dropna()     # noqa: E712
    t_q = df[df.flag_fires == False]["tau_3y_window"].dropna()    # noqa: E712
    print(f"\n  payoff: mean 3-yr tau in FLAGGED windows {t_f.mean():+.2f} "
          f"(n={len(t_f)}) vs UNFLAGGED {t_q.mean():+.2f} (n={len(t_q)})")
    print("  1-yr contrast: flagged "
          f"{df[df.flag_fires == True]['tau_1y_window'].dropna().mean():+.2f} vs unflagged "  # noqa: E712
          f"{df[df.flag_fires == False]['tau_1y_window'].dropna().mean():+.2f}")               # noqa: E712


if __name__ == "__main__":
    main()
