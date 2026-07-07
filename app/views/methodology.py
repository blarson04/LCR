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
_words = ["Heaviest", "Heavy", "Moderate", "Light", "Lightest"]
_emphasis = {b: _words[i] for i, b in
             enumerate(sorted(data.BUCKETS, key=lambda b: -_totals[b]))}
rows = []
for b in data.BUCKETS:
    ks = [k for k in data.INDICATORS if data.INDICATORS[k]["bucket"] == b]
    rows.append({"Theme": b, "Emphasis": _emphasis[b],
                 "What it captures": " · ".join(data.PRETTY[k] for k in ks)})
st.dataframe(
    pd.DataFrame(rows).style.set_properties(subset=["Theme"], **{"font-weight": "500"}),
    hide_index=True, use_container_width=True,
    column_config={"Emphasis": st.column_config.TextColumn(
        help="How much of the final score this theme carries, from heaviest to "
             "lightest. The exact percentages are the project's proprietary core "
             "and are not published.")})
theme.caption("Demand carries the most weight: the framework bets that who is moving in, "
              "hiring, and earning matters most over a three-year horizon, with a heavy "
              "penalty for oversupply as the contrarian edge. The exact weights are fixed, "
              "sum to 100%, and are deliberately not published; they are set by judgment, "
              "never fitted to the backtest, and stress-tested against alternatives (see "
              "Track record).")

if d.get("has_vintage") and not spec_mode:
    with st.expander("Data sources and vintages, measure by measure"):
        vrows = []
        for k in data.INDICATORS:
            src_txt, through = data.VINTAGE_SOURCES[k]
            vrows.append({"Measure": data.PRETTY[k],
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
                      "* Cleveland and Dayton carry 2023 employment values; their 2024 "
                      "employment file had a reporting gap when the screen was scored (a "
                      "disclosed substitution). No accuracy number on this site is "
                      "published without its data vintage.")

if spec_mode and d["has_spec"]:
    st.markdown("## The provisional screen")
    st.markdown(theme.badge(provisional=True), unsafe_allow_html=True)
    st.markdown("""
The slowest inputs (migration, income) publish about two years late, which is why the
validated screen is anchored to 2023. The provisional screen runs the **same model, same
weights, same scoring**; only the data feeding it changes. Fast inputs (rents, home values,
permits) use live data; slow inputs use preliminary substitutes or the latest available
value carried forward. It shortens the data lag; it does not extend the three-year horizon
or change the model.""")
    if len(d["nc_prov"]):
        by = d["nc_prov"].groupby("provenance").size()
        theme.caption(f"Where the provisional score's data comes from: live data for "
                      f"{by.get('fast', 0)} of {data.N_IND} measures · preliminary "
                      f"substitutes for {by.get('proxy', 0)} · the latest available "
                      f"value carried forward for {by.get('carried_forward', 0)}.")
    prows = []
    for k in data.INDICATORS:
        pm = pmap.PROXY_MAP.get(k, {})
        prows.append({"Measure": data.PRETTY[k],
                      "Finalized source": pm.get("finalized", ""),
                      "Provisional approach": pm.get("proxy", "")})
    st.dataframe(
        pd.DataFrame(prows).style.set_properties(subset=["Measure"], **{"font-weight": "500"}),
        hide_index=True, use_container_width=True)
    theme.caption("The migration substitute tracks the finalized source closely; the main "
                  "added uncertainty comes from carrying employment and income forward. "
                  "Fresher jobs data is the planned improvement.")
elif d["has_spec"]:
    theme.caption("Switch the sidebar to the provisional edition to see how the provisional "
                  "2025 screen is built.")
else:
    theme.caption("How the current screen earned publication: two fresher-data configurations "
                  "failed their pre-registered validation gate (74.8% and 84.66% signal "
                  "retention vs the 85% required; the second missed by a third of a point "
                  "and was pulled anyway). The third, built on newly finalized 2024 data with "
                  "a single validated substitute for slow migration data, passed at 95.5% and "
                  "is what this site shows. All three outcomes are published; a screen that "
                  "publishes its failures is the point. See Track record.")

st.markdown("Next: [Overview](overview), the key findings and the top 10.")

theme.page_footer()
