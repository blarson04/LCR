"""
diagrams.py: explanatory inline-SVG diagrams (author request 2026-07-20).

Each function returns an HTML string built from the ACTIVE theme tokens at
call time, so the diagrams restyle with light/dark like everything else.
They must be called after theme.inject_css(). Purposeful diagrams only, per
the design skill: they explain the method, never decorate.

Wide diagrams scroll inside their own container on small screens.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
for _p in (str(APP),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ui import theme  # noqa: E402

_FONT = "Inter, sans-serif"


def _wrap(svg: str, min_width: int = 700) -> str:
    return (f"<div style='overflow-x:auto;margin:.4rem 0 .2rem'>"
            f"<div style='min-width:{min_width}px'>{svg}</div></div>")


def method_pipeline() -> str:
    """Five-stage flow: free data -> measures -> comparison -> weights -> tier."""
    boxes = [
        ("Free public data", "Census, BLS, BEA, Zillow"),
        ("Eight measures", "grouped in five themes"),
        ("Same-year comparison", "0 = the average market"),
        ("Fixed public weights", "summed into one score"),
        ("Rank and tier", "with a 90% rank range"),
    ]
    bw, bh, gap, y = 172, 64, 30, 22
    parts = []
    for i, (title, sub) in enumerate(boxes):
        x = i * (bw + gap)
        cx = x + bw / 2
        parts.append(
            f"<rect x='{x}' y='{y}' width='{bw}' height='{bh}' rx='8' "
            f"fill='{theme.SURFACE}' stroke='{theme.LINE}'/>"
            f"<text x='{cx}' y='{y + 27}' text-anchor='middle' fill='{theme.INK}' "
            f"font-family='{_FONT}' font-size='13' font-weight='600'>{title}</text>"
            f"<text x='{cx}' y='{y + 46}' text-anchor='middle' fill='{theme.MUTED}' "
            f"font-family='{_FONT}' font-size='11'>{sub}</text>")
        if i < len(boxes) - 1:
            ax = x + bw + 4
            ay = y + bh / 2
            parts.append(
                f"<line x1='{ax}' y1='{ay}' x2='{ax + gap - 12}' y2='{ay}' "
                f"stroke='{theme.MUTED}' stroke-width='1.4'/>"
                f"<polygon points='{ax + gap - 12},{ay - 4} {ax + gap - 4},{ay} "
                f"{ax + gap - 12},{ay + 4}' fill='{theme.MUTED}'/>")
    w = len(boxes) * bw + (len(boxes) - 1) * gap
    svg = (f"<svg viewBox='0 0 {w} 108' width='100%' role='img' "
           f"aria-label='How the score is built, in five steps'>"
           + "".join(parts) + "</svg>")
    return _wrap(svg)


def weights_bar() -> str:
    """The five theme weights as one proportional bar (single accent hue)."""
    segs = [("Demand", 40, 1.0), ("Supply", 25, 0.82), ("Affordability", 20, 0.64),
            ("Momentum", 10, 0.46), ("Resilience", 5, 0.28)]
    w_total, bar_y, bar_h = 960, 30, 28
    parts, x = [], 0.0
    for name, pct, op in segs:
        seg_w = w_total * pct / 100.0
        cx = x + seg_w / 2
        parts.append(
            f"<rect x='{x:.0f}' y='{bar_y}' width='{seg_w:.0f}' height='{bar_h}' "
            f"fill='{theme.ACCENT}' fill-opacity='{op}'/>")
        if seg_w >= 150:
            parts.append(
                f"<text x='{cx:.0f}' y='{bar_y + 19}' text-anchor='middle' "
                f"fill='{theme.PAPER}' font-family='{_FONT}' font-size='12' "
                f"font-weight='600'>{name} {pct}%</text>")
        x += seg_w
    # small segments label below, staggered so they never collide, with a
    # leader tick from each segment's center
    mom_cx = w_total * (0.85 + 0.10 / 2)
    res_cx = w_total * (0.95 + 0.05 / 2)
    parts.append(
        f"<line x1='{mom_cx:.0f}' y1='{bar_y + bar_h}' x2='{mom_cx:.0f}' "
        f"y2='{bar_y + bar_h + 8}' stroke='{theme.MUTED}' stroke-width='1'/>"
        f"<text x='{mom_cx:.0f}' y='{bar_y + bar_h + 22}' text-anchor='middle' "
        f"fill='{theme.MUTED}' font-family='{_FONT}' font-size='12'>Momentum 10%</text>")
    parts.append(
        f"<line x1='{res_cx:.0f}' y1='{bar_y + bar_h}' x2='{res_cx:.0f}' "
        f"y2='{bar_y + bar_h + 26}' stroke='{theme.MUTED}' stroke-width='1'/>"
        f"<text x='{w_total:.0f}' y='{bar_y + bar_h + 40}' text-anchor='end' "
        f"fill='{theme.MUTED}' font-family='{_FONT}' font-size='12'>Resilience 5%</text>")
    svg = (f"<svg viewBox='0 0 {w_total} 106' width='100%' role='img' "
           f"aria-label='Share of the score carried by each theme'>"
           + "".join(parts) + "</svg>")
    return _wrap(svg)


def walkforward_timeline(start: int = 2019, horizon: int = 3) -> str:
    """One completed validation window: frozen at publication, graded later."""
    w, axis_y = 960, 66
    x0, x1 = 70, 900
    end = start + horizon
    parts = [
        f"<line x1='{x0}' y1='{axis_y}' x2='{x1 - 8}' y2='{axis_y}' "
        f"stroke='{theme.LINE}' stroke-width='2'/>"
        f"<polygon points='{x1 - 10},{axis_y - 5} {x1},{axis_y} "
        f"{x1 - 10},{axis_y + 5}' fill='{theme.MUTED}'/>"]
    for i in range(horizon + 1):
        x = x0 + (x1 - x0) * i / horizon
        parts.append(
            f"<line x1='{x:.0f}' y1='{axis_y - 4}' x2='{x:.0f}' y2='{axis_y + 4}' "
            f"stroke='{theme.MUTED}' stroke-width='1.2'/>"
            f"<text x='{x:.0f}' y='{axis_y + 24}' text-anchor='middle' "
            f"fill='{theme.MUTED}' font-family='{_FONT}' font-size='12'>{start + i}</text>")
    parts.append(
        f"<circle cx='{x0}' cy='{axis_y}' r='6' fill='{theme.ACCENT}'/>"
        f"<text x='{x0}' y='{axis_y - 30}' text-anchor='start' fill='{theme.INK}' "
        f"font-family='{_FONT}' font-size='13' font-weight='600'>Ranking published "
        f"and frozen</text>"
        f"<text x='{x0}' y='{axis_y - 13}' text-anchor='start' fill='{theme.MUTED}' "
        f"font-family='{_FONT}' font-size='11'>using only data available in {start}</text>")
    parts.append(
        f"<text x='{x1}' y='{axis_y - 30}' text-anchor='end' fill='{theme.INK}' "
        f"font-family='{_FONT}' font-size='13' font-weight='600'>Graded against what "
        f"happened</text>"
        f"<text x='{x1}' y='{axis_y - 13}' text-anchor='end' fill='{theme.MUTED}' "
        f"font-family='{_FONT}' font-size='11'>realized rent growth, {start} to {end}"
        f"</text>")
    svg = (f"<svg viewBox='0 0 {w} 100' width='100%' role='img' "
           f"aria-label='How a validation window works'>"
           + "".join(parts) + "</svg>")
    return _wrap(svg)
