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
# Change vs the frozen prior edition (only meaningful for the vintage screen).
show_change = bool(ed.get("vintage")) and len(d["prior_rank"]) > 0
if show_change:
    rank = rank.merge(d["prior_rank"], on="cbsa_code", how="left")

# ---- Header -----------------------------------------------------------------
theme.eyebrow("Multifamily research · the report")
st.markdown("# Full rankings")
if ed.get("vintage"):
    theme.caption(
        f"Where all {len(rank)} markets stand: a {ed['horizon']} screen scored on "
        f"{ed['year']} data, the newest vintage validated for publication (see Track "
        f"record).")
else:
    theme.caption(
        f"The {len(rank)} largest US metros ranked by fundamentals that historically precede "
        f"rent growth: a {ed['horizon']} screen scored on "
        + ("preliminary data for the current year." if ed["provisional"]
           else f"{ed['year']} fundamentals, the latest finalized vintage (slow federal "
                f"inputs mean much of its forecast window has already elapsed)."))
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
if ed.get("vintage"):
    theme.caption(f"This ranking is also supported one year further out "
                  f"({ed['year']}→{ed['year']+4}); the 4-year view backtested slightly "
                  f"stronger. Beyond that the data cannot validate.")

if not ed["provisional"]:
    # Ex-ante rule only (v3-P6): no hindsight regime labels feed the flag.
    if d["nat_growth"] > config.REGIME_FLAG_THRESHOLD:
        theme.caption(f"Elevated-uncertainty flag: national rent growth in {ed['year']} was "
                      f"{d['nat_growth']:+.1%}, above the "
                      f"{config.REGIME_FLAG_THRESHOLD:.1%} rule; in the two years this flag "
                      f"fired historically (2021–22), the screen's accuracy broke down. It "
                      f"describes the vintage year, not today.")
    else:
        theme.caption(f"Conditions in the {ed['year']} scoring year looked typical: national "
                      f"rent growth {d['nat_growth']:+.1%}, under the "
                      f"{config.REGIME_FLAG_THRESHOLD:.1%} uncertainty-flag rule (a published "
                      f"rule that fires only in the two years the screen's accuracy broke). "
                      f"It describes the vintage year, not today.")
st.write("")

# ---- Headline: the map --------------------------------------------------------
mp = rank.merge(d["coords"], on="cbsa_code", how="left")
mp["strength_txt"] = mp["strength"]
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
theme.caption(f"Darker green = stronger fundamentals. {top3[0]} leads; {top3[1]} and "
              f"{top3[2]} round out the top three. Every market's rank, range, and "
              f"drivers are in the table below.")

# ---- Tiers: the headline object (P2) ------------------------------------------
has_tiers = ("tier" in rank.columns) and (rank["tier"].fillna("") != "").any()
if has_tiers:
    st.markdown("## The tiers")
    theme.caption(
        "Single ranks overstate precision, so each market gets a 90% rank range and a "
        "tier. Markets in the same tier are peers, not an ordering.")
    tier_rows = ""
    for t in data.TIER_ORDER:
        members = rank[rank["tier"] == t]
        if not len(members):
            continue
        if t == "Leading cluster":
            names = ", ".join(m.split(",")[0] for m in members["cbsa_title"])
            detail = names
        else:
            first3 = ", ".join(m.split(",")[0] for m in members.head(3)["cbsa_title"])
            detail = f"{first3}, …" if len(members) > 3 else first3
        tier_rows += (
            f"<div class='rowline'>"
            f"<span style='font-weight:500'>{t}</span>"
            f"<span style='color:{theme.MUTED};float:right;font-variant-numeric:tabular-nums'>"
            f"{len(members)} markets</span>"
            f"<div class='cap'>{detail}</div></div>")
    st.markdown(tier_rows, unsafe_allow_html=True)
    lead_n = int((rank["tier"] == "Leading cluster").sum())
    theme.caption(f"The tier rule is fixed across editions: a market joins the Leading "
                  f"cluster when its range reaches the top 10 and its typical rank sits "
                  f"in the top quarter. {lead_n} markets currently qualify.")

