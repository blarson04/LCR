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

from ui import components, data, theme  # noqa: E402
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

components.header_art("outlook_2026")
theme.eyebrow("Multifamily research · the speculative outlook")
st.markdown("# 2026→2029 outlook")
theme.caption("The same frozen model run on data through May 2026.")

components.speculative_frame(
    f"<div style='font-size:14px;margin-top:.35rem'>Tested on history the same way "
    f"as every published screen, this recipe keeps <b>{acc['retention']:.1%}</b> of "
    f"the finalized model's signal but matches the finalized top-10 on only "
    f"<b>{acc['mean_top10_overlap']:.1f} of 10</b> names (averaged across the test "
    f"windows; a validated screen needs {gate['overlap_bar']:.0f}).</div>")

# ---- The map ----------------------------------------------------------------
mp = rank.merge(d["coords"], on="cbsa_code", how="left")
# Pre-format the hover score: mixed-type customdata serializes as text, so a
# d3 format spec in the template is silently ignored and the raw float shows.
mp["score_txt"] = mp["score"].map("{:+.2f}".format)
fig = px.scatter_geo(
    mp, lat="lat", lon="lon", color="score", scope="usa",
    hover_name="cbsa_title", size=[8] * len(mp), size_max=12,
    color_continuous_scale=theme.DIV_SCALE, color_continuous_midpoint=0,
    custom_data=["rank", "score_txt", "strength"])
fig.update_traces(
    marker=dict(line=dict(width=0.6, color=theme.MAP_BORDER)),
    hovertemplate="<b>%{hovertext}</b><br>Speculative rank %{customdata[0]} · score "
                  "%{customdata[1]}<br>%{customdata[2]}<extra></extra>")
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
st.plotly_chart(theme.style_fig(fig, 470, speculative=True),
                use_container_width=True)
top3 = [t.split(",")[0].split("-")[0] for t in rank.head(3)["cbsa_title"]]
theme.caption(f"Darker green = stronger mid-year fundamentals, speculatively. "
              f"{top3[0]} leads; {top3[1]} and {top3[2]} follow. Same map, weaker "
              f"instrument: see the warning above.")

# ---- The ranking ------------------------------------------------------------
st.markdown("## The speculative ranking")
theme.caption("Why it is weaker than the main screen: rents, jobs, home values, and "
              "permits use only five months of 2026 data; migration is one year "
              "stale; and income growth is a state-level estimate (each metro takes "
              "its primary state's early-2026 income growth).")

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

# Per-market detail lives on the Explore page's screen selector (?screen=2026).
st.markdown("Next: [the validated screen's key findings](home) · "
            "[Track record](track_record).")

theme.page_footer()
