"""
Speculative outlook: answers one question: what does the newest, unvalidated
data suggest for 2026-2029?

Ships under the FAILED v0.5 gate's pre-committed consequence (decision-log
2026-07-21): everything speculative lives on THIS page, behind the warning:
the map, the full ranking, and an embedded explore-a-market section with the
same anatomy as the validated screen's. Nothing here carries the validated
label; the validated 2025-2028 screen stays primary.
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

NC = config.PROCESSED_DIR / "nowcast"
rank = pd.read_csv(NC / "midyear_2026_ranking.csv", dtype={"cbsa_code": str})
raw = (pd.read_csv(NC / "midyear_2026_raw.csv", dtype={"cbsa_code": str})
       .set_index("cbsa_code"))
norm = (pd.read_csv(NC / "midyear_2026_norm.csv", dtype={"cbsa_code": str})
        .set_index("cbsa_code"))
pct = norm[list(data.INDICATORS)].rank(pct=True) * 100
gate = pd.read_csv(NC / "gate2026_summary.csv").iloc[0]
acc = pd.read_csv(NC / "midyear_v06_accuracy.csv").iloc[0]
rank = rank.sort_values("rank").reset_index(drop=True)
rank[["strength", "drag"]] = rank.apply(
    lambda r: pd.Series(data.strength_drag(r)), axis=1)

theme.eyebrow("Multifamily research · the speculative outlook")
st.markdown("# 2026→2029 outlook")
theme.caption("The same frozen model run on data through May 2026. It exists because "
              "readers asked for the newest possible view; the warning below is why "
              "it is not the site's screen.")
st.markdown(theme.badge(True, "Speculative 2026→2029 outlook · failed validation"),
            unsafe_allow_html=True)

st.markdown(
    f"<div style='border:1.5px solid {theme.PROVISIONAL};border-radius:8px;"
    f"padding:.9rem 1.1rem;margin:.8rem 0;background:rgba(138,109,29,.06)'>"
    f"<div style='font-weight:600;color:{theme.PROVISIONAL}'>This screen has not "
    f"passed validation. Read every rank loosely.</div>"
    f"<div style='font-size:14px;margin-top:.35rem'>Tested on history the same way "
    f"as every published screen, this recipe keeps <b>{acc['retention']:.1%}</b> of "
    f"the finalized model's signal but matches the finalized top-10 on only "
    f"<b>{acc['mean_top10_overlap']:.1f} of 10</b> names (a validated screen needs "
    f"{gate['overlap_bar']:.0f}), falling to 3–4 of 10 in fast-moving years. An "
    f"earlier mid-year recipe failed its one-shot gate outright "
    f"({gate['retention']:.1%} and {gate['mean_top10_overlap']:.1f} of 10, on Track "
    f"record); this one adds a tested income estimate and is re-measured, not "
    f"re-gated. For decisions, use the validated 2025→2028 screen.</div></div>",
    unsafe_allow_html=True)

# ---- The map ----------------------------------------------------------------
mp = rank.merge(d["coords"], on="cbsa_code", how="left")
fig = px.scatter_geo(
    mp, lat="lat", lon="lon", color="score", scope="usa",
    hover_name="cbsa_title", size=[8] * len(mp), size_max=12,
    color_continuous_scale=theme.SEQ_SCALE,
    custom_data=["rank", "score", "strength"])
fig.update_traces(
    marker=dict(line=dict(width=0.6, color=theme.MAP_BORDER)),
    hovertemplate="<b>%{hovertext}</b><br>Speculative rank %{customdata[0]} · score "
                  "%{customdata[1]:+.2f}<br>%{customdata[2]}<extra></extra>")
fig.update_geos(showland=True, landcolor=theme.MAP_LAND, showlakes=False,
                subunitcolor=theme.MAP_BORDER, countrycolor=theme.MAP_BORDER,
                coastlinecolor=theme.MAP_BORDER, bgcolor="rgba(0,0,0,0)",
                showframe=False)
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
theme.caption(f"Darker green = stronger mid-year fundamentals, speculatively. "
              f"{top3[0]} leads; {top3[1]} and {top3[2]} follow. Same map, weaker "
              f"instrument: see the warning above.")

# ---- The ranking ------------------------------------------------------------
st.markdown("## The speculative ranking")
theme.caption("Why it is weaker than the main screen: rents, jobs, home values, and "
              "permits use only five months of 2026 data; migration is one year "
              "stale; and income growth is a state-level estimate (each metro takes "
              "its primary state's early-2026 income growth, a tested stand-in that "
              "agrees with finalized metro income about half the time by rank).")

tbl = pd.DataFrame({
    "Rank": rank["rank"].astype(int),
    "Metro": rank["cbsa_title"],
    "Score": rank["score"],
    "Top strength": rank["strength"],
    "Top drag": rank["drag"],
})
st.dataframe(
    tbl.style.format({"Score": "{:+.2f}"})
       .map(lambda v: f"color:{theme.POS}" if v >= 0 else f"color:{theme.NEG}",
            subset=["Score"])
       .set_properties(subset=["Score"], **{"font-variant-numeric": "tabular-nums",
                                            "text-align": "right"})
       .set_properties(subset=["Metro"], **{"font-weight": "500"}),
    hide_index=True, use_container_width=True, height=470,
    column_config={
        "Rank": st.column_config.NumberColumn(
            help="Rank out of all markets (1 = best) under the speculative mid-year "
                 "recipe. No rank range is shown because this configuration failed "
                 "validation; treat the ordering as indicative at best."),
        "Score": st.column_config.TextColumn(
            help="The composite score on mid-year data. 0 is the average market; "
                 "income growth is a state-level estimate for every market."),
        "Top strength": st.column_config.TextColumn(
            help="The theme lifting this market's speculative score the most."),
        "Top drag": st.column_config.TextColumn(
            help="The theme pulling this market's speculative score down the most.")})

# ---- Explore a market, speculatively ----------------------------------------
st.markdown("## Explore a market, speculatively")
theme.caption("The same anatomy as the validated Explore page, on mid-year data. "
              "Every number below inherits the warning at the top of this page.")

opts = rank.sort_values("cbsa_title")
titles = list(opts["cbsa_title"])
codes_sorted = [str(c) for c in opts["cbsa_code"]]
qp = st.query_params.get("metro")
metro = st.selectbox("Choose a market", titles,
                     index=codes_sorted.index(qp) if qp in codes_sorted else 0)
row = rank[rank["cbsa_title"] == metro].iloc[0]
code = row["cbsa_code"]
st.query_params["metro"] = str(code)

c1, c2 = st.columns(2)
c1.metric("Speculative rank", f"{int(row['rank'])}",
          help="This market's rank under the failed mid-year configuration "
               "(1 = best). No 90% range is computed for a configuration that "
               "failed validation; read the rank as indicative at best.")
c2.metric("Score", f"{row['score']:+.2f}",
          help="All eight measures combined on mid-year data (income is a "
               "state-level estimate). 0 is the average market; the distance from 0 "
               "matters more than the decimals.")
st.markdown(f"<div class='cap' style='margin:.6rem 0 0'>{data.why_sentence(row)}</div>",
            unsafe_allow_html=True)

pros, cons = [], []
for k in data.INDICATORS:
    p = pct[k].get(code, float("nan"))
    if pd.isna(p):
        continue
    if p >= 65:
        pros.append((data.OUTLOOK[k][0], p))
    elif p <= 35:
        cons.append((data.OUTLOOK[k][1], p))
pros = [t for t, _ in sorted(pros, key=lambda x: -x[1])][:5]
cons = [t for t, _ in sorted(cons, key=lambda x: x[1])][:5]

oc1, oc2 = st.columns(2)


def _list(col, title, items, color, empty):
    html = (f"<div style='background:{theme.SURFACE};border:1px solid {theme.LINE};"
            f"border-radius:8px;padding:.9rem 1.1rem;height:100%'>"
            f"<div style='font-weight:600;color:{color};margin-bottom:.4rem'>"
            f"{title}</div>")
    if items:
        html += "".join(f"<div style='font-size:14px;margin:.3rem 0'>{i}</div>"
                        for i in items)
    else:
        html += f"<div class='cap'>{empty}</div>"
    col.markdown(html + "</div>", unsafe_allow_html=True)


_list(oc1, "Strengths (mid-year read)", pros, theme.POS,
      "No standout strengths on mid-year data.")
_list(oc2, "Watch-outs (mid-year read)", cons, theme.NEG,
      "No major red flags on mid-year data.")

st.markdown("### The measures, mid-year")
rows_t, missing = [], []
for k in data.INDICATORS:
    val = raw[k].get(code, float("nan"))
    if k == "income_growth":
        rows_t.append({"Measure": data.PRETTY[k],
                       "Weight": f"{data.INDICATORS[k]['weight']*100:.0f}%",
                       "Value": ("–" if pd.isna(val)
                                 else data.FMT[k](val) + " (state estimate)"),
                       "Percentile": pct[k].get(code, float("nan"))})
        continue
    if pd.isna(val):
        missing.append(data.PRETTY[k].lower())
    rows_t.append({"Measure": data.PRETTY[k],
                   "Weight": f"{data.INDICATORS[k]['weight']*100:.0f}%",
                   "Value": "–" if pd.isna(val) else data.FMT[k](val),
                   "Percentile": pct[k].get(code, float("nan"))})
st.dataframe(
    pd.DataFrame(rows_t).style
      .set_properties(subset=["Measure"], **{"font-weight": "500"})
      .set_properties(subset=["Weight"], **{"font-variant-numeric": "tabular-nums",
                                            "text-align": "right"}),
    hide_index=True, use_container_width=True,
    column_config={
        "Weight": st.column_config.TextColumn(
            help="This measure's fixed share of the composite score, identical for "
                 "every market."),
        "Value": st.column_config.TextColumn(
            help="The measure in real-world units on data through May 2026 (permits "
                 "annualized from the year-to-date count; migration from the latest "
                 "Census estimate year)."),
        "Percentile": st.column_config.ProgressColumn(
            min_value=0, max_value=100, format="%.0f",
            help="Where this market stands among all markets on that measure, "
                 "direction already applied so higher is always better. Income is "
                 "a state-level estimate, so metros in the same state tie on it.")})
if missing:
    theme.caption(f"Data note: {', '.join(missing)} is unavailable for this market "
                  "and takes a neutral (average) fill, which can flatter or "
                  "understate it.")
theme.caption("Rent history and the finalized measures for this market: "
              f"<a href='metro?metro={code}'>the validated Explore page</a>.")

theme.caption("A working view, rebuilt as data lands; unlike the validated screens it "
              "is not frozen to the registry and makes no graded claim.")
st.markdown("Next: [the validated screen's key findings](home) · "
            "[Track record](track_record), where this failure is logged.")

theme.page_footer()
