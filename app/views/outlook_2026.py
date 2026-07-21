"""
Speculative outlook: answers one question: what does the newest, unvalidated
data suggest for 2026-2029?

Ships under the FAILED v0.5 gate's pre-committed consequence (decision-log
2026-07-21): the measured failed accuracy is displayed as a warning beside
the ranking, the page lives in its own navigation group, and nothing here
carries the validated label. The validated 2025-2028 screen stays primary.
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

from ui import data, theme  # noqa: E402
import config               # noqa: E402

theme.inject_css()
d = data.load()

NC = config.PROCESSED_DIR / "nowcast"
rank = pd.read_csv(NC / "midyear_2026_ranking.csv", dtype={"cbsa_code": str})
gate = pd.read_csv(NC / "gate2026_summary.csv").iloc[0]
rank = rank.sort_values("rank").reset_index(drop=True)
rank[["strength", "drag"]] = rank.apply(
    lambda r: pd.Series(data.strength_drag(r)), axis=1)

theme.eyebrow("Multifamily research · the speculative outlook")
st.markdown("# 2026→2029 outlook")
theme.caption("The same frozen model run on data through May 2026. It exists because "
              "readers asked for the newest possible view; the warning below is why "
              "it is not the site's screen.")
st.markdown(theme.badge(True, "Speculative 2026→2029 outlook · failed validation"),
            unsafe_allow_html=True)

st.markdown(
    f"<div style='border:1.5px solid {theme.PROVISIONAL};border-radius:8px;"
    f"padding:.9rem 1.1rem;margin:.8rem 0;background:rgba(138,109,29,.06)'>"
    f"<div style='font-weight:600;color:{theme.PROVISIONAL}'>This configuration "
    f"failed its validation test. Read every rank loosely.</div>"
    f"<div style='font-size:14px;margin-top:.35rem'>Tested on history the same way "
    f"as every published screen, the mid-year recipe kept only "
    f"<b>{gate['retention']:.1%}</b> of the finalized model's signal (the "
    f"publication bar is {gate['retention_bar']:.0%}) and matched the finalized "
    f"top-10 on <b>{gate['mean_top10_overlap']:.1f} of 10</b> names (bar: "
    f"{gate['overlap_bar']:.0f}), falling to 2–3 of 10 in fast-moving years. "
    f"Both failures are published in full on Track record. For decisions, use the "
    f"validated 2025→2028 screen.</div></div>", unsafe_allow_html=True)

st.markdown("## The speculative ranking")
theme.caption("Why it is weaker than the main screen: rents, jobs, home values, and "
              "permits use only five months of 2026 data; migration is one year "
              "stale; and income growth is not observable mid-year, so every market "
              "is scored on at most 7 of 8 measures with income taken as neutral.")

tbl = pd.DataFrame({
    "Rank": rank["rank"].astype(int),
    "Metro": rank["cbsa_title"],
    "Score": rank["score"],
    "Top strength": rank["strength"],
    "Top drag": rank["drag"],
})
st.dataframe(
    tbl.style.format({"Score": "{:+.2f}"})
       .map(lambda v: f"color:{theme.POS}" if v >= 0 else f"color:{theme.NEG}",
            subset=["Score"])
       .set_properties(subset=["Score"], **{"font-variant-numeric": "tabular-nums",
                                            "text-align": "right"})
       .set_properties(subset=["Metro"], **{"font-weight": "500"}),
    hide_index=True, use_container_width=True, height=520,
    column_config={
        "Rank": st.column_config.NumberColumn(
            help="Rank out of all markets (1 = best) under the speculative mid-year "
                 "recipe. No rank range is shown because this configuration failed "
                 "validation; treat the ordering as indicative at best."),
        "Score": st.column_config.TextColumn(
            help="The composite score on mid-year data. 0 is the average market; "
                 "income growth is excluded (neutral) for every market."),
        "Top strength": st.column_config.TextColumn(
            help="The theme lifting this market's speculative score the most."),
        "Top drag": st.column_config.TextColumn(
            help="The theme pulling this market's speculative score down the most.")})
theme.caption("A working view, rebuilt as data lands; unlike the validated screens it "
              "is not frozen to the registry and makes no graded claim. How the "
              "validated screens differ: How it works.")

st.markdown("Next: [the validated screen's key findings](home) · "
            "[Track record](track_record), where this failure is logged.")

theme.page_footer()
