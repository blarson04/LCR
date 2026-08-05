"""
components.py: the B-4 component library, site side (report side lives in
report/components.py; the two implement the same six components so the PDF
and the site read as one system).

1. scorecard_row      big stat callouts, each with its caveat inline
2. glossary_panel     "How to read these numbers" tinted panel
3. gate_ledger        the five gates with a ✕/✓ left rail, failures co-equal
4. tier_border_styles per-row tier-colored left border for ranked tables
5. speculative_frame  gold-bordered container around ALL speculative content
6. freeze_grade_rail  the brand timeline: solid dot = frozen, open = graded

House rules baked in: gold is reserved for speculative content; failures
render at equal or greater visual weight than passes; numbers carry context,
never adjectives.
"""

from __future__ import annotations

import html as _html

import streamlit as st

from . import theme

try:  # site context vs bare mode
    from theme import lcr_theme
except ImportError:  # pragma: no cover
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from theme import lcr_theme


def _mode() -> str:
    return "dark" if theme.current_mode() == "Dark" else "light"


# ---- 1. scorecard row -------------------------------------------------------

def scorecard_row(stats: list[tuple[str, str, str]]) -> None:
    """stats: [(value, label, context-with-caveat), ...]. Max 4."""
    cells = "".join(
        f"<div style='flex:1;min-width:9rem;background:{theme.SURFACE};"
        f"border:1px solid {theme.LINE};border-radius:8px;padding:.8rem 1rem'>"
        f"<div style='font-size:26px;font-weight:600;"
        f"font-variant-numeric:tabular-nums;color:{theme.INK}'>{value}</div>"
        f"<div style='font-size:12px;font-weight:600;letter-spacing:.06em;"
        f"text-transform:uppercase;color:{theme.MUTED};margin-top:.15rem'>"
        f"{label}</div>"
        f"<div class='cap' style='margin-top:.3rem'>{context}</div></div>"
        for value, label, context in stats[:4])
    st.markdown(f"<div style='display:flex;gap:.8rem;flex-wrap:wrap'>{cells}</div>",
                unsafe_allow_html=True)


# ---- 2. glossary panel ------------------------------------------------------

def glossary_panel(title: str, entries: list[tuple[str, str]]) -> None:
    rows = "".join(
        f"<div style='margin-top:.35rem'><span style='font-weight:600'>{term}.</span> "
        f"<span style='font-size:13.5px'>{body}</span></div>"
        for term, body in entries)
    st.markdown(
        f"<div style='background:{theme.SURFACE};border:1px solid {theme.LINE};"
        f"border-radius:8px;padding:.8rem 1.1rem;margin-bottom:1rem'>"
        f"<div style='font-family:{theme.FONT_HEAD};font-size:16px;font-weight:600'>"
        f"{title}</div>{rows}</div>",
        unsafe_allow_html=True)


# ---- 3. gate ledger ---------------------------------------------------------

def gate_ledger(gates: list[tuple[bool, str, str]]) -> None:
    """gates: [(passed, description, outcome), ...] in gate order. The ✕/✓
    rail renders failures at the same size and weight as passes (house
    rule 4: no design may soften a negative result)."""
    rows = ""
    for i, (passed, desc, outcome) in enumerate(gates, 1):
        mark, color = ("✓", theme.POS) if passed else ("✕", theme.NEG)
        rows += (
            f"<div style='display:flex;gap:.7rem;padding:.5rem 0;"
            f"border-bottom:1px solid {theme.LINE};align-items:baseline'>"
            f"<span style='font-weight:700;font-size:16px;color:{color};"
            f"min-width:1.2rem;text-align:center'>{mark}</span>"
            f"<span style='color:{theme.MUTED};font-variant-numeric:tabular-nums;"
            f"min-width:1.1rem'>{i}.</span>"
            f"<span style='flex:1;font-size:14px'>{desc}</span>"
            f"<span style='font-weight:600;font-size:13.5px;color:{color};"
            f"font-variant-numeric:tabular-nums;white-space:nowrap'>{outcome}</span>"
            f"</div>")
    st.markdown(rows, unsafe_allow_html=True)


