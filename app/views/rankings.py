"""
Rankings: answers one question: where does every market stand?

The map, then the full table with tiers and rank ranges as the headline
objects. The tier machinery and the rank-movement explainer live in
expanders (v4 rebuild).
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
show_change = bool(ed.get("vintage")) and len(d["prior_rank"]) > 0
if show_change:
    rank = rank.merge(d["prior_rank"], on="cbsa_code", how="left")

# ---- Header -----------------------------------------------------------------
theme.eyebrow("Multifamily research · the report")
st.markdown("# Full rankings")
theme.caption(
    f"All {len(rank)} markets in the {ed['horizon']} screen, with a tier and a rank "
    "range for each: a screen, not a precise ordering.")
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
if not ed["provisional"]:
    flag_on = d["nat_growth"] > config.REGIME_FLAG_THRESHOLD
    theme.caption(
        (f"Elevated-uncertainty flag: national rent growth in {ed['year']} was "
         f"{d['nat_growth']:+.1%}, above the published rule; in the two years this "
         f"flag fired historically (2021–22), the screen's accuracy broke down."
         if flag_on else
         f"Conditions in the {ed['year']} scoring year looked typical: national rent "
         f"growth {d['nat_growth']:+.1%}, under the published uncertainty-flag rule "
         f"(it fires only in the two years the screen's accuracy broke)."))
st.write("")

# ---- The map ----------------------------------------------------------------
mp = rank.merge(d["coords"], on="cbsa_code", how="left")
fig = px.scatter_geo(
    mp, lat="lat", lon="lon", color="score", scope="usa",
    hover_name="cbsa_title", size=[8] * len(mp), size_max=12,
    color_continuous_scale=theme.SEQ_SCALE,
    custom_data=["rank", "score", "strength"])
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
              f"{top3[2]} round out the top three.")

# ---- The table --------------------------------------------------------------
st.markdown("## Every market")
has_tiers = ("tier" in rank.columns) and (rank["tier"].fillna("") != "").any()
if has_tiers:
    n_lead = int((rank["tier"] == "Leading cluster").sum())
    theme.caption(
        f"Markets in the same tier are peers, not an ordering; {n_lead} sit in the "
        "leading cluster. How the tiers, ranges, and edition-to-edition moves work: "
        "the notes below the table.")

n_total = data.N_IND
cols = {
    "Rank": [f"{int(r['rank'])} ({int(r['rank_lo'])}–{int(r['rank_hi'])})"
             for _, r in rank.iterrows()],
    **({"Tier": rank["tier"]} if has_tiers else {}),
    "Metro": rank["cbsa_title"],
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
st.dataframe(styler, hide_index=True, use_container_width=True, height=560,
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
theme.caption(f"Column headers explain each field on hover. "
              + (f"{n_short} markets are missing a measure at the source and take a "
                 f"neutral fill; lean on their ranges. " if n_short else "")
              + (f"This ranking is also supported one year further out "
                 f"({ed['year']}→{ed['year']+4}); beyond that the data cannot validate."
                 if ed.get("vintage") else ""))

with st.expander("How the tiers and rank ranges are built"):
    theme.caption(
        "Single ranks overstate precision. The two fastest-moving inputs (job growth "
        "and income growth) agree only weakly between editions, so each market's rank "
        "is re-computed 1,000 times with those two inputs jittered by their measured "
        "noise; the range is where the rank lands 90% of the time, and the tier bands "
        "the typical rank. The tier rule is fixed across editions: a market joins the "
        "Leading cluster when its range reaches the top 10 and its typical rank sits "
        "in the top quarter; Strong, Mid, Weak, and Lagging band the rest.")
    theme.caption(
        "This interval captures input-measurement noise only, not model error; the "
        "accuracy statement is the walk-forward record on Track record. A separate "
        "weight-sensitivity range (how far ranks move under alternative reasonable "
        "weightings) tells the same story: exact ranks are soft, tiers are stable.")

with st.expander("Why ranks move between editions"):
    theme.caption(
        "Rank moves between editions mix one real year of market change with "
        "measurement noise in the fast-moving inputs; most movement is compression in "
        "the crowded middle of the table, where a tiny score change moves a market "
        "many places. Even two fully finalized years historically keep only 1 to 6 of "
        "the same top-10 names, so turnover is normal, not a signal. A tested "
        "smoothing fix (averaging three years of the noisy inputs) cut the churn but "
        "reliably cost accuracy, so it was rejected and published as a negative "
        "result; the ranges above are the honest answer. Side-by-side editions: the "
        "expander on Home.")

with st.expander("Advanced view: how each score breaks down"):
    theme.caption("Contribution of each theme to the composite score, in standardized "
                  "units (0 = the average market that year; positive helps, negative "
                  "hurts).")
    adv = rank[["rank", "cbsa_title", "score", "bucket_Demand", "bucket_Supply",
                "bucket_Affordability", "bucket_Momentum", "bucket_Resilience"]].rename(
        columns={"rank": "Rank", "cbsa_title": "Metro", "score": "Score",
                 "bucket_Demand": "Demand", "bucket_Supply": "Supply",
                 "bucket_Affordability": "Affordability", "bucket_Momentum": "Momentum",
                 "bucket_Resilience": "Resilience"})
    num_cols = ["Score", "Demand", "Supply", "Affordability", "Momentum", "Resilience"]
    _theme_help = {b: (f"How much the {b} theme adds to or subtracts from this "
                       f"market's composite score. 0 means the theme neither helps "
                       f"nor hurts; positive helps, negative hurts.")
                   for b in ["Demand", "Supply", "Affordability", "Momentum",
                             "Resilience"]}
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

st.markdown("Next: [pick a market to explore](metro), or "
            "[how the score works](how_it_works).")

theme.page_footer()
