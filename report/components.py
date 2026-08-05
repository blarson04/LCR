"""
components.py: the B-4 component library, report side (reportlab flowables).

Mirrors app/ui/components.py so the PDF and the site read as one system:

1. scorecard_row(stats)      big stat callouts with caveats inline
2. glossary_panel(...)       "How to read these numbers" ruled table
3. gate_ledger(gates)        five gates, ✕/✓ left rail, failures co-equal
4. tier_band_table(...)      ranked table with tier-colored left borders
5. speculative_frame(...)    the ONE gold-bordered surface
6. freeze_grade_rail(...)    the brand timeline as a reportlab Drawing

All colors come from theme/tokens.json via lcr_theme. Consumers register the
Inter/Serif fonts before building flowables (build_pdf.py does).
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.graphics.shapes import Circle, Drawing, Line, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from theme import lcr_theme  # noqa: E402

_T = lcr_theme.roles("light")
_TOK = lcr_theme.tokens("light")
C_INK = colors.HexColor(_T["INK"])
C_MUTED = colors.HexColor(_T["MUTED"])
C_LINE = colors.HexColor(_T["LINE"])
C_POS = colors.HexColor(_T["POS"])
C_NEG = colors.HexColor(_T["NEG"])
C_FLAG = colors.HexColor(_T["PROVISIONAL"])
C_TINT = colors.HexColor(_TOK["tint"])
C_SURFACE = colors.HexColor(_T["SURFACE"])

SPEC_WARNING = "This screen has not passed validation. Read every rank loosely."


# ---- 1. scorecard row -------------------------------------------------------

def scorecard_row(stats, width):
    """stats: [(value, label, context-with-caveat), ...] (max 4). One row of
    big tabular figures, small caps labels, caveat inline underneath."""
    stats = stats[:4]
    cw = width / len(stats)
    val = ParagraphStyle("sc_v", fontName="Inter-SB", fontSize=19, leading=22,
                         textColor=C_INK)
    lab = ParagraphStyle("sc_l", fontName="Inter-SB", fontSize=6.8, leading=9,
                         textColor=C_MUTED, spaceBefore=2)
    cav = ParagraphStyle("sc_c", fontName="Inter", fontSize=7.2, leading=9.6,
                         textColor=C_MUTED, spaceBefore=3)
    cells = [[Paragraph(v, val) for v, _, _ in stats],
             [Paragraph(l.upper(), lab) for _, l, _ in stats],
             [Paragraph(c, cav) for _, _, c in stats]]
    t = Table(cells, colWidths=[cw] * len(stats))
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.0, C_INK),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, C_LINE),
        ("TOPPADDING", (0, 0), (-1, 0), 6), ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -2), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ---- 2. glossary panel ------------------------------------------------------

def glossary_panel(entries, width, title="How to read these numbers"):
    """entries: [(term, definition), ...]. Tinted, ruled panel."""
    term_s = ParagraphStyle("gl_t", fontName="Inter-SB", fontSize=8,
                            leading=10.8, textColor=C_INK)
    body_s = ParagraphStyle("gl_b", fontName="Inter", fontSize=8,
                            leading=10.8, textColor=C_INK)
    head_s = ParagraphStyle("gl_h", fontName="Inter-SB", fontSize=10,
                            leading=13, textColor=C_INK)
    rows = [[Paragraph(title, head_s), ""]]
    rows += [[Paragraph(t, term_s), Paragraph(b, body_s)] for t, b in entries]
    t = Table(rows, colWidths=[width * 0.22, width * 0.78])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, -1), C_TINT),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, C_LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ---- 3. gate ledger ---------------------------------------------------------

def gate_ledger(gates, width):
    """gates: [(passed, description, outcome), ...] in gate order. ✕/✓ left
    rail in clay/pine; failures at identical size and weight to passes
    (house rule 4)."""
    mark_s_pass = ParagraphStyle("gm_p", fontName="Inter-SB", fontSize=11,
                                 leading=13, textColor=C_POS, alignment=1)
    mark_s_fail = ParagraphStyle("gm_f", fontName="Inter-SB", fontSize=11,
                                 leading=13, textColor=C_NEG, alignment=1)
    num_s = ParagraphStyle("gn", fontName="Inter", fontSize=8.6, leading=12,
                           textColor=C_MUTED)
    desc_s = ParagraphStyle("gd", fontName="Inter", fontSize=8.6, leading=12,
                            textColor=C_INK)
    out_p = ParagraphStyle("go_p", fontName="Inter-SB", fontSize=8.6,
                           leading=12, textColor=C_POS, alignment=2)
    out_f = ParagraphStyle("go_f", fontName="Inter-SB", fontSize=8.6,
                           leading=12, textColor=C_NEG, alignment=2)
    rows = []
    for i, (passed, desc, outcome) in enumerate(gates, 1):
        # "×" (U+00D7), not "✕" (U+2715): Inter lacks the latter glyph and a
        # silently missing fail mark would soften failures (house rule 4).
        rows.append([
            Paragraph("✓" if passed else "×",
                      mark_s_pass if passed else mark_s_fail),
            Paragraph(f"{i}.", num_s),
            Paragraph(desc, desc_s),
            Paragraph(outcome, out_p if passed else out_f)])
    t = Table(rows, colWidths=[0.32 * inch, 0.28 * inch,
                               width - 1.9 * inch, 1.3 * inch])
    t.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.7, C_INK),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, C_LINE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.7, C_INK),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ---- 4. tier band table -----------------------------------------------------

def tier_band_style(base_style: list, tiers: list[str], header_rows: int = 1):
    """Extend a TableStyle command list with per-row tier-colored left
    borders (5-step pine→tint scale) and zebra tint striping. `tiers` is in
    body-row order."""
    scale = lcr_theme.tier_scale("light")
    order = ["Leading cluster", "Strong", "Mid", "Weak", "Lagging"]
    cmds = list(base_style)
    for i, tier in enumerate(tiers):
        r = i + header_rows
        try:
            c = colors.HexColor(scale[order.index(tier)])
        except ValueError:
            c = C_LINE
        cmds.append(("LINEBEFORE", (0, r), (0, r), 2.2, c))
        if i % 2:
            cmds.append(("BACKGROUND", (0, r), (-1, r), C_TINT))
    return cmds


# ---- 5. speculative frame ---------------------------------------------------

def speculative_frame(flowables, width, header: str = SPEC_WARNING):
    """The ONE gold surface: 2px flag-gold border + standing warning header
    around any speculative flowables."""
    head_s = ParagraphStyle("sp_h", fontName="Inter-SB", fontSize=9.4,
                            leading=12.5, textColor=C_FLAG)
    inner = [Paragraph(header, head_s)] + list(flowables)
    t = Table([[inner]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 2.0, C_FLAG),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


# ---- 6. freeze-grade rail ---------------------------------------------------

def freeze_grade_rail(frozen_label: str, graded_label: str,
                      graded: bool = False, width: float = 3.0 * inch,
                      color_ink=None, color_muted=None):
    """The brand mark: a rail from a solid dot (frozen) to an open circle
    (graded; filled once the grade lands). Returns a Drawing."""
    ink = color_ink or C_INK
    muted = color_muted or C_MUTED
    h, y, r = 30, 18, 4
    d = Drawing(width, h)
    x0, x1 = r + 2, width - r - 2
    d.add(Line(x0, y, x1, y, strokeColor=muted, strokeWidth=1.1))
    d.add(Circle(x0, y, r, fillColor=ink, strokeColor=ink, strokeWidth=1))
    d.add(Circle(x1, y, r, fillColor=(ink if graded else None),
                 strokeColor=ink, strokeWidth=1.2))
    d.add(String(x0 - r, y - 13, frozen_label, fontName="Inter",
                 fontSize=6.6, fillColor=muted))
    d.add(String(x1 + r, y - 13, graded_label, fontName="Inter",
                 fontSize=6.6, fillColor=muted, textAnchor="end"))
    return d
