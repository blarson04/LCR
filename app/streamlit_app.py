"""
streamlit_app.py — entry point / router.

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
            st.markdown(theme.badge(provisional=True), unsafe_allow_html=True)
            st.markdown("<div class='cap' style='margin-top:.4rem'>Uses preliminary and "
                        "proxy data that will be revised.</div>", unsafe_allow_html=True)
    st.markdown("<div class='cap' style='margin-top:.8rem'>Appearance</div>",
                unsafe_allow_html=True)
    st.radio("Appearance", ["Light", "Dark"], key=theme.MODE_KEY,
             horizontal=True, label_visibility="collapsed")
    # Sync Streamlit's native theme AFTER the widget renders (may rerun once).
    theme.sync_native_theme()

# ---- Pages ------------------------------------------------------------------
pages = [
    st.Page("views/methodology.py", title="About & methodology", default=True),
    st.Page("views/rankings.py", title="Rankings"),
    st.Page("views/metro_detail.py", title="Metro detail"),
    st.Page("views/compare.py", title="Compare markets"),
]
if d["has_spec"]:
    pages.append(st.Page("views/acc_vs_spec.py", title="Accurate vs speculative"))
pages.append(st.Page("views/track_record.py", title="Track record"))

st.navigation(pages).run()
