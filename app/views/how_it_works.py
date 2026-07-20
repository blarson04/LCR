"""
How it works: answers one question: how is the score built, and by whom?

Methodology and the theme explainers merged and condensed (v4 rebuild): five
plain paragraphs, the published weight table, the data ledger, the repair
story, the current-screen proxy scheme, and the author. Depth in expanders.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ui import data, theme          # noqa: E402
from src.nowcast import proxy_map as pmap  # noqa: E402

theme.inject_css(reading=True)
d = data.load()
ed = data.edition(d)
rank = ed["rank"].sort_values("rank").reset_index(drop=True)

theme.eyebrow("Multifamily research · the fine print")
st.markdown("# How it works")
theme.caption("How the score is built, what feeds it, and who built it.")
st.write("")

st.markdown(f"""
Can free public data tell strong future rental markets from weak ones in advance? The
screen ranks the **{len(rank)} largest US metro areas** (over 500,000 people, with
continuous rent data) on **{data.N_IND} measures** of fundamentals that historically
come before strong rent growth. Each measure is compared within the same
year, flipped where more is worse, weighted by a published share, and summed into one
score. No market is ever hand-adjusted.
""")

# ---- The five themes (condensed) --------------------------------------------
st.markdown("## The five themes")

THEMES = [
    ("Demand", "40%", "Net migration, job growth, and income growth. Markets that "
     "people and paychecks are moving into fill apartments first; migration is the "
     "screen's biggest bet."),
    ("Supply", "25%", "Building permits relative to existing housing, counted the "
     "opposite way: the less a market is building, the better it scores, because "
     "today's construction is tomorrow's competition."),
    ("Affordability", "20%", "Rent as a share of local income (stretched rents have "
     "nowhere to go) and the cost of owning versus renting (when buying is far "
     "pricier, households stay renters longer)."),
    ("Momentum", "10%", "Recent rent growth, deliberately held to a small weight: "
     "informative, but it decays and inverted badly in the 2021–22 shock."),
    ("Resilience", "5%", "Employment spread across industries; a one-sector economy "
     "carries more downside risk to rents."),
]
for bucket, share, body in THEMES:
    st.markdown(f"**{bucket} ({share} of the score).** {body}")

with st.expander("Which markets each theme helps and hurts most (charts)"):
    def _short(title, maxlen=24):
        place, _, state = title.rpartition(",")
        parts = place.split("-")
        keep = parts[:1]
        for seg in parts[1:]:
            if len("-".join(keep + [seg])) > maxlen:
                break
            keep.append(seg)
        return f"{'-'.join(keep)},{state[:3]}"

    for bucket, share, _ in THEMES:
        col = f"bucket_{bucket}"
        sub = rank[["cbsa_title", col]].dropna().sort_values(col, ascending=False)
        show = pd.concat([sub.head(5), sub.tail(5)])
        vals = show[col].tolist()
        fig = go.Figure(go.Bar(
            x=vals, y=[_short(t) for t in show["cbsa_title"]], orientation="h",
            marker_line_width=0,
            marker_color=[theme.POS if v >= 0 else theme.NEG for v in vals],
            hovertemplate="%{y}<br>contribution %{x:+.2f}<extra></extra>"))
        fig.update_yaxes(autorange="reversed", showgrid=False,
                         tickfont=dict(size=11, color=theme.MUTED))
        fig = theme.style_fig(fig, 280)
        fig.update_xaxes(showgrid=True, gridcolor=theme.LINE, zeroline=True,
                         zerolinecolor=theme.MUTED, zerolinewidth=1,
                         title=f"{bucket}: contribution to the composite score")
        fig.update_yaxes(showgrid=False)
        st.plotly_chart(fig, use_container_width=True)

# ---- The weights (published) ------------------------------------------------
st.markdown("## The weights")
_totals = {b: sum(data.INDICATORS[k]["weight"] for k in data.INDICATORS
                  if data.INDICATORS[k]["bucket"] == b) for b in data.BUCKETS}
rows = []
for b in data.BUCKETS:
    ks = [k for k in data.INDICATORS if data.INDICATORS[k]["bucket"] == b]
    rows.append({"Theme": b, "Weight": f"{_totals[b]*100:.0f}%",
                 "What it captures": " · ".join(
                     f"{data.PRETTY[k]} ({data.INDICATORS[k]['weight']*100:.0f}%)"
                     for k in ks)})
st.dataframe(
    pd.DataFrame(rows).style
      .set_properties(subset=["Theme"], **{"font-weight": "500"})
      .set_properties(subset=["Weight"], **{"font-variant-numeric": "tabular-nums",
                                            "text-align": "right"}),
    hide_index=True, use_container_width=True,
    column_config={"Weight": st.column_config.TextColumn(
        help="The share of the final score this theme carries. Each measure's own "
             "share is shown beside it. All weights sum to 100%.")})
theme.caption("Fixed, published in full, set by judgment rather than fitted, and "
              "stress-tested: alternatives land within noise, so the testing, not "
              "the weights, is the point.")

# ---- Data: sources, vintages, repairs ---------------------------------------
st.markdown("## The data")
st.markdown(
    "Everything comes from free public sources (Census, IRS, BLS, BEA, Zillow, FRED), "
    "and no accuracy number is shown without its data vintage. A 2023 federal "
    "boundary redraw silently corrupted job and population data for over thirty "
    "metros, twice putting an artifact at #1. Every affected series was rebuilt on "
    "consistent boundaries, and an automated quality review now cross-checks every "
    "input before anything publishes.")

with st.expander("Data sources and vintages, measure by measure"):
    vrows = []
    for k in data.INDICATORS:
        src_txt, through = data.VINTAGE_SOURCES[k]
        vrows.append({"Measure": data.PRETTY[k],
                      "Weight": f"{data.INDICATORS[k]['weight']*100:.0f}%",
                      "Source": src_txt, "Data through": through})
    st.dataframe(
        pd.DataFrame(vrows).style
          .set_properties(subset=["Measure"], **{"font-weight": "500"})
          .set_properties(subset=["Data through"],
                          **{"font-variant-numeric": "tabular-nums",
                             "text-align": "right"}),
        hide_index=True, use_container_width=True,
        column_config={"Data through": st.column_config.TextColumn(
            help="The most recent year of data feeding this measure in the "
                 "vintage screen. Nothing on this site is shown without its data "
                 "vintage.")})
    theme.caption(f"The ledger for the {data.VINTAGE_YEAR}-vintage screen. "
                  "* Connecticut redrew its geography between 2023 and 2024, so the "
                  "three Connecticut metros' job and income growth are chained using "
                  "validated boundary-stable substitutes; a disclosed fix for those "
                  "three markets only.")

with st.expander("The repair story, in more detail"):
    theme.caption(
        "The 2023 federal boundary redraw (and its predecessors) silently corrupted "
        "every metro-keyed federal series the panel uses: employment files and Census "
        "population and housing data alike mixed boundaries across years. Systematic "
        "sweeps found 35 metros needing employment rebuilt from county files on "
        "current boundaries and 36 needing population and housing rebuilt from county "
        "estimates; one metro's fake +15.6% job print and another's fake decline were "
        "each caught by cross-checking against an independent monthly series. "
        "Headline accuracy barely moved after the repairs (data hygiene, not model "
        "change), but individual ranks moved a lot, which is the point. The full "
        "audit trail is in the project's public decision log.")

# ---- The current screen's fresher inputs ------------------------------------
st.markdown("## How the current screen gets fresh data")
st.markdown(
    f"The slowest inputs publish one to two years late, so the "
    f"{data.SPEC_YEAR}→{data.SPEC_YEAR+3} current screen runs the same frozen model "
    "with validated substitutes for them; the configuration passed a pre-registered "
    "gate, keeping 96.6% of the finalized model's signal, after two earlier attempts "
    "failed and were published.")
with st.expander("The substitute for each measure"):
    if len(d["nc_prov"]):
        byw = d["nc_prov"].groupby("provenance")["weight"].sum()
        theme.caption(f"Data behind the {data.SPEC_YEAR} score, by share of the "
                      f"score's weight: live {byw.get('fast', 0):.0%} · validated "
                      f"substitutes {byw.get('proxy', 0):.0%} · carried forward "
                      f"{byw.get('carried_forward', 0):.0%}.")
    prows = []
    for k in data.INDICATORS:
        pm = pmap.PROXY_MAP.get(k, {})
        prows.append({"Measure": data.PRETTY[k],
                      "Finalized source": pm.get("finalized", ""),
                      "Current-screen approach": pm.get("proxy", "")})
    st.dataframe(
        pd.DataFrame(prows).style.set_properties(subset=["Measure"],
                                                 **{"font-weight": "500"}),
        hide_index=True, use_container_width=True)
    theme.caption("Each substitute was validated individually before the configuration "
                  "was tested as a whole; the ranking is reconciled against finalized "
                  "data as it lands each year.")

# ---- About the author -------------------------------------------------------
st.markdown("## About the author")
photo = APP / "assets" / "author.jpg"
if photo.exists():
    pcol, tcol = st.columns([1, 2.4], gap="large")
    pcol.image(str(photo), use_container_width=True, caption="Ben Larson")
else:
    tcol = st.container()
with tcol:
    st.markdown("""
I'm **Ben Larson**, an **Indiana University** student in economics and applied
mathematics. Everything here is my own work: every method documented, every claim
validated before publication, failed experiments published beside the successes.
""")

st.markdown("Next: [Track record](track_record), every completed call graded.")

theme.page_footer()
