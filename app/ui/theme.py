"""
theme.py — design tokens + global styling (single source of truth).

Implements the screener-site-design skill: a calm, report-like site. One
accent color, serif headings, restrained tables and charts. Page code must
never hardcode a hex value — import tokens from here.

Light is the default (per the skill); a dark palette is available as a user
preference via the sidebar toggle (session key MODE_KEY). Tokens are applied
per run by inject_css(), so every page reads the active palette.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

MODE_KEY = "ui_mode"

# ---- Palettes (skill §1; dark is the same system on dark surfaces) ---------
_LIGHT = dict(
    INK="#1B2A3B", PAPER="#FBFBF9", SURFACE="#FFFFFF", LINE="#E4E6EA",
    MUTED="#66707D", ACCENT="#2C6E63", POS="#1E7F4F", NEG="#B3462E",
    PROVISIONAL="#8A6D1D",
    GRAY_SERIES=["#8E98A3", "#B9C0C8", "#D3D8DE"],
    SEQ_LOW="#E7ECEA", MAP_LAND="#EFF1ED", MAP_BORDER="#FFFFFF",
)
_DARK = dict(
    INK="#E7ECF1", PAPER="#0F151B", SURFACE="#171E26", LINE="#28313B",
    MUTED="#8C98A4", ACCENT="#45A492", POS="#3FA574", NEG="#CE6B4E",
    PROVISIONAL="#D3AC3B",
    GRAY_SERIES=["#7E8A96", "#5D6873", "#454F59"],
    SEQ_LOW="#22302B", MAP_LAND="#1B232C", MAP_BORDER="#0F151B",
)

# Module-level tokens default to light; _apply() swaps them per run.
globals().update(_LIGHT)
SEQ_SCALE = [[0.0, _LIGHT["SEQ_LOW"]], [1.0, _LIGHT["ACCENT"]]]

FONT_BODY = "Inter, sans-serif"
FONT_HEAD = "'Source Serif 4', Georgia, serif"


def current_mode() -> str:
    return st.session_state.get(MODE_KEY, "Light")


def _apply_tokens(mode: str) -> None:
    """Swap the module-level tokens to the active palette (no side effects)."""
    t = _DARK if mode == "Dark" else _LIGHT
    globals().update(t)
    global SEQ_SCALE
    SEQ_SCALE = [[0.0, t["SEQ_LOW"]], [1.0, t["ACCENT"]]]


def sync_native_theme() -> None:
    """Point Streamlit's own theme (native widgets, dataframes) at the active
    palette. Must be called AFTER the Appearance widget has rendered: it may
    trigger a rerun, and a rerun before the widget renders would drop the
    widget's state and snap the mode back."""
    mode = current_mode()
    if st.session_state.get("_applied_mode") == mode:
        return
    t = _DARK if mode == "Dark" else _LIGHT
    try:
        from streamlit import config as _cfg
        _cfg.set_option("theme.base", "dark" if mode == "Dark" else "light")
        _cfg.set_option("theme.backgroundColor", t["PAPER"])
        _cfg.set_option("theme.secondaryBackgroundColor", t["SURFACE"])
        _cfg.set_option("theme.textColor", t["INK"])
        _cfg.set_option("theme.primaryColor", t["ACCENT"])
    except Exception:
        pass
    first = "_applied_mode" not in st.session_state
    st.session_state["_applied_mode"] = mode
    if not first:
        st.rerun()


