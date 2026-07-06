"""
theme.py — design tokens + global styling (single source of truth).

Implements the screener-site-design skill: a calm, report-like light site.
One accent color, serif headings, restrained tables and charts. Page code must
never hardcode a hex value — import tokens from here.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# ---- Palette (skill §1) ----------------------------------------------------
INK = "#1B2A3B"          # headings, body, table text
PAPER = "#FBFBF9"        # page background
SURFACE = "#FFFFFF"      # cards, tables
LINE = "#E4E6EA"         # hairlines, dividers
MUTED = "#66707D"        # captions, secondary text, axis labels
ACCENT = "#2C6E63"       # THE brand color
POS = "#1E7F4F"          # positive data values only
NEG = "#B3462E"          # negative data values only
PROVISIONAL = "#8A6D1D"  # provisional/nowcast badge only

GRAY_SERIES = ["#8E98A3", "#B9C0C8", "#D3D8DE"]   # context series in charts
SEQ_SCALE = [[0.0, "#E7ECEA"], [1.0, ACCENT]]     # map/score sequential scale
MAP_LAND = "#EFF1ED"
MAP_BORDER = "#FFFFFF"

FONT_BODY = "Inter, sans-serif"
FONT_HEAD = "'Source Serif 4', Georgia, serif"


def inject_css(reading: bool = False) -> None:
    """Global CSS. `reading=True` narrows the column for text-heavy pages."""
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

      [data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {LINE}; }}
      [data-testid="stSidebar"] * {{ font-size: 14px; }}

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
