"""
About & methodology — answers one question: what is this project, and how is
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

st.markdown("# About this project")
theme.caption("What the screener is, who built it, and how the score works — in plain terms.")
st.write("")

# ---- Purpose, simply ---------------------------------------------------------
st.markdown(f"""
Some rental markets grow rents for years; others stall. This project asks a simple question:
**can public data tell them apart in advance?**

The screener ranks the **{len(d['acc_rank'])} largest US metro areas** on the fundamentals that
have historically come *before* strong rent growth — who is moving in, whether jobs and incomes
are growing, how much new housing is being built, and whether rents still have room to rise.
Everything is built from **free public data** (Census, IRS, BLS, BEA, Zillow, FRED), every method
is documented, and every published ranking is frozen so its calls can be checked against what
actually happens. It is a research screen — a disciplined starting point for where to look
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
I'm a student at **Indiana University** majoring in **economics and applied mathematics**, with
a strong interest in **data analytics and real estate**.

I built this screener to put that interest to work: to learn what public data can honestly say
about rental markets, and to practice doing research the right way — documented methods,
validation before claims, and a frozen track record that anyone can audit. Everything on this
site, from the data pipeline to the backtests, was built as part of that project.
""")

# ---- How the score works --------------------------------------------------------
st.markdown("## How the score works")
st.markdown(f"""
The screen scores every market on **{data.N_IND} measures**, grouped into five themes. Each
measure compares a market **against all the others in the same year**, so a nationwide swing
cancels out and only relative standing counts. Measures where more is worse (heavy homebuilding,
rents that already stretch incomes) are flipped, so higher always means better. Each measure is
multiplied by a fixed weight and summed into one composite score, and markets are ranked by it.
The same formula runs for every market — no market is ever hand-adjusted. (The weights
themselves are set by judgment and stress-tested; see Track record.)
""")

rows = []
for b in data.BUCKETS:
    ks = [k for k in data.INDICATORS if data.INDICATORS[k]["bucket"] == b]
    w = sum(data.INDICATORS[k]["weight"] for k in ks)
    rows.append({"Theme": b, "Weight": f"{w*100:.0f}%",
                 "What it captures": " · ".join(data.PRETTY[k] for k in ks)})
st.dataframe(
    pd.DataFrame(rows).style.set_properties(subset=["Theme"], **{"font-weight": "500"}),
    hide_index=True, use_container_width=True)
theme.caption("Demand leads at 40% — the framework bets that who is moving in, hiring, and "
              "earning matters most over a three-year horizon, with a heavy penalty for "
              "oversupply (25%) as the contrarian edge. Weights are set by judgment and "
              "tested against alternatives; see Track record for how it has performed.")

if spec_mode and d["has_spec"]:
    st.markdown("## The provisional screen")
    st.markdown(theme.badge(provisional=True), unsafe_allow_html=True)
    st.markdown("""
The slowest inputs (migration, income) publish about two years late, which is why the
validated screen is anchored to 2023. The provisional screen runs the **same model, same
weights, same scoring** — only the data feeding it changes. Fast inputs (rents, home values,
permits) use live data; slow inputs use preliminary substitutes or the latest available
value carried forward. It shortens the data lag; it does not extend the three-year horizon
or change the model.""")
    if len(d["nc_prov"]):
        by = d["nc_prov"].groupby("provenance")["weight"].sum()
        theme.caption(f"Where the provisional score's data comes from: live "
                      f"{by.get('fast', 0):.0%} · preliminary substitutes "
                      f"{by.get('proxy', 0):.0%} · carried forward "
                      f"{by.get('carried_forward', 0):.0%}.")
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
else:
    theme.caption("Switch the sidebar to the provisional edition to see how the provisional "
                  "2025 screen is built.")

theme.page_footer()
