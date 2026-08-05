"""
build_pdf.py: the report as a PDF, built from the same frozen outputs as the
site (app/ui/data.py in bare mode), for sharing off-platform (LinkedIn).

Arbor-style spine: cover, key findings, overview + top 10, the full ranked
chart, map + tiers, the five themes, spotlight, track record, methodology,
appendix table, about + disclaimer. Brand tokens match app/ui/theme.py.

Run:  .venv/Scripts/python.exe report/build_pdf.py
Out:  report/Larson_Capital_Research-Report.pdf
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
APP = ROOT / "app"
for _p in (str(ROOT), str(APP)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config                      # noqa: E402
from ui import data                # noqa: E402  (bare mode: no Streamlit runtime)
from theme import lcr_theme        # noqa: E402
from theme import hero_art         # noqa: E402

# ---- Brand tokens (theme/tokens.json, the single source of truth) -----------
_T = lcr_theme.roles("light")
INK, PAPER, SURFACE = _T["INK"], _T["PAPER"], _T["SURFACE"]
LINE, MUTED, ACCENT = _T["LINE"], _T["MUTED"], _T["ACCENT"]
POS, NEG, GRAY = _T["POS"], _T["NEG"], _T["GRAY_SERIES"][0]
SEQ_LOW = _T["SEQ_LOW"]
FLAG = _T["PROVISIONAL"]
_TOKENS_TINT = lcr_theme.tokens("light")["tint"]

FONTS = HERE / "fonts"
BUILD = HERE / "_build"
BUILD.mkdir(exist_ok=True)
OUT = HERE / "Larson_Capital_Research-Report.pdf"

for f in FONTS.glob("*.ttf"):
    font_manager.fontManager.addfont(str(f))
plt.rcParams.update(lcr_theme.mpl_rcparams("light"))


def style_ax(ax, xgrid: bool = True):
    """The house chart template (theme/lcr_theme.py): hairline grid one way
    only, recessive axes, no spines except a light bottom."""
    lcr_theme.style_ax(ax, "light", xgrid=xgrid)


# ============================ data ===========================================
print("loading model outputs...")
d = data.load()
ed = data.edition(d)
rank = ed["rank"].sort_values("rank").reset_index(drop=True)
rank[["strength_1", "strength_2"]] = rank.apply(
    lambda r: pd.Series(data.top_strengths(r)), axis=1)
rank[["strength", "drag"]] = rank.apply(
    lambda r: pd.Series(data.strength_drag(r)), axis=1)
YEAR, HORIZON = ed["year"], ed["horizon"]
N = len(rank)
top = rank.iloc[0]
top_city = top["cbsa_title"].split(",")[0]

ew = pd.read_csv(config.PROCESSED_DIR / "effect_size_windows.csv")
comp = ew[ew.strategy == "Composite (model)"].sort_values("pred_year")
mom = ew[ew.strategy == "Momentum (trailing rent)"].sort_values("pred_year")
pp_pooled = float(comp["top10_pp_vs_median"].mean())
pp_mom = float(mom["top10_pp_vs_median"].mean())
ib = pd.read_csv(config.PROCESSED_DIR / "industry_baseline.csv")
ind_tau, full_tau = float(ib["tau_3y"].iloc[0]), float(ib["full_tau_3y"].iloc[0])

has_tiers = ("tier" in rank.columns) and (rank["tier"].fillna("") != "").any()
n_cluster = int((rank["tier"] == "Leading cluster").sum()) if has_tiers else 0
n_in = int((rank.head(10)["tier"] == "Leading cluster").sum()) if has_tiers else 0

# Prior edition (C-1): frozen ranks + that edition's 90% ranges, for the
# change column and the spotlight's edition-over-edition line.
prior_df, prior_label = data.prior_edition(d)
show_change = len(prior_df) > 0

m3_path = config.PROCESSED_DIR / "nowcast" / "gate2025_summary.csv"
if not m3_path.exists():
    m3_path = config.PROCESSED_DIR / "nowcast" / "m3_summary.csv"
m3 = pd.read_csv(m3_path) if m3_path.exists() else pd.DataFrame()
bl = pd.read_csv(config.PROCESSED_DIR / "baseline_comparison.csv")

# A-11: the report may not build if any headline number drifts from the
# canonical-figures YAML (tests/canonical_figures.yaml).
sys.path.insert(0, str(ROOT / "tests"))
import copy_qa                     # noqa: E402
_canon_problems = copy_qa.canonical_figure_mismatches(
    rank, d["backtest"], config.PROCESSED_DIR, config.INDICATORS)
if _canon_problems:
    raise SystemExit("canonical figures out of sync:\n  "
                     + "\n  ".join(_canon_problems))
print("canonical figures: OK")

TODAY = date.today().strftime("%B %Y")


# ============================ charts =========================================
def short(title: str, n: int = 26) -> str:
    place, _, state = title.rpartition(",")
    return f"{place.split('-')[0][:n]},{state[:3]}"


def chart_all_markets() -> Path:
    """Every market against the average, two columns (Arbor's Chart 1)."""
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 8.9))
    halves = (rank.iloc[:(N + 1) // 2], rank.iloc[(N + 1) // 2:])
    for ax, half in zip(axes, halves):
        vals = half["score"].tolist()
        labels = [f"{int(r['rank'])}  {short(r['cbsa_title'], 20)}" for _, r in half.iterrows()]
        colors = [POS if v >= 0 else NEG for v in vals]
        y = range(len(half))
        ax.barh(y, vals, color=colors, height=0.62)
        ax.set_yticks(list(y), labels)
        ax.invert_yaxis()
        ax.axvline(0, color=MUTED, linewidth=0.8)
        style_ax(ax)
        ax.tick_params(axis="y", labelsize=6.3)
        ax.tick_params(axis="x", labelsize=7)
        lim = max(abs(rank["score"].min()), abs(rank["score"].max())) * 1.12
        ax.set_xlim(-lim, lim)
    fig.suptitle("")
    fig.tight_layout(pad=0.4)
    p = BUILD / "all_markets.png"
    fig.savefig(p, dpi=300)
    plt.close(fig)
    return p


def chart_map() -> Path:
    """The site's score map, exported via plotly + kaleido."""
    import plotly.express as px
    import plotly.graph_objects as go
    mp = rank.merge(d["coords"], on="cbsa_code", how="left")
    fig = px.scatter_geo(mp, lat="lat", lon="lon", color="score", scope="usa",
                         size=[8] * len(mp), size_max=12,
                         color_continuous_scale=[[0.0, NEG], [0.5, SEQ_LOW],
                                                 [1.0, POS]],
                         color_continuous_midpoint=0)
    fig.update_traces(marker=dict(line=dict(width=0.6, color=_T["MAP_BORDER"])))
    fig.update_geos(showland=True, landcolor=_T["MAP_LAND"], showlakes=False,
                    subunitcolor=_T["MAP_BORDER"], countrycolor=_T["MAP_BORDER"],
                    coastlinecolor=_T["MAP_BORDER"], bgcolor="rgba(0,0,0,0)",
                    showframe=False)
    fig.add_trace(go.Scattergeo(
        lat=[v[0] for v in data.STATE_CENTROIDS.values()],
        lon=[v[1] for v in data.STATE_CENTROIDS.values()],
        text=list(data.STATE_CENTROIDS), mode="text",
        textfont=dict(family="Inter", size=9, color=MUTED),
        hoverinfo="skip", showlegend=False))
    fig.update_layout(font=dict(family="Inter", color=INK, size=13),
                      paper_bgcolor="white", plot_bgcolor="white",
                      margin=dict(l=0, r=0, t=0, b=0),
                      coloraxis_colorbar=dict(title="Score", thickness=10, len=0.6,
                                              tickfont=dict(color=MUTED)))
    p = BUILD / "map.png"
    # kaleido's subprocess is unreliable on this machine; render via playwright
    # (the project's proven screenshot path) instead.
    html = BUILD / "map.html"
    fig.update_layout(width=980, height=560)
    fig.write_html(str(html), include_plotlyjs=True, full_html=True,
                   config={"staticPlot": True})
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        page = b.new_page(viewport={"width": 980, "height": 560},
                          device_scale_factor=3)
        page.goto(html.resolve().as_uri())
        # the geo layer paints only after plotly fetches its US topojson;
        # wait for actual land paths, not just the plot div.
        page.wait_for_selector(".geo path", timeout=30000)
        page.wait_for_timeout(1000)
        page.screenshot(path=str(p))
        b.close()
    return p


def chart_theme(bucket: str) -> Path:
    col = f"bucket_{bucket}"
    sub = rank[["cbsa_title", col]].dropna().sort_values(col, ascending=False)
    show = pd.concat([sub.head(5), sub.tail(5)])
    vals = show[col].tolist()
    labels = [short(t, 22) for t in show["cbsa_title"]]
    fig, ax = plt.subplots(figsize=(5.4, 2.0))
    ax.barh(range(len(show)), vals, color=[POS if v >= 0 else NEG for v in vals], height=0.62)
    ax.set_yticks(range(len(show)), labels)
    ax.invert_yaxis()
    ax.axvline(0, color=MUTED, linewidth=0.8)
    style_ax(ax)
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout(pad=0.3)
    p = BUILD / f"theme_{bucket}.png"
    fig.savefig(p, dpi=300)
    plt.close(fig)
    return p


def chart_effect() -> Path:
    fig, ax = plt.subplots(figsize=(6.6, 2.3))
    vals = comp["top10_pp_vs_median"].tolist()
    years = comp["pred_year"].astype(int).tolist()
    ax.bar(range(len(vals)), vals, color=[POS if v >= 0 else NEG for v in vals], width=0.62)
    ax.set_xticks(range(len(vals)), [str(y) for y in years])
    ax.axhline(0, color=MUTED, linewidth=0.8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.spines["left"].set_visible(False)
    ax.yaxis.grid(True, color=LINE, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=8)
    for i, v in enumerate(vals):
        # negative bars get their label above the zero line, clear of the
        # year labels beneath the axis
        ax.annotate(f"{v:+.1f}", (i, max(v, 0)), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=7.5, color=INK)
    ax.set_ylabel("Top-10 edge (pp of rent growth)", fontsize=8)
    ax.set_xlabel("3-year window, by start year", fontsize=8)
    fig.tight_layout(pad=0.3)
    p = BUILD / "effect.png"
    fig.savefig(p, dpi=300)
    plt.close(fig)
    return p


def chart_trend() -> Path | None:
    tr = d["rent_trend"]
    code = top["cbsa_code"]
    if not len(tr) or not (tr.cbsa_code == code).any():
        return None
    mt = tr[tr.cbsa_code == code].set_index("month")["yoy"]
    us = tr[tr.cbsa_code == "US"].set_index("month")["yoy"]
    j = pd.concat([mt.rename("m"), us.rename("u")], axis=1).dropna().reset_index()
    j["month"] = pd.to_datetime(j["month"])
    fig, ax = plt.subplots(figsize=(6.6, 2.4))
    ax.plot(j["month"], j["u"], color=GRAY, linewidth=1.4)
    ax.plot(j["month"], j["m"], color=ACCENT, linewidth=2.0)
    ax.annotate("National median", (j["month"].iloc[-1], j["u"].iloc[-1]),
                textcoords="offset points", xytext=(6, -4), fontsize=7.5, color=MUTED)
    ax.annotate(top_city.split("-")[0], (j["month"].iloc[-1], j["m"].iloc[-1]),
                textcoords="offset points", xytext=(6, 4), fontsize=7.5, color=ACCENT)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(LINE)
    ax.yaxis.grid(True, color=LINE, linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=8)
    ax.margins(x=0.02)
    fig.tight_layout(pad=0.3)
    fig.subplots_adjust(right=0.82)
    p = BUILD / "trend.png"
    fig.savefig(p, dpi=300)
    plt.close(fig)
    return p


def chart_pipeline() -> Path:
    """Five-stage method flow (the site's pipeline diagram, print edition)."""
    from matplotlib.patches import FancyArrow, FancyBboxPatch
    boxes = [("Free public data", "Census, BLS, BEA, Zillow"),
             ("Eight measures", "grouped in five themes"),
             ("Same-year comparison", "0 = the average market"),
             ("Fixed public weights", "summed into one score"),
             ("Rank and tier", "with a 90% rank range")]
    fig, ax = plt.subplots(figsize=(7.0, 0.9))
    ax.set_xlim(-0.04, 5.42)
    ax.set_ylim(0, 1)
    ax.axis("off")
    bw = 0.94
    step = 1.11
    for i, (title, sub) in enumerate(boxes):
        x = i * step
        ax.add_patch(FancyBboxPatch(
            (x, 0.12), bw, 0.76, boxstyle="round,pad=0.015,rounding_size=0.045",
            facecolor="white", edgecolor=LINE, linewidth=0.9))
        ax.text(x + bw / 2, 0.60, title, ha="center", va="center",
                fontsize=6.6, fontweight=600, color=INK)
        ax.text(x + bw / 2, 0.33, sub, ha="center", va="center",
                fontsize=5.7, color=MUTED)
        if i < len(boxes) - 1:
            ax.add_patch(FancyArrow(
                x + bw + 0.035, 0.5, step - bw - 0.10, 0, width=0.006,
                head_width=0.085, head_length=0.04, color=MUTED,
                length_includes_head=True))
    p = BUILD / "pipeline.png"
    fig.savefig(p, dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    return p


def chart_weights_bar() -> Path:
    """The five theme weights as one proportional single-hue bar."""
    segs = [("Demand", 40, 1.0), ("Supply", 25, 0.82), ("Affordability", 20, 0.64),
            ("Momentum", 10, 0.46), ("Resilience", 5, 0.28)]
    fig, ax = plt.subplots(figsize=(7.0, 0.72))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 1)
    ax.axis("off")
    x = 0.0
    for name, pct, alpha in segs:
        ax.barh(0.62, pct, left=x, height=0.5, color=ACCENT, alpha=alpha)
        if pct >= 20:
            ax.text(x + pct / 2, 0.62, f"{name} {pct}%", ha="center", va="center",
                    fontsize=6.8, fontweight=600, color="white")
        x += pct
    ax.plot([87.5, 87.5], [0.30, 0.37], color=MUTED, linewidth=0.7)
    ax.text(87.5, 0.16, "Momentum 10%", ha="center", va="center",
            fontsize=6.2, color=MUTED)
    ax.plot([97.5, 97.5], [0.30, 0.37], color=MUTED, linewidth=0.7)
    ax.text(100, 0.01, "Resilience 5%", ha="right", va="center",
            fontsize=6.2, color=MUTED)
    p = BUILD / "weights_bar.png"
    fig.savefig(p, dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    return p


def chart_timeline(start: int = 2019, horizon: int = 3) -> Path:
    """One validation window: frozen at publication, graded three years on."""
    fig, ax = plt.subplots(figsize=(7.0, 1.05))
    ax.set_xlim(-0.25, horizon + 0.35)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.annotate("", xy=(horizon + 0.28, 0.42), xytext=(-0.1, 0.42),
                arrowprops=dict(arrowstyle="-|>", color=MUTED, linewidth=1.2))
    for i in range(horizon + 1):
        ax.plot([i, i], [0.37, 0.47], color=MUTED, linewidth=0.9)
        ax.text(i, 0.18, str(start + i), ha="center", fontsize=6.8, color=MUTED)
    ax.plot(0, 0.42, "o", markersize=6, color=ACCENT, zorder=5)
    ax.text(0, 0.80, "Ranking published and frozen", ha="left", fontsize=7.2,
            fontweight=600, color=INK)
    ax.text(0, 0.60, f"using only data available in {start}", ha="left",
            fontsize=6.2, color=MUTED)
    ax.text(horizon, 0.80, "Graded against what happened", ha="right",
            fontsize=7.2, fontweight=600, color=INK)
    ax.text(horizon, 0.60, f"realized rent growth, {start} to {start + horizon}",
            ha="right", fontsize=6.2, color=MUTED)
    p = BUILD / "timeline.png"
    fig.savefig(p, dpi=300, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    return p


print("rendering charts...")
P_ALL = chart_all_markets()
P_MAP = chart_map()
P_THEMES = {b: chart_theme(b) for b in data.BUCKETS}
P_EFFECT = chart_effect()
P_TREND = chart_trend()
P_PIPE = chart_pipeline()
P_WBAR = chart_weights_bar()
P_TLINE = chart_timeline()

# ---- Hero art (B-7 Tier 1: generated from this edition's frozen data) -------
print("rendering hero art...")
_top10 = rank.head(10)
P_COVER_ART = hero_art.save(
    hero_art.cover_backdrop(rank["score"].tolist()),
    BUILD / "art_cover.png", transparent=True)
P_DIV_KEY = hero_art.save(
    hero_art.divider_top10_ranges(_top10["rank_lo"].tolist(),
                                  _top10["rank_hi"].tolist(),
                                  _top10["rank"].tolist()),
    BUILD / "art_div_key.png")
P_DIV_THEMES = hero_art.save(
    hero_art.divider_weights([40, 25, 20, 10, 5]),
    BUILD / "art_div_themes.png")
P_DIV_TRACK = hero_art.save(
    hero_art.divider_edge_windows(comp["top10_pp_vs_median"].tolist()),
    BUILD / "art_div_track.png")
P_DIV_APPX = hero_art.save(
    hero_art.divider_tier_strip(rank["tier"].tolist() if has_tiers else []),
    BUILD / "art_div_appendix.png")
P_DIV_SPEC = hero_art.save(
    hero_art.divider_speculative(), BUILD / "art_div_spec.png")

# Site parity (B-7.3): the same generated assets serve as page-header art on
# the corresponding site pages; committed so the deployed site has them.
_SITE_ART = APP / "assets" / "art"
_SITE_ART.mkdir(parents=True, exist_ok=True)
import shutil                       # noqa: E402
for _src, _dst in [(P_DIV_KEY, "home.png"), (P_DIV_APPX, "rankings.png"),
                   (P_DIV_TRACK, "track_record.png"),
                   (P_DIV_THEMES, "how_it_works.png"),
                   (P_DIV_SPEC, "outlook_2026.png")]:
    shutil.copyfile(_src, _SITE_ART / _dst)


# ============================ document =======================================
from reportlab.lib.pagesizes import letter                     # noqa: E402
from reportlab.lib.styles import ParagraphStyle                # noqa: E402
from reportlab.lib.units import inch                           # noqa: E402
from reportlab.lib import colors                               # noqa: E402
from reportlab.pdfbase import pdfmetrics                       # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont                   # noqa: E402
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Spacer, Table, TableStyle)  # noqa: E402
from reportlab.platypus import Paragraph as _Paragraph  # noqa: E402

from typo import smart              # noqa: E402
import components as rl_comp        # noqa: E402  (report/components.py, B-4)


def Paragraph(text, style, **kw):
    """Every paragraph passes through the typographic-hygiene filter."""
    return _Paragraph(smart(text), style, **kw)

pdfmetrics.registerFont(TTFont("Inter", FONTS / "Inter-400.ttf"))
pdfmetrics.registerFont(TTFont("Inter-Md", FONTS / "Inter-500.ttf"))
pdfmetrics.registerFont(TTFont("Inter-SB", FONTS / "Inter-600.ttf"))
pdfmetrics.registerFont(TTFont("Serif", FONTS / "SourceSerif4-400.ttf"))
pdfmetrics.registerFont(TTFont("Serif-SB", FONTS / "SourceSerif4-600.ttf"))
pdfmetrics.registerFontFamily("Inter", normal="Inter", bold="Inter-SB", italic="Inter")

C_INK, C_MUTED, C_ACCENT = colors.HexColor(INK), colors.HexColor(MUTED), colors.HexColor(ACCENT)
C_LINE, C_PAPER = colors.HexColor(LINE), colors.HexColor(PAPER)
C_POS, C_NEG = colors.HexColor(POS), colors.HexColor(NEG)

W, H = letter
M = 0.75 * inch
CW = W - 2 * M

# B-1 type scale: 30/20/14/10.5/9, eyebrow 8.5 letterspaced.
_TS = lcr_theme.type_scale_pdf()
S = dict(
    h1=ParagraphStyle("h1", fontName="Serif-SB", fontSize=_TS["h1"],
                      leading=_TS["h1"] * 1.12, textColor=C_INK, spaceAfter=7),
    h2=ParagraphStyle("h2", fontName="Serif-SB", fontSize=_TS["h2"],
                      leading=_TS["h2"] * 1.2, textColor=C_INK, spaceBefore=16,
                      spaceAfter=5, keepWithNext=1),
    h3=ParagraphStyle("h3", fontName="Inter-SB", fontSize=_TS["h3"],
                      leading=_TS["h3"] * 1.25, textColor=C_INK, spaceBefore=10,
                      spaceAfter=3, keepWithNext=1),
    body=ParagraphStyle("body", fontName="Inter", fontSize=_TS["body"],
                        leading=_TS["body"] * 1.42, textColor=C_INK, spaceAfter=6),
    bullet=ParagraphStyle("bullet", fontName="Inter", fontSize=_TS["body"],
                          leading=_TS["body"] * 1.42, textColor=C_INK,
                          leftIndent=12, bulletIndent=2, spaceAfter=5),
    cap=ParagraphStyle("cap", fontName="Inter", fontSize=_TS["caption"],
                       leading=_TS["caption"] * 1.35, textColor=C_MUTED,
                       spaceAfter=8),
    eyebrow=ParagraphStyle("eyebrow", fontName="Inter-SB",
                           fontSize=_TS["eyebrow"], leading=_TS["eyebrow"] * 1.3,
                           textColor=C_MUTED, spaceAfter=2),
)


def eyebrow(txt):
    return Paragraph(f"<font name='Inter-SB'>{txt.upper()}</font>",
                     ParagraphStyle("eb", parent=S["eyebrow"],
                                    textColor=C_MUTED, tracking=1.4))


def hr(width=CW, space_before=4, space_after=8):
    t = Table([[""]], colWidths=[width], rowHeights=[0.6])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.6, C_LINE)]))
    return [Spacer(1, space_before), t, Spacer(1, space_after)]


