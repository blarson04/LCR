"""
Accurate vs speculative — answers one question: how does the provisional 2025
view differ from the finalized 2023 ranking?
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

theme.inject_css()
d = data.load()

st.markdown("# Accurate vs speculative")
theme.caption("The finalized 2023 ranking beside the provisional 2025 screen. Differences "
              "mix real market change with the provisional data's added uncertainty — read "
              "big moves as directional, not precise.")
st.markdown(theme.badge(provisional=True), unsafe_allow_html=True)
st.write("")

val = d["acc_rank"][["cbsa_code", "cbsa_title", "rank"]].rename(columns={"rank": "acc"})
spec = d["spec_rank"][["cbsa_code", "rank"]].rename(columns={"rank": "spec"})
cmp = val.merge(spec, on="cbsa_code")
cmp["move"] = cmp["acc"] - cmp["spec"]   # + = rose in the provisional screen

c1, c2 = st.columns(2, gap="large")


def _top10(col, title, key):
    col.markdown(f"### {title}")
    for _, r in cmp.sort_values(key).head(10).iterrows():
        col.markdown(
            f"<div style='padding:.28rem 0;border-bottom:1px solid {theme.LINE};font-size:14px'>"
            f"<span style='color:{theme.MUTED};display:inline-block;width:1.6rem'>"
            f"{int(r[key])}</span>{r['cbsa_title'].split(',')[0][:28]}</div>",
            unsafe_allow_html=True)


_top10(c1, "Accurate — finalized 2023", "acc")
_top10(c2, "Speculative — provisional 2025", "spec")

st.markdown("## Every market")
theme.caption("Move = change in rank from the finalized to the provisional screen "
              "(positive = rose).")
tbl = cmp.sort_values("acc")[["cbsa_title", "acc", "spec", "move"]].rename(columns={
    "cbsa_title": "Metro", "acc": "Accurate (2023)", "spec": "Speculative (2025)",
    "move": "Move"})
st.dataframe(
    tbl.style.format({"Accurate (2023)": "{:.0f}", "Speculative (2025)": "{:.0f}",
                      "Move": "{:+.0f}"})
       .map(lambda v: f"color:{theme.POS}" if v > 0 else (f"color:{theme.NEG}" if v < 0 else ""),
            subset=["Move"])
       .set_properties(subset=["Move", "Accurate (2023)", "Speculative (2025)"],
                       **{"font-variant-numeric": "tabular-nums", "text-align": "right"})
       .set_properties(subset=["Metro"], **{"font-weight": "500"}),
    hide_index=True, use_container_width=True, height=480)

theme.page_footer()
