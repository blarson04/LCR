"""
About & methodology: answers one question: what is this project, and how is
the score built?

The provisional (nowcast) method appears only when the provisional edition is
selected, so it never mixes into the accurate methodology.
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

from ui import data, theme          # noqa: E402
from src.nowcast import proxy_map as pmap  # noqa: E402

theme.inject_css(reading=True)
d = data.load()
spec_mode = data.is_spec(d)

st.markdown("# Methodology & about")
theme.caption("Start here: what this project is, who built it, and how the score works. "
              "The findings follow on the Overview page.")
st.write("")

# ---- Purpose, simply ---------------------------------------------------------
st.markdown(f"""
Some rental markets grow rents for years; others stall. This project asks a simple question:
**can public data tell them apart in advance?**

The screener ranks the **{len(d['acc_rank'])} largest US metro areas** on the fundamentals that
have historically come *before* strong rent growth: who is moving in, whether jobs and incomes
are growing, how much new housing is being built, and whether rents still have room to rise.
Everything is built from **free public data** (Census, IRS, BLS, BEA, Zillow, FRED), every method
is documented, and every published ranking is frozen so its calls can be checked against what
actually happens. It is a research screen, a disciplined starting point for where to look
closer, not a promise about any market.
""")

# ---- About me -----------------------------------------------------------------
st.markdown("## About me")
photo = APP / "assets" / "author.jpg"
if photo.exists():
    pcol, tcol = st.columns([1, 2.4], gap="large")
    pcol.image(str(photo), use_container_width=True)
else:
    tcol = st.container()
with tcol:
    st.markdown("""
I'm **Ben Larson**, a student at **Indiana University** majoring in **economics and applied
mathematics**, with a strong interest in **data analytics and real estate**.

I built this screener to answer a question I kept running into: how much of a rental market's
future is already visible in free public data? I held the answer to a standard I'd be willing
to defend: every method documented, every claim validated before it's published, failed
experiments published alongside the successes, and a frozen track record that anyone can check
against what actually happens. Everything here, from the data pipeline to the backtests to
this site, is my own work.
""")

# ---- How the score works --------------------------------------------------------
st.markdown("## How the score works")
st.markdown(f"""
The screen scores every market on **{data.N_IND} measures**, grouped into five themes. Each
measure compares a market **against all the others in the same year**, so a nationwide swing
cancels out and only relative standing counts. Measures where more is worse (heavy homebuilding,
rents that already stretch incomes) are flipped, so higher always means better. Each measure is
multiplied by a fixed weight and summed into one composite score, and markets are ranked by it.
The same formula runs for every market; no market is ever hand-adjusted. (The weights
themselves are set by judgment and stress-tested; see Track record.)
""")

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
theme.caption("Demand carries the most weight (40%): the framework bets that who is moving "
              "in, hiring, and earning matters most over a three-year horizon, with a heavy "
              "penalty for oversupply (25%) as the contrarian edge. The exact weights are "
              "fixed and published in full; they are set by judgment, never fitted to the "
              "backtest, and stress-tested against alternatives — schemes built on the same "
              "reasoning land within noise of each other, which is why the weights are not "
              "the secret here; the testing is (see Track record).")

if d.get("has_vintage") and not spec_mode:
    with st.expander("Data sources and vintages, measure by measure"):
        vrows = []
        for k in data.INDICATORS:
            src_txt, through = data.VINTAGE_SOURCES[k]
            vrows.append({"Measure": data.PRETTY[k],
                          "Weight": f"{data.INDICATORS[k]['weight']*100:.0f}%",
                          "Source": src_txt,
                          "Data through": through})
        st.dataframe(
            pd.DataFrame(vrows).style
              .set_properties(subset=["Measure"], **{"font-weight": "500"})
              .set_properties(subset=["Data through"],
                              **{"font-variant-numeric": "tabular-nums",
                                 "text-align": "right"}),
            hide_index=True, use_container_width=True,
            column_config={"Data through": st.column_config.TextColumn(
                help="The most recent year of data feeding this measure in the "
                     "current screen. Nothing on this site is shown without its "
                     "data vintage.")})
        theme.caption(f"The data ledger for the current {data.VINTAGE_YEAR}-vintage screen: "
                      "what feeds each measure and how fresh it is. "
                      "* Connecticut redrew its government geography between 2023 and "
                      "2024, so the three Connecticut metros' 2024 job and income growth "
                      "are chained from 2023 using validated boundary-stable substitutes "
                      "(a Census employment series and Connecticut's statewide income "
                      "growth); a disclosed substitution for those three markets only. "
                      "No accuracy number on this site is published without its data "
                      "vintage.")

if spec_mode and d["has_spec"]:
    st.markdown("## The current 2025 screen")
    st.markdown(theme.badge(True, "Validated 2025 screen · proxied inputs"),
                unsafe_allow_html=True)
    st.markdown("""
The slowest inputs (migration, income) publish one to two years late. The 2025 screen runs
the **same frozen model, same weights, same scoring**; only the data feeding it changes.
Fast inputs (rents, home values, permits) use live data; migration uses a validated Census
substitute; jobs use a validated monthly employment series; income is chained forward by
each metro's state income growth (states publish about a year ahead of metros). This
configuration **passed its pre-registered validation gate** on history (96.6% of the
finalized model's signal kept; top-10 overlap 7.4 of 10). It shortens the data lag; it
does not extend the three-year horizon or change the model.""")
    if len(d["nc_prov"]):
        byw = d["nc_prov"].groupby("provenance")["weight"].sum()
        theme.caption(f"Where the 2025 score's data comes from, by share of the score's "
                      f"weight: live data {byw.get('fast', 0):.0%} · validated "
                      f"substitutes {byw.get('proxy', 0):.0%} · the latest available "
                      f"value carried forward {byw.get('carried_forward', 0):.0%}.")
    prows = []
    for k in data.INDICATORS:
        pm = pmap.PROXY_MAP.get(k, {})
        prows.append({"Measure": data.PRETTY[k],
                      "Finalized source": pm.get("finalized", ""),
                      "2025-screen approach": pm.get("proxy", "")})
    st.dataframe(
        pd.DataFrame(prows).style.set_properties(subset=["Measure"], **{"font-weight": "500"}),
        hide_index=True, use_container_width=True)
    theme.caption("Each substitute was validated individually before the configuration "
                  "was tested as a whole; the ranking is reconciled against finalized "
                  "data as it lands each year.")
elif d["has_spec"]:
    theme.caption("Switch the sidebar to the 2025 edition to see how the current screen "
                  "is built from preliminary data.")

theme.caption("How the screens earned publication: two fresher-data configurations failed "
              "their pre-registered validation gate (74.8% and 84.66% signal retention vs "
              "the 85% required; the second missed by a third of a point and was pulled "
              "anyway, not rounded up). The third passed at 95.5% on newly finalized 2024 "
              "data (the vintage edition), and a fourth, adding a validated state-income "
              "chain, passed at 96.6% (the 2025 screen). All four outcomes are published; "
              "a screen that publishes its failures is the point. See Track record.")
theme.caption("What 'validated' means here, precisely: TWO separately logged checks. "
              "(1) The configuration passed its one-shot, pre-registered accuracy gate "
              "on history, and (2) the data build it scores passed an automated "
              "quality review — every input is cross-checked against an independent "
              "second source, extreme values and geography changes are flagged, and "
              "nothing publishes until every flag is investigated and signed off in "
              "the public decision log. A validated configuration fed corrupted data "
              "once; the second check exists so it cannot happen silently again.")

st.markdown("Next: [Overview](overview), the key findings and the top 10.")

theme.page_footer()
