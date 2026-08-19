"""
theme.py: the site's styling layer over the shared brand tokens.

All colors come from theme/tokens.json at the repo root (handoff B-1: one
tokens file governs the PDF report and the site alike); this module maps
them to the site's role names and applies the global CSS. Page code must
never hardcode a hex value; import tokens from here.

The site ships in the light palette only (author direction 2026-08-18: dark
mode removed). Tokens are applied per run by inject_css().
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from theme import lcr_theme  # noqa: E402

# ---- Palette (theme/tokens.json, light set) --------------------------------
_LIGHT = lcr_theme.roles("light")

globals().update(_LIGHT)
SEQ_SCALE = [[0.0, _LIGHT["SEQ_LOW"]], [1.0, _LIGHT["ACCENT"]]]
# Diverging pine↔clay for SIGNED values (composite score, rent growth):
# clay below the average market, pine above, tint at 0 (B-3; use with
# color_continuous_midpoint=0 so the neutral point sits at zero).
DIV_SCALE = [[0.0, _LIGHT["NEG"]], [0.5, _LIGHT["SEQ_LOW"]],
             [1.0, _LIGHT["POS"]]]

FONT_BODY = "Inter, sans-serif"
FONT_HEAD = "'Source Serif 4', Georgia, serif"


def inject_css(reading: bool = False) -> None:
    """Apply the palette + global CSS. `reading=True` narrows the
    column for text-heavy pages."""
    maxw = "860px" if reading else "1100px"
    st.markdown(f"""<style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,600&display=swap');

      html {{ color-scheme: light; }}
      html, body, [class*="css"], .stApp {{
          font-family: {FONT_BODY}; color: {INK}; font-size: 15px; }}
      .stApp {{ background: {PAPER}; }}
      #MainMenu, footer {{ visibility: hidden; }}
      [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none; }}
      .block-container {{ max-width: {maxw}; padding-top: 2.5rem; padding-bottom: 3rem; }}

      h1, h2, h3 {{ font-family: {FONT_HEAD}; color: {INK}; font-weight: 600;
          text-wrap: balance; }}
      h1 {{ font-size: 28px; }}
      h2 {{ font-size: 20px; margin-top: 48px; }}
      h3 {{ font-size: 17px; }}
      p {{ text-wrap: pretty; }}

      .eyebrow {{ font-size: 11px; font-weight: 600; letter-spacing: .14em;
          text-transform: uppercase; color: {MUTED}; margin-bottom: .4rem; }}
      .rowline {{ padding: .42rem 0; border-bottom: 1px solid {LINE};
          transition: background-color .15s ease; }}
      .rowline:hover {{ background: {ROW_HOVER}; }}
      .footlink {{ color: {MUTED} !important; }}
      .footlink:hover {{ color: {ACCENT} !important; }}

      /* Links: accent is the stated use; sidebar nav keeps Streamlit's styling. */
      .block-container a {{ color: {ACCENT}; text-decoration: none; }}
      .block-container a:hover {{ text-decoration: underline; }}
      a:focus-visible, button:focus-visible {{
          outline: 2px solid {ACCENT}; outline-offset: 2px; }}

      @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
            animation-duration: .01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: .01ms !important;
            scroll-behavior: auto !important; }}
      }}

      /* Sidebar styling */
      [data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {LINE}; }}
      [data-testid="stSidebar"] * {{ font-size: 14px; }}
      /* Desktop: sidebar is ALWAYS visible; force it open whatever the
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
          box-shadow: 0 1px 3px {lcr_theme.rgba(INK, .08)}; }}
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
          padding: .1rem .6rem; background: {lcr_theme.rgba(PROVISIONAL, .07)}; }}

      hr {{ border-color: {LINE}; }}
      [data-testid="stExpander"] {{ border: 1px solid {LINE}; border-radius: 8px;
          background: {SURFACE}; }}
    </style>""", unsafe_allow_html=True)


def caption(text: str) -> None:
    st.markdown(f"<div class='cap'>{text}</div>", unsafe_allow_html=True)


def eyebrow(text: str) -> None:
    """Small kicker above a page title: situates the page inside the report
    (linear reading order) even when the sidebar is collapsed on a phone."""
    st.markdown(f"<div class='eyebrow'>{text}</div>", unsafe_allow_html=True)


def badge(provisional: bool, label: str | None = None) -> str:
    """HTML badge; proxied/preliminary data must always carry its badge (skill §4)."""
    if provisional:
        return (f"<span class='badge-provisional'>"
                f"{label or 'Provisional: based on preliminary data'}</span>")
    return f"<span class='badge-final'>{label or 'Finalized 2023'}</span>"


def style_fig(fig: go.Figure, height: int = 380,
              speculative: bool = False) -> go.Figure:
    """The single chart template (skill §4): paper bg, horizontal gridlines
    only, muted axes, Inter, no legend unless the caller re-enables it.

    speculative=True bakes the gold corner tag into the figure itself (B-3:
    a governance feature, so screenshots cannot shed the warning)."""
    fig.update_layout(
        height=height, margin=dict(l=0, r=8, t=18 if speculative else 8, b=0),
        font=dict(family="Inter, sans-serif", color=INK, size=13),
        paper_bgcolor=PAPER, plot_bgcolor=PAPER, showlegend=False,
        hoverlabel=dict(font_family="Inter, sans-serif", bgcolor=SURFACE,
                        font_color=INK, bordercolor=LINE),
    )
    if speculative:
        fig.add_annotation(
            xref="paper", yref="paper", x=1, y=1.0, xanchor="right",
            yanchor="bottom", showarrow=False,
            text="<b>speculative · failed validation</b>",
            font=dict(family="Inter, sans-serif", size=10, color=PROVISIONAL))
    fig.update_xaxes(showgrid=False, color=MUTED, linecolor=LINE, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=lcr_theme.rgba(MUTED, .20),
                     color=MUTED, zeroline=False)
    return fig


AUTHOR_EMAIL = "blarson5187@gmail.com"
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/blarson1105"

_ICON_MAIL = (
    "<svg width='16' height='16' viewBox='0 0 24 24' fill='none' "
    "stroke='currentColor' stroke-width='2' stroke-linecap='round' "
    "stroke-linejoin='round' style='vertical-align:-3px'>"
    "<rect x='2' y='4' width='20' height='16' rx='2'/>"
    "<path d='m22 7-10 6L2 7'/></svg>")
_ICON_LINKEDIN = (
    "<svg width='16' height='16' viewBox='0 0 24 24' fill='currentColor' "
    "style='vertical-align:-3px'>"
    "<path d='M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.86 0-2.14 "
    "1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.47-.9 1.63-1.85 3.36-1.85 3.6 "
    "0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.12 2.06 2.06 "
    "0 0 1 0 4.12zM7.12 20.45H3.55V9h3.57v11.45z'/></svg>")


def contact_links(size: str = "14px") -> str:
    """The author's contact links as icon + label anchors (HTML). One source
    for the site footer and the about section."""
    style = (f"display:inline-flex;align-items:center;gap:.3rem;"
             f"font-size:{size};color:{ACCENT};text-decoration:none")
    return (
        f"<a href='mailto:{AUTHOR_EMAIL}' style='{style}' "
        f"title='Email Ben Larson'>{_ICON_MAIL} {AUTHOR_EMAIL}</a>"
        f"<span class='cap'> · </span>"
        f"<a href='{AUTHOR_LINKEDIN}' target='_blank' rel='noopener' "
        f"style='{style}' title='Ben Larson on LinkedIn'>{_ICON_LINKEDIN} "
        f"LinkedIn</a>")


def page_footer() -> None:
    """Report-style footer: brand line, the reading order, contact, then the
    fine print."""
    links = " · ".join(
        f"<a class='footlink' href='{href}'>{label}</a>"
        for label, href in [("How it works", "how_it_works"),
                            ("Key findings", "home"),
                            ("2025→2028 outlook", "rankings"),
                            ("Track record", "track_record")])
    st.markdown(
        f"<hr style='margin-top:48px'>"
        f"<div style='display:flex;justify-content:space-between;align-items:baseline;"
        f"flex-wrap:wrap;gap:.35rem .8rem'>"
        f"<div><span style='font-family:{FONT_HEAD};font-size:15px;font-weight:600;"
        f"color:{INK}'>Larson Capital Research</span>"
        f"<span class='cap'> · the rent-growth screener</span></div>"
        f"<div class='cap'>{links}</div></div>"
        f"<div style='margin-top:.5rem'>{contact_links('13px')}</div>"
        f"<div class='cap' style='margin-top:.7rem'>A screening framework built on free "
        f"public data (Census, IRS, BLS, BEA, Zillow, FRED). A research screen, not "
        f"investment advice.</div>", unsafe_allow_html=True)
