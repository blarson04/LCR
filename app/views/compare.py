"""
Compare markets: answers one question: how do these markets stack up?
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ui import data, theme  # noqa: E402

theme.inject_css()
d = data.load()
ed = data.edition(d)
rank = ed["rank"]

st.markdown("# Compare markets")
theme.caption("Two or three markets side by side: where each stands on every measure, "
              "and which themes drive the difference.")
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
st.write("")

default2 = list(rank.sort_values("rank")["cbsa_title"].head(2))
picks = st.multiselect("Markets", list(rank.sort_values("cbsa_title")["cbsa_title"]),
                       default=default2, max_selections=3, label_visibility="collapsed")

if len(picks) < 2:
    st.info("Choose at least two markets to compare.")
else:
    cols = st.columns(len(picks))
    codes = {}
    for i, mt in enumerate(picks):
        r = rank[rank.cbsa_title == mt].iloc[0]
        codes[mt] = r["cbsa_code"]
        cols[i].metric(mt.split(",")[0],
                       f"{int(r['rank'])} ({int(r['rank_lo'])}–{int(r['rank_hi'])})",
                       help=f"Score {r['score']:+.2f}. Range reflects statistical "
                            f"uncertainty in the score.")

    st.markdown("## Measure by measure")
    theme.caption("Percentile across all markets (100 = best on that measure; higher is "
                  "always better).")
    comp = pd.DataFrame({"Measure": [data.PRETTY[k] for k in data.INDICATORS]})
    names = []
    for mt, code in codes.items():
        nm = mt.split(",")[0]
        names.append(nm)
        comp[nm] = [ed["pct"][k].get(code, float("nan")) for k in data.INDICATORS]
    st.dataframe(
        comp.style.set_properties(subset=["Measure"], **{"font-weight": "500"}),
        hide_index=True, use_container_width=True,
        column_config={nm: st.column_config.ProgressColumn(min_value=0, max_value=100,
                                                           format="%.0f") for nm in names})

    st.markdown("## What drives each score")
    bard = [{"Market": mt.split(",")[0], "Theme": b,
             "Contribution": rank[rank.cbsa_title == mt].iloc[0][f"bucket_{b}"]}
            for mt in picks for b in data.BUCKETS]
    palette = [theme.ACCENT] + theme.GRAY_SERIES
    figb = px.bar(pd.DataFrame(bard), x="Theme", y="Contribution", color="Market",
                  barmode="group", color_discrete_sequence=palette[:len(picks)])
    figb.update_yaxes(title="Contribution to score")
    figb.update_xaxes(title=None)
    figb = theme.style_fig(figb, 320)
    figb.update_layout(showlegend=True, legend=dict(orientation="h", y=1.12, title=None))
    st.plotly_chart(figb, use_container_width=True)
    lead = max(picks, key=lambda mt: rank[rank.cbsa_title == mt].iloc[0]["score"]).split(",")[0]
    theme.caption(f"Bars above zero help a market's score; below zero hurt it. "
                  f"{lead} has the strongest overall fundamentals of this group.")

theme.page_footer()
