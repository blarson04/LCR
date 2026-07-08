"""
2024 vintage vs 2025 screen: answers one question: how does the current
(2025, proxied-input) screen differ from the fully validated 2024 vintage?

Both editions passed pre-registered validation gates; differences mix real
one-year market change with the proxied inputs' added uncertainty.
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

st.markdown("# 2024 vintage vs 2025 screen")
theme.caption("The fully finalized 2024 vintage (a 2024→2027 forecast) beside the current "
              "2025 screen (a 2025→2028 forecast on preliminary inputs; same model). "
              "Differences mix real one-year market change with the proxied data's added "
              "uncertainty; read big moves as directional, not precise.")
st.markdown(theme.badge(True, "Validated 2025 screen · proxied inputs"),
            unsafe_allow_html=True)
st.markdown(
    "<div class='cap' style='margin-top:.5rem'><b>How much of a move is noise?</b> The "
    "2025 configuration was tested on history where the truth is known: it <b>passed its "
    "pre-registered validation gate</b>, keeping 96.6% of the finalized model's signal, "
    f"and its top-10 matched the finalized top-10 on <b>{d['overlap_mean']:.1f} of 10</b> "
    "names on average (as few as 5/10 in shock-era years, when preliminary data is least "
    "reliable). Two earlier configurations failed the same gate and were published as "
    "negative results; see Track record.</div>", unsafe_allow_html=True)
st.write("")

base = d["vint_rank"] if d.get("has_vintage") else d["acc_rank"]
base_year = data.VINTAGE_YEAR if d.get("has_vintage") else data.SCORE_YEAR
val = base[["cbsa_code", "cbsa_title", "rank"]].rename(columns={"rank": "acc"})
spec = d["spec_rank"][["cbsa_code", "rank"]].rename(columns={"rank": "spec"})
cmp = val.merge(spec, on="cbsa_code")
cmp["move"] = cmp["acc"] - cmp["spec"]   # + = rose in the 2025 screen

c1, c2 = st.columns(2, gap="large")


def _top10(col, title, key):
    col.markdown(f"### {title}")
    for _, r in cmp.sort_values(key).head(10).iterrows():
        col.markdown(
            f"<div style='padding:.28rem 0;border-bottom:1px solid {theme.LINE};font-size:14px'>"
            f"<span style='color:{theme.MUTED};display:inline-block;width:1.6rem'>"
            f"{int(r[key])}</span>{r['cbsa_title'].split(',')[0][:28]}</div>",
            unsafe_allow_html=True)


_top10(c1, f"{base_year} vintage (fully validated)", "acc")
_top10(c2, "2025 screen (validated proxies)", "spec")

st.markdown("## Every market")
score_corr = float(pd.concat([
    base[["cbsa_code", "score"]].rename(columns={"score": "a"}).set_index("cbsa_code"),
    d["spec_rank"][["cbsa_code", "score"]].rename(columns={"score": "b"}).set_index("cbsa_code")],
    axis=1).dropna().corr().iloc[0, 1]) if "score" in base.columns else float("nan")
theme.caption(f"Move = change in rank from the {base_year} vintage to the 2025 screen "
              "(positive = rose). Moves inside a market's rank range are noise. The two "
              f"editions' underlying scores agree closely (correlation {score_corr:.2f}); "
              "most rank movement is compression, not disagreement: in the middle of the "
              "table one rank is worth well under a hundredth of a score point, so a "
              "small real change moves a market many places. What genuinely changes "
              "between years is whose jobs and incomes grew fastest; the structural "
              "measures (migration, building, affordability) barely move. Even between "
              "two fully finalized years the top 10 has historically kept only 1 to 6 of "
              "its names. That is exactly why every rank ships with a range.")
tbl = cmp.sort_values("acc")[["cbsa_title", "acc", "spec", "move"]].rename(columns={
    "cbsa_title": "Metro", "acc": f"{base_year} vintage", "spec": "2025 screen",
    "move": "Move"})
st.dataframe(
    tbl.style.format({f"{base_year} vintage": "{:.0f}", "2025 screen": "{:.0f}",
                      "Move": "{:+.0f}"})
       .map(lambda v: f"color:{theme.POS}" if v > 0 else (f"color:{theme.NEG}" if v < 0 else ""),
            subset=["Move"])
       .set_properties(subset=["Move", f"{base_year} vintage", "2025 screen"],
                       **{"font-variant-numeric": "tabular-nums", "text-align": "right"})
       .set_properties(subset=["Metro"], **{"font-weight": "500"}),
    hide_index=True, use_container_width=True, height=480,
    column_config={
        f"{base_year} vintage": st.column_config.TextColumn(
            help="Rank in the fully validated vintage edition (1 = best)."),
        "2025 screen": st.column_config.TextColumn(
            help="Rank in the current screen built on preliminary 2025 inputs."),
        "Move": st.column_config.TextColumn(
            help="Rank change between the two editions; positive means the market "
                 "rose in the 2025 screen. Small moves are noise.")})

theme.page_footer()
