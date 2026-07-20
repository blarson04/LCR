"""
Home: answers one question: what does this screen say right now?

The report's front door (v4 rebuild): what this is, the three key findings,
the top 10, one chart, and one validation line. Everything deeper is one
click away; every number is computed from validated outputs.
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
import config               # noqa: E402

theme.inject_css(reading=True)
d = data.load()
ed = data.edition(d)
rank = ed["rank"].sort_values("rank").reset_index(drop=True)
rank[["strength_1", "strength_2"]] = rank.apply(
    lambda r: pd.Series(data.top_strengths(r)), axis=1)

# ---- Header -----------------------------------------------------------------
theme.eyebrow("Multifamily research · the report")
st.markdown("# Key findings")
theme.caption(f"What the screen says right now: the {len(rank)} largest US rental "
              "markets, ranked by fundamentals that have historically come before "
              "strong rent growth. A research screen; not investment advice.")
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
theme.caption("Built on preliminary 2025 inputs through validated substitutes; what "
              "\"validated\" means and how every number works: "
              "<a href='how_it_works'>How it works</a>.")
st.write("")

# ---- Key findings -----------------------------------------------------------
top_row = rank.iloc[0]
top_city = top_row["cbsa_title"].split(",")[0]
code = top_row["cbsa_code"]
s1, s2 = data.top_strengths(top_row)
lift = " and ".join(s.lower() for s in (s1, s2) if s) or "balanced fundamentals"

pp_pooled, pp_mom = float("nan"), float("nan")
es_path = config.PROCESSED_DIR / "effect_size_windows.csv"
if es_path.exists():
    ew = pd.read_csv(es_path)
    comp = ew[ew.strategy == "Composite (model)"]
    pp_pooled = float(comp["top10_pp_vs_median"].mean())
    mom = ew[ew.strategy == "Momentum (trailing rent)"]
    if len(mom):
        pp_mom = float(mom["top10_pp_vs_median"].mean())

ind_tau, full_tau = float("nan"), float("nan")
ib_path = config.PROCESSED_DIR / "industry_baseline.csv"
if ib_path.exists():
    ib = pd.read_csv(ib_path)
    if len(ib):
        ind_tau = float(ib["tau_3y"].iloc[0])
        full_tau = float(ib["full_tau_3y"].iloc[0])

lead_range = ""
if pd.notna(top_row.get("rank_lo")):
    lead_range = (f"; its 90% rank range is "
                  f"{int(top_row['rank_lo'])}–{int(top_row['rank_hi'])}")

st.markdown("## Key findings")
st.markdown(f"""
- **{top_city} leads the current screen**, lifted most by {lift}{lead_range}.
- **The screen's top-10 markets out-grew the median market by {pp_pooled:+.1f} points
  of rent growth** across six completed windows; picking on recent rent growth alone
  earned {pp_mom:+.1f}.
- **Every measure earned its place by test.** An industry-style scorecard rebuilt from
  the same free data barely beats chance ({ind_tau:.2f} vs {full_tau:.2f} on a −1 to
  +1 rank-agreement scale), and this project's own failed configurations are published.
