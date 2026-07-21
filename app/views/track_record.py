"""
Track record: answers one question: has this worked?

v4 order: the plain-units edge first, then the gate arc, the baseline table,
the honest limits, the frozen registry with its pre-announced 2028 scoring,
and the full statistics in expanders. Vintage-honest throughout.
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

from ui import data, diagrams, theme  # noqa: E402
import config               # noqa: E402

theme.inject_css(reading=True)
d = data.load()

theme.eyebrow("Multifamily research · the fine print")
st.markdown("# Track record")
theme.caption("How the screen has performed against what actually happened, plus the "
              "frozen record of every published run.")
st.write("")

# ---- 1. The edge, in plain units --------------------------------------------
st.markdown("## The edge, in points of rent growth")
st.markdown(diagrams.walkforward_timeline(2019), unsafe_allow_html=True)
theme.caption("How every window is graded, shown for 2019: the call is frozen at "
              "publication and scored three years later.")
es_path = config.PROCESSED_DIR / "effect_size_windows.csv"
if es_path.exists():
    st.markdown(
        "Each completed three-year window asks: how much more rent growth did each "
        "strategy's top-10 markets deliver than the median market?")
    ew = pd.read_csv(es_path)
    piv = ew.pivot_table(index="pred_year", columns="strategy",
                         values="top10_pp_vs_median")
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
        hide_index=True, use_container_width=True,
        column_config={
            "Window start": st.column_config.NumberColumn(
                help="The first year of the 3-year window: the 2019 row grades "
                     "predictions made on 2019 data against 2019-2022 rent growth."),
            **{c: st.column_config.TextColumn(
                help=f"How many percentage points more 3-year rent growth the top-10 "
                     f"markets picked by '{c}' delivered than the median market. "
                     f"+6.0 means their rents grew 6 points more than the middle "
                     f"market's over those three years.")
               for c in show.columns if c != "Window start"}})
    cm, mm = piv["Composite (model)"], piv["Momentum (trailing rent)"]
    theme.caption(
        f"Pooled: this screen's top-10 beat the median market by {cm.mean():+.1f} "
        f"points of 3-year rent growth (momentum {mm.mean():+.1f}); in the 2021–22 "
        f"shock rows momentum flipped firmly negative while the screen held near "
        f"flat. Validation reflects normal conditions; the site flags shock periods.")

# ---- 2. The gate arc --------------------------------------------------------
st.markdown("## Five gates, three failures, two passes")
st.markdown(
    "Every fresher-than-finalized configuration faced the same pre-registered gate "
    "(keep 85% of the model's signal, match the top-10 on 7 of 10 names), one "
    "attempt each, outcome published either way:\n\n"
    "1. **Five estimated inputs** kept 74.8%. **Failed;** not published.\n"
    "2. **Fresher jobs data** kept 84.66%. **Failed by a third of a point**; pulled, "
    "not rounded up.\n"
    "3. **The 2024-vintage screen** (one estimated input) kept **95.5%**. **Passed.**\n"
    "4. **Income chained by state growth** (the fix for failure #2's diagnosed cause) "
    "kept **96.6%**. **Passed**; it is the current 2025→2028 screen.\n"
    "5. **The mid-year 2026 screen** (five months of data; income not observable) "
    "kept **82.7%** and matched **4.8 of 10**. **Failed both bars**; it ships only "
    "as a labeled speculative outlook, never as a validated screen.")
theme.caption("A validation bar that never fails anything proves nothing; ours failed "
              "three of five attempts. Separately, nine candidate measures and model "
              "variants have been gated one-shot; zero were adopted, every negative "
              "result published.")
with st.expander("Two disclosures about the gates"):
    theme.caption(
        "The fourth attempt's fix was diagnosed on the same historical windows it was "
        "scored on, so its real test is the frozen 2025→2028 call itself, published "
        "whatever it shows. And since July 2026 a gate pass alone is not enough: the "
        "data build must also clear an automated quality review, with every flag "
        "signed off in the public decision log.")
    theme.caption(
        "The most recent candidate gate (July 2026) tested smoothing the two noisiest "
        "inputs over three years: it made rankings measurably calmer between editions "
        "but reliably less accurate, so it was rejected; the tiers and rank ranges "
        "shown sitewide are the honest answer to that noise instead.")

# ---- 3. Against simple alternatives -----------------------------------------
st.markdown("## Against simple alternatives")
bl_path = config.PROCESSED_DIR / "baseline_comparison.csv"
if bl_path.exists():
    bl = pd.read_csv(bl_path)[["model", "tau_3y", "prec_3y"]].rename(columns={
        "model": "Strategy (finalized data)", "tau_3y": "3-yr tau",
        "prec_3y": "Precision@10"})
    st.dataframe(
        bl.style.format({"3-yr tau": "{:.2f}", "Precision@10": "{:.0%}"})
          .set_properties(subset=["3-yr tau", "Precision@10"],
                          **{"font-variant-numeric": "tabular-nums",
                             "text-align": "right"}),
        hide_index=True, use_container_width=True,
        column_config={
            "3-yr tau": st.column_config.TextColumn(
                help="How well each strategy's ranking agreed with the 3-year rent "
                     "growth that followed, on a -1 to +1 scale where 0 means no "
                     "relationship and random guessing scores about 0."),
            "Precision@10": st.column_config.TextColumn(
                help="Of the 10 markets each strategy ranked highest, the share that "
                     "landed in the top quarter of markets by actual rent growth.")})
    theme.caption("All rows use finalized data, apples-to-apples. The industry-style "
                  "row rebuilds a common equal-weight scorecard from the six of its "
                  "ten categories free data can populate; it scores industry practice "
                  "at this task, not any vendor's product at theirs.")

# ---- 4. Honest limits -------------------------------------------------------
st.markdown("## Honest limits")
st.markdown(
    "- The rent data measures asking rents, not signed leases.\n"
    "- No capital-markets or operating-cost data (sale prices, cap rates, insurance, "
    "taxes); rent growth stands in for profitability. Florida 2023–26 shows the gap: "
    "insurance-cost shocks moved multifamily economics in ways no rent-side measure "
    "captures.\n"
    "- Measure weights are set by judgment and tested, not statistically fitted.\n"
    "- In shock periods like 2020–22 the screen loses most of its edge; treat it as a "
    "screen, not a forecast.")

# ---- 5. The frozen record ---------------------------------------------------
st.markdown("## The frozen record")
st.markdown(
    "Every published run is frozen with its scores, rankings, inputs, and settings, "
    "and never edited, so old calls cannot be quietly rewritten. **The frozen "
    "2025→2028 screen will be scored against realized rent growth when 2028 rent "
    "data closes (early 2029), whatever it shows**; the 2023-vintage calls are "
    "graded first, in mid-2027.")
if len(d["registry"]):
    rt = d["registry"].rename(columns={
        "timestamp_utc": "Run (UTC)", "model_version": "Version", "score_year": "Year",
        "n_metros": "Markets", "top_metro": "Top-ranked market"})
    rt = rt[["Run (UTC)", "Version", "Year", "Markets", "Top-ranked market"]]
    st.dataframe(rt, hide_index=True, use_container_width=True)
theme.caption("Frozen live predictions, distinct from the backtest; each passed a "
              "pre-registered gate to publish.")

# ---- 6. Full statistics (expanders) -----------------------------------------
with st.expander("Full statistics: rank agreement, real-time vs finalized"):
    bt = d["backtest"]
    _pc = bt[(bt.horizon == 3) & (bt.regime == "pre_covid")]
    pc_prec = float(_pc["mean_precision@10"].iloc[0]) if len(_pc) else float("nan")
    _sh = bt[(bt.horizon == 3) & (bt.regime == "shock")]
    sh_tau = float(_sh["mean_tau"].iloc[0]) if len(_sh) else float("nan")
    theme.caption(
        f"Agreement is weighted Kendall's tau, a rank-agreement score from −1 to +1 "
        f"where 0 means no relationship. In calm (pre-COVID) windows the finalized "
        f"model scores {d['pc_tau']:.2f} with {pc_prec:.0%} of top-10 picks landing "
        f"in the top quarter of markets; in the 2021–22 shock windows agreement falls "
        f"to {sh_tau:.2f}. Real-time uses only proxies and carried-forward values a "
        f"user could have held at the time; finalized uses revised data that arrives "
        f"about two years later, a ceiling no live user ever had.")
    m3_path = config.PROCESSED_DIR / "nowcast" / "gate2025_summary.csv"
    if not m3_path.exists():
        m3_path = config.PROCESSED_DIR / "nowcast" / "m3_summary.csv"
    if m3_path.exists():
        m3 = pd.read_csv(m3_path)
        tv = m3.rename(columns={
            "horizon": "Horizon (yrs)", "regime": "Period",
            "mean_tau_ps": "Tau (real-time)", "mean_tau_fin": "Tau (finalized ceiling)",
            "mean_precision@10_ps": "P@10 (real-time)",
            "mean_precision@10_fin": "P@10 (finalized)"})
        tv["Period"] = (tv["Period"].str.replace("_", " ")
                        .str.replace("pre covid", "Pre-COVID")
                        .str.replace("shock", "Shock (2020–22)")
                        .str.replace("normalization", "Normalization")
                        .str.replace("POOLED", "All periods"))
        tv = tv[["Horizon (yrs)", "Period", "Tau (real-time)",
                 "Tau (finalized ceiling)", "P@10 (real-time)", "P@10 (finalized)"]]
        st.dataframe(
            tv.style.format({"Tau (real-time)": "{:.2f}",
                             "Tau (finalized ceiling)": "{:.2f}",
                             "P@10 (real-time)": "{:.0%}", "P@10 (finalized)": "{:.0%}",
                             "Horizon (yrs)": "{:.0f}"})
              .set_properties(subset=["Tau (real-time)", "Tau (finalized ceiling)"],
                              **{"font-variant-numeric": "tabular-nums",
                                 "text-align": "right"}),
            hide_index=True, use_container_width=True,
            column_config={
                "Horizon (yrs)": st.column_config.NumberColumn(
                    help="How many years ahead the prediction looks. 3 years is the "
                         "real target; 1 year is shown as a contrast."),
                "Tau (real-time)": st.column_config.TextColumn(
                    help="Agreement with the rent growth that followed, using only "
                         "data a user could actually have had at the time."),
                "Tau (finalized ceiling)": st.column_config.TextColumn(
                    help="The same agreement score using the complete revised data; "
                         "a best-case ceiling no live user ever had."),
                "P@10 (real-time)": st.column_config.TextColumn(
                    help="Of the 10 markets the screen ranked highest, the share that "
                         "landed in the top quarter by actual rent growth, using "
                         "real-time data."),
                "P@10 (finalized)": st.column_config.TextColumn(
                    help="The same top-10 hit rate using finalized data.")})
    theme.caption("Real-time numbers come from the pseudo-nowcast test (current data "
                  "vintages stand in for true unrevised prints, a disclosed "
                  "simplification). One-year results are a contrast, not the target: "
                  "the screen is built for the three-year horizon.")

with st.expander("How sure are we? The uncertainty behind the averages"):
    tu_path = config.PROCESSED_DIR / "temporal_uncertainty.csv"
    if tu_path.exists():
        tu = pd.read_csv(tu_path).iloc[0]
        st.markdown(f"""
- **The primary uncertainty is which market regime a window lands in.** Across the
  {int(tu['win3_n'])} observed 3-year windows, tau ranged from **{tu['win3_min']:+.2f}
  to {tu['win3_max']:+.2f}**; calm windows sat near the top of that range, shock
  windows near the bottom. No pooled average conveys that spread.
- **No single window drives the pooled result**: removing any one window moves the
  pooled 3-year tau only between **{tu['jk3_min']:.2f} and {tu['jk3_max']:.2f}**.
- **Neighboring markets move together**, so the analysis was re-run treating whole
  states as the unit of chance ({int(tu['n_states'])} states): the pooled tau's 95%
  interval widens to **[{tu['state_tau_lo']:.2f}, {tu['state_tau_hi']:.2f}]**, and the
  edge over equal weighting
  {"**survives**" if bool(tu['eq_edge_survives_state_cluster']) else "**does not survive**"}
  that stricter test.
- Narrow pooled intervals reported elsewhere capture **ranking uncertainty only**:
  they say which metros, conditional on the six windows history happened to provide,
  and are silent about what the next regime does.""")

st.markdown("Next: [back to the key findings](home).")

theme.page_footer()
