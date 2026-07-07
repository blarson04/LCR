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
import plotly.express as px
import streamlit as st

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ui import data, theme          # noqa: E402
from src.nowcast import proxy_map as pmap  # noqa: E402
import config                        # noqa: E402

theme.inject_css(reading=True)
d = data.load()
spec_mode = data.is_spec(d)

st.markdown("# About this project")
theme.caption("What the screener is, who built it, and how the score works — in plain terms.")
st.write("")

# ---- The one-minute version (claim → evidence → limitations) -----------------
st.markdown("## The one-minute version")
st.markdown(
    "A backtested screen of the 110 largest US rental markets, built on free public data. "
    "The current edition is a **validated 2024-vintage screen forecasting 2024–27** (with a "
    "supported extension to 2028) — its configuration passed a pre-registered validation "
    "gate after two earlier configurations failed theirs and were published as negative "
    "results. In calm markets its top-10 picks have meaningfully out-grown the median "
    "market; in the 2021–22 shock its edge largely disappeared — and it says so.")

bt = d["backtest"]
_pc = bt[(bt.horizon == 3) & (bt.regime == "pre_covid")]
pc_prec = float(_pc["mean_precision@10"].iloc[0]) if len(_pc) else float("nan")
_sh = bt[(bt.horizon == 3) & (bt.regime == "shock")]
sh_tau = float(_sh["mean_tau"].iloc[0]) if len(_sh) else float("nan")

pp_pooled, pp_win = float("nan"), None
es_path = config.PROCESSED_DIR / "effect_size_windows.csv"
if es_path.exists():
    ew = pd.read_csv(es_path)
    comp = ew[ew.strategy == "Composite (model)"].sort_values("pred_year")
    pp_pooled = float(comp["top10_pp_vs_median"].mean())
    pp_win = comp

c1, c2, c3 = st.columns(3)
c1.metric("Top-10 edge", f"+{pp_pooled:.1f} pp",
          help="Extra 3-year rent growth of the screen's top-10 markets vs the median market, "
               "averaged over six backtest windows (finalized data).")
c2.metric("Calm-market accuracy", f"{pc_prec:.0%}",
          help=f"Pre-COVID windows: share of top-10 picks landing in the top quarter of "
               f"markets (finalized data; τ {d['pc_tau']:.2f}, real-time equivalent "
               f"τ {d['spec_tau']:.2f}).")
c3.metric("In the 2021–22 shock", f"τ {sh_tau:.2f}",
          help="Rank agreement with realized growth in shock windows — the edge largely "
               "disappears, and the site flags such periods.")

if pp_win is not None and len(pp_win):
    figp = px.bar(pp_win, x="pred_year", y="top10_pp_vs_median")
    figp.update_traces(marker_color=[theme.POS if v >= 0 else theme.NEG
                                     for v in pp_win["top10_pp_vs_median"]],
                       marker_line_width=0)
    figp.update_xaxes(title=None, dtick=1)
    figp.update_yaxes(title="Top-10 edge (pp, 3-yr)")
    st.plotly_chart(theme.style_fig(figp, 230), use_container_width=True)
    theme.caption("Per backtest window: the top-10's extra 3-year rent growth vs the median "
                  "market. Four calm windows between +6.6 and +12.2 points; roughly flat in "
                  "the 2021–22 shock — where a pure rent-momentum strategy flipped firmly "
                  "negative.")
st.markdown("[See the rankings](rankings) · [Full track record & every caveat](track_record)")
theme.caption("A research screen, not a forecast: numbers above use finalized data (the "
              "real-time equivalent is about 15% lower), windows overlap, and shock periods "
              "break the edge.")
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
elif d["has_spec"]:
    theme.caption("Switch the sidebar to the provisional edition to see how the provisional "
                  "2025 screen is built.")
else:
    theme.caption("How the current screen earned publication: two fresher-data configurations "
                  "failed their pre-registered validation gate (74.8% and 84.66% signal "
                  "retention vs the 85% required — the second missed by a third of a point "
                  "and was pulled anyway). The third, built on newly finalized 2024 data with "
                  "a single validated substitute for slow migration data, passed at 95.5% and "
                  "is what this site shows. All three outcomes are published; a screen that "
                  "publishes its failures is the point. See Track record.")

theme.page_footer()