# ---- Section divider band (B-1/B-7): pine field, paper-color serif title,
# this section's own data as linework art. Structure is information: every
# divider carries a real graphic from the frozen edition.
C_PINE = colors.HexColor(_T["ACCENT"])
_DIV_KICK = ParagraphStyle("div_kick", fontName="Inter-SB", fontSize=8.5,
                           leading=11, textColor=C_PAPER)
_DIV_TITLE = ParagraphStyle("div_title", fontName="Serif-SB", fontSize=26,
                            leading=30, textColor=C_PAPER)
_DIV_SUB = ParagraphStyle("div_sub", fontName="Inter", fontSize=9,
                          leading=12.2, textColor=C_PAPER)


def divider(kicker: str, title: str, art_path, art_ratio: float = 2.1 / 8.5,
            subtitle: str | None = None):
    """A half-page section divider: pine band with kicker, serif title, and
    the section's data rendered as paper-color linework."""
    # Letterspaced eyebrow: NBSPs, because reportlab collapses runs of
    # ASCII spaces and Inter lacks the em-space glyph.
    spaced = " ".join(kicker.upper()).replace(" ", "  ")
    rows = [[Paragraph(spaced, _DIV_KICK)],
            [Paragraph(title, _DIV_TITLE)]]
    if subtitle:
        rows.append([Paragraph(subtitle, _DIV_SUB)])
    rows.append([Image(str(art_path), width=CW - 0.5 * inch,
                       height=(CW - 0.5 * inch) * art_ratio)])
    t = Table(rows, colWidths=[CW])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_PINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (0, 0), 18),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 18),
        ("ALIGN", (0, -1), (0, -1), "CENTER"),
    ]))
    return [t, Spacer(1, 16)]


