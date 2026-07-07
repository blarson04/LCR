"""
Rankings: answers one question: which markets look strongest?

Headline view = map + top-10 list (the point in 10 seconds). The full table
and the numeric breakdown live behind expanders (progressive disclosure).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ui import data, theme  # noqa: E402
import config               # noqa: E402

theme.inject_css()
d = data.load()
ed = data.edition(d)
rank = ed["rank"].sort_values("rank").reset_index(drop=True)
rank[["strength", "drag"]] = rank.apply(
    lambda r: pd.Series(data.strength_drag(r)), axis=1)

# ---- Header -----------------------------------------------------------------
st.markdown("# Market rankings")
if ed.get("vintage"):
    theme.caption(
        f"The {len(rank)} largest US metros ranked by fundamentals that historically precede "
        f"rent growth: a {ed['horizon']} screen scored on {ed['year']} data, the newest "
        f"vintage validated for publication (its configuration passed a pre-registered gate "
        f"at 95.5% signal retention; see Track record).")
else:
    theme.caption(
        f"The {len(rank)} largest US metros ranked by fundamentals that historically precede "
        f"rent growth: a {ed['horizon']} screen scored on "
        + ("preliminary data for the current year." if ed["provisional"]
           else f"{ed['year']} fundamentals, the latest finalized vintage (the slowest federal "
                f"inputs publish about two years late, so much of the {ed['horizon']} forecast "
                f"window has already elapsed)."))
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
if ed.get("vintage"):
    theme.caption(f"Extended horizon: this same ranking is also supported one year further "
                  f"out ({ed['year']}→{ed['year']+4}). In backtests the 4-year view was, if "
                  f"anything, stronger (top-10 edge +8.4 points of rent growth vs +6.0 at "
                  f"3 years). Beyond that we do not publish: the data cannot validate it.")

if not ed["provisional"]:
    # Ex-ante rule only (v3-P6): no hindsight regime labels feed the flag.
    if d["nat_growth"] > config.REGIME_FLAG_THRESHOLD:
        theme.caption(f"Elevated-uncertainty flag: national rent growth in the {ed['year']} "
                      f"scoring year was {d['nat_growth']:+.1%}, above the "
                      f"{config.REGIME_FLAG_THRESHOLD:.1%} rule. In the two historical years "
                      f"this flag fired (2021–22), the screen's accuracy broke down. This "
                      f"describes the vintage year, not today.")
    else:
        theme.caption(f"Conditions in the {ed['year']} scoring year looked typical (national "
                      f"rent growth {d['nat_growth']:+.1%}, under the "
                      f"{config.REGIME_FLAG_THRESHOLD:.1%} flag rule), inside the framework's "
                      f"validated range. This describes the vintage year, not today. "
                      f"Flag rule, published and tested on history: it fires only in 2021–22 ("
                      f"exactly the windows where accuracy broke) with no false alarms; it did "
                      f"not catch 2020, a shock that never moved rents.")
st.write("")

# ---- Headline: map + top 10 --------------------------------------------------
col_map, col_top = st.columns([7, 3], gap="large")

with col_map:
    mp = rank.merge(d["coords"], on="cbsa_code", how="left")
    mp["strength_txt"] = mp["strength"].where(mp["strength"] != "–", "Broadly average")
    fig = px.scatter_geo(
        mp, lat="lat", lon="lon", color="score", scope="usa",
        hover_name="cbsa_title", size=[8] * len(mp), size_max=12,
        color_continuous_scale=theme.SEQ_SCALE,
        custom_data=["rank", "score", "strength_txt"])
    fig.update_traces(
        marker=dict(line=dict(width=0.6, color=theme.MAP_BORDER)),
        hovertemplate="<b>%{hovertext}</b><br>Rank %{customdata[0]} · score "
                      "%{customdata[1]:+.2f}<br>%{customdata[2]}<extra></extra>")
    fig.update_geos(showland=True, landcolor=theme.MAP_LAND, showlakes=False,
                    subunitcolor=theme.MAP_BORDER, countrycolor=theme.MAP_BORDER,
                    coastlinecolor=theme.MAP_BORDER, bgcolor="rgba(0,0,0,0)", showframe=False)
    fig.add_trace(go.Scattergeo(
        lat=[v[0] for v in data.STATE_CENTROIDS.values()],
        lon=[v[1] for v in data.STATE_CENTROIDS.values()],
        text=list(data.STATE_CENTROIDS), mode="text",
        textfont=dict(family="Inter, sans-serif", size=9, color=theme.MUTED),
        hoverinfo="skip", showlegend=False))
    fig.update_layout(coloraxis_colorbar=dict(title="Score", thickness=10, len=0.6,
                                              tickfont=dict(color=theme.MUTED)))
    st.plotly_chart(theme.style_fig(fig, 470), use_container_width=True)
    top3 = [t.split(",")[0].split("-")[0] for t in rank.head(3)["cbsa_title"]]
    theme.caption(f"Darker green = stronger fundamentals. {top3[0]} leads the {ed['year']} "
                  f"screen; {top3[1]} and {top3[2]} round out the top three.")

with col_top:
    st.markdown("### Top 10")
    rows_html = ""
    for _, r in rank.head(10).iterrows():
        color = theme.POS if r["score"] >= 0 else theme.NEG
        rows_html += (
            f"<div style='padding:.42rem 0;border-bottom:1px solid {theme.LINE}'>"
            f"<span style='color:{theme.MUTED};display:inline-block;width:1.6rem'>{int(r['rank'])}</span>"
            f"<span style='font-weight:500'>{r['cbsa_title'].split(',')[0][:26]}</span>"
            f"<span style='float:right;color:{color};font-variant-numeric:tabular-nums'>"
            f"{r['score']:+.2f}</span>"
            f"<div class='cap' style='margin-left:1.6rem'>{r['strength']}</div></div>")
    st.markdown(rows_html, unsafe_allow_html=True)

# ---- Full table (progressive disclosure) -------------------------------------
with st.expander(f"See all {len(rank)} markets"):
    tbl = pd.DataFrame({
        "Rank": [f"{int(r['rank'])} ({int(r['rank_lo'])}–{int(r['rank_hi'])})"
                 for _, r in rank.iterrows()],
        "Metro": rank["cbsa_title"],
        "Score": rank["score"],
        "Top strength": rank["strength"],
        "Top drag": rank["drag"],
    })
    styler = (tbl.style
              .format({"Score": "{:+.2f}"})
              .map(lambda v: f"color:{theme.POS}" if v >= 0 else f"color:{theme.NEG}",
                   subset=["Score"])
              .set_properties(subset=["Score"], **{"font-variant-numeric": "tabular-nums",
                                                   "text-align": "right"})
              .set_properties(subset=["Metro"], **{"font-weight": "500"}))
    st.dataframe(styler, hide_index=True, use_container_width=True, height=520,
                 column_config={"Rank": st.column_config.TextColumn(
                     help="Range reflects statistical uncertainty in the score.")})
    theme.caption("Rank ranges show the span across several reasonable model weightings; "
                  "treat this as a screen, not a precise ordering. Strength and drag are the "
                  "themes that helped or hurt each market's score the most.")

with st.expander("Advanced view: how each score breaks down"):
    theme.caption("Contribution of each theme to the composite score, in standardized units "
                  "(0 = the average market that year; positive helps, negative hurts).")
    adv = rank[["rank", "cbsa_title", "score", "bucket_Demand", "bucket_Supply",
                "bucket_Affordability", "bucket_Momentum", "bucket_Resilience"]].rename(
        columns={"rank": "Rank", "cbsa_title": "Metro", "score": "Score",
                 "bucket_Demand": "Demand", "bucket_Supply": "Supply",
                 "bucket_Affordability": "Affordability", "bucket_Momentum": "Momentum",
                 "bucket_Resilience": "Resilience"})
    num_cols = ["Score", "Demand", "Supply", "Affordability", "Momentum", "Resilience"]
    st.dataframe(
        adv.style.format({c: "{:+.2f}" for c in num_cols})
           .set_properties(subset=num_cols, **{"font-variant-numeric": "tabular-nums",
                                               "text-align": "right"})
           .set_properties(subset=["Metro"], **{"font-weight": "500"}),
        hide_index=True, use_container_width=True, height=420)

theme.page_footer()
