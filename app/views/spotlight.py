"""
Market spotlight: answers one question: what is the case for the #1 market?

A narrative close-up of whichever metro currently tops the active edition
(build-spec §4.4): why it ranks first, the concrete numbers behind its
strengths, its drag, and how its rents have tracked the national median.
Everything on the page is computed from the same frozen outputs as Rankings;
nothing is hand-written for a specific market.
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

from ui import data, theme  # noqa: E402

theme.inject_css(reading=True)
d = data.load()
ed = data.edition(d)
rank = ed["rank"].sort_values("rank").reset_index(drop=True)
top = rank.iloc[0]
code = top["cbsa_code"]
city = top["cbsa_title"].split(",")[0]

# ---- Header -------------------------------------------------------------------
st.markdown(f"# Market spotlight: {city}")
theme.caption(f"A closer look at the market ranked first in the {ed['horizon']} screen, "
              "and the case the data makes for it.")
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
st.write("")

# ---- The case, in words (all computed) -----------------------------------------
s1, s2 = data.top_strengths(top)
_, drag = data.strength_drag(top)
contribs = {b: top.get(f"bucket_{b}", 0.0) for b in data.BUCKETS}
top_buckets = [b for b in sorted(contribs, key=contribs.get, reverse=True)
               if contribs[b] > 0.02][:2]

BUCKET_INDS = {b: [k for k in data.INDICATORS if data.INDICATORS[k]["bucket"] == b]
               for b in data.BUCKETS}


def _ordinal(x: float) -> str:
    n = int(round(x))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
raw = ed["raw"]
pct = ed["pct"]

st.markdown(f"""
{top['cbsa_title']} ranks **#1 of {len(rank)}** markets, with a rank range of
{int(top['rank_lo'])}–{int(top['rank_hi'])} across reasonable alternative weightings.
Its score is built the same way as every other market's; what sets it apart:
""")

detail_lines = []
for b in top_buckets:
    label = {"Demand": "Demand", "Supply": "Limited new supply",
             "Affordability": "Affordability", "Momentum": "Rent momentum",
             "Resilience": "Economic resilience"}[b]
    parts = []
    for k in BUCKET_INDS[b]:
        if code in raw.index and pd.notna(raw.loc[code].get(k)):
            v = data.FMT[k](raw.loc[code][k])
            p = pct.loc[code][k] if code in pct.index else float("nan")
            parts.append(f"{data.PRETTY[k].lower()}: {v}"
                         + (f" ({_ordinal(p)} percentile)" if pd.notna(p) else ""))
    if parts:
        detail_lines.append(f"- **{label}** ({contribs[b]:+.2f} to the score): "
                            + "; ".join(parts) + ".")
if drag != "–":
    neg_b = min(contribs, key=contribs.get)
    detail_lines.append(f"- **The drag: {drag.lower()}** ({contribs[neg_b]:+.2f}); "
                        "no market in the top ten is strong everywhere.")
st.markdown("\n".join(detail_lines))
theme.caption("Contributions are in standardized units (0 = the average market that year). "
              "Percentiles compare against all markets in the same scoring year.")

# ---- Rents vs the national median ----------------------------------------------
tr = d["rent_trend"]
if len(tr) and (tr.cbsa_code == code).any():
    st.markdown("## Rents against the national median")
    mt = tr[tr.cbsa_code == code].set_index("month")["yoy"]
    us = tr[tr.cbsa_code == "US"].set_index("month")["yoy"]
    j = pd.concat([mt.rename("m"), us.rename("u")], axis=1).dropna().reset_index()
    j["month"] = pd.to_datetime(j["month"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=j["month"], y=j["u"], mode="lines",
                             line=dict(color=theme.GRAY_SERIES[0], width=1.6),
                             hovertemplate="%{x|%b %Y}: %{y:.1%}<extra>National median</extra>"))
    fig.add_trace(go.Scatter(x=j["month"], y=j["m"], mode="lines",
                             line=dict(color=theme.ACCENT, width=2.2),
                             hovertemplate="%{x|%b %Y}: %{y:.1%}<extra>" + city + "</extra>"))
    for y_end, txt, col in [(float(j["u"].iloc[-1]), "National median", theme.MUTED),
                            (float(j["m"].iloc[-1]), city, theme.ACCENT)]:
        fig.add_annotation(x=j["month"].iloc[-1], y=y_end, text=txt, showarrow=False,
                           xanchor="left", xshift=6,
                           font=dict(size=12, color=col, family=theme.FONT_BODY))
    fig.update_yaxes(tickformat=".0%", title="Rent growth, year over year")
    fig = theme.style_fig(fig, 320)
    fig.update_layout(margin=dict(l=0, r=110, t=8, b=0))
    st.plotly_chart(fig, use_container_width=True)

    above = (j["m"] > j["u"]).tolist()
    streak = 0
    for v in reversed(above):
        if not v:
            break
        streak += 1
    last12 = sum(above[-12:])
    latest = j["month"].iloc[-1].strftime("%B %Y")
    if streak >= 3:
        trend_txt = (f"{city} has out-grown the national median for "
                     f"{streak} consecutive months (through {latest}).")
    else:
        trend_txt = (f"{city} out-grew the national median in {last12} of the last "
                     f"12 months (through {latest}).")
    theme.caption(trend_txt + " Monthly Zillow rent index, year-over-year; the national "
                  "line is the median of the 110 screened markets. Rent history describes "
                  "the past; the rank comes from the forward-looking fundamentals above.")

# ---- Honesty block --------------------------------------------------------------
n_ind = int(top.get("n_indicators", data.N_IND))
if n_ind < data.N_IND:
    theme.caption(f"Data note: {city} was scored on {n_ind} of {data.N_IND} measures in "
                  "this vintage; a missing measure takes a neutral value rather than a "
                  "guess, which if anything holds its score down.")
if int(top["rank_hi"]) > 1:
    theme.caption(f"A #1 rank is a screening result, not a verdict: under reasonable "
                  f"alternative weightings this market ranks as low as "
                  f"#{int(top['rank_hi'])}, so read the top of the table as a group of "
                  f"strong candidates rather than a single winner.")
else:
    theme.caption("A #1 rank is a screening result, not a verdict; treat the top of the "
                  "table as a group of strong candidates.")
st.markdown("[Full measure-by-measure breakdown](metro_detail) · [All rankings](rankings)")

theme.page_footer()