def draw_rail_mark(canvas, x, y, width=0.24 * inch, r=1.7):
    """The freeze-grade rail reduced to its geometry (B-7 rail motif): line,
    solid dot (frozen), open circle (graded). The running brand mark."""
    canvas.saveState()
    canvas.setStrokeColor(C_MUTED)
    canvas.setLineWidth(0.8)
    canvas.line(x + r, y, x + width - r, y)
    canvas.setFillColor(C_MUTED)
    canvas.circle(x + r, y, r, stroke=0, fill=1)
    canvas.circle(x + width - r, y, r, stroke=1, fill=0)
    canvas.restoreState()


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(C_MUTED)
    canvas.setFont("Inter", 7)
    canvas.drawString(M, 0.45 * inch,
                      "Larson Capital Research  ·  a research screen, not investment advice")
    canvas.drawRightString(W - M, 0.45 * inch, f"{canvas.getPageNumber()}")
    canvas.setStrokeColor(C_LINE)
    canvas.setLineWidth(0.6)
    canvas.line(M, 0.62 * inch, W - M, 0.62 * inch)
    draw_rail_mark(canvas, M, H - 0.475 * inch)
    canvas.setFont("Inter-SB", 6.6)
    canvas.setFillColor(C_MUTED)
    canvas.drawRightString(W - M, H - 0.5 * inch,
                           f"LARSON CAPITAL RESEARCH · {TODAY.upper()}")
    canvas.restoreState()


