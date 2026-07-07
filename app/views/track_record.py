"""
Track record: answers one question: has this worked?

Vintage-honest (v3-P2): the accuracy a real-time user could actually have had
is the headline; finalized-data accuracy is shown as the ceiling. Uncertainty
is stated per-window first (v3-P3); pooled CIs are labeled as cross-sectional.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ui import data, theme  # noqa: E402
import config               # noqa: E402

theme.inject_css(reading=True)
d = data.load()

st.markdown("# Track record")
theme.caption("How the screen would have performed historically, in the data a user could "
              "actually have had, plus the frozen record of every published run.")
st.write("")

# ---- Backtest, two vintages --------------------------------------------------
st.markdown("## Backtest: what was achievable in real time")
st.markdown(
    "Each year's ranking is compared with the rent growth that followed over the next three "
    "years (one-year results as a contrast). Agreement is measured with weighted Kendall's "
    "tau (a rank-agreement score from −1 to +1, where 0 means no relationship) and "
    "precision@10, the share of top-10 picks that landed in the top quarter of markets. "
    "**Two vintages are shown**: *real-time* uses only proxies and carried-forward values a "
    "user could have held at the time; *finalized* uses the complete revised data that "
    "arrives about two years later, and is therefore a ceiling no live user ever had.")

m3_path = config.PROCESSED_DIR / "nowcast" / "m3_summary.csv"
if m3_path.exists():
    m3 = pd.read_csv(m3_path)
    tv = m3.rename(columns={
        "horizon": "Horizon (yrs)", "regime": "Period",
        "mean_tau_ps": "Tau (real-time)", "mean_tau_fin": "Tau (finalized ceiling)",
        "mean_precision@10_ps": "P@10 (real-time)",
        "mean_precision@10_fin": "P@10 (finalized)"})
    tv["Period"] = (tv["Period"].str.replace("_", " ").str.replace("pre covid", "Pre-COVID")
                    .str.replace("shock", "Shock (2020–22)")
                    .str.replace("normalization", "Normalization")
                    .str.replace("POOLED", "All periods"))
    tv = tv[["Horizon (yrs)", "Period", "Tau (real-time)", "Tau (finalized ceiling)",
             "P@10 (real-time)", "P@10 (finalized)"]]
    st.dataframe(
        tv.style.format({"Tau (real-time)": "{:.2f}", "Tau (finalized ceiling)": "{:.2f}",
                         "P@10 (real-time)": "{:.0%}", "P@10 (finalized)": "{:.0%}",
                         "Horizon (yrs)": "{:.0f}"})
          .set_properties(subset=["Tau (real-time)", "Tau (finalized ceiling)"],
                          **{"font-variant-numeric": "tabular-nums", "text-align": "right"}),
        hide_index=True, use_container_width=True)
theme.caption("Validation reflects normal market conditions; the framework underperforms in "
              "shocks. Real-time numbers come from the pseudo-nowcast test (current data "
              "vintages stand in for true unrevised prints, a disclosed simplification).")

# ---- vs simple baselines -------------------------------------------------------
st.markdown("## Against simple alternatives")
bl_path = config.PROCESSED_DIR / "baseline_comparison.csv"
if bl_path.exists():
    bl = pd.read_csv(bl_path)[["model", "tau_3y", "prec_3y"]].rename(columns={
        "model": "Strategy (finalized data)", "tau_3y": "3-yr tau", "prec_3y": "Precision@10"})
    st.dataframe(
        bl.style.format({"3-yr tau": "{:.2f}", "Precision@10": "{:.0%}"})
          .set_properties(subset=["3-yr tau", "Precision@10"],
                          **{"font-variant-numeric": "tabular-nums", "text-align": "right"}),
        hide_index=True, use_container_width=True)
    theme.caption("All rows use finalized data, so the comparison is apples-to-apples. On rank "
                  "agreement the composite's edge over pure rent momentum is within noise, but "
                  "see below for where the two differ. (The composite's real-time equivalent "
                  "is 0.38.)")

# ---- In plain units --------------------------------------------------------
es_path = config.PROCESSED_DIR / "effect_size_windows.csv"
if es_path.exists():
    st.markdown("## In plain units: percentage points of rent growth")
    st.markdown(
        "The same comparison translated into money terms: how much more 3-year rent growth did "
        "each strategy's top-10 markets deliver than the median market, per window?")
    ew = pd.read_csv(es_path)
    piv = ew.pivot_table(index="pred_year", columns="strategy", values="top10_pp_vs_median")
    show = piv[["Composite (model)", "Momentum (trailing rent)", "Equal weight",
                "Random (50-seed mean)"]].round(1).reset_index().rename(columns={
        "pred_year": "Window start", "Composite (model)": "This screen",
        "Momentum (trailing rent)": "Rent momentum", "Equal weight": "Equal weight",
        "Random (50-seed mean)": "Random"})
    st.dataframe(
        show.style.format({c: "{:+.1f}" for c in show.columns if c != "Window start"}
                          | {"Window start": "{:.0f}"})
            .map(lambda v: f"color:{theme.POS}" if isinstance(v, float) and v > 0
                 else (f"color:{theme.NEG}" if isinstance(v, float) and v < 0 else ""),
                 subset=[c for c in show.columns if c != "Window start"]),
        hide_index=True, use_container_width=True)
    cm, mm = piv["Composite (model)"], piv["Momentum (trailing rent)"]
    theme.caption(
        f"Rows are completed 3-year windows labeled by start year; 2022 (covering 2022–25) is "
        f"the most recent that has finished; the current screen's own window (2024–27) is "
        f"graded when 2027 data closes. Pooled: this screen's top-10 beat the median market by "
        f"{cm.mean():+.1f} pp of 3-year rent growth (momentum {mm.mean():+.1f} pp). The "
        f"difference shows in the 2021–22 shock: momentum's picks flipped to {mm.loc[2021]:+.1f} "
        f"and {mm.loc[2022]:+.1f} pp while this screen's held at {cm.loc[2021]:+.1f} and "
        f"{cm.loc[2022]:+.1f} pp. Even after stripping out what momentum already knows, the "
        f"screen still adds predictive signal, though the two miss on many of the same markets, "
        f"so the protection is partial.")

# ---- Honest uncertainty ---------------------------------------------------------
st.markdown("## How sure are we?")
tu_path = config.PROCESSED_DIR / "temporal_uncertainty.csv"
if tu_path.exists():
    tu = pd.read_csv(tu_path).iloc[0]
    st.markdown(f"""
