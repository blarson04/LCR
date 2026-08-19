"""
How it works: the site's front door (author direction 2026-07-20).

Opens with the thesis in larger type, explains the methodology, then defines
every number a reader will meet on the later pages (score, rank range, tier,
tau, precision@10, the pp edge) in plain language with why each matters.
This page is exempted from the 400-word surface budget by the same author
direction; depth still layers into expanders.
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

from ui import components, data, diagrams, theme  # noqa: E402
import config                       # noqa: E402
from src.nowcast import proxy_map as pmap  # noqa: E402

theme.inject_css(reading=True)
d = data.load()
ed = data.edition(d)
rank = ed["rank"].sort_values("rank").reset_index(drop=True)

components.header_art("how_it_works")
st.markdown(
    f'<div style="font-family:{theme.FONT_HEAD};font-size:40px;font-weight:600;'
    f'line-height:1.2;color:{theme.INK};margin-bottom:.9rem;text-wrap:balance">'
    "A quantified prediction of America’s emerging rental markets, built by "
    "synthesizing public data.</div>",
    unsafe_allow_html=True)
st.write("")

# ---- The method -------------------------------------------------------------
st.markdown("## The method")
st.markdown(f"""
The screen ranks every US metro area over 500,000 people with continuous rent data on
eight measures of fundamentals that historically come before strong rent
growth. Each measure is compared across markets within the same year (so nationwide
swings cancel out), weighted by a fixed published share, and summed into one score.
The same formula runs for every market; no market is ever hand-adjusted; the weights
are set by judgment.
""")
st.markdown(diagrams.method_pipeline(), unsafe_allow_html=True)

# ---- The five themes --------------------------------------------------------
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
     "informative, but it decays and inverted badly in the 2020–22 shock."),
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
st.markdown(diagrams.weights_bar(), unsafe_allow_html=True)
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

# ---- What the numbers mean --------------------------------------------------
st.markdown("## What the numbers mean")

pp_pooled = float("nan")
_es = config.PROCESSED_DIR / "effect_size_windows.csv"
if _es.exists():
    _ew = pd.read_csv(_es)
    pp_pooled = float(_ew[_ew.strategy == "Composite (model)"]
                      ["top10_pp_vs_median"].mean())

GLOSSARY = [
    ("The composite score",
     "All eight weighted measures summed; 0 is the average market that year, positive "
     "is stronger, negative weaker."),
    ("Rank and the 90% confidence range",
     "The market's position (1 = best) plus the range its rank lands in 90% of the "
     "time once measured noise in the two fast-moving inputs is accounted for; "
     "markets with overlapping ranges are statistically tied."),
    ("Tiers (Leading cluster to Lagging)",
     "Bands built from the confidence ranges under a fixed rule; same-tier markets "
     "are peers, not an ordering."),
    ("Weighted Kendall's tau",
     "A rank-agreement score from −1 to +1 between the screen's ranking and the rent "
     "growth that actually followed; 0 means no relationship, and extra weight goes "
     "to getting the top markets right."),
    ("Precision@10",
     "Of the screen's top 10 markets, the share that landed in the top quarter of "
     "all markets by actual rent growth."),
    ("The top-10 edge, in points",
     "How much more 3-year rent growth the screen's top 10 delivered than the median "
     f"market: {pp_pooled:+.1f} points averaged across six completed windows."),
]
gl_html = ""
for term, what in GLOSSARY:
    gl_html += (
        f"<div class='rowline'><span style='font-weight:600'>{term}.</span> "
        f"<span style='font-size:14px'>{what}</span></div>")
st.markdown(gl_html, unsafe_allow_html=True)

# ---- The data ---------------------------------------------------------------
st.markdown("## The data")
st.markdown(
    "Everything comes from free public sources (Census, IRS, BLS, BEA, Zillow, FRED), "
    "and no accuracy number is shown without its data vintage. A 2023 federal "
    "boundary redraw silently corrupted job and population data for over thirty "
    "metros. Every affected series was rebuilt on consistent boundaries, and an "
    "automated quality review now cross-checks every input before anything "
    "publishes.")

with st.expander("Data sources and vintages, measure by measure"):
    vrows = []
    for k in data.INDICATORS:
        src_txt, through = data.VINTAGE_SOURCES[k]
        vrows.append({"Measure": data.PRETTY[k],
                      "Weight": f"{data.INDICATORS[k]['weight']*100:.0f}%",
                      "Source": src_txt, "Data through": through,
                      "Link": data.SOURCE_LINKS.get(k, "")})
    vdf = pd.DataFrame(vrows).rename(columns={"Link": "Source page"})
    components.text_table(vdf, right=("Weight", "Data through"),
                          links={"Source page": "source page"})
    theme.caption("The finalized sources each measure is built from. * Connecticut "
                  "redrew its geography between 2023 and 2024, so the three "
                  "Connecticut metros' job and income growth are chained using "
                  "validated boundary-stable substitutes; a disclosed fix for those "
                  "three markets only.")

with st.expander("Boundary corrections in detail"):
    theme.caption(
        "The redraw's full extent: the 2023 federal boundary change (and its "
        "predecessors) silently corrupted "
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
    "Some inputs, like income and migration, publish one to two years behind. The "
    f"{data.SPEC_YEAR}→{data.SPEC_YEAR+3} current screen fills those gaps with "
    "faster sources, each tested against the finalized data before use. The "
    "combined setup was then tested as a whole: it kept 96.6% of the finalized "
    "model's accuracy. Two earlier versions failed that test and were published "
    "anyway.")
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
    components.text_table(pd.DataFrame(prows))
    theme.caption("The ranking is reconciled against finalized data as it lands "
                  "each year.")

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
My name is **Ben Larson**, and I am a junior at **Indiana University** studying
economics and applied math. My research interests center on quantitative market
selection: applying data to identify optimal real estate markets across the U.S.
and to help inform investment decisions across commercial real estate asset
classes, including multifamily, industrial, retail, office, and data centers.
""")
    st.markdown(theme.contact_links(), unsafe_allow_html=True)

st.markdown("Next: [Key findings](home), what the screen says right now.")

theme.page_footer()