def on_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(C_PAPER)
    canvas.rect(0, 0, W, H, stroke=0, fill=1)
    canvas.setStrokeColor(C_ACCENT)
    canvas.setLineWidth(2)
    canvas.line(M, H - 1.5 * inch, M + 0.42 * inch, H - 1.5 * inch)
    canvas.setFont("Inter-SB", 8.5)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(M, H - 1.78 * inch,
                      f"LARSON CAPITAL RESEARCH  ·  {TODAY.upper()}")
    canvas.setFont("Serif-SB", 34)
    canvas.setFillColor(C_INK)
    canvas.drawString(M, H - 2.45 * inch, "The Rent-Growth")
    canvas.drawString(M, H - 2.95 * inch, "Screen")
    canvas.setFont("Serif-SB", 14)
    canvas.setFillColor(C_ACCENT)
    canvas.drawString(M, H - 3.5 * inch,
                      "Private companies pay heavily for market data.")
    canvas.drawString(M, H - 3.76 * inch,
                      "Can you still find an edge with free, public data?")
    canvas.setFont("Inter", 11)
    canvas.setFillColor(C_INK)
    canvas.drawString(M, H - 4.22 * inch,
                      f"The {N} largest US rental markets, ranked by the fundamentals")
    canvas.drawString(M, H - 4.42 * inch,
                      "that historically precede rent growth.")
    canvas.setFont("Inter", 10)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(M, H - 4.78 * inch,
                      f"A validated {HORIZON} outlook and a speculative 2026→"
                      f"2029 view, built entirely on free public data.")

    # ---- hero band: the dataset itself as cover art (B-2/B-7 Tier 1) ---------
    # The full 110-market diverging chart, quiet and unlabeled, edge to edge.
    canvas.drawImage(str(P_COVER_ART), 0, 3.05 * inch, width=W,
                     height=2.35 * inch, mask="auto",
                     preserveAspectRatio=False)

    # ---- the freeze-grade rail, large (the signature element, B-1) -----------
    rail_y = 2.72 * inch
    rx0, rx1 = M + 0.05 * inch, W - M - 0.05 * inch
    canvas.setStrokeColor(C_MUTED)
    canvas.setLineWidth(1.1)
    canvas.line(rx0 + 5, rail_y, rx1 - 5, rail_y)
    canvas.setFillColor(C_INK)
    canvas.setStrokeColor(C_INK)
    canvas.circle(rx0 + 5, rail_y, 4.4, stroke=0, fill=1)
    canvas.circle(rx1 - 5, rail_y, 4.4, stroke=1, fill=0)
    canvas.setFont("Inter-SB", 7)
    canvas.setFillColor(C_INK)
    canvas.drawString(rx0, rail_y - 0.19 * inch, f"Frozen · {TODAY}")
    canvas.drawRightString(rx1, rail_y - 0.19 * inch, "Graded · early 2029")
    canvas.setFont("Inter", 6.6)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(rx0, rail_y - 0.33 * inch,
                      "every ranking published before its outcome")
    canvas.drawRightString(rx1, rail_y - 0.33 * inch,
                           "scored against realized rent growth, whatever it shows")

    # ---- anchored stat row: each number carries its caveat inline (B-2) ------
    full_tau_row = bl.loc[bl["tau_3y"].idxmax()]
    band_h = 2.05 * inch
    canvas.setStrokeColor(C_INK)
    canvas.setLineWidth(1.1)
    canvas.line(M, band_h, W - M, band_h)
    stats = [
        (f"{float(full_tau_row['tau_3y']):.2f}", "POOLED TAU ON FINALIZED DATA",
         "RANDOM GUESSING SCORES ABOUT 0"),
        (f"{pp_pooled:+.1f} pp", "TOP-10 EDGE PER COMPLETED WINDOW",
         "NEAR ZERO IN THE 2020–22 SHOCK"),
        (f"{N}", "MARKETS RANKED, EVERY RANKING",
         "FROZEN BEFORE ITS OUTCOME"),
    ]
    col_w = (W - 2 * M) / 3.0
    for i, (num, l1, l2) in enumerate(stats):
        x = M + i * col_w
        canvas.setFont("Serif-SB", 23)
        canvas.setFillColor(C_INK)
        canvas.drawString(x, band_h - 0.52 * inch, num)
        canvas.setFont("Inter-SB", 6.4)
        canvas.setFillColor(C_MUTED)
        canvas.drawString(x, band_h - 0.74 * inch, l1)
        canvas.drawString(x, band_h - 0.87 * inch, l2)
    canvas.setStrokeColor(C_LINE)
    canvas.setLineWidth(0.6)
    canvas.line(M, band_h - 1.08 * inch, W - M, band_h - 1.08 * inch)
    canvas.setFont("Inter-SB", 8.5)
    canvas.setFillColor(C_INK)
    canvas.drawString(M, band_h - 1.34 * inch, "Ben Larson")
    canvas.setFont("Inter", 8)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(M, band_h - 1.50 * inch,
                      "Economics and applied mathematics, Indiana University")
    canvas.drawRightString(W - M, band_h - 1.34 * inch,
                           f"Model v{config.MODEL_VERSION} · methods documented, "
                           f"failures published")
    canvas.drawRightString(W - M, band_h - 1.50 * inch,
                           "A research screen, not investment advice")
    canvas.restoreState()


doc = BaseDocTemplate(str(OUT), pagesize=letter, leftMargin=M, rightMargin=M,
                      topMargin=0.85 * inch, bottomMargin=0.85 * inch,
                      title="Larson Capital Research: The Rent-Growth Screen",
                      author="Ben Larson")
frame = Frame(M, 0.85 * inch, CW, H - 1.7 * inch, id="main")
doc.addPageTemplates([
    PageTemplate(id="cover", frames=[Frame(M, M, CW, H - 2 * M)], onPage=on_cover),
    PageTemplate(id="page", frames=[frame], onPage=on_page),
])

story = [NextPageTemplate("page"), PageBreak()]

# ---- Contents (B-5: the pre-commitment is a feature; grade dates surface) ----
_toc_items = [
    ("Key findings and the top 10", ""),
    ("Every market against the average", ""),
    ("The map and the tiers", ""),
    ("The five themes", ""),
    (f"Market spotlight: {top_city}", ""),
    ("The track record",
     "2023 calls graded mid-2027 · 2025→2028 graded early 2029"),
    ("How the score is built", ""),
    ("The speculative 2026–2029 outlook", "failed validation; labeled throughout"),
    (f"Appendix: all {N} markets", ""),
]
_toc_title = ParagraphStyle("toc_t", fontName="Serif", fontSize=11.5,
                            leading=15, textColor=C_INK)
_toc_note = ParagraphStyle("toc_n", fontName="Inter", fontSize=8,
                           leading=11, textColor=C_MUTED)
_toc_rows = []
for _t, _note in _toc_items:
    _cell = [Paragraph(_t, _toc_title)]
    if _note:
        _cell.append(Paragraph(_note, _toc_note))
    _toc_rows.append(["", _cell])
_toc_tab = Table(_toc_rows, colWidths=[0.28 * inch, CW - 0.28 * inch])
_toc_tab.setStyle(TableStyle([
    ("LINEBEFORE", (0, 0), (0, -1), 2.2, C_ACCENT),
    ("LINEBELOW", (0, 0), (-1, -2), 0.4, C_LINE),
    ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ("LEFTPADDING", (1, 0), (1, -1), 4),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
]))
story += [eyebrow("Contents"),
          Paragraph("In this report", S["h1"]), *hr(),
          _toc_tab,
          Spacer(1, 10),
          Paragraph("Grading dates are pre-committed: each frozen screen is scored "
                    "against realized rent growth when its window closes, whatever "
                    "the result shows.", S["cap"]),
          PageBreak()]

# ---- Key findings ------------------------------------------------------------
s1, s2 = data.top_strengths(top)
lift = " and ".join(s.lower() for s in (s1, s2) if s) or "balanced fundamentals"
lead_range = (f"; its 90% rank range is {int(top['rank_lo'])}-{int(top['rank_hi'])}"
              if pd.notna(top.get("rank_lo")) else "")
story += [*divider("Key findings", "What the screen says", P_DIV_KEY,
                   subtitle="The top ten's rank ranges, drawn to scale: the "
                            "interval, not the point, is the claim."),
          Paragraph(f"<b>{top_city} leads the current screen</b> (a {HORIZON} outlook), "
                    f"lifted most by {lift}{lead_range}.", S["bullet"], bulletText="•"),
          Paragraph(f"<b>The screen's top-10 markets out-grew the median market by "
                    f"{pp_pooled:+.1f} points of rent growth</b> over three years, averaged "
                    f"across six completed backtest windows. Picking on recent rent growth "
                    f"alone earned {pp_mom:+.1f}.", S["bullet"], bulletText="•"),
          Paragraph(f"<b>Every measure had to earn its place by test.</b> An industry-style "
                    f"scorecard rebuilt from the same free data barely beats chance "
                    f"({ind_tau:.2f} on a -1 to +1 rank-agreement scale, vs {full_tau:.2f} "
                    f"here), and three of this project's own failed configurations were "
                    f"published as negative results.", S["bullet"], bulletText="•")]