- **The primary uncertainty is which market regime a window lands in.** Across the
  {int(tu['win3_n'])} observed 3-year windows, tau ranged from **{tu['win3_min']:+.2f} to
  {tu['win3_max']:+.2f}**; calm-period windows sat near the top of that range, shock windows
  near the bottom. No pooled average conveys that spread.
- **No single window drives the pooled result**: removing any one window moves the pooled
  3-year tau only between **{tu['jk3_min']:.2f} and {tu['jk3_max']:.2f}**.
- **Neighboring markets move together**, so we also re-ran the analysis treating whole states
  as the unit of chance ({int(tu['n_states'])} states): the pooled tau's 95% interval widens to
  **[{tu['state_tau_lo']:.2f}, {tu['state_tau_hi']:.2f}]**, and the edge over equal weighting
  {"**survives**" if bool(tu['eq_edge_survives_state_cluster']) else "**does not survive**"}
  that stricter test.
- Narrow pooled intervals reported elsewhere are **cross-sectional only**: they say which
  metros, conditional on the six windows history happened to provide, and are silent about
  what the next regime does.""")

# ---- The frozen record -----------------------------------------------------------
st.markdown("## The frozen record")
st.markdown(
    "Every published run is frozen with its scores, rankings, input data, and settings, and "
    "never edited. As real outcomes arrive, anyone can check the old calls against what "
    "happened; the record cannot be quietly rewritten. **The 2023-vintage calls below will "
    "be scored when finalized 2026 rent data lands (expected mid-2027).**")
if len(d["registry"]):
    rt = d["registry"].rename(columns={
        "timestamp_utc": "Run (UTC)", "model_version": "Version", "score_year": "Year",
        "n_metros": "Markets", "top_metro": "Top-ranked market"})
    rt = rt[["Run (UTC)", "Version", "Year", "Markets", "Top-ranked market"]]
    st.dataframe(rt, hide_index=True, use_container_width=True)
theme.caption("These are frozen live predictions, distinct from the retrospective backtest "
              "above. The 2024-vintage entry is the site's current screen; it publishes "
              "because its configuration passed a pre-registered validation gate.")

st.markdown("## Three gates, two failures, one pass")
st.markdown(
    "Every fresher-than-finalized configuration had to pass the same pre-registered gate "
    "(retain ≥85% of the model's signal and match the top-10 on ≥7 of 10 names) in a single "
    "attempt, with the outcome published either way:\n\n"
    "1. **2025 screen, five estimated inputs** kept 74.8% of the signal. **Failed;** "
    "not published.\n"
    "2. **2025 screen, fresher jobs data** kept 84.66%. **Failed by a third of a point**; "
    "we did not round it up; the edition was pulled.\n"
    "3. **2024-vintage screen, one estimated input** (the validated migration substitute) "
    "kept **95.5%**, matched the top-10 on 8.3/10. **Passed**, and is what you see on this "
    "site today, extended one further year (to 2028) after a separate horizon study.")
theme.caption("A validation bar that never fails anything proves nothing. Ours failed two of "
              "three attempts, including one at a margin of 0.34 points, which is exactly "
              "why the one that passed means something.")

st.markdown("## Honest limits")
st.markdown(
    "- The rent data measures asking rents, not signed leases.\n"
    "- No capital-markets or operating-cost data (sale prices, cap rates, insurance, taxes); "
    "rent growth stands in for profitability. Florida 2023–26 shows the gap: insurance-cost "
    "shocks moved multifamily economics in ways no rent-side measure captures.\n"
    "- Measure weights are set by judgment and tested, not statistically fitted.\n"
    "- In shock periods like 2020–22 the screen loses most of its edge; treat it as a "
    "screen, not a forecast.")

theme.page_footer()
