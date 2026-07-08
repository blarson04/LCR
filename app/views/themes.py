"""
What drives the rankings: answers one question: what do the numbers mean?

The report's thematic middle (the benchmark's strongest organizational idea):
one section per scoring theme, each with a plain-language explanation of what
is measured and why it should precede rent growth, plus one chart showing
which markets the theme helps and hurts most this edition. Everything is
computed from the active edition's scores.
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

theme.eyebrow("Multifamily research · the report")
st.markdown("# What drives the rankings")
theme.caption("The five themes behind every score, in plain language: what each one "
              "measures, why it should come before rent growth, and which markets it "
              f"helps or hurts most in the {ed['year']} scoring year.")
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
st.write("")
st.markdown(
    "Every market is scored on the same eight measures, grouped into the five themes "
    "below (heaviest first). Each measure compares markets within the same year, each "
    "theme carries a fixed published weight, and no market is ever hand-adjusted.")

THEMES = [
    ("Demand", "40% of the score", "Who is moving in, hiring, and earning",
     "Net domestic migration, job growth, and income growth. Markets that people and "
     "paychecks are moving into fill apartments first and support rent increases later. "
     "Migration is the heaviest single measure — the screen's biggest bet, and the one "
     "the backtests reward most."),
    ("Supply", "25% of the score", "How much new housing is being built",
     "Building permits relative to the housing that already exists, counted the opposite "
     "way: the *less* a market is building, the better it scores. Today's construction "
     "is tomorrow's competition — the contrarian edge that pushes several fast-growing "
     "but over-built Sun Belt markets near the bottom."),
    ("Affordability", "20% of the score", "Whether rents have room to grow",
     "Two measures: rent as a share of local income (lower is better; stretched rents "
     "have nowhere to go), and the cost of owning versus renting (higher is better; "
     "when buying is far pricier than renting, households stay renters longer and "
     "demand stays in the rental pool)."),
    ("Momentum", "a deliberately small 10%", "What rents have done lately",
     "Recent rent growth, deliberately held to a small weight: informative, but it "
     "decays with time and inverted badly in the 2021-22 shock. A supporting witness, "
     "not the verdict."),
    ("Resilience", "5% of the score", "How diversified the local economy is",
     "Employment spread across industries: a market leaning on one sector carries more "
     "downside risk to rents, so diversity earns a small, steady credit."),
]


def short_title(title: str, maxlen: int = 24) -> str:
    """'Palm Bay-Melbourne-Titusville, FL' -> 'Palm Bay-Melbourne, FL': drop
    trailing city segments rather than cutting mid-word."""
    place, _, state = title.rpartition(",")
    parts = place.split("-")
    keep = parts[:1]
    for seg in parts[1:]:
        if len("-".join(keep + [seg])) > maxlen:
            break
        keep.append(seg)
    return f"{'-'.join(keep)},{state[:3]}"


def theme_chart(bucket: str) -> None:
    col = f"bucket_{bucket}"
    sub = rank[["rank", "cbsa_title", col]].dropna().sort_values(col, ascending=False)
    show = pd.concat([sub.head(5), sub.tail(5)])
    labels = [short_title(t) for t in show["cbsa_title"]]
    vals = show[col].tolist()
    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h", marker_line_width=0,
        marker_color=[theme.POS if v >= 0 else theme.NEG for v in vals],
        hovertemplate="%{y}<br>contribution %{x:+.2f}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False,
                     tickfont=dict(size=11, color=theme.MUTED))
    fig = theme.style_fig(fig, 300)
    fig.update_xaxes(showgrid=True, gridcolor=theme.LINE, zeroline=True,
                     zerolinecolor=theme.MUTED, zerolinewidth=1,
                     title="Contribution to the composite score")
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True)


for bucket, emphasis, subtitle, body in THEMES:
    inds = [data.PRETTY[k].lower() for k in data.INDICATORS
            if data.INDICATORS[k]["bucket"] == bucket]
    st.markdown(f"## {bucket}: {subtitle.lower()}")
    theme.caption(f"Share of the score: {emphasis}.")
    st.markdown(body)
    theme_chart(bucket)
    col = f"bucket_{bucket}"
    sub = rank[["rank", "cbsa_title", col]].dropna()
    best = sub.loc[sub[col].idxmax()]
    worst = sub.loc[sub[col].idxmin()]
    theme.caption(
        f"{best['cbsa_title'].split(',')[0]} gains the most ({best[col]:+.2f}); "
        f"{worst['cbsa_title'].split(',')[0]} gives up the most ({worst[col]:+.2f}). "
        f"Measures: {', '.join(inds)}.")

st.markdown("")
theme.caption("Formulas and data vintages: Methodology & about. Performance against "
              "realized rent growth: Track record.")
st.markdown("[Full rankings](rankings) · [Methodology & about](methodology)")

theme.page_footer()