# ---- Overview + top 10 ---------------------------------------------------------
story += [Paragraph("Overview", S["h2"]),
          Paragraph(f"Some rental markets grow rents for years; others stall. This report "
                    f"asks a simple question: <b>can public data tell them apart in "
                    f"advance?</b> The screen ranks the {N} largest US metro areas on "
                    f"fundamentals that historically come <i>before</i> strong rent growth: "
                    f"who is moving in, whether jobs and incomes are growing, how much new "
                    f"housing is being built, and whether rents still have room to rise. "
                    f"Everything is built from free public data (Census, IRS, BLS, BEA, "
                    f"Zillow, FRED), every method is documented, and every published ranking "
                    f"is frozen so its calls can be checked against what actually happens.",
                    S["body"]),
          Image(str(P_PIPE), width=CW, height=CW * (0.9 / 7.0)),
          Paragraph("How the score is built, in five steps; the full method is in the "
                    "back of this report.", S["cap"]),
          Paragraph("The top 10", S["h2"])]
if has_tiers:
    story.append(Paragraph(
        f"{n_in} of these ten sit in a {n_cluster}-market leading cluster; any market "
        f"in that cluster could plausibly hold a top-10 seat, so treat the exact "
        f"ordering loosely.", S["cap"]))
rows = [["Rank", "Metro", "Score", "What lifts it most"]]
for _, r in rank.head(10).iterrows():
    strengths = " · ".join(s for s in (r["strength_1"], r["strength_2"]) if s) \
        or "Broadly average"
    rng = (f"{int(r['rank'])}  ({int(r['rank_lo'])}-{int(r['rank_hi'])})"
           if pd.notna(r.get("rank_lo")) else f"{int(r['rank'])}")
    rows.append([rng, r["cbsa_title"], f"{r['score']:+.2f}", strengths])
t = Table(rows, colWidths=[0.9 * inch, 2.6 * inch, 0.7 * inch, 2.8 * inch])
t.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, 0), "Inter-SB"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
    ("TEXTCOLOR", (0, 0), (-1, 0), C_INK),
    ("LINEABOVE", (0, 0), (-1, 0), 1.0, C_INK),
    ("LINEBELOW", (0, 0), (-1, 0), 0.7, C_INK),
    ("FONTNAME", (0, 1), (-1, -1), "Inter"), ("FONTSIZE", (0, 1), (-1, -1), 8.6),
    ("FONTNAME", (1, 1), (1, -1), "Inter-Md"),
    ("TEXTCOLOR", (0, 1), (-1, -1), C_INK),
    ("TEXTCOLOR", (2, 1), (2, -1), C_POS),
    ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_LINE),
    ("LINEBELOW", (0, 1), (-1, -2), 0.4, C_LINE),
    # 3.0 (not 3.5) so the reading-guide caption fits under the table on the
    # same page instead of widowing onto the next.
    ("TOPPADDING", (0, 0), (-1, -1), 3.0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.0),
]))
story += [t,
          Paragraph("Rank (90% range), score vs the average market (0), and the themes "
                    "that lift each score most. The spread between markets matters more "
                    "than any single value. A market can hold a high single-edition rank "
                    "while its range sits lower; the tier, not the rank, is the durable "
                    "claim.", S["cap"]),
          PageBreak()]

# ---- Chart 1: every market ------------------------------------------------------
story += [eyebrow("Chart 1"),
          Paragraph("Every market against the average", S["h1"]), *hr(),
          Paragraph(f"Composite score for all {N} markets in the {YEAR} scoring year, "
                    f"relative to the average market (0). Green helps, red hurts.",
                    S["cap"]),
          Image(str(P_ALL), width=6.7 * inch, height=6.7 * inch * (8.9 / 7.6)),
          PageBreak()]

# ---- Map + tiers ---------------------------------------------------------------
story += [eyebrow("The map"),
          Paragraph("Where the strongest markets are", S["h1"]), *hr(),
          Image(str(P_MAP), width=CW, height=CW * (560 / 980)),
          Paragraph(f"Green = above the average market (score 0), clay = below; the "
                    f"tiers below group markets the data cannot separate. "
                    f"{rank.iloc[0]['cbsa_title'].split(',')[0].split('-')[0]} leads; "
                    f"{rank.iloc[1]['cbsa_title'].split(',')[0].split('-')[0]} and "
                    f"{rank.iloc[2]['cbsa_title'].split(',')[0].split('-')[0]} round out "
                    f"the top three.", S["cap"])]
if has_tiers:
    story += [Paragraph("The tiers", S["h2"]),
              Paragraph("Single ranks overstate precision, so each market gets a 90% rank "
                        "range and a tier. Markets in the same tier are peers, not an "
                        "ordering.", S["body"])]
    trows = [["Tier", "Markets", "Reading"]]
    for tname in data.TIER_ORDER:
        members = rank[rank["tier"] == tname]
        if not len(members):
            continue
        trows.append([tname, str(len(members)), data.TIER_BLURB.get(tname, "")])
    tt = Table(trows, colWidths=[1.4 * inch, 0.7 * inch, 4.9 * inch])
    tt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Inter-SB"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_INK),
    ("LINEABOVE", (0, 0), (-1, 0), 1.0, C_INK),
    ("LINEBELOW", (0, 0), (-1, 0), 0.7, C_INK),
        ("FONTNAME", (0, 1), (-1, -1), "Inter"), ("FONTSIZE", (0, 1), (-1, -1), 8.6),
        ("FONTNAME", (0, 1), (0, -1), "Inter-Md"),
        ("TEXTCOLOR", (0, 1), (-1, -1), C_INK),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, C_LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story += [tt]
story += [PageBreak()]

# ---- The five themes -------------------------------------------------------------
THEMES = [
    ("Demand", "40% of the score", "Who is moving in, hiring, and earning",
     "Net domestic migration, job growth, and income growth. Markets that people and "
     "paychecks are moving into fill apartments first and support rent increases later. "
     "Migration is the heaviest single measure: the screen's biggest bet, and the one "
     "the backtests reward most."),
    ("Supply", "25% of the score", "How much new housing is being built",
     "Building permits relative to the housing that already exists, counted the opposite "
     "way: the less a market is building, the better it scores. Today's construction "
     "is tomorrow's competition, the contrarian edge that pushes several fast-growing "
     "but over-built Sun Belt markets near the bottom."),
    ("Affordability", "20% of the score", "Whether rents have room to grow",
     "Two measures: rent as a share of local income (lower is better; stretched rents "
     "have nowhere to go), and the cost of owning versus renting (higher is better; "
     "when buying is far pricier than renting, households stay renters longer)."),
    ("Momentum", "a deliberately small 10%", "What rents have done lately",
     "Recent rent growth, deliberately held to a small weight: informative, but it "
     "decays with time and inverted badly in the 2020-22 shock. A supporting witness, "
     "not the verdict."),
    ("Resilience", "5% of the score", "How diversified the local economy is",
     "Employment spread across industries: a market leaning on one sector carries more "
     "downside risk to rents, so diversity earns a small, steady credit."),
]
story += [*divider("What drives the rankings", "Five themes, eight measures",
                   P_DIV_THEMES,
                   subtitle="The five published weights, drawn to scale: "
                            "40 · 25 · 20 · 10 · 5."),
          Paragraph("Every market is scored on the same eight measures, grouped into the "
                    "five themes below (heaviest first). Each measure compares markets "
                    "within the same year, each theme carries a fixed published weight, and "
                    "no market is ever hand-adjusted.", S["body"])]
for bucket, wt, subtitle, body in THEMES:
    col = f"bucket_{bucket}"
    sub = rank[["cbsa_title", col]].dropna()
    best = sub.loc[sub[col].idxmax()]
    worst = sub.loc[sub[col].idxmin()]
    story.append(KeepTogether([
        Paragraph(f"{bucket}: {subtitle.lower()}", S["h2"]),
        Paragraph(f"Share of the score: {wt}.", S["cap"]),
        Paragraph(body, S["body"]),
        Image(str(P_THEMES[bucket]), width=5.4 * inch, height=2.0 * inch),
        Paragraph(f"The five markets this theme helps and hurts most. "
                  f"{best['cbsa_title'].split(',')[0]} gains the most "
                  f"({best[col]:+.2f}); {worst['cbsa_title'].split(',')[0]} gives up "
                  f"the most ({worst[col]:+.2f}).", S["cap"])]))
story += [PageBreak()]

# ---- Spotlight -----------------------------------------------------------------
contribs = {b: top.get(f"bucket_{b}", 0.0) for b in data.BUCKETS}
top_buckets = [b for b in sorted(contribs, key=contribs.get, reverse=True)
               if contribs[b] > 0.02][:2]
