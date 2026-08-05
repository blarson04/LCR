"""
lcr_theme.py: the one chart/brand theme for every LCR deliverable (B-3).

Loads theme/tokens.json (the single source of truth for color and type) and
exposes:

  - tokens(mode)        the raw palette dict for "light" or "dark"
  - roles(mode)         role-named tokens (INK, PAPER, ACCENT, POS, NEG, ...)
                        matching the site's historical API
  - rgba(hex, alpha)    CSS rgba() string from a token hex
  - mpl_rcparams(mode)  matplotlib rcParams for the house chart style
  - style_ax(ax)        per-axes finishing: no top/right spines, hairline
                        horizontal-only grid at 20%-alpha slate
  - plotly_template(mode)  a plotly Template implementing the same style
  - spec_tag(ax)        the gold "speculative · failed validation" corner tag
                        baked into a matplotlib figure (governance feature:
                        screenshots must not be able to shed the warning)

Rules enforced by convention here (house style): direct labels over legends
when a chart has three series or fewer; bar values at bar ends in tabular
figures; diverging bars pine/clay anchored at 0 with a hairline zero axis;
every chart carries an eyebrow, a sentence-case takeaway title, and a caption
ending "Data through {vintage}."
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _load() -> dict:
    return json.loads((HERE / "tokens.json").read_text(encoding="utf-8"))


def tokens(mode: str = "light") -> dict:
    return _load()[mode]


def tier_scale(mode: str = "light") -> list[str]:
    return _load()["tiers"][mode]


def type_scale_pdf() -> dict:
    return _load()["type_scale_pdf"]


def roles(mode: str = "light") -> dict:
    """Role-named tokens matching the site's historical token API."""
    t = tokens(mode)
    return dict(
        INK=t["ink"], PAPER=t["paper"], SURFACE=t["surface"], LINE=t["line"],
        MUTED=t["slate"], ACCENT=t["pine"], POS=t["pine"], NEG=t["clay"],
        PROVISIONAL=t["flag"], SEQ_LOW=t["seq_low"], MAP_LAND=t["map_land"],
        MAP_BORDER=t["map_border"], GRAY_SERIES=list(t["grays"]),
        ROW_HOVER=rgba(t["ink"], 0.045 if mode == "dark" else 0.035),
    )


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgba(hex_color: str, alpha: float) -> str:
    r, g, b = _rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha})"


def grid_color(mode: str = "light") -> tuple[float, float, float, float]:
    """Slate at 20% alpha, as an mpl RGBA tuple (B-3 gridline spec)."""
    r, g, b = _rgb(tokens(mode)["slate"])
    return (r / 255, g / 255, b / 255, 0.20)


# ---- matplotlib -------------------------------------------------------------

def mpl_rcparams(mode: str = "light") -> dict:
    """House rcParams. Callers register the Inter/Source Serif fonts first
    (report/fonts/); 'Inter' falls back silently if absent."""
    t = tokens(mode)
    return {
        "font.family": "Inter",
        "text.color": t["ink"],
        "axes.edgecolor": t["line"],
        "axes.labelcolor": t["slate"],
        "xtick.color": t["slate"],
        "ytick.color": t["slate"],
        "figure.facecolor": t["paper"],
        "axes.facecolor": t["paper"],
        "savefig.facecolor": t["paper"],
        "svg.fonttype": "none",
        "axes.grid": False,
    }


def style_ax(ax, mode: str = "light", xgrid: bool = True) -> None:
    """Finish an axes to the house style: no top/right/left spines, hairline
    bottom spine, one-direction hairline grid in 20%-alpha slate."""
    t = tokens(mode)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(t["line"])
    if xgrid:
        ax.xaxis.grid(True, color=grid_color(mode), linewidth=0.7)
        ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=8)


def spec_tag(ax, mode: str = "light") -> None:
    """Bake the gold speculative tag into a figure's corner (B-3). Required
    on every chart of failed-validation content."""
    t = tokens(mode)
    ax.figure.text(
        0.995, 0.985, "SPECULATIVE · FAILED VALIDATION",
        ha="right", va="top", fontsize=6.5, color=t["flag"],
        fontweight="bold", family="Inter")


# ---- plotly -----------------------------------------------------------------

def plotly_template(mode: str = "light"):
    """The same house style as a plotly Template (registered by the caller,
    e.g. pio.templates['lcr'] = plotly_template())."""
    import plotly.graph_objects as go

    t = tokens(mode)
    return go.layout.Template(layout=go.Layout(
        font=dict(family="Inter, sans-serif", color=t["ink"], size=13),
        paper_bgcolor=t["paper"], plot_bgcolor=t["paper"],
        colorway=[t["pine"], *t["grays"]],
        margin=dict(l=0, r=8, t=8, b=0),
        showlegend=False,
        hoverlabel=dict(font_family="Inter, sans-serif", bgcolor=t["surface"],
                        font_color=t["ink"], bordercolor=t["line"]),
        xaxis=dict(showgrid=False, color=t["slate"], linecolor=t["line"],
                   zeroline=False),
        yaxis=dict(showgrid=True, gridcolor=rgba(t["slate"], 0.20),
                   color=t["slate"], zeroline=False),
    ))