def inject_css(reading: bool = False) -> None:
    """Apply the active palette + global CSS. `reading=True` narrows the
    column for text-heavy pages."""
    _apply_tokens(current_mode())
    maxw = "860px" if reading else "1100px"
    st.markdown(f"""<style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,600&display=swap');

      html, body, [class*="css"], .stApp {{
          font-family: {FONT_BODY}; color: {INK}; font-size: 15px; }}
      .stApp {{ background: {PAPER}; }}
      #MainMenu, footer {{ visibility: hidden; }}
      [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none; }}
      .block-container {{ max-width: {maxw}; padding-top: 2.5rem; padding-bottom: 3rem; }}

      h1, h2, h3 {{ font-family: {FONT_HEAD}; color: {INK}; font-weight: 600; }}
      h1 {{ font-size: 28px; }}
      h2 {{ font-size: 20px; margin-top: 40px; }}
      h3 {{ font-size: 17px; }}

      /* Sidebar styling */
      [data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {LINE}; }}
      [data-testid="stSidebar"] * {{ font-size: 14px; }}
      /* Desktop: sidebar is ALWAYS visible — force it open whatever the
         collapsed state or Streamlit version, and remove the collapse
         controls. Phones keep the default overlay behavior. */
      @media (min-width: 992px) {{
        [data-testid="stSidebar"] {{
            display: block !important; visibility: visible !important;
            transform: none !important; margin-left: 0 !important;
            width: 252px !important; min-width: 252px !important;
        }}
        [data-testid="stSidebar"][aria-expanded="false"] {{ transform: none !important; }}
        [data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"], [data-testid="stExpandSidebarButton"] {{
            display: none !important; }}
      }}

      [data-testid="stMetric"] {{ background: {SURFACE}; border: 1px solid {LINE};
          border-radius: 8px; padding: .75rem 1rem;
          box-shadow: 0 1px 3px rgba(27,42,59,.08); }}
      [data-testid="stMetricLabel"] p {{ font-size: 12px; color: {MUTED}; }}
      [data-testid="stMetricValue"] {{ color: {INK}; font-weight: 600;
          font-variant-numeric: tabular-nums; }}

      [data-testid="stDataFrame"] {{ border: 1px solid {LINE}; border-radius: 8px;
          background: {SURFACE}; }}

      .cap {{ color: {MUTED}; font-size: 13px; line-height: 1.55; }}
      .badge-final {{ display: inline-block; font-size: 12px; font-weight: 500;
          color: {MUTED}; border: 1px solid {LINE}; border-radius: 999px;
          padding: .1rem .6rem; background: {SURFACE}; }}
      .badge-provisional {{ display: inline-block; font-size: 12px; font-weight: 600;
          color: {PROVISIONAL}; border: 1px solid {PROVISIONAL}; border-radius: 999px;
          padding: .1rem .6rem; background: rgba(138,109,29,.07); }}

      hr {{ border-color: {LINE}; }}
      [data-testid="stExpander"] {{ border: 1px solid {LINE}; border-radius: 8px;
          background: {SURFACE}; }}
    </style>""", unsafe_allow_html=True)


def caption(text: str) -> None:
    st.markdown(f"<div class='cap'>{text}</div>", unsafe_allow_html=True)


def badge(provisional: bool) -> str:
    """HTML badge; provisional data must always carry its badge (skill §4)."""
    if provisional:
        return "<span class='badge-provisional'>Provisional — based on preliminary data</span>"
    return "<span class='badge-final'>Finalized 2023</span>"


def style_fig(fig: go.Figure, height: int = 380) -> go.Figure:
    """The single chart template (skill §4): paper bg, horizontal gridlines
    only, muted axes, Inter, no legend unless the caller re-enables it."""
    fig.update_layout(
        height=height, margin=dict(l=0, r=8, t=8, b=0),
        font=dict(family="Inter, sans-serif", color=INK, size=13),
        paper_bgcolor=PAPER, plot_bgcolor=PAPER, showlegend=False,
        hoverlabel=dict(font_family="Inter, sans-serif", bgcolor=SURFACE,
                        font_color=INK, bordercolor=LINE),
    )
    fig.update_xaxes(showgrid=False, color=MUTED, linecolor=LINE, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=LINE, color=MUTED, zeroline=False)
    return fig


def page_footer() -> None:
    st.markdown(
        f"<hr style='margin-top:40px'><div class='cap'>A screening framework built on free "
        f"public data (Census, IRS, BLS, BEA, Zillow, FRED). A research screen, not "
        f"investment advice.</div>", unsafe_allow_html=True)