_, drag = data.strength_drag(top)
BUCKET_INDS = {b: [k for k in data.INDICATORS if data.INDICATORS[k]["bucket"] == b]
               for b in data.BUCKETS}


def _ordinal(x):
    n = int(round(x))
    sfx = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{sfx}"


_spot_tier = (f" and sits in the {str(top['tier']).lower()} tier"
              if has_tiers and str(top.get("tier", "")) else "")
_spot_move = ""
_prior_for_spot = (prior_df[prior_df.cbsa_code == top["cbsa_code"]]
                   if show_change else pd.DataFrame())
if len(_prior_for_spot):
    _pr = _prior_for_spot.iloc[0]
    _delta = int(_pr["prior_rank"]) - int(top["rank"])
    _inside = (pd.notna(_pr.get("prior_lo"))
               and int(_pr["prior_lo"]) <= int(top["rank"]) <= int(_pr["prior_hi"]))
    _moved = ("held the same rank" if _delta == 0 else
              f"moved {_delta:+d} rank{'s' if abs(_delta) != 1 else ''}")
    _spot_move = (f" Vs the frozen {prior_label} edition it {_moved}, "
                  + ("inside its own 90% range, expected churn rather than a "
                     "signal." if _inside else
                     "outside its prior 90% range, one of the few moves the "
                     "noise model flags as notable."))
story += [eyebrow("Market spotlight"),
          Paragraph(f"The case for {top_city}", S["h1"]), *hr(),
          Paragraph(f"{top['cbsa_title']} ranks <b>#1 of {N}</b> markets, with a rank range "
                    f"of {int(top['rank_lo'])}-{int(top['rank_hi'])}{_spot_tier}."
                    f"{_spot_move} Its score is built the "
                    f"same way as every other market's; what sets it apart:", S["body"])]
label_map = {"Demand": "Demand", "Supply": "Limited new supply",
             "Affordability": "Affordability", "Momentum": "Rent momentum",
             "Resilience": "Economic resilience"}
raw, pct = ed["raw"], ed["pct"]
code = top["cbsa_code"]
for b in top_buckets:
    parts = []
    for k in BUCKET_INDS[b]:
        if code in raw.index and pd.notna(raw.loc[code].get(k)):
            v = data.FMT[k](raw.loc[code][k])
            p = pct.loc[code][k] if code in pct.index else float("nan")
            parts.append(f"{data.PRETTY[k].lower()}: {v}"
                         + (f" ({_ordinal(p)} percentile)" if pd.notna(p) else ""))
    if parts:
        story.append(Paragraph(f"<b>{label_map[b]}</b> ({contribs[b]:+.2f} to the score): "
                               + "; ".join(parts) + ".", S["bullet"], bulletText="•"))
if drag != data.NO_DRAG:
    neg_b = min(contribs, key=contribs.get)
    story.append(Paragraph(f"<b>The drag: {drag.lower()}</b> ({contribs[neg_b]:+.2f}); no "
                           f"market in the top ten is strong everywhere.",
                           S["bullet"], bulletText="•"))
if P_TREND:
    story += [Paragraph("Rents against the national median", S["h2"]),
              Image(str(P_TREND), width=6.6 * inch, height=2.4 * inch),
              Paragraph(f"Zillow rent index, year over year; the national line is the "
                        f"median of the screened markets. History describes the past; the "
                        f"rank comes from the fundamentals above.", S["cap"])]
# The standing closer (C-5), always present.
_closer = "A #1 rank is a screening result, not a verdict"
if int(top["rank_hi"]) > 1:
    _closer += (f": under alternative weightings this market ranks as low as "
                f"#{int(top['rank_hi'])}. Read the top of the table as a group "
                f"of strong candidates.")
else:
    _closer += "."
story.append(Paragraph(_closer, S["cap"]))
story += [PageBreak()]

# ---- Track record ---------------------------------------------------------------
story += [*divider("Has it worked?", "The track record", P_DIV_TRACK,
                   subtitle="Six completed windows' top-10 edge, with the "
                            "freeze-then-grade rail beneath: frozen at "
                            "publication, graded three years on."),
          Image(str(P_TLINE), width=CW, height=CW * (1.05 / 7.0)),
          Paragraph("How every window is graded, shown for 2019: the call is frozen at "
                    "publication and scored three years later.", S["cap"]),
          Paragraph("Each completed three-year window is graded the same way: how much "
                    "more rent growth did the screen's top-10 markets deliver than the "
                    "median market?", S["body"]),
          Image(str(P_EFFECT), width=6.6 * inch, height=2.3 * inch),
          Paragraph(f"Calm windows came in between "
                    f"{comp[comp.pred_year <= 2019]['top10_pp_vs_median'].min():+.1f} and "
                    f"{comp[comp.pred_year <= 2019]['top10_pp_vs_median'].max():+.1f} points. "
                    f"The shock (2020-22) windows were roughly flat; picking on rent momentum "
                    f"alone turned firmly negative in those same windows. The screen earns "
                    f"its edge in normal conditions and loses most of it in shocks.",
                    S["cap"])]
if len(m3):
    story += [Paragraph("What was achievable in real time", S["h2"]),
              Paragraph("The same backtest, two ways: <i>real-time</i> uses only data a "
                        "user could have had at the time; <i>finalized</i> uses the "
                        "complete revised data that arrives about two years later, a "
                        "ceiling no live user ever had. Agreement is weighted Kendall's "
                        "tau, a rank-agreement score from -1 to +1 where 0 means no "
                        "relationship.", S["body"])]
    tv = m3.rename(columns={
        "horizon": "Horizon", "regime": "Period",
        "mean_tau_ps": "Tau (real-time)", "mean_tau_fin": "Tau (finalized)",
        "mean_precision@10_ps": "P@10 (real-time)",
        "mean_precision@10_fin": "P@10 (finalized)"})
    tv["Period"] = (tv["Period"].str.replace("_", " ").str.replace("pre covid", "Pre-COVID")
                    .str.replace("shock", "Shock (2020-22)")
                    .str.replace("normalization", "Normalization")
                    .str.replace("POOLED", "All periods"))
    tv = tv[tv["Horizon"] == 3]
    rows = [["Period", "Tau (real-time)", "Tau (finalized)", "P@10 (real-time)", "P@10 (finalized)"]]
    for _, r in tv.iterrows():
        rows.append([r["Period"], f"{r['Tau (real-time)']:.2f}", f"{r['Tau (finalized)']:.2f}",
                     f"{r['P@10 (real-time)']:.0%}", f"{r['P@10 (finalized)']:.0%}"])
    tt = Table(rows, colWidths=[1.9 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch, 1.2 * inch])
    tt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Inter-SB"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_INK),
    ("LINEABOVE", (0, 0), (-1, 0), 1.0, C_INK),
    ("LINEBELOW", (0, 0), (-1, 0), 0.7, C_INK),
        ("FONTNAME", (0, 1), (-1, -1), "Inter"), ("FONTSIZE", (0, 1), (-1, -1), 8.6),
        ("TEXTCOLOR", (0, 1), (-1, -1), C_INK),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, C_LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story += [tt, Paragraph("3-year horizon. Real-time numbers come from the pseudo-nowcast "
                            "test, a disclosed simplification. Data vintage: finalized "
                            "panel through 2024; rent index through May 2026.", S["cap"])]
    _g_cell = ParagraphStyle("gcell", fontName="Inter", fontSize=8, leading=10.8,
                             textColor=C_INK)
    _g_term = ParagraphStyle("gterm", fontName="Inter-SB", fontSize=8, leading=10.8,
                             textColor=C_INK)
    guide_rows = [
        ["Tau (rank agreement)", "How well the ranking agreed with the rent growth "
         "that followed, from -1 to +1; 0 means no relationship, and random guessing "
         "scores about 0."],
        ["Precision@10 (P@10)", "Of the screen's ten highest-ranked markets, the "
         "share that landed in the top quarter by actual rent growth."],
        ["Top-10 edge (pp)", "How many percentage points more rent growth the top "
         "ten delivered than the median market over the window."],
        ["Rank range and tier", "Where a rank lands 90% of the time once measurement "
         "noise is accounted for; same-tier markets are peers, not an ordering."],
    ]
    gt = Table([[Paragraph(t, _g_term), Paragraph(x, _g_cell)]
                for t, x in guide_rows],
               colWidths=[1.55 * inch, 5.45 * inch])
    gt.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.7, C_INK),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, C_LINE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.7, C_INK),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [KeepTogether([Paragraph("How to read these numbers", S["h3"]), gt]),
              Spacer(1, 4)]

