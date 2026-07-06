"""
Track record — answers one question: has this worked?
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ui import data, theme  # noqa: E402

theme.inject_css(reading=True)
d = data.load()

st.markdown("# Track record")
theme.caption("How the screen would have performed historically, and the frozen record of "
              "every published run.")
st.write("")

st.markdown("## Backtest — checked against what actually happened")
st.markdown(
    "Each year's ranking is compared with the rent growth that followed over the next three "
    "years (with one-year results as a contrast). Agreement is measured with weighted "
    "Kendall's tau — a rank-agreement score from −1 to +1, where 0 means no relationship — "
    "and precision@10, the share of the top-10 picks that landed in the top quarter of "
    "markets.")
bt = d["backtest"].rename(columns={
    "horizon": "Horizon (yrs)", "regime": "Period", "n_windows": "Windows",
    "mean_tau": "Tau", "mean_precision@10": "Precision@10"})
bt["Period"] = (bt["Period"].str.replace("_", " ").str.replace("pre covid", "Pre-COVID")
                .str.replace("shock", "Shock (2020–22)")
                .str.replace("normalization", "Normalization")
                .str.replace("POOLED", "All periods"))
st.dataframe(
    bt.style.format({"Tau": "{:.2f}", "Precision@10": "{:.0%}", "Horizon (yrs)": "{:.0f}",
                     "Windows": "{:.0f}"})
      .set_properties(subset=["Tau", "Precision@10"],
                      **{"font-variant-numeric": "tabular-nums", "text-align": "right"}),
    hide_index=True, use_container_width=True)
theme.caption("Validation reflects normal market conditions; the framework underperforms in "
              "shocks. Rent history begins around 2015, so these windows overlap — read the "
              "results as directional evidence, not statistical proof.")

st.markdown("## The frozen record")
st.markdown(
    "Every published run is frozen with its scores, rankings, input data, and settings, and "
    "never edited. As real outcomes arrive, anyone can check the old calls against what "
    "happened — the record cannot be quietly rewritten.")
if len(d["registry"]):
    rt = d["registry"].rename(columns={
        "timestamp_utc": "Run (UTC)", "model_version": "Version", "score_year": "Year",
        "n_metros": "Markets", "top_metro": "Top-ranked market"})
    rt = rt[["Run (UTC)", "Version", "Year", "Markets", "Top-ranked market"]]
    st.dataframe(rt, hide_index=True, use_container_width=True)

st.markdown("## Honest limits")
st.markdown(
    "- The rent data measures asking rents, not signed leases.\n"
    "- No capital-markets data (sale prices, cap rates) — rent growth stands in for "
    "profitability.\n"
    "- Measure weights are set by judgment and tested, not statistically fitted.\n"
    "- In shock periods like 2020–22 the screen loses most of its edge; treat it as a "
    "screen, not a forecast.")

theme.page_footer()
