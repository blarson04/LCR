"""
Metro detail — answers one question: why does this market rank where it does?
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

theme.inject_css()
d = data.load()
ed = data.edition(d)
rank = ed["rank"]

st.markdown("# Metro detail")
theme.caption("Why a market ranks where it does — its score, the themes driving it, "
              "and each measure in plain terms.")
st.markdown(theme.badge(ed["provisional"], ed.get("badge_label")), unsafe_allow_html=True)
if ed.get("vintage"):
    theme.caption("One measure in this vintage is an early estimate: migration uses the "
                  "Census population-estimate substitute (validated against the finalized "
                  "IRS series, which arrives about two years later). Everything else is "
                  "finalized data.")
st.write("")

metro = st.selectbox("Choose a market", rank.sort_values("cbsa_title")["cbsa_title"])
row = rank[rank["cbsa_title"] == metro].iloc[0]
code = row["cbsa_code"]

c1, c2, c3 = st.columns(3)
c1.metric("Rank", f"{int(row['rank'])} ({int(row['rank_lo'])}–{int(row['rank_hi'])})",
          help="Range reflects statistical uncertainty in the score.")
c2.metric("Score", f"{row['score']:+.2f}",
          help="Composite of the eight measures; 0 is the average market this year.")
c3.metric("Of markets", f"{len(rank)}")

st.markdown(f"<div class='cap' style='margin:.6rem 0 0'>{data.why_sentence(row)}</div>",
            unsafe_allow_html=True)

# ---- Strengths / watch-outs ---------------------------------------------------
pros, cons = [], []
for k in data.INDICATORS:
    p = ed["pct"][k].get(code, float("nan"))
    if pd.isna(p):
        continue
    if p >= 65:
        pros.append((data.OUTLOOK[k][0], p))
    elif p <= 35:
        cons.append((data.OUTLOOK[k][1], p))
pros = [t for t, _ in sorted(pros, key=lambda x: -x[1])][:5]
cons = [t for t, _ in sorted(cons, key=lambda x: x[1])][:5]

st.markdown("## The quick read")
oc1, oc2 = st.columns(2)


def _list(col, title, items, color, empty):
    html = (f"<div style='background:{theme.SURFACE};border:1px solid {theme.LINE};"
            f"border-radius:8px;padding:.9rem 1.1rem;height:100%'>"
            f"<div style='font-weight:600;color:{color};margin-bottom:.4rem'>{title}</div>")
    if items:
        html += "".join(f"<div style='font-size:14px;margin:.3rem 0'>{i}</div>" for i in items)
    else:
        html += f"<div class='cap'>{empty}</div>"
    col.markdown(html + "</div>", unsafe_allow_html=True)


_list(oc1, "Strengths", pros, theme.POS, "No standout strengths this year.")
_list(oc2, "Watch-outs", cons, theme.NEG, "No major red flags this year.")

# ---- Measures table -------------------------------------------------------------
st.markdown("## The eight measures")
theme.caption("Percentile = where this market stands among all markets (100 = best), with "
              "direction already applied so higher is always better.")
rows = []
for k in data.INDICATORS:
    val = ed["raw"][k].get(code, float("nan"))
    rows.append({"Measure": data.PRETTY[k],
                 "Weight": f"{data.INDICATORS[k]['weight']*100:.0f}%",
                 "Value": "—" if pd.isna(val) else data.FMT[k](val),
                 "Percentile": ed["pct"][k].get(code, float("nan"))})
st.dataframe(
    pd.DataFrame(rows).style.set_properties(subset=["Measure"], **{"font-weight": "500"}),
    hide_index=True, use_container_width=True,
    column_config={"Percentile": st.column_config.ProgressColumn(
        min_value=0, max_value=100, format="%.0f")})

if not ed["provisional"]:
    with st.expander("Context measures (tracked, not scored)"):
        theme.caption("Tested as candidate measures but not added to the score — neither "
                      "reliably improved accuracy. Shown for description only.")
        crows = []
        for colname, (label, note) in data.CTX.items():
            v = d["ctx_year"][colname].get(code, float("nan"))
            crows.append({"Measure": label,
                          "Value": "—" if pd.isna(v) else f"{v*100:.1f}%",
                          "Percentile": d["ctx_pct"][colname].get(code, float("nan")),
                          "Note": note})
        st.dataframe(pd.DataFrame(crows).style.format({"Percentile": "{:.0f}"}),
                     hide_index=True, use_container_width=True)

# ---- History charts -------------------------------------------------------------
st.markdown("## History")
t1, t2 = st.columns(2, gap="large")
hist = d["panel"][d["panel"]["cbsa_code"] == code][["year", "zori"]].dropna()
if len(hist) > 1:
    figh = px.line(hist, x="year", y="zori", markers=True)
    figh.update_traces(line=dict(color=theme.ACCENT, width=2.2),
                       marker=dict(color=theme.ACCENT, size=5))
    figh.update_xaxes(dtick=2, title=None)
    figh.update_yaxes(title="Typical asking rent ($/month)")
    t1.plotly_chart(theme.style_fig(figh, 290), use_container_width=True)
    chg = hist["zori"].iloc[-1] / hist["zori"].iloc[0] - 1
    t1.markdown(f"<div class='cap'>Asking rents are {'up' if chg >= 0 else 'down'} "
                f"{abs(chg):.0%} since {int(hist['year'].iloc[0])} (Zillow index, annual "
                f"average).</div>", unsafe_allow_html=True)

# Trajectory: finalized-vintage years only, plus the validated 2024-vintage
# point — never the unvalidated later rows of the finalized frame (which have
# missing migration and would silently mix vintages; v3-plan critique).
traj = (d["scored"][(d["scored"]["cbsa_code"] == code)
                    & (d["scored"]["year"] <= data.SCORE_YEAR)]
        [["year", "rank"]].dropna().sort_values("year"))
if ed.get("vintage"):
    vrow = ed["rank"][ed["rank"]["cbsa_code"] == code]
    if len(vrow):
        traj = pd.concat([traj, pd.DataFrame(
            {"year": [ed["year"]], "rank": [int(vrow["rank"].iloc[0])]})],
            ignore_index=True).sort_values("year")
if len(traj) > 1:
    figr = px.line(traj, x="year", y="rank", markers=True)
    figr.update_traces(line=dict(color=theme.GRAY_SERIES[0], width=2.2),
                       marker=dict(color=theme.GRAY_SERIES[0], size=5))
    figr.update_xaxes(dtick=2, title=None)
    figr.update_yaxes(autorange="reversed", title="Rank (1 = best)")
    t2.plotly_chart(theme.style_fig(figr, 290), use_container_width=True)
    move = int(traj["rank"].iloc[0] - traj["rank"].iloc[-1])
    word = "risen" if move > 0 else ("slipped" if move < 0 else "held steady")
    t2.markdown(f"<div class='cap'>This market has {word} "
                f"{(abs(move)) if move else ''}{' places' if move else ''} in the ranking "
                f"since {int(traj['year'].iloc[0])}.</div>", unsafe_allow_html=True)

theme.page_footer()
