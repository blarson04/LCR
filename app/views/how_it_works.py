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

from ui import data, theme          # noqa: E402
import config                       # noqa: E402
from src.nowcast import proxy_map as pmap  # noqa: E402

theme.inject_css(reading=True)
d = data.load()
ed = data.edition(d)
rank = ed["rank"].sort_values("rank").reset_index(drop=True)

theme.eyebrow("Multifamily research · the report")
st.markdown(
    f'<div style="font-family:{theme.FONT_HEAD};font-size:32px;font-weight:600;'
    f'line-height:1.25;color:{theme.INK};margin-bottom:.6rem;text-wrap:balance">'
    "Private companies pay heavily for market data. Can you still find an edge "
    "with free, public data?</div>",
    unsafe_allow_html=True)
theme.caption("This site is the tested answer: a rent-growth screen for the "
              f"{len(rank)} largest US rental markets, built entirely on free public "
              "data, validated before publication. This page explains how it works "
              "and what every number means.")
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
st.write("")

# ---- The method -------------------------------------------------------------
st.markdown("## The method")
st.markdown(f"""
The screen ranks every US metro area over 500,000 people with continuous rent data on
**{data.N_IND} measures** of fundamentals that historically come before strong rent
growth. Each measure is compared across markets within the same year (so nationwide
swings cancel out), flipped where more is worse (heavy construction, stretched rents),
weighted by a fixed published share, and summed into one score. The same formula runs
for every market; no market is ever hand-adjusted; the weights are set by judgment,
published in full, and stress-tested rather than statistically fitted.
""")

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

# ---- What the numbers mean --------------------------------------------------
st.markdown("## What the numbers mean")
st.markdown(
    "Every number on this site, in plain terms, and why it matters:")

bt = d["backtest"]
_p3 = bt[(bt.horizon == 3) & (bt.regime == "POOLED")]
pooled_tau = float(_p3["mean_tau"].iloc[0]) if len(_p3) else float("nan")
pooled_p10 = float(_p3["mean_precision@10"].iloc[0]) if len(_p3) else float("nan")
pp_pooled = float("nan")
_es = config.PROCESSED_DIR / "effect_size_windows.csv"
if _es.exists():
    _ew = pd.read_csv(_es)
    pp_pooled = float(_ew[_ew.strategy == "Composite (model)"]
                      ["top10_pp_vs_median"].mean())

GLOSSARY = [
    ("The composite score",
     "All eight weighted measures summed; 0 is the average market that year, positive "
     "is stronger, negative weaker.",
     "It is the ranking's raw material; the distance from 0 matters more than the "
     "exact decimals."),
    ("Rank and the 90% range",
     "The market's position (1 = best) plus the range its rank lands in 90% of the "
     "time once measured noise in the two fast-moving inputs is accounted for.",
     "A single rank oversells precision; markets with overlapping ranges are "
     "statistically tied, and treating them otherwise invites bad decisions."),
    ("Tiers (Leading cluster to Lagging)",
     "Bands built from the rank ranges under a fixed rule; same-tier markets are "
     "peers, not an ordering.",
     "The tier is the honest headline: it is what the data can actually support."),
    ("Weighted Kendall's tau",
     "A rank-agreement score from −1 to +1 between the screen's ranking and the rent "
     "growth that actually followed; 0 means no relationship, and extra weight goes "
     "to getting the top markets right.",
     "It is the main accuracy test: it asks whether the whole ranking pointed the "
     f"right way, not whether one pick got lucky. This screen scores {pooled_tau:.2f} "
     "pooled on finalized data; random guessing scores about 0."),
    ("Precision@10",
     "Of the screen's top 10 markets, the share that landed in the top quarter of "
     "all markets by actual rent growth.",
     "It grades the short list an investor would actually look at; "
     f"{pooled_p10:.0%} pooled, with a caveat: one miss moves it by 10 points, so "
     "read it with tau."),
    ("The top-10 edge, in points",
     "How much more 3-year rent growth the screen's top 10 delivered than the median "
     f"market: {pp_pooled:+.1f} points averaged across six completed windows.",
     "It converts the statistics into money terms: the units an underwriting "
     "decision is made in."),
    ("Validated",
     "Two separately logged checks passed: a one-shot, pre-registered accuracy gate "
     "on history, and an automated data-quality review with every flag signed off "
     "in the public decision log.",
     "A bar that never fails proves nothing; two configurations failed it and were "
     "published, which is what makes the passes meaningful."),
    ("Proxied inputs",
     "The current screen substitutes validated fast-publishing sources for inputs "
     "that publish one to two years late; the badge marks it wherever it applies.",
     "It is why a 2025→2028 forecast can exist at all, and the substitution kept "
     "96.6% of the finalized model's signal in testing."),
]
gl_html = ""
for term, what, why in GLOSSARY:
    gl_html += (
        f"<div class='rowline'><span style='font-weight:600'>{term}.</span> "
        f"<span style='font-size:14px'>{what}</span>"
        f"<div class='cap' style='margin-top:.15rem'><b>Why it matters:</b> "
        f"{why}</div></div>")
st.markdown(gl_html, unsafe_allow_html=True)

# ---- The data ---------------------------------------------------------------
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
            help="The most recent FINALIZED year behind this measure. The current "
                 "screen layers validated fast-publishing substitutes on top, as "
                 "described below.")})
    theme.caption("The finalized sources each measure is built from. * Connecticut "
                  "redrew its geography between 2023 and 2024, so the three "
                  "Connecticut metros' job and income growth are chained using "
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

st.markdown("Next: [Key findings](home), what the screen says right now.")

theme.page_footer()
