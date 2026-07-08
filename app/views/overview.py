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
theme.eyebrow("Multifamily research · the report")
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
    stay_txt = f" {stay} of the prior edition's top ten stay; every rank ships with a range."

lead_range = ""
if "rank_lo" in rank.columns and pd.notna(top_row.get("rank_lo")):
    lead_range = (f" — top of a leading cluster; its 90% rank range is "
                  f"{int(top_row['rank_lo'])}–{int(top_row['rank_hi'])}")

st.markdown("## Key findings")
st.markdown(f"""
- **{top_city} leads the current screen** (a {ed['year']}–{ed['year']+3} outlook), lifted
  most by {lift}{lead_range}.{stay_txt}
- **The screen's top-10 markets out-grew the median market by {pp_pooled:+.1f} points of
  rent growth** over three years, averaged across six completed backtest windows. Picking
  on recent rent growth alone earned {pp_mom:+.1f}; the gap widens the further out you look.
- **Every measure had to earn its place by test.** An industry-style scorecard rebuilt
  from the same free data barely beats chance ({ind_tau:.2f} on a -1 to +1
  rank-agreement scale, vs {full_tau:.2f} here), and two of this project's own failed
  configurations were published as negative results.
""")

# ---- The top 10, inside its leading cluster (tier + interval, P2) -------------
has_tiers = ("tier" in rank.columns) and (rank["tier"].fillna("") != "").any()
leaders = rank.head(10)
st.markdown("## The top 10")
if has_tiers:
    n_cluster = int((rank["tier"] == "Leading cluster").sum())
    n_in = int((leaders["tier"] == "Leading cluster").sum())
    outside = ("" if n_in == len(leaders) else
               f" ({len(leaders) - n_in} rank high today but carry ranges too wide to "
               f"make the cluster — read those loosely.)")
    theme.caption(
        f"Read the ranges: {n_in} of these ten sit in a {n_cluster}-market leading "
        f"cluster, any of whose members could plausibly hold a top-10 seat. Ordering "
        f"inside the cluster is noise.{outside}")
rows_html = ""
any_short = False
for _, r in leaders.iterrows():
    color = theme.POS if r["score"] >= 0 else theme.NEG
    strengths = " · ".join(s for s in (r["strength_1"], r["strength_2"]) if s) \
        or "Broadly average"
    if int(r["n_indicators"]) < data.N_IND:
        strengths += (f" · scored on {int(r['n_indicators'])} of {data.N_IND} measures")
        any_short = True
    rank_txt = (f"{int(r['rank'])} <span style='color:{theme.MUTED};font-size:.85em'>"
                f"({int(r['rank_lo'])}–{int(r['rank_hi'])})</span>"
                if has_tiers and pd.notna(r.get("rank_lo")) else f"{int(r['rank'])}")
    rows_html += (
        f"<div class='rowline'>"
        f"<span style='color:{theme.MUTED};display:inline-block;width:3.4rem;"
        f"font-variant-numeric:tabular-nums'>{rank_txt}</span>"
        f"<span style='font-weight:500'>{r['cbsa_title']}</span>"
        f"<span style='float:right;color:{color};font-variant-numeric:tabular-nums'>"
        f"{r['score']:+.2f}</span>"
        f"<div class='cap' style='margin-left:3.4rem'>{strengths}</div></div>")
st.markdown(rows_html, unsafe_allow_html=True)
short_note = (" Markets scored on fewer measures take neutral fills for the gaps; read "
              "their exact ranks loosely." if any_short else "")
theme.caption("Rank (90% range), score vs the average market (0), and the themes that "
              "lift each score most. All five tiers: Full rankings." + short_note)

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
    calm = pp_win[pp_win["pred_year"] <= 2019]["top10_pp_vs_median"]
    theme.caption(f"Calm windows came in between {calm.min():+.1f} and {calm.max():+.1f} "
                  "points; the 2021–22 shock windows were roughly flat, where pure rent "
                  "momentum flipped firmly negative. Each published screen is graded when "
                  "its end-year data closes. Full validation: Track record.")

# ---- Reading order ---------------------------------------------------------------
st.markdown("## Read the report")
st.markdown(
    "[What drives the rankings](themes): the five themes behind every score, in plain "
    "language · [Full rankings](rankings): the map and all "
    f"{len(rank)} markets · [Market spotlight](spotlight): the case for {top_city} · "
    "[Track record](track_record): every completed call, graded · "
    "[Methodology & about](methodology): how the score is built, and by whom.")

theme.page_footer()
