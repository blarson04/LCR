"""
Metro pages: answers one question: why does this market rank where it does?

The metro-detail layout (the site's strongest page, kept), with the compare
picker embedded as an optional second selector: pick one market for the full
story, add a second for a side-by-side (v4 rebuild).
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

from ui import components, data, theme  # noqa: E402
import config               # noqa: E402

theme.inject_css()
d = data.load()
ed = data.edition(d)
rank = ed["rank"]

components.header_art("metro")
theme.eyebrow("Multifamily research · explore a market")
st.markdown("# Explore a market")
theme.caption("Why a market ranks where it does: its score, the themes driving it, and "
              "each measure in plain terms. Add a second market to compare side by side.")
if ed.get("vintage"):
    theme.caption("One measure is an early estimate: migration uses a validated Census "
                  "substitute. Everything else is finalized, apart from a disclosed "
                  "geography fix for the three Connecticut metros (see How it works).")
st.write("")

# ---- Screen selector (author direction 2026-08-18) --------------------------
# Explore either the validated 2025→2028 screen or the speculative 2026→2029
# outlook. The speculative view MUST carry its failed-validation warning: with
# the nav group gone, the on-page disclosure is the required separation
# (decision-log 2026-08-18); it may not be removed while this mode exists.
_VAL_LABEL = f"{data.SPEC_YEAR}→{data.SPEC_YEAR+3} (validated)"
_SPEC_LABEL = "2026→2029 (speculative)"
_nc_dir = config.PROCESSED_DIR / "nowcast"
_have26 = all((_nc_dir / f"midyear_2026_{s}.csv").exists()
              for s in ("ranking", "raw", "norm"))
screen_opts = [_VAL_LABEL] + ([_SPEC_LABEL] if _have26 else [])
screen = st.radio(
    "Screen", screen_opts, horizontal=True,
    index=1 if (st.query_params.get("screen") == "2026" and _have26) else 0,
    help="The validated screen passed its pre-registered accuracy gate; the "
         "speculative outlook failed validation and is shown with its measured "
         "accuracy as a warning.")
spec26 = screen == _SPEC_LABEL
if spec26:
    st.query_params["screen"] = "2026"
    _r26 = (pd.read_csv(_nc_dir / "midyear_2026_ranking.csv",
                        dtype={"cbsa_code": str})
            .sort_values("rank").reset_index(drop=True))
    _raw26 = (pd.read_csv(_nc_dir / "midyear_2026_raw.csv",
                          dtype={"cbsa_code": str}).set_index("cbsa_code"))
    _norm26 = (pd.read_csv(_nc_dir / "midyear_2026_norm.csv",
                           dtype={"cbsa_code": str}).set_index("cbsa_code"))
    ed = dict(rank=_r26, raw=_raw26,
              pct=_norm26[list(data.INDICATORS)].rank(pct=True) * 100,
              year=2026, provisional=True, vintage=False, horizon="2026→2029")
    rank = ed["rank"]
    _acc = pd.read_csv(_nc_dir / "midyear_v06_accuracy.csv").iloc[0]
    components.speculative_frame(
        f"<div style='font-size:14px;margin-top:.35rem'>This 2026→2029 view "
        f"failed its validation gate and is speculative. Tested on history, its "
        f"recipe keeps <b>{_acc['retention']:.1%}</b> of the finalized model's "
        f"signal but matches the finalized top-10 on only "
        f"<b>{_acc['mean_top10_overlap']:.1f} of 10</b> names (averaged across "
        f"the test windows). No confidence ranges or tiers are computed for it. "
        f"For decisions, use the validated {data.SPEC_YEAR}→{data.SPEC_YEAR+3} "
        f"screen.</div>")
elif "screen" in st.query_params:
    del st.query_params["screen"]

# Selections live in the URL (?metro=, ?vs=) so a view is shareable.
opts = rank.sort_values("cbsa_title")
titles = list(opts["cbsa_title"])
codes_sorted = [str(c) for c in opts["cbsa_code"]]
qp = st.query_params.get("metro")
c_sel1, c_sel2 = st.columns(2)
metro = c_sel1.selectbox("Choose a market", titles,
                         index=codes_sorted.index(qp) if qp in codes_sorted else 0)
qv = st.query_params.get("vs")
vs_options = ["None"] + [t for t in titles if t != metro]
vs_default = 0
if qv in codes_sorted:
    vt = titles[codes_sorted.index(qv)]
    if vt in vs_options:
        vs_default = vs_options.index(vt)
vs = c_sel2.selectbox("Compare with (optional)", vs_options, index=vs_default)

row = rank[rank["cbsa_title"] == metro].iloc[0]
code = row["cbsa_code"]
st.query_params["metro"] = str(code)
compare = vs != "None"
if compare:
    row2 = rank[rank["cbsa_title"] == vs].iloc[0]
    code2 = row2["cbsa_code"]
    st.query_params["vs"] = str(code2)
else:
    if "vs" in st.query_params:
        del st.query_params["vs"]


def _rank_text(r) -> str:
    """Rank plus its 90% range where one is computed (validated editions
    only; the speculative view has no interval)."""
    lo, hi = r.get("rank_lo"), r.get("rank_hi")
    if pd.notna(lo) and pd.notna(hi):
        return f"{int(r['rank'])} ({int(lo)}–{int(hi)})"
    return f"{int(r['rank'])}"


def _rank_metric(col, r, label=None):
    has_range = pd.notna(r.get("rank_lo"))
    col.metric(label or r["cbsa_title"].split(",")[0], _rank_text(r),
               help=f"This market's rank (1 = best); its composite score is "
                    f"{r['score']:+.2f}, where 0 is the average market. "
                    + ("The range in parentheses is the 90% range once measurement "
                       "noise in the two fast-moving inputs (job and income growth) "
                       "is accounted for; markets with overlapping ranges are "
                       "roughly tied." if has_range else
                       "No confidence range is computed for the speculative view; "
                       "read the rank loosely."))


# ============================ SIDE-BY-SIDE MODE ==============================
if compare:
    picks = [metro, vs]
    codes = {metro: code, vs: code2}
    cols = st.columns(2)
    for i, mt in enumerate(picks):
        _rank_metric(cols[i], rank[rank.cbsa_title == mt].iloc[0])

    st.markdown("## Measure by measure")
    theme.caption("Percentile across all markets (100 = best on that measure; direction "
                  "is already applied, so higher is always better).")
    comp = pd.DataFrame({"Measure": [data.PRETTY[k] for k in data.INDICATORS]})
    names = []
    for mt, cd in codes.items():
        nm = mt.split(",")[0]
        names.append(nm)
        comp[nm] = [ed["pct"][k].get(cd, float("nan")) for k in data.INDICATORS]
    st.dataframe(
        comp.style.set_properties(subset=["Measure"], **{"font-weight": "500"}),
        hide_index=True, use_container_width=True,
        column_config={nm: st.column_config.ProgressColumn(
            min_value=0, max_value=100, format="%.0f",
            help="Where this market stands among all markets on each measure: 100 "
                 "means best in the country, 50 the middle. Direction is already "
                 "applied, so higher is always better.") for nm in names})

    st.markdown("## What drives each score")
    bard = [{"Market": mt.split(",")[0], "Theme": b,
             "Contribution": rank[rank.cbsa_title == mt].iloc[0][f"bucket_{b}"]}
            for mt in picks for b in data.BUCKETS]
    palette = [theme.ACCENT] + theme.GRAY_SERIES
    figb = px.bar(pd.DataFrame(bard), x="Theme", y="Contribution", color="Market",
                  barmode="group", color_discrete_sequence=palette[:2])
    figb.update_yaxes(title="Contribution to score")
    figb.update_xaxes(title=None)
    figb = theme.style_fig(figb, 320)
    figb.update_layout(showlegend=True, legend=dict(orientation="h", y=1.12, title=None))
    st.plotly_chart(figb, use_container_width=True)
    leadr = max(picks, key=lambda mt: rank[rank.cbsa_title == mt].iloc[0]["score"])
    theme.caption(f"Bars above zero help a market's score; below zero hurt it. "
                  f"{leadr.split(',')[0]} has the stronger overall fundamentals of the "
                  f"two. Set the comparison to None for either market's full story.")

# ============================ SINGLE-MARKET MODE =============================
else:
    tier_txt = str(row.get("tier", "") or "")
    has_tier = tier_txt not in ("", "nan")
    _has_range = pd.notna(row.get("rank_lo"))
    c1, c2, c3 = st.columns(3)
    c1.metric("Rank", _rank_text(row),
              help=("This market's rank (1 = best). The range in parentheses is the "
                    "90% range once measurement noise in the two fast-moving inputs "
                    "(job and income growth) is accounted for; the single rank is a "
                    "point inside that range, not a precise fact." if _has_range else
                    "This market's rank (1 = best) in the speculative view. No "
                    "confidence range is computed for a screen that has not passed "
                    "validation; read the rank loosely."))
    if has_tier:
        c2.metric("Tier", tier_txt,
                  help="The tier is the honest headline: "
                       + data.TIER_BLURB.get(tier_txt, "")
                       + ". Markets in the same tier are peers; ordering within a tier "
                         "is inside the noise.")
    c_score = c3 if has_tier else c2
    c_score.metric("Score", f"{row['score']:+.2f}",
                   help="All eight measures combined into one number. 0 is the average "
                        "market this year; positive means stronger fundamentals than "
                        "average, negative weaker. The distance from 0 matters more "
                        "than the exact decimals.")
    if not has_tier:
        c3.metric("Of markets", f"{len(rank)}",
                  help="How many markets are ranked in this edition: every US metro "
                       "area with at least 500,000 people and continuous rent data.")

    st.markdown(f"<div class='cap' style='margin:.6rem 0 0'>{data.why_sentence(row)}</div>",
                unsafe_allow_html=True)

    # ---- Strengths / watch-outs --------------------------------------------
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
                f"<div style='font-weight:600;color:{color};margin-bottom:.4rem'>"
                f"{title}</div>")
        if items:
            html += "".join(f"<div style='font-size:14px;margin:.3rem 0'>{i}</div>"
                            for i in items)
        else:
            html += f"<div class='cap'>{empty}</div>"
        col.markdown(html + "</div>", unsafe_allow_html=True)

    _list(oc1, "Strengths", pros, theme.POS, "No standout strengths this year.")
    _list(oc2, "Watch-outs", cons, theme.NEG, "No major red flags this year.")

    # ---- Measures table ----------------------------------------------------
    st.markdown("## The eight measures")
    theme.caption("Percentile = where this market stands among all markets (100 = best), "
                  "with direction already applied so higher is always better.")
    rows, missing = [], []
    for k in data.INDICATORS:
        val = ed["raw"][k].get(code, float("nan"))
        if pd.isna(val):
            missing.append(data.PRETTY[k].lower())
        rows.append({"Measure": data.PRETTY[k],
                     "Weight": f"{data.INDICATORS[k]['weight']*100:.0f}%",
                     "Value": "–" if pd.isna(val) else data.FMT[k](val),
                     "Percentile": ed["pct"][k].get(code, float("nan"))})
    st.dataframe(
        pd.DataFrame(rows).style
          .set_properties(subset=["Measure"], **{"font-weight": "500"})
          .set_properties(subset=["Weight"], **{"font-variant-numeric": "tabular-nums",
                                                "text-align": "right"}),
        hide_index=True, use_container_width=True,
        column_config={
            "Weight": st.column_config.TextColumn(
                help="This measure's fixed share of the composite score, identical for "
                     "every market."),
            "Value": st.column_config.TextColumn(
                help="The measure in real-world units for this market, before any "
                     "scoring."),
            "Percentile": st.column_config.ProgressColumn(
                min_value=0, max_value=100, format="%.0f",
                help="Where this market stands among all markets on that measure: 100 "
                     "means the best in the country, 50 the middle. Direction is "
                     "already applied, so higher is always better for future rent "
                     "growth.")})
    if missing:
        theme.caption(f"Data note: {', '.join(missing)} is unavailable for this market "
                      "and takes a neutral (average) fill in the score, which can "
                      "flatter or understate it; lean on the rank range.")

    # ---- Forward-supply context (C-3): trajectory of the permit input ------
    # Display-only: the same permits/stock ratio the supply measure reads,
    # shown over recent scoring years. It does not touch the model.
    _pan = d["panel"]
    supply_hist = (_pan[(_pan["cbsa_code"] == code)
                        & (_pan["year"] <= ed["year"])]
                   [["year", "permits_total", "housing_units"]].dropna()
                   .sort_values("year").tail(5))
    if len(supply_hist) >= 3:
        supply_hist = supply_hist.assign(
            pts=supply_hist["permits_total"] / supply_hist["housing_units"] * 100)
        with st.container(border=True):
            st.markdown(
                f"<div style='font-weight:600;color:{theme.MUTED}'>"
                "Context, not model input</div>", unsafe_allow_html=True)
            figs = px.bar(supply_hist, x="year", y="pts",
                          text=[f"{v:.2f}%" for v in supply_hist["pts"]])
            figs.update_traces(marker_color=theme.GRAY_SERIES[0],
                               textposition="outside",
                               textfont=dict(size=11, color=theme.MUTED))
            figs.update_xaxes(dtick=1, title=None)
            figs.update_yaxes(title="Permits vs existing stock (%)",
                              rangemode="tozero")
            st.plotly_chart(theme.style_fig(figs, 240), use_container_width=True)
            theme.caption(
                "New building permits as a share of existing housing, the raw "
                "input behind the supply measure (less building scores better). "
                "The screen scores the latest year only; the trajectory is shown "
                "for context and does not affect the rank.")

    if not ed["provisional"]:
        with st.expander("Context measures (tracked, not scored)"):
            theme.caption("Tested as candidate measures but not added: neither showed "
                          "a reliably detectable improvement. Shown for description "
                          "only.")
            crows = []
            for colname, (label, note) in data.CTX.items():
                v = d["ctx_year"][colname].get(code, float("nan"))
                p = d["ctx_pct"][colname].get(code, float("nan"))
                crows.append({"Measure": label,
                              "Value": "–" if pd.isna(v) else f"{v*100:.1f}%",
                              "Percentile": "–" if pd.isna(p) else f"{p:.0f}",
                              "Note": note})
            components.text_table(pd.DataFrame(crows),
                                  right=("Value", "Percentile"))

    # ---- History charts ----------------------------------------------------
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
                    f"{abs(chg):.0%} since {int(hist['year'].iloc[0])} (Zillow index, "
                    f"annual average).</div>", unsafe_allow_html=True)

    # Trajectory: finalized-vintage years only, plus the validated 2024-vintage
    # point; never the unvalidated later rows of the finalized frame (which have
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
                    f"{(abs(move)) if move else ''}{' places' if move else ''} in the "
                    f"ranking since {int(traj['year'].iloc[0])}.</div>",
                    unsafe_allow_html=True)

st.markdown("Next: [how the score is built](how_it_works).")

theme.page_footer()