# C-2 sidebar: methods comparison, no vendors named.
_ind_txt = Paragraph(
    f"Prominent 2026 industry opportunity rankings are built the way this "
    f"project's benchmark scorecard is: equal weights across categories, chosen "
    f"without validation, published as point ranks with no uncertainty attached. "
    f"Within six months, roughly half of one such ranking's markets moved by "
    f"double-digit ranks, churn of the kind this screen's rank ranges are built "
    f"to absorb. Rebuilt from the same free public data, that scorecard style "
    f"agrees with realized 3-year rent growth at {ind_tau:.2f} on the -1 to +1 "
    f"tau scale; this screen's finalized-data figure is {full_tau:.2f}. A "
    f"comparison of methods, not of any vendor's product at its own task.",
    S["body"])
_ind_panel = Table([[Paragraph("Against an industry ranking", S["h3"])],
                    [_ind_txt]], colWidths=[CW])
_ind_panel.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(_TOKENS_TINT)),
    ("TOPPADDING", (0, 0), (0, 0), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
    ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
]))
story += [KeepTogether([_ind_panel]), Spacer(1, 6)]

story += [KeepTogether([
          Paragraph("Five gates, three failures, two passes", S["h2"]),
          Paragraph("Every screen built on early or estimated data had to pass the same "
                    "pre-registered test (keep at least 85% of the finalized model's "
                    "signal and match its top 10 on at least 7 of 10 names) in a single "
                    "attempt, with the outcome published either way:", S["body"]),
          rl_comp.gate_ledger([
              (False, "2025 screen, five estimated inputs kept 74.8% of the "
                      "signal; never shipped.", "Failed"),
              (False, "2025 screen, fresher jobs data kept 84.66%; not rounded "
                      "up; the edition was pulled.", "Failed by 0.34 pt"),
              (True, "2024-vintage screen, one estimated input kept 95.5%, "
                     "matched the top-10 on 8.3/10 (a 2024-2027 forecast).",
                     "Passed"),
              (True, "2025 screen, income chained by state growth kept 96.6%, "
                     "matched the top-10 on 7.4/10; this report's current "
                     "2025-2028 forecast.", "Passed"),
              (False, "Mid-year 2026 screen, five months of data kept 82.7% and "
                      "matched 4.8 of 10 (averaged across the test windows); it "
                      "appears in this report only as a clearly-labeled "
                      "speculative outlook, never as a validated screen.",
                      "Failed both bars"),
          ], CW),
          Paragraph("A validation bar that never fails anything proves nothing. Ours failed "
                    "three of five attempts, which is exactly why the two that passed mean "
                    "something.", S["cap"])]),
          Paragraph("Honest limits", S["h2"]),
          Paragraph("The rent data measures asking rents, not signed leases.",
                    S["bullet"], bulletText="•"),
          Paragraph("No capital-markets or operating-cost data (sale prices, cap rates, "
                    "insurance, taxes); rent growth stands in for profitability.",
                    S["bullet"], bulletText="•"),
          Paragraph("Measure weights are set by judgment and tested, not statistically "
                    "fitted.", S["bullet"], bulletText="•"),
          Paragraph("The supply measure reads permit levels in the scoring year; a "
                    "sharp turn in construction starts shows up only as it enters the "
                    "permit data, so supply inflections can lag.",
                    S["bullet"], bulletText="•"),
          Paragraph("In shock periods like 2020-22 the screen loses most of its edge; "
                    "treat it as a screen, not a forecast.", S["bullet"], bulletText="•"),
          PageBreak()]

# ---- Methodology ------------------------------------------------------------------
story += [eyebrow("Methodology"),
          Paragraph("How the score is built", S["h1"]), *hr(),
          Paragraph(f"The screen scores every market on {data.N_IND} measures, grouped into "
                    f"five themes. Each measure compares a market against all the others in "
                    f"the same year, so a nationwide swing cancels out and only relative "
                    f"standing counts. Measures where more is worse (heavy homebuilding, "
                    f"rents that already stretch incomes) are flipped, so higher always "
                    f"means better. Each measure is multiplied by a fixed weight and summed "
                    f"into one composite score; markets are ranked by it. The same formula "
                    f"runs for every market; no market is ever hand-adjusted.", S["body"])]
story += [Image(str(P_WBAR), width=CW, height=CW * (0.72 / 7.0)),
          Spacer(1, 4)]
wrows = [["Theme", "Weight", "Measures (weight)"]]
_totals = {b: sum(data.INDICATORS[k]["weight"] for k in data.INDICATORS
                  if data.INDICATORS[k]["bucket"] == b) for b in data.BUCKETS}
for b in data.BUCKETS:
    ks = [k for k in data.INDICATORS if data.INDICATORS[k]["bucket"] == b]
    wrows.append([b, f"{_totals[b]*100:.0f}%",
                  " · ".join(f"{data.PRETTY[k]} ({data.INDICATORS[k]['weight']*100:.0f}%)"
                             for k in ks)])
wt = Table(wrows, colWidths=[1.1 * inch, 0.7 * inch, 5.2 * inch])
wt.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, 0), "Inter-SB"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
    ("TEXTCOLOR", (0, 0), (-1, 0), C_INK),
    ("LINEABOVE", (0, 0), (-1, 0), 1.0, C_INK),
    ("LINEBELOW", (0, 0), (-1, 0), 0.7, C_INK),
    ("FONTNAME", (0, 1), (-1, -1), "Inter"), ("FONTSIZE", (0, 1), (-1, -1), 8.4),
    ("FONTNAME", (0, 1), (0, -1), "Inter-Md"),
    ("TEXTCOLOR", (0, 1), (-1, -1), C_INK),
    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_LINE),
    ("LINEBELOW", (0, 1), (-1, -2), 0.4, C_LINE),
    ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
]))
story += [wt,
          Paragraph("The weights are fixed, published in full, set by judgment rather "
                    "than fitted, and stress-tested: reasonable alternative weightings "
                    "score about the same, so the testing, not the weights, is the "
                    "point.", S["cap"]),
          Paragraph("Where the data comes from", S["h2"])]
_cell_md = ParagraphStyle("cellmd", fontName="Inter-Md", fontSize=8, leading=10.5,
                          textColor=C_INK)
_cell = ParagraphStyle("cell", fontName="Inter", fontSize=8, leading=10.5,
                       textColor=C_INK)
vrows = [["Measure", "Source", "Through"]]
for k in data.INDICATORS:
    src_txt, through = data.VINTAGE_SOURCES[k]
    url = data.SOURCE_LINKS.get(k)
    if url:
        src_txt = (f"{src_txt} · <a href='{url}' color='{ACCENT}'>"
                   f"source page</a>")
    vrows.append([Paragraph(data.PRETTY[k], _cell_md),
                  Paragraph(src_txt, _cell), through])
vt = Table(vrows, colWidths=[1.9 * inch, 4.4 * inch, 0.7 * inch])
vt.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, 0), "Inter-SB"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
    ("TEXTCOLOR", (0, 0), (-1, 0), C_INK),
    ("LINEABOVE", (0, 0), (-1, 0), 1.0, C_INK),
    ("LINEBELOW", (0, 0), (-1, 0), 0.7, C_INK),
    ("FONTNAME", (0, 1), (-1, -1), "Inter"), ("FONTSIZE", (0, 1), (-1, -1), 8),
    ("FONTNAME", (0, 1), (0, -1), "Inter-Md"),
    ("TEXTCOLOR", (0, 1), (-1, -1), C_INK),
    ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_LINE),
    ("LINEBELOW", (0, 1), (-1, -2), 0.4, C_LINE),
    ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
]))
story += [vt,
          Paragraph("* The three Connecticut metros' job and income growth are chained "
                    "across a 2023-24 state geography change using validated substitutes, "
                    "a disclosed fix for those three markets only. The current screen's "
                    "slowest inputs use validated substitutes (Census migration, monthly "
                    "employment, state-chained income); the configuration passed its "
                    "pre-registered gate at 96.6% signal retention.", S["cap"]),
          PageBreak()]

