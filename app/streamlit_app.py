"""
streamlit_app.py: entry point / router.

Multipage site per the screener-site-design skill: the sidebar carries only
navigation and the global data-edition toggle (finalized vs provisional).
Each page lives in app/views/ and answers exactly one question. All styling
comes from app/ui/theme.py; shared data from app/ui/data.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
ROOT = APP.parent
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ui import data, theme  # noqa: E402
import config               # noqa: E402

st.set_page_config(page_title="Multifamily Market Screener", layout="wide",
                   initial_sidebar_state="expanded")

theme.inject_css()   # applies the saved light/dark preference before anything renders
d = data.load()

# ---- Sidebar: brand + the global controls ----------------------------------
with st.sidebar:
    st.markdown(
        f"<div style='font-family:{theme.FONT_HEAD};font-size:19px;font-weight:600;"
        f"color:{theme.INK};line-height:1.25'>The Rent-Growth Screener</div>"
        f"<div class='cap' style='margin-bottom:.8rem'>Multifamily research · v{config.MODEL_VERSION}</div>",
        unsafe_allow_html=True)
    if d["has_spec"]:
        st.markdown("<div class='cap'>Data edition</div>", unsafe_allow_html=True)
        st.radio("Data edition", [data.FINAL_LABEL, data.SPEC_LABEL],
                 key=data.EDITION_KEY, label_visibility="collapsed")
        if data.is_spec(d):
            st.markdown(theme.badge(True, "Validated 2025 screen · proxied inputs"),
                        unsafe_allow_html=True)
            st.markdown(
                "<div class='cap' style='margin-top:.4rem'>The same frozen model on "
                "preliminary 2025 inputs (validated substitutes for migration, jobs, and "
                "income). This configuration <b>passed its pre-registered validation "
                "gate</b> on history: it kept 96.6% of the finalized model's signal and "
                f"matched the finalized top-10 on {d['overlap_mean']:.1f} of 10 names on "
                f"average ({d['overlap_last']:.0f}/10 in the hardest, shock-era year). "
                "Two earlier configurations failed and were published as negative "
                "results. Per-measure provenance: Methodology.</div>",
                unsafe_allow_html=True)
    st.markdown("<div class='cap' style='margin-top:.8rem'>Appearance</div>",
                unsafe_allow_html=True)
    st.radio("Appearance", ["Light", "Dark"], key=theme.MODE_KEY,
             horizontal=True, label_visibility="collapsed")
    # Sync Streamlit's native theme AFTER the widget renders (may rerun once).
    theme.sync_native_theme()

# ---- Pages: a report's table of contents (reading order, tools, fine print) ---
report = [
    st.Page("views/methodology.py", title="Methodology & about", default=True),
    st.Page("views/overview.py", title="Overview"),
    st.Page("views/themes.py", title="What drives the rankings"),
    st.Page("views/rankings.py", title="Full rankings"),
    st.Page("views/spotlight.py", title="Market spotlight"),
]
explore = [
    st.Page("views/metro_detail.py", title="Metro detail"),
    st.Page("views/compare.py", title="Compare markets"),
]
fine_print = [st.Page("views/track_record.py", title="Track record")]
if d["has_spec"]:
    fine_print.append(st.Page("views/acc_vs_spec.py", title="2024 vintage vs 2025 screen"))

st.navigation({"The report": report, "Explore a market": explore,
               "The fine print": fine_print}).run()
