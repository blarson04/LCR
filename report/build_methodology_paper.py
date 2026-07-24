"""
build_methodology_paper.py: the academic-style methodology paper
(furton.ai methodology-paper format as the inspiration: title block, italic
abstract, contents, numbered sections, dark-header tables, primary sources).

Every number is computed from the same frozen artifacts as the site and the
research report, so the paper regenerates with each refresh.

Run:  .venv/Scripts/python.exe report/build_methodology_paper.py
Out:  report/Rent-Growth-Screen_Methodology-Paper.pdf
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
APP = ROOT / "app"
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config                      # noqa: E402
from ui import data                # noqa: E402

INK, MUTED, ACCENT, LINE = "#1B2A3B", "#66707D", "#2C6E63", "#E4E6EA"
POS, NEG, PROV = "#1E7F4F", "#B3462E", "#8A6D1D"
FONTS = HERE / "fonts"
OUT = HERE / "Rent-Growth-Screen_Methodology-Paper.pdf"
P = config.PROCESSED_DIR

# ============================ numbers ========================================
print("loading artifacts...")
d = data.load()
ed = data.edition(d)
rank = ed["rank"].sort_values("rank").reset_index(drop=True)
N = len(rank)
top_city = rank.iloc[0]["cbsa_title"].split(",")[0]

bt = pd.read_csv(P / "backtest_summary.csv")


def _bt(h, r, c="mean_tau"):
    m = bt[(bt.horizon == h) & (bt.regime == r)]
    return float(m[c].iloc[0]) if len(m) else float("nan")


tau3 = _bt(3, "POOLED")
tau1 = _bt(1, "POOLED")
tau_pc = _bt(3, "pre_covid")
tau_sh = _bt(3, "shock")
p10_pool = _bt(3, "POOLED", "mean_precision@10")
p10_pc = _bt(3, "pre_covid", "mean_precision@10")

ut = pd.read_csv(P / "uncertainty_tau.csv")
full_row = ut[ut.ranking == "full"].iloc[0]
tau_lo, tau_hi = float(full_row["lo"]), float(full_row["hi"])

bl = pd.read_csv(P / "baseline_comparison.csv")
ib = pd.read_csv(P / "industry_baseline.csv").iloc[0]
ew = pd.read_csv(P / "effect_size_windows.csv")
comp = ew[ew.strategy == "Composite (model)"]
mom = ew[ew.strategy == "Momentum (trailing rent)"]
pp_pooled = float(comp["top10_pp_vs_median"].mean())
pp_mom = float(mom["top10_pp_vs_median"].mean())

pk = pd.read_csv(P / "precision_k.csv")
p20 = float(pk[pk.pred_year.astype(str) == "POOLED"]["precision_at_20"].iloc[0])

tu = pd.read_csv(P / "temporal_uncertainty.csv").iloc[0]
g25 = pd.read_csv(P / "nowcast" / "gate2025_summary.csv")
g25p = g25[(g25.horizon == 3) & (g25.regime == "POOLED")].iloc[0]
g26 = pd.read_csv(P / "nowcast" / "gate2026_summary.csv").iloc[0]
v06 = pd.read_csv(P / "nowcast" / "midyear_v06_accuracy.csv").iloc[0]
p3g = pd.read_csv(P / "p3_gate_summary.csv").iloc[0]
t3 = pd.read_csv(P / "tier3_gates.csv")
iv = pd.read_csv(P / "rank_intervals.csv")
iv_cur = iv[iv.edition == "current_2025"]
n_lead = int((iv_cur.tier == "Leading cluster").sum())

TODAY = date.today().strftime("%B %Y")

# ============================ document =======================================
from reportlab.lib import colors                               # noqa: E402
from reportlab.lib.pagesizes import letter                     # noqa: E402
from reportlab.lib.styles import ParagraphStyle                # noqa: E402
from reportlab.lib.units import inch                           # noqa: E402
from reportlab.pdfbase import pdfmetrics                       # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont                   # noqa: E402
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)  # noqa: E402

pdfmetrics.registerFont(TTFont("Serif", FONTS / "SourceSerif4-400.ttf"))
pdfmetrics.registerFont(TTFont("Serif-SB", FONTS / "SourceSerif4-600.ttf"))
pdfmetrics.registerFont(TTFont("Inter", FONTS / "Inter-400.ttf"))
pdfmetrics.registerFont(TTFont("Inter-SB", FONTS / "Inter-600.ttf"))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-SB",
                              italic="Serif", boldItalic="Serif-SB")

C_INK, C_MUTED = colors.HexColor(INK), colors.HexColor(MUTED)
C_ACCENT, C_LINE = colors.HexColor(ACCENT), colors.HexColor(LINE)
W, H = letter
M = 1.0 * inch
CW = W - 2 * M

S = dict(
    title=ParagraphStyle("title", fontName="Serif-SB", fontSize=17, leading=22,
                         textColor=C_INK, alignment=1, spaceAfter=4),
    brand=ParagraphStyle("brand", fontName="Serif-SB", fontSize=15, leading=18,
                         textColor=C_ACCENT, alignment=1, spaceAfter=10),
    subtitle=ParagraphStyle("subtitle", fontName="Serif", fontSize=11.5, leading=15,
                            textColor=C_ACCENT, alignment=1, spaceAfter=6),
    authorline=ParagraphStyle("authorline", fontName="Serif", fontSize=11, leading=15,
                              textColor=C_INK, alignment=1, spaceAfter=2),
    h1=ParagraphStyle("h1", fontName="Serif-SB", fontSize=13, leading=17,
                      textColor=C_INK, spaceBefore=16, spaceAfter=5),
    h2=ParagraphStyle("h2", fontName="Serif-SB", fontSize=10.8, leading=14,
                      textColor=C_INK, spaceBefore=10, spaceAfter=3),
    body=ParagraphStyle("body", fontName="Serif", fontSize=10, leading=14.2,
                        textColor=C_INK, spaceAfter=6, alignment=4),
    bullet=ParagraphStyle("bullet", fontName="Serif", fontSize=10, leading=14.2,
                          textColor=C_INK, leftIndent=16, bulletIndent=4,
                          spaceAfter=4, alignment=4),
    abstract=ParagraphStyle("abstract", fontName="Serif", fontSize=10, leading=14.2,
                            textColor=C_INK, spaceAfter=6, alignment=4,
                            leftIndent=6, rightIndent=6),
    cap=ParagraphStyle("cap", fontName="Serif", fontSize=8.5, leading=11.5,
                       textColor=C_MUTED, spaceBefore=2, spaceAfter=8),
    toc=ParagraphStyle("toc", fontName="Serif", fontSize=10.5, leading=17,
                       textColor=C_INK),
    cell=ParagraphStyle("cell", fontName="Serif", fontSize=9, leading=11.5,
                        textColor=C_INK),
    cellhead=ParagraphStyle("cellhead", fontName="Inter-SB", fontSize=8, leading=10.5,
                            textColor=colors.white),
)


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(C_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(M, H - 0.62 * inch, W - M, H - 0.62 * inch)
    canvas.setFont("Serif", 8.5)
    canvas.setFillColor(C_MUTED)
    canvas.drawRightString(W - M, H - 0.55 * inch,
                           "The Rent-Growth Screen · Methodology and Validation Paper")
    canvas.setFont("Serif", 9)
    canvas.drawCentredString(W / 2, 0.5 * inch, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


doc = BaseDocTemplate(str(OUT), pagesize=letter, leftMargin=M, rightMargin=M,
                      topMargin=0.9 * inch, bottomMargin=0.85 * inch,
                      title="The Rent-Growth Screen: A Methodology and Validation Paper",
                      author="Ben Larson")
frame = Frame(M, 0.8 * inch, CW, H - 1.75 * inch, id="main")
doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=on_page)])


def tbl(rows, widths, *, fontsize=9, header_fill=C_INK):
    body_rows = [[Paragraph(str(c), S["cellhead"]) if i == 0
                  else (Paragraph(c, S["cell"]) if isinstance(c, str) and len(c) > 28
                        else c)
                  for c in row] for i, row in enumerate(rows)]
    t = Table(body_rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_fill),
        ("FONTNAME", (0, 1), (-1, -1), "Serif"),
        ("FONTSIZE", (0, 1), (-1, -1), fontsize),
        ("TEXTCOLOR", (0, 1), (-1, -1), C_INK),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, C_LINE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.6, C_LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


story = []

# ============================ title page =====================================
story += [
    Spacer(1, 40),
    Paragraph("THE RENT-GROWTH SCREEN", S["brand"]),
    Paragraph("Screening US Rental Markets for Future Rent Growth "
              "with Free Public Data", S["title"]),
    Paragraph("A Methodology and Validation Paper · Results and Negative "
              "Results Disclosed", S["subtitle"]),
    Paragraph("Ben Larson<super>1</super> · Indiana University", S["authorline"]),
    Paragraph(TODAY, S["authorline"]),
    Spacer(1, 18),
    Paragraph("<b>Abstract</b>", ParagraphStyle("abshead", parent=S["h2"],
                                                spaceBefore=0)),
    Paragraph(
        f"<i>Commercial real-estate research runs on expensive proprietary data. This "
        f"project asks whether a disciplined screen built entirely on free public "
        f"sources (Census, IRS, BLS, BEA, Zillow, FRED) can still identify, in "
        f"advance, which of the {N} largest US rental markets will deliver the "
        f"strongest rent growth over the following three years. The screen scores "
        f"each market on eight validated measures of demand, supply, affordability, "
        f"momentum, and resilience, with hand-set published weights and no "
        f"statistical fitting. Walk-forward validation over 2016-2022 windows yields "
        f"a pooled top-weighted rank agreement (weighted Kendall's tau) of "
        f"{tau3:.2f} with realized three-year rent growth "
        f"(95% CI [{tau_lo:.2f}, {tau_hi:.2f}]); the screen's top ten out-grew the "
        f"median market by {pp_pooled:+.1f} percentage points per window, and an "
        f"industry-style equal-weight conditions index rebuilt from the same free "
        f"data scores {float(ib['tau_3y']):.2f} on the identical task. The project's "
        f"distinguishing discipline is governance: every configuration faces a "
        f"pre-registered, single-attempt validation gate; five gates have run, three "
        f"failed, and all outcomes are published; every published ranking is frozen "
        f"to an immutable registry with its resolution dates pre-committed. This "
        f"paper documents the data, the measures, the weighting argument, the "
        f"validation design and results, the governance rules, and the honest "
        f"limits of the approach.</i>", S["abstract"]),
    Spacer(1, 26),
    Table([[""]], colWidths=[2.2 * inch], rowHeights=[0.5],
          style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.5, C_MUTED)])),
    Paragraph("<super>1</super> Economics and applied mathematics, Indiana "
              "University. The interactive companion site carries every ranking, "
              "the full validation record, and the public decision log.",
              S["cap"]),
    PageBreak(),
]

# ============================ contents =======================================
story += [Paragraph("Contents", S["h1"])]
for num, name in [
        ("1.", "Introduction and Research Question"),
        ("2.", "Data and the Vintage Discipline"),
        ("3.", "The Eight Measures"),
        ("4.", "Weighting: The Case Against Fitting"),
        ("5.", "Validation Design"),
        ("6.", "Validation Results"),
        ("7.", "Governance: Gates, Freezes, and Negative Results"),
        ("8.", "The Current Screen and the Speculative Outlook"),
        ("9.", "Communicating Uncertainty"),
        ("10.", "Limitations"),
        ("11.", "The Forward Test"),
        ("", "Primary Sources")]:
    story.append(Paragraph(f"{num} {name}", S["toc"]))
story.append(PageBreak())

# ============================ 1. introduction ================================
story += [
    Paragraph("1. Introduction and Research Question", S["h1"]),
    Paragraph(
        "Institutional real-estate investors buy market selection: proprietary rent "
        "series, pipeline databases, and research teams that rank metros for "
        "acquisition. The premise of this project is a specific, testable question: "
        "how much of that edge is actually in the data access, and how much is in "
        "the discipline? Put concretely: can a screen built exclusively from free "
        "public sources rank the largest US rental markets by their <i>future</i> "
        "three-year rent growth well enough to be useful?", S["body"]),
    Paragraph(
        "The claim under examination is deliberately narrow. The screen does not "
        "forecast rent levels, returns, or any single market's path; it ranks "
        "markets cross-sectionally by fundamentals that have historically preceded "
        "strong rent growth, and it is graded on whether that ranking agreed with "
        "what subsequently happened. Throughout, the object is a screen (a "
        "disciplined starting point for where to look closer), not investment "
        "advice, and the paper reports the conditions under which the screen "
        "fails as prominently as those under which it works.", S["body"]),
    Paragraph(
        "The project is public by design. Every method is documented in a running "
        "decision log, every published ranking is frozen to an immutable registry "
        "before its outcome window closes, failed experiments are published "
        "alongside successes, and the dates on which the outstanding forecasts "
        "will be graded are pre-committed. The methodological posture borrows from "
        "pre-registration practice: specifications are logged before computation, "
        "each gets one attempt, and first results are final.", S["body"]),

    # ======================== 2. data ========================================
    Paragraph("2. Data and the Vintage Discipline", S["h1"]),
    Paragraph("2.1 Universe and sources", S["h2"]),
    Paragraph(
        f"The universe is every US metropolitan area with at least 500,000 "
        f"residents and continuous rent-index coverage: {N} metros. All inputs are "
        f"free and public: Census population estimates, housing-unit estimates, "
        f"and building permits; IRS county-to-county migration; BLS employment "
        f"(QCEW and CES) and industry mix; BEA personal income; Zillow rent and "
        f"home-value indices; and FRED mortgage rates. No paid source enters the "
        f"model at any point.", S["body"]),
    Paragraph("2.2 The vintage rule", S["h2"]),
    Paragraph(
        "No accuracy number is reported without its data vintage. Federal metro "
        "data arrives with lags of months (permits, employment) to two years "
        "(income, migration), and revisions are common, so the project maintains "
        "two published editions at all times: a fully finalized vintage edition "
        "and a current edition built with validated fast-publishing substitutes "
        "(Section 8). Backtests additionally report a real-time variant using "
        "only inputs a user could have held at the time, alongside the "
        "finalized-data ceiling no live user ever had.", S["body"]),
    Paragraph("2.3 Boundary corruption and the automated quality regime", S["h2"]),
    Paragraph(
        "The project's hardest data lesson is on the record: the 2023 federal "
        "metro-boundary redraw (and its predecessors) silently corrupted every "
        "CBSA-keyed federal series in the panel. Agencies mixed old and new "
        "boundaries across years, manufacturing fake growth prints, and twice an "
        "artifact briefly held the #1 rank. Systematic sweeps found 35 metros "
        "requiring employment rebuilt from county files on current boundaries and "
        "36 requiring population and housing rebuilt from county estimates; the "
        "repairs moved individual ranks substantially while headline accuracy "
        "barely moved, which is the signature of data hygiene rather than model "
        "change. Since July 2026 a blocking quality regime cross-checks every "
        "input against an independent sister series (QCEW vs CES, ZHVI vs FHFA, "
        "ACS vs PEP), flags distributional outliers and boundary changes, asserts "
        "golden-metro regression values on every rebuild, and mechanically "
        "prevents publication until every flag is dispositioned in the public "
        "decision log.", S["body"]),

    # ======================== 3. measures ====================================
    Paragraph("3. The Eight Measures", S["h1"]),
    Paragraph(
        "Each market-year is scored on eight measures, chosen to capture the "
        "fundamentals that precede rent growth and de-duplicated after a "
        "correlation audit (an earlier ten-measure version folded population "
        "growth into migration and the multifamily pipeline into total permitting). "
        "Within each year, every measure is standardized across markets (a "
        "z-score), so nationwide swings cancel and only relative standing counts; "
        "measures where more is worse are sign-flipped; a market missing a measure "
        "receives the neutral cross-market average, disclosed wherever it occurs.",
        S["body"]),
]

meas_rows = [["Measure", "Definition", "Direction"],
             ["Net domestic migration", "net migrants / population", "higher better"],
             ["Job growth", "YoY total employment growth", "higher better"],
             ["Income growth", "YoY per-capita income growth", "higher better"],
             ["Permits to stock", "permitted units / housing stock", "lower better"],
             ["Rent to income", "annual rent / per-capita income", "lower better"],
             ["Cost to own vs rent", "mortgage payment on the typical home / rent",
              "higher better"],
             ["Trailing rent growth", "YoY rent-index growth", "higher better"],
             ["Employment diversity", "1 - industry concentration (HHI)",
              "higher better"]]
story += [tbl(meas_rows, [1.75 * inch, 3.15 * inch, 1.15 * inch]),
          Paragraph("Table 1. The eight measures. YoY growth always uses the exact "
                    "prior calendar year, so panel gaps never manufacture multi-year "
                    "jumps.", S["cap"])]

# ======================== 4. weighting =======================================
story += [
    Paragraph("4. Weighting: The Case Against Fitting", S["h1"]),
    Paragraph(
        "The composite score is a fixed weighted sum: Demand 40% (migration 20, "
        "jobs 12, income 8), Supply 25 (permits to stock, counted inversely), "
        "Affordability 20 (rent to income 12, cost to own vs rent 8), Momentum 10 "
        "(trailing rent growth), Resilience 5 (employment diversity). The weights "
        "are set by judgment, published in full, and never statistically fitted.",
        S["body"]),
    Paragraph(
        "The no-fitting rule is a deliberate methodological position, not an "
        "omission. With roughly 110 markets and six overlapping evaluation "
        "windows, fitted weights would be overfitting by construction; the "
        "decision-science literature on improper linear models (Dawes 1979) shows "
        "that sensible fixed weights routinely match or beat fitted ones out of "
        "sample in small noisy panels. The project measured this locally: a "
        "weight-scheme study found the accuracy landscape flat across reasonable "
        "hypothesis-driven schemes, and equal weighting over the same eight "
        "measures scores within a few hundredths of the hand-set scheme. The "
        "conclusion the project draws, and states publicly, is that the weights "
        "are not the intellectual property; the component selection and the "
        "validation discipline are.", S["body"]),

    # ======================== 5. validation design ============================
    Paragraph("5. Validation Design", S["h1"]),
    Paragraph("5.1 Walk-forward protocol", S["h2"]),
    Paragraph(
        "For each scoring year T, the screen is computed from data available for "
        "year T and compared against realized rent growth from T to T+3 (the "
        "primary horizon; one-year results are reported as a contrast). The model "
        "never sees the future; prediction years roll forward across 2016-2022, "
        "giving six completed three-year windows through 2025. Realized growth is "
        "winsorized at the 1st and 99th percentile within each window. Windows "
        "are tagged by regime (pre-COVID, the 2020-22 shock, normalization) and "
        "reported per-regime as well as pooled, because the pooled average "
        "conceals the single most decision-relevant fact about the screen "
        "(Section 6.3).", S["body"]),
    Paragraph("5.2 Metrics", S["h2"]),
    Paragraph(
        "The primary metric is top-weighted Kendall's tau, weighted by realized "
        "rank so that agreement on the true top markets counts most; 0 means no "
        "relationship, 1 perfect agreement. The headline supplementary metric is "
        "precision@10: the share of the screen's top ten that landed in the top "
        "quartile of realized growth. Because one top-10 miss moves precision@10 "
        f"by ten points, precision@20 is co-reported once ({p20:.2f} pooled beside "
        f"{p10_pool:.2f}); the story is unchanged at half the lump size. For "
        "readers who think in units of money rather than rank statistics, every "
        "result is also translated into percentage points of rent growth: the "
        "average excess three-year growth of the screen's top ten over the median "
        "market.", S["body"]),
    Paragraph("5.3 Statistical machinery", S["h2"]),
    Paragraph(
        "Confidence intervals use a metro-cluster bootstrap (metros resampled "
        "with replacement, B=800-1,000, fixed seed), computed paired across "
        "competing rankings so that gaps between strategies get their own "
        "intervals. Temporal fragility is probed separately: a per-window range, "
        "a leave-one-window-out jackknife, and a state-cluster bootstrap that "
        "treats whole states as the unit of chance. All thresholds, seeds, and "
        "consequence rules are frozen in dated decision-log entries before any "
        "computation runs.", S["body"]),
    PageBreak(),

    # ======================== 6. results =====================================
    Paragraph("6. Validation Results", S["h1"]),
    Paragraph("6.1 Headline accuracy", S["h2"]),
    Paragraph(
        f"On finalized data, the pooled three-year weighted tau is "
        f"<b>{tau3:.3f}</b> (95% metro-cluster CI [{tau_lo:.3f}, {tau_hi:.3f}]); "
        f"precision@10 is {p10_pool:.2f}. Pre-COVID windows, the cleanest test, "
        f"score {tau_pc:.3f} with precision@10 of {p10_pc:.2f}. At the one-year "
        f"horizon tau rises to {tau1:.3f}, but the screen's purpose is the "
        f"three-year horizon, where fundamentals rather than momentum carry the "
        f"signal. In plain units, the screen's top ten out-grew the median market "
        f"by <b>{pp_pooled:+.1f} percentage points</b> of three-year rent growth "
        f"per completed window (rent momentum alone: {pp_mom:+.1f}). The "
        f"real-time variant, using only data a user could have held, retains "
        f"{float(g25p['mean_tau_ps']):.2f} pooled against the finalized "
        f"{float(g25p['mean_tau_fin']):.2f}.", S["body"]),
    Paragraph("6.2 Against baselines and industry practice", S["h2"]),
]

bl_rows = [["Ranking rule", "3-yr tau", "Precision@10"]]
for _, r in bl.iterrows():
    bl_rows.append([str(r["model"]), f"{r['tau_3y']:.2f}", f"{r['prec_3y']:.0%}"])
story += [tbl(bl_rows, [3.7 * inch, 1.2 * inch, 1.2 * inch]),
          Paragraph("Table 2. All rows computed on finalized data, identical years "
                    "and markets.", S["cap"]),
          Paragraph(
              f"The most consequential row is the industry-style index: a faithful "
              f"free-data replica of a leading published opportunity matrix (ten "
              f"equal-weighted condition categories; six replicable from free "
              f"sources), frozen before its single run. It scores "
              f"{float(ib['tau_3y']):.2f} at this task, below simple persistence, "
              f"and the composite's edge over it is reliable (gap "
              f"{float(ib['gap_tau_3y']):+.2f}, 95% CI [{float(ib['gap_ci_lo']):+.2f}, "
              f"{float(ib['gap_ci_hi']):+.2f}]). The project's own pre-registered "
              f"prediction about that replica (that it would be re-packaged rent "
              f"momentum) was wrong and is published as such: its correlation with "
              f"trailing rent growth is only ~0.2. The honest diagnosis is that "
              f"untested conditions components dilute predictive signal. The claim "
              f"is about equal-weight conditions indices at this prediction task, "
              f"not about any vendor's product at its own task, and the replica "
              f"omits four proprietary categories that may be its originator's "
              f"strongest.", S["body"]),
          Paragraph("6.3 The regime caveat, stated as a result", S["h2"]),
          Paragraph(
              f"In the 2021-22 shock windows the screen's agreement falls to "
              f"{tau_sh:.2f} and the top-ten edge to roughly zero, while pure "
              f"momentum flips firmly negative. Across the "
              f"{int(tu['win3_n'])} observed windows tau ranges from "
              f"{float(tu['win3_min']):+.2f} to {float(tu['win3_max']):+.2f}; no "
              f"single window drives the pooled result (jackknife range "
              f"[{float(tu['jk3_min']):.2f}, {float(tu['jk3_max']):.2f}]), and "
              f"under the stricter state-cluster bootstrap the pooled interval "
              f"widens to [{float(tu['state_tau_lo']):.2f}, "
              f"{float(tu['state_tau_hi']):.2f}]. A published ex-ante rule flags "
              f"elevated-uncertainty scoring years (national rent growth above a "
              f"fixed threshold, the only two historical firings being 2021-22) "
              f"wherever rankings are shown.", S["body"]),

          # ==================== 7. governance ================================
          Paragraph("7. Governance: Gates, Freezes, and Negative Results", S["h1"]),
          Paragraph(
              "The governance layer is the project's central methodological claim: "
              "results are only as credible as the process that could have "
              "falsified them. Five rules bind every change.", S["body"]),
          Paragraph(
              "<b>Pre-registration with one attempt.</b> No predictive computation "
              "may run on a candidate before a dated log entry freezes its "
              "definition, gate, thresholds, consequence, and attempt count; a "
              "specification logged on day T may not run before day T+1 (the "
              "cooling-off rule); at most one new attempt per federal data-release "
              "cycle; first results are final, with no re-runs and no tuning.",
              S["bullet"], bulletText="•"),
          Paragraph(
              "<b>Frozen registry.</b> Every published run is frozen with its "
              "scores, inputs, and settings, and never edited; prior runs are "
              "annotated, never deleted; comparisons against earlier editions read "
              "from the registry so history cannot be silently rewritten.",
              S["bullet"], bulletText="•"),
          Paragraph(
              "<b>Negative results publish.</b> Failed gates, rejected proxies, and "
              "wrong pre-registered predictions are published with the same "
              "prominence as successes.", S["bullet"], bulletText="•"),
          Paragraph(
              "<b>Blocking data QA.</b> Publication is mechanically impossible "
              "until the automated quality report for the exact panel build is "
              "clean or fully dispositioned (Section 2.3).",
              S["bullet"], bulletText="•"),
          Paragraph(
              "<b>Claims match evidence.</b> A headline claim that fails its own "
              "published sensitivity analysis may not ship; the honest object (a "
              "tier, a range) ships instead.", S["bullet"], bulletText="•"),
          Paragraph("7.1 The gate record", S["h2"]),
]

gate_rows = [["#", "Configuration", "Retention", "Top-10 overlap", "Verdict"],
             ["1", "2025 screen, five estimated inputs", "74.8%", "-", "Fail"],
             ["2", "2025 screen, fresher jobs data", "84.66%", "-",
              "Fail (by 0.34)"],
             ["3", "2024-vintage screen, one estimated input", "95.5%", "8.3 / 10",
              "Pass"],
             ["4", "2025 screen, state-chained income", "96.6%", "7.4 / 10",
              "Pass"],
             ["5", f"Mid-year 2026 screen, five months of data",
              f"{float(g26['retention']):.1%}",
              f"{float(g26['mean_top10_overlap']):.1f} / 10", "Fail (both bars)"]]
story += [tbl(gate_rows, [0.35 * inch, 2.6 * inch, 1.0 * inch, 1.2 * inch,
                          1.15 * inch]),
          Paragraph("Table 3. The five pre-registered configuration gates (bar: "
                    "retain at least 85% of the finalized model's signal and match "
                    "its top ten on at least 7 of 10 names). Attempt 2 was pulled "
                    "rather than rounded up; attempt 5 ships only as a labeled "
                    "speculative outlook (Section 8.2).", S["cap"]),
          Paragraph(
              f"Separately, nine candidate measures and model variants have faced "
              f"one-shot gates (five external signals including operating income "
              f"and absorption indices; vacancy and unemployment changes; a "
              f"three-year smoothing of the noisy growth inputs that proved "
              f"reliably calmer but reliably less accurate, retention "
              f"{float(p3g['tau_multi_year']) / float(p3g['tau_current']):.0%} "
              f"with a loss CI entirely below zero). Zero were adopted; the model "
              f"has remained frozen at v2.0.0 throughout, and every rejection is "
              f"published with its numbers.", S["body"]),
          PageBreak(),

          # ==================== 8. current screen ============================
          Paragraph("8. The Current Screen and the Speculative Outlook", S["h1"]),
          Paragraph("8.1 The validated 2025-2028 screen", S["h2"]),
          Paragraph(
              "The slowest inputs publish one to two years late, so a current "
              "screen requires substitutes. Each substitute was validated "
              "individually against its finalized counterpart before the "
              "configuration as a whole faced a gate: Census population-estimate "
              "migration for IRS migration (rank agreement ~0.9), monthly CES "
              "employment for QCEW (0.90-0.96 per year), and the scoring-year "
              "income level chained from the prior finalized metro level by the "
              "primary state's income growth (0.60 mean rank agreement, versus "
              "0.11 for the flat carry it replaced). This configuration is gate "
              "attempt 4 in Table 3; its pseudo-test retained 96.6% of the "
              "finalized model's signal, and the resulting 2025-2028 screen "
              f"(currently led by {top_city}) is the published current edition. "
              "One disclosed asymmetry: the fix that produced attempt 4 was "
              "diagnosed on the same historical windows it was then scored on, so "
              "its genuine test is the frozen forward call (Section 11).",
              S["body"]),
          Paragraph("8.2 The speculative mid-year outlook", S["h2"]),
          Paragraph(
              f"Reader demand for the newest possible view led to a mid-year 2026 "
              f"recipe built from five months of data. Its gate (attempt 5) "
              f"failed both bars, and per the consequence frozen in advance it "
              f"ships only as a clearly separated speculative surface carrying "
              f"its measured accuracy as a warning beside every number. A "
              f"subsequent author-directed revision added a quarterly state "
              f"income chain (instrument agreement 0.464, measured before "
              f"adoption) and was re-measured descriptively, not re-gated: "
              f"retention {float(v06['retention']):.1%}, top-10 overlap "
              f"{float(v06['mean_top10_overlap']):.1f}/10. The surface remains "
              f"speculative and cannot earn the validated label without a "
              f"properly gated future specification; the episode is reported "
              f"because it illustrates the governance design under product "
              f"pressure: the recipe could improve, the label could not.",
              S["body"]),

          # ==================== 9. uncertainty ===============================
          Paragraph("9. Communicating Uncertainty", S["h1"]),
          Paragraph(
              f"Exact ranks oversell precision. The two fastest-moving inputs "
              f"(job and income growth) agree between editions at Spearman 0.29 "
              f"and 0.28 respectively, while every other input agrees above 0.83; "
              f"measured against that noise, each market's rank is re-computed "
              f"1,000 times with those inputs jittered at their measured "
              f"edition-to-edition agreement, and the published object is the "
              f"90% rank interval plus a deterministic tier (a market joins the "
              f"leading cluster when its interval reaches the top ten and its "
              f"median rank sits in the top quarter; {n_lead} markets currently "
              f"qualify). Editions themselves turn over: even fully finalized "
              f"consecutive years historically keep only one to six of the same "
              f"top-ten names, a fact stated on every ranking surface. The "
              f"interval captures input-measurement noise only; model error is "
              f"what the walk-forward record measures.", S["body"]),

          # ==================== 10. limitations ==============================
          Paragraph("10. Limitations", S["h1"]),
          Paragraph("The rent indices measure asking rents on advertised units, "
                    "not signed leases or renewals.", S["bullet"], bulletText="•"),
          Paragraph("No capital-markets or operating-cost data enters the model "
                    "(sale prices, cap rates, insurance, taxes); rent growth "
                    "stands in for profitability, and insurance-cost shocks of the "
                    "kind Florida experienced move multifamily economics in ways "
                    "no rent-side measure captures. Repeated searches for a free, "
                    "full-coverage expense signal have failed their acquisition "
                    "audits and are documented as such.", S["bullet"],
                    bulletText="•"),
          Paragraph("Weights are judgment-set and stress-tested, not estimated; "
                    "the defense is robustness, not optimality.",
                    S["bullet"], bulletText="•"),
          Paragraph("In shock regimes the screen loses most of its edge "
                    "(Section 6.3); it is a screen for normal conditions and "
                    "says so wherever it is shown.", S["bullet"], bulletText="•"),
          Paragraph("Six overlapping windows are directional evidence, not "
                    "significance; the cross-sectional intervals are conditional "
                    "on the history that happened to occur.",
                    S["bullet"], bulletText="•"),

          # ==================== 11. forward test =============================
          Paragraph("11. The Forward Test", S["h1"]),
          Paragraph(
              "Backtests, however carefully walk-forwarded, share their historical "
              "sample with the researchers who designed the model. The registry is "
              "the project's only genuine out-of-sample instrument, and its "
              "scoring is pre-committed and un-skippable: the frozen 2023-vintage "
              "calls are graded when finalized 2026 rent data closes (mid-2027), "
              "and the frozen 2024-vintage and 2025-2028 screens when their "
              "windows close (2028 and early 2029 respectively), with the results "
              "published whatever they show. The resolution machinery is already "
              "built and reports, today, exactly which data each frozen run still "
              "awaits. This paper will be revised with those resolutions; per the "
              "project's rules, the revision will be disclosed, not silent.",
              S["body"]),

          Paragraph("Primary Sources", S["h1"]),
          Paragraph("US Census Bureau: Population Estimates Program, Housing Unit "
                    "Estimates, Building Permits Survey, American Community "
                    "Survey; Office of Management and Budget metro delineations.",
                    S["bullet"], bulletText="•"),
          Paragraph("Internal Revenue Service: county-to-county migration flows.",
                    S["bullet"], bulletText="•"),
          Paragraph("Bureau of Labor Statistics: Quarterly Census of Employment "
                    "and Wages; Current Employment Statistics.",
                    S["bullet"], bulletText="•"),
          Paragraph("Bureau of Economic Analysis: county and state personal "
                    "income (annual and quarterly).", S["bullet"], bulletText="•"),
          Paragraph("Zillow Research: Observed Rent Index (ZORI) and Home Value "
                    "Index (ZHVI); FHFA house-price indices (quality assurance "
                    "only); Federal Reserve Economic Data: 30-year mortgage "
                    "rates.", S["bullet"], bulletText="•"),
          Paragraph("Dawes, R. M. (1979). The robust beauty of improper linear "
                    "models in decision making. American Psychologist, 34(7), "
                    "571-582.", S["bullet"], bulletText="•"),
          Paragraph("Arbor Realty Trust and Chandan Economics, Top Markets for "
                    "Multifamily Investment Report (Spring 2026): the published "
                    "industry matrix whose construction the Section 6.2 replica "
                    "follows.", S["bullet"], bulletText="•"),
          ]

print("building pdf...")
doc.build(story)
print(f"done: {OUT}")