# ---- Speculative outlook (v0.6; decision-log 2026-07-21) ----------------------------
_nc = config.PROCESSED_DIR / "nowcast"
_spec_rank_p = _nc / "midyear_2026_ranking.csv"
_spec_acc_p = _nc / "midyear_v06_accuracy.csv"
if _spec_rank_p.exists() and _spec_acc_p.exists():
    spec_rank = pd.read_csv(_spec_rank_p, dtype={"cbsa_code": str}).sort_values("rank")
    spec_rank[["s_strength", "s_drag"]] = spec_rank.apply(
        lambda r: pd.Series(data.strength_drag(r)), axis=1)
    acc = pd.read_csv(_spec_acc_p).iloc[0]
    C_PROV = colors.HexColor(FLAG)
    warn = Table([[Paragraph(
        f"<font name='Inter-SB' color='{FLAG}'>This screen has not passed validation. "
        f"Read every rank loosely.</font><br/>"
        f"Tested on history the same way as every published screen, this recipe keeps "
        f"<b>{acc['retention']:.1%}</b> of the finalized model's signal but matches the "
        f"finalized top-10 on only <b>{acc['mean_top10_overlap']:.1f} of 10</b> names "
        f"(a validated screen needs 7), falling to 3-4 of 10 in fast-moving years. An "
        f"earlier mid-year recipe failed its one-shot gate outright (82.7% and 4.8 of "
        f"10). For decisions, use the validated {HORIZON} screen in the body of this "
        f"report.", S["body"])]], colWidths=[CW])
    warn.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.2, C_PROV),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story += [*divider("Speculative outlook", "The speculative 2026-2029 outlook",
                       P_DIV_SPEC,
                       subtitle="The freeze-grade rail breaks here: this "
                                "configuration failed its validation gate and "
                                "makes no graded claim."),
              warn, Spacer(1, 8),
              Paragraph("This is the same frozen model run on data through May 2026: "
                        "five months of rents, jobs, home values, and permits; migration "
                        "one year stale; and income growth estimated from each metro's "
                        "state, so metros in the same state share one income figure.",
                        S["body"]),
              Paragraph("The speculative top 10", S["h2"])]
    srows = [["Rank", "Metro", "Score", "What lifts it most"]]
    for _, r in spec_rank.head(10).iterrows():
        srows.append([f"{int(r['rank'])}", r["cbsa_title"], f"{r['score']:+.2f}",
                      r["s_strength"]])
    st_t = Table(srows, colWidths=[0.6 * inch, 2.9 * inch, 0.7 * inch, 2.8 * inch])
    st_t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Inter-SB"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_INK),
    ("LINEABOVE", (0, 0), (-1, 0), 1.0, C_INK),
    ("LINEBELOW", (0, 0), (-1, 0), 0.7, C_INK),
        ("FONTNAME", (0, 1), (-1, -1), "Inter"), ("FONTSIZE", (0, 1), (-1, -1), 8.6),
        ("FONTNAME", (1, 1), (1, -1), "Inter-Md"),
        ("TEXTCOLOR", (0, 1), (-1, -1), C_INK),
        ("TEXTCOLOR", (2, 1), (2, -1), C_POS),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_LINE),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, C_LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story += [st_t,
              Paragraph("No rank ranges are shown: this configuration failed validation, "
                        "so the ordering is indicative at best. A working view, rebuilt as "
                        "data lands; unlike the validated screens it is not frozen to the "
                        "registry and makes no graded claim. The full speculative ranking "
                        "and per-market detail are on the companion site.", S["cap"]),
              PageBreak()]

# ---- Appendix: full table -----------------------------------------------------------
story += [*divider("Appendix", f"All {N} markets", P_DIV_APPX,
                   subtitle="All 110 markets as one strip, colored by tier, "
                            "leading cluster to lagging: the legend for the "
                            "table that follows."),
          Paragraph("Treat this as a screen, not a precise ordering: the range beside "
                    "each rank shows where that rank lands 90% of the time once "
                    "measurement noise is accounted for, and markets with overlapping "
                    "ranges are roughly tied.", S["cap"])]

# Change vs prior edition (C-1): frozen prior ranks from the registry; slate
# unless the new rank falls outside the market's PRIOR edition's 90% range.
if show_change:
    rank_appx = rank.merge(prior_df, on="cbsa_code", how="left")
    story.append(Paragraph(
        "Rank moves mix one real year of market change with measurement noise; "
        "a move inside a market's own 90% range is expected, not a signal. "
        "Historically even two fully finalized years share only 1 to 6 of the "
        "same top-10 names. Gray moves are expected churn; colored moves fall "
        "outside the market's prior 90% range.", S["cap"]))
else:
    rank_appx = rank

C_SLATE = C_MUTED


def _chg_cell(r):
    """(text, color) for the change column."""
    if not show_change or pd.isna(r.get("prior_rank")):
        return ("new" if show_change else "", C_SLATE)
    delta = int(r["prior_rank"]) - int(r["rank"])
    txt = f"{delta:+d}" if delta else "0"
    if pd.notna(r.get("prior_lo")):
        if int(r["rank"]) < int(r["prior_lo"]):
            return (txt, C_POS)
        if int(r["rank"]) > int(r["prior_hi"]):
            return (txt, C_NEG)
    return (txt, C_SLATE)


head = ["Rank", "Metro", "Score"] + \
    ([f"Vs {prior_label}"] if show_change else []) + ["Top strength", "Top drag"]
arows = [head]
chg_styles = []
for i, (_, r) in enumerate(rank_appx.iterrows()):
    rng = (f"{int(r['rank'])}  ({int(r['rank_lo'])}-{int(r['rank_hi'])})"
           if pd.notna(r.get("rank_lo")) else f"{int(r['rank'])}")
    row = [rng, r["cbsa_title"][:42], f"{r['score']:+.2f}"]
    if show_change:
        txt, col = _chg_cell(r)
        row.append(txt)
        chg_styles.append(("TEXTCOLOR", (3, i + 1), (3, i + 1), col))
    row += [r["strength"], r["drag"]]
    arows.append(row)
_appx_widths = ([0.85 * inch, 2.45 * inch, 0.6 * inch, 0.55 * inch,
                 1.35 * inch, 1.2 * inch] if show_change else
                [0.85 * inch, 2.75 * inch, 0.6 * inch, 1.45 * inch, 1.35 * inch])
at = Table(arows, colWidths=_appx_widths, repeatRows=1)
score_colors = [("TEXTCOLOR", (2, i + 1), (2, i + 1), C_POS if r["score"] >= 0 else C_NEG)
                for i, (_, r) in enumerate(rank_appx.iterrows())]
# Ranges read as context, not noise: the range half of the Rank column and the
# whole row sit on the tier-band component (B-4.4).
_appx_base = [
    ("FONTNAME", (0, 0), (-1, 0), "Inter-SB"), ("FONTSIZE", (0, 0), (-1, 0), 7),
    ("TEXTCOLOR", (0, 0), (-1, 0), C_INK),
    ("LINEABOVE", (0, 0), (-1, 0), 1.0, C_INK),
    ("LINEBELOW", (0, 0), (-1, 0), 0.7, C_INK),
    ("FONTNAME", (0, 1), (-1, -1), "Inter"), ("FONTSIZE", (0, 1), (-1, -1), 7),
    ("TEXTCOLOR", (0, 1), (-1, -1), C_INK),
    ("ALIGN", (2, 0), (3 if show_change else 2, -1), "RIGHT"),
    ("LINEBELOW", (0, 0), (-1, 0), 0.6, C_LINE),
    ("LINEBELOW", (0, 1), (-1, -2), 0.3, C_LINE),
    ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
    *score_colors,
    *chg_styles,
]
if has_tiers:
    at.setStyle(TableStyle(rl_comp.tier_band_style(_appx_base,
                                                   rank_appx["tier"].tolist())))
else:
    at.setStyle(TableStyle(_appx_base))
story += [at, PageBreak()]

# ---- About + disclaimer ------------------------------------------------------------
story += [eyebrow("About"),
          Paragraph("About this research", S["h1"]), *hr(),
          Paragraph("I'm <b>Ben Larson</b>, a student at Indiana University majoring in "
                    "economics and applied mathematics, with a strong interest in data "
                    "analytics and real estate. I built this screen to answer a question I "
                    "kept running into: how much of a rental market's future is already "
                    "visible in free public data? I held the answer to a standard I'd be "
                    "willing to defend: every method documented, every claim validated "
                    "before it's published, failed experiments published alongside the "
                    "successes, and a frozen track record anyone can check against what "
                    "actually happens. Everything here, from the data pipeline and the "
                    "backtests to the interactive site and this report, is my own work.",
                    S["body"]),
          Paragraph("The interactive version of this report, with every market's detail "
                    "page, side-by-side comparisons, and the full validation record, is "
                    "on the companion site.", S["body"]),
          Spacer(1, 14),
          Paragraph("Disclaimer", S["h3"]),
          Paragraph("This report is a research screen built on free public data (Census, "
                    "IRS, BLS, BEA, Zillow, FRED). It is intended for general information "
                    "purposes only, is not investment advice, and is not an offer or "
                    "solicitation of any kind. Rankings reflect a validated statistical "
                    "screen of historical fundamentals; they are not forecasts of any "
                    "individual market's performance, and in shock periods the framework "
                    "loses most of its edge. Verify all figures against the primary "
                    "sources before relying on them.", S["cap"])]

print("building pdf...")
doc.build(story)
print(f"done: {OUT}")