""")

# ---- The top 10 -------------------------------------------------------------
st.markdown("## The top 10")
has_tiers = ("tier" in rank.columns) and (rank["tier"].fillna("") != "").any()
rows_html = ""
for _, r in rank.head(10).iterrows():
    strengths = " · ".join(s for s in (r["strength_1"], r["strength_2"]) if s) \
        or "Broadly average"
    if int(r["n_indicators"]) < data.N_IND:
        strengths += f" · scored on {int(r['n_indicators'])} of {data.N_IND} measures"
    rank_txt = (f"{int(r['rank'])} <span style='color:{theme.MUTED};font-size:.85em'>"
                f"({int(r['rank_lo'])}–{int(r['rank_hi'])})</span>"
                if pd.notna(r.get("rank_lo")) else f"{int(r['rank'])}")
    rows_html += (
        f"<div class='rowline'>"
        f"<span style='color:{theme.MUTED};display:inline-block;min-width:4.4rem;"
        f"margin-right:.5rem;font-variant-numeric:tabular-nums'>{rank_txt}</span>"
        f"<span style='font-weight:500'>{r['cbsa_title']}</span>"
        f"<div class='cap' style='margin-left:4.9rem'>{strengths}</div></div>")
st.markdown(rows_html, unsafe_allow_html=True)
cluster_note = ""
if has_tiers:
    n_cluster = int((rank["tier"] == "Leading cluster").sum())
    cluster_note = (f" These ten sit in a {n_cluster}-market leading cluster; "
                    "ordering inside it is noise.")
theme.caption("Rank (90% range) and the themes lifting each score most."
              f"{cluster_note} Markets missing a measure take a neutral fill. "
              "Scores and all tiers: Full rankings.")

# ---- The case for the leader (auto-derived, replaces the spotlight page) ----
case_bits = []
contribs = {b: top_row.get(f"bucket_{b}", 0.0) for b in data.BUCKETS}
for b in sorted(contribs, key=contribs.get, reverse=True)[:2]:
    if contribs[b] > 0.02:
        case_bits.append(f"{data.BUCKET_LABEL[b]} ({contribs[b]:+.2f})")
streak_txt = ""
tr = d["rent_trend"]
if len(tr) and (tr.cbsa_code == code).any():
    mt = tr[tr.cbsa_code == code].set_index("month")["yoy"]
    us = tr[tr.cbsa_code == "US"].set_index("month")["yoy"]
    j = pd.concat([mt.rename("m"), us.rename("u")], axis=1).dropna()
    above = (j["m"] > j["u"]).tolist()
    streak = 0
    for v in reversed(above):
        if not v:
            break
        streak += 1
    if streak >= 3:
        streak_txt = (f" Its rents have out-grown the national median for "
                      f"{streak} consecutive months.")
st.markdown(
    f"<div style='background:{theme.SURFACE};border:1px solid {theme.LINE};"
    f"border-radius:8px;padding:.9rem 1.1rem;margin-top:1rem'>"
    f"<div style='font-family:{theme.FONT_HEAD};font-size:17px;font-weight:600'>"
    f"Why {top_city} leads</div>"
    f"<div style='font-size:14px;margin-top:.35rem'>Strongest on "
    f"{' and '.join(case_bits) if case_bits else 'balanced fundamentals'} "
    f"(contribution to its score).{streak_txt} "
    f"A #1 rank is a screening result, not a verdict.</div>"
    f"<div class='cap' style='margin-top:.4rem'><a href='metro?metro={code}'>"
    f"The full measure-by-measure case</a></div></div>",
    unsafe_allow_html=True)

# ---- One chart: top and bottom 10 vs the average ----------------------------
st.markdown("## The spread")


def _bars(sub_rank, height):
    labels = [(f"{int(r['rank'])}  {r['cbsa_title'].split(',')[0][:24]}"
               if int(r["rank"]) else r["cbsa_title"])
              for _, r in sub_rank.iterrows()]
    vals = sub_rank["score"].tolist()
    fig = go.Figure(go.Bar(
        x=vals, y=labels, orientation="h", marker_line_width=0,
        marker_color=[theme.POS if (v or 0) >= 0 else theme.NEG for v in vals],
        hovertemplate="%{y}<br>score %{x:+.2f}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", showgrid=False,
                     tickfont=dict(size=11, color=theme.MUTED))
    fig = theme.style_fig(fig, height)
    fig.update_xaxes(showgrid=True, gridcolor=theme.LINE, zeroline=True,
                     zerolinecolor=theme.MUTED, zerolinewidth=1,
                     title="Composite score (0 = the average market)")
    fig.update_yaxes(showgrid=False)
    return fig


head, tail = rank.head(10), rank.tail(10)
gap_row = pd.DataFrame({"rank": [0], "cbsa_title": [f"(…{len(rank)-20} markets…)"],
                        "score": [float("nan")]})
cols3 = ["rank", "cbsa_title", "score"]
st.plotly_chart(_bars(pd.concat([head[cols3], gap_row, tail[cols3]],
                                ignore_index=True), 24 * 21 + 60),
                use_container_width=True)
theme.caption("Score vs the average market (0); the spread matters more than any "
              "single value.")
with st.expander(f"All {len(rank)} markets on this chart"):
    st.plotly_chart(_bars(rank, 24 * len(rank) + 60), use_container_width=True)

# ---- Validation, in one line ------------------------------------------------
st.markdown(
    "**Has it worked?** Every screen is ranked before the fact and graded against "
    "what actually happened. The full record: [Track record](track_record).")

st.markdown("Next: [Full rankings](rankings), the map and every market's tier.")

theme.page_footer()