# ---- Full table (progressive disclosure) -------------------------------------
with st.expander(f"See all {len(rank)} markets"):
    n_total = data.N_IND
    cols = {
        "Rank": [f"{int(r['rank'])} ({int(r['rank_lo'])}–{int(r['rank_hi'])})"
                 for _, r in rank.iterrows()],
        "Metro": rank["cbsa_title"],
        **({"Tier": rank["tier"]} if has_tiers else {}),
        "Score": rank["score"],
        "Top strength": rank["strength"],
        "Top drag": rank["drag"],
        "Measures": [f"{int(n)} of {n_total}" for n in rank["n_indicators"]],
    }
    if show_change:
        def _chg(r):
            if pd.isna(r["prior_rank"]):
                return "new"
            delta = int(r["prior_rank"]) - int(r["rank"])
            return f"{delta:+d}" if delta else "0"
        cols["Vs 2023"] = rank.apply(_chg, axis=1)
    tbl = pd.DataFrame(cols)
    styler = (tbl.style
              .format({"Score": "{:+.2f}"})
              .map(lambda v: f"color:{theme.POS}" if v >= 0 else f"color:{theme.NEG}",
                   subset=["Score"])
              .set_properties(subset=["Score", "Measures"],
                              **{"font-variant-numeric": "tabular-nums",
                                 "text-align": "right"})
              .set_properties(subset=["Metro"], **{"font-weight": "500"}))
    if show_change:
        styler = styler.set_properties(subset=["Vs 2023"],
                                       **{"font-variant-numeric": "tabular-nums",
                                          "text-align": "right"})
    st.dataframe(styler, hide_index=True, use_container_width=True, height=520,
                 column_config={
                     "Rank": st.column_config.TextColumn(
                         help="This market's rank out of all markets. The range in "
                              "parentheses is the 90% range once measurement noise in "
                              "the two fast-moving inputs (job and income growth) is "
                              "accounted for; treat markets with overlapping ranges "
                              "as roughly tied."),
                     "Tier": st.column_config.TextColumn(
                         help="The tier is the honest headline: markets in the same "
                              "tier are peers on these fundamentals, and the exact "
                              "ordering within a tier is inside the noise."),
                     "Score": st.column_config.TextColumn(
                         help="The composite score: all eight measures combined. 0 is "
                              "the average market that year; higher is stronger "
                              "fundamentals for future rent growth."),
                     "Top strength": st.column_config.TextColumn(
                         help="The theme that lifts this market's score the most. "
                              "'Broadly average' means no theme helps it meaningfully."),
                     "Top drag": st.column_config.TextColumn(
                         help="The theme that pulls this market's score down the most. "
                              "'No material drag' means nothing pulls it down "
                              "meaningfully; strong markets often have none."),
                     "Measures": st.column_config.TextColumn(
                         help="How many of the eight measures had data for this market. "
                              "A missing measure takes a neutral (exactly average) "
                              "value, which can flatter or understate the market, so "
                              "read a short-count market's exact rank loosely."),
                     "Vs 2023": st.column_config.TextColumn(
                         help="Rank change since the frozen 2023 edition; positive "
                              "means the market moved up.")})
    n_short = int((rank["n_indicators"] < n_total).sum())
    change_note = ("The 'vs 2023' column compares against the frozen prior edition; a "
                   "move inside a market's rank range is noise, not a trend. "
                   if show_change else "")
    short_note = (f" {n_short} markets are missing a measure at the source and take a "
                  f"neutral fill; lean on their ranges."
                  if n_short else "")
    theme.caption(f"Treat this as a screen, not a precise ordering: ranges are 90% "
                  f"intervals under measured input noise. {change_note}"
                  f"Column headers explain each field on hover.{short_note}")

# ---- Diverging bars: every market against the average -------------------------
with st.expander("Every market against the average"):
    theme.caption("Composite score relative to the average market that year (zero line). "
                  "The default view shows the top and bottom 25.")
    show_all = st.toggle(f"Show all {len(rank)} markets", key="diverging_all")
    if show_all:
        sub = rank
        labels = [f"{int(r['rank'])}  {r['cbsa_title'].split(',')[0][:24]}"
                  for _, r in sub.iterrows()]
        vals = sub["score"].tolist()
    else:
        head, tail = rank.head(25), rank.tail(25)
        gap_label = f"(…{len(rank) - 50} markets in between…)"
        labels = ([f"{int(r['rank'])}  {r['cbsa_title'].split(',')[0][:24]}"
                   for _, r in head.iterrows()] + [gap_label]
                  + [f"{int(r['rank'])}  {r['cbsa_title'].split(',')[0][:24]}"
                     for _, r in tail.iterrows()])
        vals = head["score"].tolist() + [None] + tail["score"].tolist()
    colors = [(theme.POS if (v or 0) >= 0 else theme.NEG) for v in vals]
    figd = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h", marker_color=colors, marker_line_width=0,
        hovertemplate="%{y}<br>score %{x:+.2f}<extra></extra>"))
    figd.update_yaxes(autorange="reversed", showgrid=False,
                      tickfont=dict(size=11, color=theme.MUTED))
    height = 24 * len(labels) + 60
    figd = theme.style_fig(figd, height)
    figd.update_xaxes(showgrid=True, gridcolor=theme.LINE, zeroline=True,
                      zerolinecolor=theme.MUTED, zerolinewidth=1,
                      title="Composite score (0 = the average market)")
    figd.update_yaxes(showgrid=False)
    st.plotly_chart(figd, use_container_width=True)
    lead, trail = rank.iloc[0], rank.iloc[-1]
    theme.caption(f"{lead['cbsa_title'].split(',')[0]} leads at {lead['score']:+.2f}; "
                  f"{trail['cbsa_title'].split(',')[0]} trails at {trail['score']:+.2f}. "
                  f"The spread matters more than any single value.")

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
    _theme_help = {b: (f"How much the {b} theme adds to or subtracts from this market's "
                       f"composite score. 0 means the theme neither helps nor hurts; "
                       f"positive helps, negative hurts.")
                   for b in ["Demand", "Supply", "Affordability", "Momentum", "Resilience"]}
    st.dataframe(
        adv.style.format({c: "{:+.2f}" for c in num_cols})
           .set_properties(subset=num_cols, **{"font-variant-numeric": "tabular-nums",
                                               "text-align": "right"})
           .set_properties(subset=["Metro"], **{"font-weight": "500"}),
        hide_index=True, use_container_width=True, height=420,
        column_config={
            "Rank": st.column_config.NumberColumn(
                help="This market's rank out of all markets (1 = best)."),
            "Score": st.column_config.TextColumn(
                help="The composite score: the five theme contributions summed. 0 is "
                     "the average market that year."),
            **{b: st.column_config.TextColumn(help=h) for b, h in _theme_help.items()}})

theme.page_footer()
