"""
build_onepager.py: the distributable one-pager, one per frozen edition (C-4).

A single letter page built from the B-4 components and registry data:
masthead, scorecard row, top-10 with ranges and tiers, the gate ledger in
miniature, the freeze-grade rail with the pre-committed grade dates, footer
disclaimer, and (when config.SITE_URL is set) a link + QR to the site.

Wired into the freeze pipeline: src/registry.py calls generate() so the
one-pager lands INSIDE the frozen run directory and its hash joins the
manifest — old one-pagers can't be quietly revised any more than old ranks.

Standalone run (regenerates the current edition's copy under report/):

    .venv/Scripts/python.exe report/build_onepager.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
APP = ROOT / "app"
for _p in (str(ROOT), str(APP), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config                      # noqa: E402
from theme import lcr_theme        # noqa: E402

from reportlab.lib.pagesizes import letter                     # noqa: E402
from reportlab.lib.styles import ParagraphStyle                # noqa: E402
from reportlab.lib.units import inch                           # noqa: E402
from reportlab.lib import colors                               # noqa: E402
from reportlab.pdfbase import pdfmetrics                       # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont                   # noqa: E402
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)  # noqa: E402

import components as rl_comp       # noqa: E402

_T = lcr_theme.roles("light")
C_INK = colors.HexColor(_T["INK"])
C_MUTED = colors.HexColor(_T["MUTED"])
C_LINE = colors.HexColor(_T["LINE"])
C_POS = colors.HexColor(_T["POS"])
C_NEG = colors.HexColor(_T["NEG"])
C_PAPER = colors.HexColor(_T["PAPER"])
C_ACCENT = colors.HexColor(_T["ACCENT"])

W, H = letter
M = 0.6 * inch
CW = W - 2 * M

# The five pre-registered gates: fixed history, identical to the report and
# the site (canonical figures asserted by the smoke test).
GATES = [
    (False, "2025 screen, five estimated inputs", "74.8% · failed"),
    (False, "2025 screen, fresher jobs data", "84.66% · failed, pulled"),
    (True, "2024-vintage screen, one estimated input", "95.5% · passed"),
    (True, "2025 screen, income chained by state", "96.6% · passed"),
    (False, "Mid-year 2026 screen, five months of data", "82.7% · failed"),
]


def _register_fonts() -> None:
    fonts = HERE / "fonts"
    for name, file in [("Inter", "Inter-400.ttf"), ("Inter-Md", "Inter-500.ttf"),
                       ("Inter-SB", "Inter-600.ttf"),
                       ("Serif", "SourceSerif4-400.ttf"),
                       ("Serif-SB", "SourceSerif4-600.ttf")]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, fonts / file))


def _qr_flowable(url: str, size: float = 0.85 * inch):
    """QR code for the site link; None if the qrcode lib is unavailable."""
    try:
        import io
        import qrcode
        from reportlab.platypus import Image as RLImage
        img = qrcode.make(url, box_size=4, border=1)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return RLImage(buf, width=size, height=size)
    except ImportError:
        return None


def generate(ranking: pd.DataFrame, score_year: int, out_dir: Path,
             frozen_stamp: str | None = None) -> Path:
    """Render LCR_screen_{edition}.pdf into out_dir from a frozen ranking.

    ranking: the frozen ranking frame (cbsa_code, cbsa_title, rank, score).
    Ranges and tiers come from the committed rank_intervals.csv when the
    edition is present there.
    """
    _register_fonts()
    edition = f"{score_year}→{score_year + 3}"
    out = out_dir / f"LCR_screen_{score_year}-{score_year + 3}.pdf"

    # Ranges + tiers for this edition, if computed.
    iv_label = {2023: "2023", 2024: "vintage_2024", 2025: "current_2025"}.get(
        score_year)
    iv_path = config.PROCESSED_DIR / "rank_intervals.csv"
    rk = ranking.copy()
    rk["cbsa_code"] = rk["cbsa_code"].astype(str)
    if iv_label and iv_path.exists():
        iv = pd.read_csv(iv_path, dtype={"cbsa_code": str})
        iv = iv[iv["edition"] == iv_label][["cbsa_code", "rank_lo", "rank_hi",
                                            "tier"]]
        rk = rk.merge(iv, on="cbsa_code", how="left")

    S_title = ParagraphStyle("op_t", fontName="Serif-SB", fontSize=21,
                             leading=24, textColor=C_INK)
    S_sub = ParagraphStyle("op_s", fontName="Inter", fontSize=8.6, leading=12,
                           textColor=C_MUTED)
    S_h = ParagraphStyle("op_h", fontName="Inter-SB", fontSize=9.5, leading=12,
                         textColor=C_INK, spaceBefore=8, spaceAfter=3)
    S_cap = ParagraphStyle("op_c", fontName="Inter", fontSize=7, leading=9.6,
                           textColor=C_MUTED)

    story = []
    story.append(Paragraph(
        "L A R S O N   C A P I T A L   R E S E A R C H", ParagraphStyle(
            "op_eb", fontName="Inter-SB", fontSize=7.5, leading=10,
            textColor=C_MUTED)))
    story.append(Paragraph(f"The rent-growth screen · {edition}", S_title))
    story.append(Paragraph(
        f"The {int(rk['cbsa_code'].nunique())} largest US rental markets, "
        f"ranked by fundamentals that historically precede rent growth. Built "
        f"entirely on free public data; frozen before its outcome.", S_sub))
    story.append(Spacer(1, 6))

    # Scorecard row (canonical figures with caveats inline).
    bt = pd.read_csv(config.PROCESSED_DIR / "backtest_summary.csv")
    p3 = bt[(bt.horizon == 3) & (bt.regime == "POOLED")]
    tau = float(p3["mean_tau"].iloc[0])
    ew = pd.read_csv(config.PROCESSED_DIR / "effect_size_windows.csv")
    edge = float(ew[ew.strategy == "Composite (model)"]
                 ["top10_pp_vs_median"].mean())
    story.append(rl_comp.scorecard_row([
        (f"{tau:.2f}", "pooled tau on finalized data",
         "random guessing scores about 0"),
        (f"{edge:+.1f} pp", "top-10 edge per completed window",
         "near zero in the 2020–22 shock"),
        (f"{int(rk['cbsa_code'].nunique())}", "markets ranked",
         "every ranking frozen before its outcome"),
    ], CW))
    story.append(Spacer(1, 4))

    # Top 10 with ranges and tiers.
    story.append(Paragraph("The top 10", S_h))
    rows = [["Rank", "Metro", "Score", "Tier"]]
    top10 = rk.sort_values("rank").head(10)
    for _, r in top10.iterrows():
        rng = (f"{int(r['rank'])}  ({int(r['rank_lo'])}-{int(r['rank_hi'])})"
               if pd.notna(r.get("rank_lo")) else f"{int(r['rank'])}")
        rows.append([rng, r["cbsa_title"][:40], f"{r['score']:+.2f}",
                     str(r.get("tier", "") or "")])
    t = Table(rows, colWidths=[0.85 * inch, 3.6 * inch, 0.6 * inch,
                               2.25 * inch])
    base = [
        ("FONTNAME", (0, 0), (-1, 0), "Inter-SB"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTNAME", (0, 1), (-1, -1), "Inter"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.6),
        ("TEXTCOLOR", (0, 0), (-1, -1), C_INK),
        ("TEXTCOLOR", (2, 1), (2, -1), C_POS),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.9, C_INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, C_LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 2.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
    ]
    tiers = [str(r.get("tier", "") or "") for _, r in top10.iterrows()]
    t.setStyle(TableStyle(rl_comp.tier_band_style(base, tiers)))
    story.append(t)
    story.append(Paragraph(
        "Rank (90% range once measurement noise is accounted for) and tier; "
        "markets with overlapping ranges are roughly tied, and the tier, not "
        "the rank, is the durable claim.", S_cap))

    # Gate ledger miniature + freeze-grade rail.
    story.append(Paragraph("Five gates, three failures, two passes", S_h))
    story.append(rl_comp.gate_ledger(GATES, CW))
    story.append(Paragraph(
        "Every fresher-than-finalized configuration faced the same "
        "pre-registered gate, one attempt each, outcome published either way.",
        S_cap))
    story.append(Spacer(1, 6))
    frozen_lbl = (f"Frozen {frozen_stamp[:4]}-{frozen_stamp[4:6]}-{frozen_stamp[6:8]}"
                  if frozen_stamp else f"Frozen {date.today():%Y-%m-%d}")
    story.append(rl_comp.freeze_grade_rail(
        frozen_lbl, f"Graded early {score_year + 4}", width=CW))
    story.append(Paragraph(
        f"The {edition} calls are scored against realized rent growth when "
        f"{score_year + 3} rent data closes, whatever they show; grading dates "
        f"are pre-committed.", S_cap))

    # Link + QR (only when the public URL is configured).
    if config.SITE_URL:
        qr = _qr_flowable(config.SITE_URL)
        link_p = Paragraph(
            f"Every market's detail, the full methodology, and the complete "
            f"validation record: <a href='{config.SITE_URL}' "
            f"color='{_T['ACCENT']}'>{config.SITE_URL}</a>", S_sub)
        if qr is not None:
            lt = Table([[link_p, qr]], colWidths=[CW - 1.0 * inch, 1.0 * inch])
            lt.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(lt)
        else:
            story.append(link_p)

    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Model v{config.MODEL_VERSION} · methods documented, failures "
        f"published · free public data (Census, IRS, BLS, BEA, Zillow, FRED). "
        f"A research screen, not investment advice.", S_cap))

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(C_PAPER)
        canvas.rect(0, 0, W, H, stroke=0, fill=1)
        # Tier 2 band motif as the one-pager's spine (B-7).
        scale = lcr_theme.tier_scale("light")
        seg_h = H / len(scale)
        for i, c in enumerate(scale):
            canvas.setFillColor(colors.HexColor(c))
            canvas.rect(0, H - (i + 1) * seg_h, 0.09 * inch, seg_h,
                        stroke=0, fill=1)
        canvas.restoreState()

    doc = BaseDocTemplate(str(out), pagesize=letter, leftMargin=M,
                          rightMargin=M, topMargin=0.55 * inch,
                          bottomMargin=0.5 * inch,
                          title=f"LCR rent-growth screen {edition}",
                          author="Ben Larson")
    frame = Frame(M + 0.12 * inch, 0.5 * inch, CW - 0.12 * inch,
                  H - 1.05 * inch, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame],
                                       onPage=on_page)])
    doc.build(story)
    return out


def main() -> None:
    """Regenerate the current edition's one-pager under report/ from the
    latest frozen run (standalone convenience; freezes embed their own)."""
    idx = pd.read_csv(config.PREDICTIONS_DIR / "registry_index.csv")
    latest = idx.sort_values("timestamp_utc").iloc[-1]
    run_dir = config.PREDICTIONS_DIR / latest["timestamp_utc"]
    ranking = pd.read_csv(run_dir / "ranking.csv", dtype={"cbsa_code": str})
    out = generate(ranking, int(latest["score_year"]), HERE,
                   frozen_stamp=str(latest["timestamp_utc"]))
    print(f"done: {out}")


if __name__ == "__main__":
    main()