# ---- 4. tier band helpers ---------------------------------------------------

def tier_color(tier: str) -> str:
    """The 5-step pine→tint tier scale from the tokens file."""
    scale = lcr_theme.tier_scale(_mode())
    order = ["Leading cluster", "Strong", "Mid", "Weak", "Lagging"]
    try:
        return scale[order.index(tier)]
    except ValueError:
        return theme.LINE


def tier_border_styles(tiers: list[str]) -> list[dict]:
    """Per-row style dicts (pandas Styler.apply-compatible): a thin tier-
    colored left border plus zebra tint striping."""
    t = lcr_theme.tokens(_mode())
    styles = []
    for i, tier in enumerate(tiers):
        css = f"border-left: 3px solid {tier_color(tier)};"
        if i % 2:
            css += f" background-color: {t['tint']};"
        styles.append(css)
    return styles


# ---- 5. speculative frame ---------------------------------------------------

SPEC_WARNING = "This screen has not passed validation. Read every rank loosely."


def speculative_frame(body_html: str, header_html: str | None = None) -> None:
    """The ONE gold surface (house rule: gold marks speculative content and
    nothing else). Every speculative page, chart, or table sits inside it."""
    gold = theme.PROVISIONAL
    head = header_html if header_html is not None else \
        f"<div style='font-weight:600;color:{gold}'>{SPEC_WARNING}</div>"
    st.markdown(
        f"<div style='border:2px solid {gold};border-radius:8px;"
        f"padding:.9rem 1.1rem;margin:.8rem 0;"
        f"background:{lcr_theme.rgba(gold, .06)}'>"
        f"{head}{body_html}</div>",
        unsafe_allow_html=True)


# ---- header art (B-7.3: site parity with the report's dividers) -------------

def header_art(page: str, height: int = 72) -> None:
    """The report divider art as a slim page-header band. Texture made of
    truth: it carries no readable data and needs no caption. Silently does
    nothing if the asset has not been generated yet."""
    import base64
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "assets" / "art" / f"{page}.png"
    if not path.exists():
        return
    b64 = base64.b64encode(path.read_bytes()).decode()
    st.markdown(
        f"<div style='height:{height}px;overflow:hidden;border-radius:8px;"
        f"margin-bottom:1rem'><img src='data:image/png;base64,{b64}' "
        f"style='width:100%;object-fit:cover;object-position:center;display:block'"
        f" alt=''/></div>",
        unsafe_allow_html=True)


# ---- 6. freeze-grade rail ---------------------------------------------------

def freeze_grade_rail(frozen_label: str, graded_label: str,
                      graded: bool = False, width: int = 300) -> str:
    """The brand mark as inline SVG: a rail from a solid dot (frozen) to an
    open circle (graded; filled once the grade lands). Returns HTML."""
    ink, slate = theme.INK, theme.MUTED
    fill_g = ink if graded else "none"
    y, r = 14, 5
    x0, x1 = r + 2, width - r - 2
    lbl = (f"<div style='display:flex;justify-content:space-between;"
           f"width:{width}px;font-size:11.5px;color:{slate};"
           f"font-variant-numeric:tabular-nums'>"
           f"<span>{_html.escape(frozen_label)}</span>"
           f"<span>{_html.escape(graded_label)}</span></div>")
    svg = (f"<svg width='{width}' height='24' role='img' "
           f"aria-label='frozen {_html.escape(frozen_label)}, "
           f"graded {_html.escape(graded_label)}'>"
           f"<line x1='{x0}' y1='{y}' x2='{x1}' y2='{y}' "
           f"stroke='{slate}' stroke-width='1.2'/>"
           f"<circle cx='{x0}' cy='{y}' r='{r}' fill='{ink}'/>"
           f"<circle cx='{x1}' cy='{y}' r='{r}' fill='{fill_g}' "
           f"stroke='{ink}' stroke-width='1.4'/></svg>")
    return f"<div>{svg}{lbl}</div>"
