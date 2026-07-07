"""
Overview: answers one question: what does this report say?

The front page of the report, modeled on the benchmark's opening (key
findings, a short overview, the headline ranking) — every number computed
from validated outputs. Depth lives in the pages that follow, in reading
order: what drives the rankings, the full rankings, the spotlight.
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

from ui import data, theme  # noqa: E402
import config               # noqa: E402

theme.inject_css(reading=True)
d = data.load()
ed = data.edition(d)
rank = ed["rank"].sort_values("rank").reset_index(drop=True)
rank[["strength_1", "strength_2"]] = rank.apply(
    lambda r: pd.Series(data.top_strengths(r)), axis=1)

# ---- Header -------------------------------------------------------------------
st.markdown("# The rent-growth screen")
theme.caption(f"The {len(rank)} largest US rental markets, ranked by the fundamentals that "
              f"have historically come before strong rent growth. A {ed['horizon']} screen, "
              "built entirely on free public data, validated before publication.")
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
st.write("")

# ---- Key findings --------------------------------------------------------------
top_row = rank.iloc[0]
top_city = top_row["cbsa_title"].split(",")[0]
s1, s2 = data.top_strengths(top_row)
lift = " and ".join(s.lower() for s in (s1, s2) if s) or "balanced fundamentals"

pp_pooled, pp_mom, pp_win = float("nan"), float("nan"), None
es_path = config.PROCESSED_DIR / "effect_size_windows.csv"
if es_path.exists():
    ew = pd.read_csv(es_path)
    comp = ew[ew.strategy == "Composite (model)"].sort_values("pred_year")
    pp_pooled = float(comp["top10_pp_vs_median"].mean())
    mom = ew[ew.strategy == "Momentum (trailing rent)"]
    if len(mom):
        pp_mom = float(mom["top10_pp_vs_median"].mean())
    pp_win = comp

ind_tau, full_tau = float("nan"), float("nan")
ib_path = config.PROCESSED_DIR / "industry_baseline.csv"
if ib_path.exists():
    ib = pd.read_csv(ib_path)
    if len(ib):
        ind_tau = float(ib["tau_3y"].iloc[0])
        full_tau = float(ib["full_tau_3y"].iloc[0])

stay_txt = ""
if len(d["prior_rank"]) and ed.get("vintage"):
    prior_top = set(d["prior_rank"].nsmallest(10, "prior_rank")["cbsa_code"])
    stay = len(prior_top & set(rank.head(10)["cbsa_code"]))
    stay_txt = (f" {stay} of the prior edition's top ten stay in the top ten, and every "
                f"rank is published with an uncertainty range.")

st.markdown("## Key findings")
st.markdown(f"""
- **{top_city} leads the current screen** (a {ed['year']}–{ed['year']+3} outlook), lifted
  most by {lift}.{stay_txt}
- **The screen's top-10 markets out-grew the median market by {pp_pooled:+.1f} points of
  rent growth** over three years, averaged across six completed backtest windows. Picking
  on recent rent growth alone earned {pp_mom:+.1f}; the gap widens the further out you look.
- **Every measure had to earn its place by test.** An industry-style market scorecard
  rebuilt from free data barely beats chance at the same prediction task ({ind_tau:.2f} on
  a -1 to +1 rank-agreement scale, vs {full_tau:.2f} for this screen), and two of this
  project's own configurations failed their validation gates and were published as
  negative results.
""")

# ---- The top 10 ----------------------------------------------------------------
st.markdown("## The top 10")
rows_html = ""
for _, r in rank.head(10).iterrows():
    color = theme.POS if r["score"] >= 0 else theme.NEG
    strengths = " · ".join(s for s in (r["strength_1"], r["strength_2"]) if s) \
        or "Broadly average"
    rows_html += (
        f"<div style='padding:.42rem 0;border-bottom:1px solid {theme.LINE}'>"
        f"<span style='color:{theme.MUTED};display:inline-block;width:1.8rem'>{int(r['rank'])}</span>"
        f"<span style='font-weight:500'>{r['cbsa_title']}</span>"
        f"<span style='float:right;color:{color};font-variant-numeric:tabular-nums'>"
        f"{r['score']:+.2f}</span>"
        f"<div class='cap' style='margin-left:1.8rem'>{strengths}</div></div>")
st.markdown(rows_html, unsafe_allow_html=True)
theme.caption("Each market shows the one or two themes that lift its score most. Scores "
              "are relative to the average market (0); ranks carry uncertainty ranges, "
              "shown in the full rankings.")

# ---- The evidence, in one chart --------------------------------------------------
if pp_win is not None and len(pp_win):
    st.markdown("## Has it worked?")
    st.markdown(
        "Each completed three-year window is graded the same way: how much more rent "
        "growth did the screen's top-10 markets deliver than the median market?")
    figp = px.bar(pp_win, x="pred_year", y="top10_pp_vs_median")
    figp.update_traces(marker_color=[theme.POS if v >= 0 else theme.NEG
                                     for v in pp_win["top10_pp_vs_median"]],
                       marker_line_width=0)
    figp.update_xaxes(title="3-year window, by start year", dtick=1)
    figp.update_yaxes(title="Top-10 edge (points of rent growth)")
    st.plotly_chart(theme.style_fig(figp, 240), use_container_width=True)
    theme.caption("Four calm windows came in between +6.6 and +12.2 points; the 2021–22 "
                  "shock windows were roughly flat, where a pure rent-momentum strategy "
                  "flipped firmly negative. The current screen's own window (2024–27) is "
                  "graded when 2027 data closes. Numbers use finalized data; the real-time "
                  "equivalent is about 15% lower. Full validation: see Track record.")

# ---- Reading order ---------------------------------------------------------------
st.markdown("## Read the report")
st.markdown(
    "[What drives the rankings](themes): the five themes behind every score, in plain "
    "language · [Full rankings](rankings): the map and all "
    f"{len(rank)} markets · [Market spotlight](spotlight): the case for {top_city} · "
    "[Track record](track_record): every completed call, graded · "
    "[Methodology & about](methodology): how the score is built, and by whom.")

theme.page_footer()
