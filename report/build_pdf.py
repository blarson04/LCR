"""
build_pdf.py: the report as a PDF, built from the same frozen outputs as the
site (app/ui/data.py in bare mode), for sharing off-platform (LinkedIn).

Teaser rebuild (author request 2026-08-19): the PDF is a six-page snapshot of
the site, in the site's reading order — cover, the method, Key findings with
the map, the top 10, Track record, and a closing page that routes the reader
to the companion site (config.SITE_URL links when set). Each section opens
with the photo header band its site page uses; brand tokens match
app/ui/theme.py. The depth the teaser omits (the full 110-market table, the
speculative outlook, Explore a market, data sourcing, full statistics) lives
on the site and in the methodology paper.

Run:  .venv/Scripts/python.exe report/build_pdf.py
Out:  report/Larson_Capital_Research-Report.pdf
"""

from __future__ import annotations

import shutil
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
from src.nowcast import proxy_map as pmap  # noqa: E402

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

has_tiers = ("tier" in rank.columns) and (rank["tier"].fillna("") != "").any()
n_cluster = int((rank["tier"] == "Leading cluster").sum()) if has_tiers else 0
n_in = int((rank.head(10)["tier"] == "Leading cluster").sum()) if has_tiers else 0

# Prior edition (C-1): frozen ranks + that edition's 90% ranges, for the
# change column.
prior_df, prior_label = data.prior_edition(d)
show_change = len(prior_df) > 0

# Scoring-year uncertainty flag (ex-ante rule, v3-P6): must show when it
# fires; quiet years show nothing (author direction 2026-08-17).
nat = data.national_rent_growth(d["panel"], YEAR)
flag_on = nat > config.REGIME_FLAG_THRESHOLD

m3_path = config.PROCESSED_DIR / "nowcast" / "gate2025_summary.csv"
if not m3_path.exists():
    m3_path = config.PROCESSED_DIR / "nowcast" / "m3_summary.csv"
m3 = pd.read_csv(m3_path) if m3_path.exists() else pd.DataFrame()
bl = pd.read_csv(config.PROCESSED_DIR / "baseline_comparison.csv")

# Speculative 2026→2029 outlook (v0.6; decision-log 2026-07-21).
_nc = config.PROCESSED_DIR / "nowcast"
_spec_rank_p = _nc / "midyear_2026_ranking.csv"
_spec_acc_p = _nc / "midyear_v06_accuracy.csv"
_spec_gate_p = _nc / "gate2026_summary.csv"
have_spec26 = _spec_rank_p.exists() and _spec_acc_p.exists()
if have_spec26:
    spec_rank = pd.read_csv(_spec_rank_p, dtype={"cbsa_code": str}).sort_values("rank")
    spec_rank[["s_strength", "s_drag"]] = spec_rank.apply(
        lambda r: pd.Series(data.strength_drag(r)), axis=1)
    spec_acc = pd.read_csv(_spec_acc_p).iloc[0]
    spec_gate = (pd.read_csv(_spec_gate_p).iloc[0]
                 if _spec_gate_p.exists() else None)

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


def chart_spread() -> Path:
    """The site's spread chart: top 10 and bottom 10 against the average."""
    head, tail = rank.head(10), rank.tail(10)
    labels = ([f"{int(r['rank'])}  {short(r['cbsa_title'], 24)}"
               for _, r in head.iterrows()]
              + [f"(…{N - 20} markets…)"]
              + [f"{int(r['rank'])}  {short(r['cbsa_title'], 24)}"
                 for _, r in tail.iterrows()])
    vals = head["score"].tolist() + [float("nan")] + tail["score"].tolist()
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    colors_ = [POS if (v or 0) >= 0 else NEG for v in vals]
    ax.barh(range(len(vals)), vals, color=colors_, height=0.62)
    ax.set_yticks(range(len(vals)), labels)
    ax.invert_yaxis()
    ax.axvline(0, color=MUTED, linewidth=0.8)
    style_ax(ax)
    ax.tick_params(axis="y", labelsize=7)
    ax.tick_params(axis="x", labelsize=7.5)
    ax.set_xlabel("Composite score (0 = the average market)", fontsize=8)
    fig.tight_layout(pad=0.3)
    p = BUILD / "spread.png"
    fig.savefig(p, dpi=300)
    plt.close(fig)
    return p


def chart_map(df: pd.DataFrame, fname: str, speculative: bool = False) -> Path:
    """The site's score map, exported via plotly + playwright."""
    import plotly.express as px
    import plotly.graph_objects as go
    mp = df.merge(d["coords"], on="cbsa_code", how="left")
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
    if speculative:
        # The gold tag is baked into the image (governance feature: a
        # screenshot must not be able to shed the warning).
        fig.add_annotation(
            xref="paper", yref="paper", x=0.99, y=0.99, xanchor="right",
            yanchor="top", showarrow=False,
            text="<b>speculative · failed validation</b>",
            font=dict(family="Inter", size=12, color=FLAG))
    p = BUILD / f"{fname}.png"
    # kaleido's subprocess is unreliable on this machine; render via playwright
    # (the project's proven screenshot path) instead.
    html = BUILD / f"{fname}.html"
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
    ax.set_xlabel(f"{bucket}: contribution to the composite score", fontsize=7.5)
    fig.tight_layout(pad=0.3)
    p = BUILD / f"theme_{bucket}.png"
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
P_SPREAD = chart_spread()
P_MAP = chart_map(rank, "map")
P_MAP_SPEC = chart_map(spec_rank, "map_spec", speculative=True) if have_spec26 else None
P_THEMES = {b: chart_theme(b) for b in data.BUCKETS}
P_TREND = chart_trend()
P_PIPE = chart_pipeline()
P_WBAR = chart_weights_bar()
P_TLINE = chart_timeline()

# ---- Hero art (B-7 Tier 1: generated from this edition's frozen data) -------
# Still generated: the same assets serve as the site's page-header fallback
# art (B-7.3), and the cover keeps its generative backdrop as the photo
# fallback.
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

# Site parity (B-7.3): committed so the deployed site has the fallback art.
_SITE_ART = APP / "assets" / "art"
_SITE_ART.mkdir(parents=True, exist_ok=True)
for _src, _dst in [(P_DIV_KEY, "home.png"), (P_DIV_APPX, "rankings.png"),
                   (P_DIV_TRACK, "track_record.png"),
                   (P_DIV_THEMES, "how_it_works.png"),
                   (P_DIV_SPEC, "outlook_2026.png")]:
    shutil.copyfile(_src, _SITE_ART / _dst)


# ---- Photo header bands (site parity: the same photos, cropped to a band) ---
def photo_band(page: str, height_in: float = 1.05) -> Path | None:
    """Crop the site page's header photo to the print band's aspect, matching
    the site's object-fit: cover / object-position: center 35%."""
    from PIL import Image as PILImage
    src = APP / "assets" / "photos" / f"{page}.jpg"
    if not src.exists():
        return None
    im = PILImage.open(src)
    w, h = im.size
    aspect = 7.0 / height_in            # CW is 7.0in wide
    crop_h = int(w / aspect)
    if crop_h <= h:
        top_px = int((h - crop_h) * 0.35)
        im = im.crop((0, top_px, w, top_px + crop_h))
    else:
        crop_w = int(h * aspect)
        left = (w - crop_w) // 2
        im = im.crop((left, 0, left + crop_w, h))
    p = BUILD / f"band_{page}.jpg"
    im.save(p, quality=88)
    return p


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
    """Every paragraph passes through the typographic-hygiene filter. <b> is
    mapped to the semibold face directly: reportlab's family mapping does not
    resolve it for these TTF registrations."""
    text = text.replace("<b>", "<font name='Inter-SB'>").replace("</b>", "</font>")
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
C_SURFACE = colors.HexColor(SURFACE)

W, H = letter
M = 0.75 * inch
CW = W - 2 * M

# B-1 type scale: 30/20/14/10.5/9, eyebrow 8.5 letterspaced.
_TS = lcr_theme.type_scale_pdf()
S = dict(
    h1=ParagraphStyle("h1", fontName="Serif-SB", fontSize=_TS["h1"] - 4,
                      leading=(_TS["h1"] - 4) * 1.12, textColor=C_INK, spaceAfter=5),
    h2=ParagraphStyle("h2", fontName="Serif-SB", fontSize=_TS["h2"],
                      leading=_TS["h2"] * 1.2, textColor=C_INK, spaceBefore=20,
                      spaceAfter=7, keepWithNext=1),
    h3=ParagraphStyle("h3", fontName="Inter-SB", fontSize=_TS["h3"],
                      leading=_TS["h3"] * 1.25, textColor=C_INK, spaceBefore=13,
                      spaceAfter=4, keepWithNext=1),
    body=ParagraphStyle("body", fontName="Inter", fontSize=_TS["body"],
                        leading=_TS["body"] * 1.52, textColor=C_INK, spaceAfter=8),
    bullet=ParagraphStyle("bullet", fontName="Inter", fontSize=_TS["body"],
                          leading=_TS["body"] * 1.52, textColor=C_INK,
                          leftIndent=12, bulletIndent=2, spaceAfter=7),
    cap=ParagraphStyle("cap", fontName="Inter", fontSize=_TS["caption"],
                       leading=_TS["caption"] * 1.45, textColor=C_MUTED,
                       spaceAfter=10),
    eyebrow=ParagraphStyle("eyebrow", fontName="Inter-SB",
                           fontSize=_TS["eyebrow"], leading=_TS["eyebrow"] * 1.3,
                           textColor=C_MUTED, spaceAfter=2),
    thesis=ParagraphStyle("thesis", fontName="Serif-SB", fontSize=21,
                          leading=26, textColor=C_INK, spaceAfter=8),
)


def eyebrow(txt):
    # Letterspaced via NBSPs (reportlab collapses runs of ASCII spaces):
    # one per letter gap, so word gaps (three ASCII spaces after the join)
    # come out triple-width.
    spaced = " ".join(txt.upper()).replace(" ", " ")
    return Paragraph(f"<font name='Inter-SB'>{spaced}</font>",
                     ParagraphStyle("eb", parent=S["eyebrow"], textColor=C_MUTED))


def hr(width=CW, space_before=4, space_after=8):
    t = Table([[""]], colWidths=[width], rowHeights=[0.6])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.6, C_LINE)]))
    return [Spacer(1, space_before), t, Spacer(1, space_after)]


def section_header(page: str, kicker: str, title: str,
                   caption_txt: str | None = None, title_style: str = "h1"):
    """A site page header, in print: the page's photo band, the eyebrow, the
    serif title, and the page's one-line opening caption."""
    flow = []
    band = photo_band(page)
    if band:
        flow += [Image(str(band), width=CW, height=1.05 * inch), Spacer(1, 12)]
    flow.append(eyebrow(kicker))
    flow.append(Paragraph(title, S[title_style]))
    if caption_txt:
        flow.append(Paragraph(caption_txt, S["cap"]))
    flow.append(Spacer(1, 8))
    return flow


# The house data-table look, shared by every ruled table in the report.
def ruled_table(rows, col_widths, body_size=8.6, align_right=(), md_col=None,
                extra=None, repeat_header=False):
    t = Table(rows, colWidths=col_widths, repeatRows=1 if repeat_header else 0)
    cmds = [
        ("FONTNAME", (0, 0), (-1, 0), "Inter-SB"), ("FONTSIZE", (0, 0), (-1, 0), 7.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_INK),
        ("LINEABOVE", (0, 0), (-1, 0), 1.0, C_INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, C_INK),
        ("FONTNAME", (0, 1), (-1, -1), "Inter"),
        ("FONTSIZE", (0, 1), (-1, -1), body_size),
        ("TEXTCOLOR", (0, 1), (-1, -1), C_INK),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, C_LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    for c in align_right:
        cmds.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    if md_col is not None:
        cmds.append(("FONTNAME", (md_col, 1), (md_col, -1), "Inter-Md"))
    if extra:
        cmds += extra
    t.setStyle(TableStyle(cmds))
    return t


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
    # The thesis IS the title (author request 2026-08-19): the accent line,
    # promoted to display size; no separate product name above it.
    canvas.setFont("Serif-SB", 25)
    canvas.setFillColor(C_ACCENT)
    canvas.drawString(M, H - 2.35 * inch, "A quantified prediction of America’s")
    canvas.drawString(M, H - 2.74 * inch, "emerging rental markets, built by")
    canvas.drawString(M, H - 3.13 * inch, "synthesizing public data.")
    canvas.setFont("Inter", 11)
    canvas.setFillColor(C_INK)
    canvas.drawString(M, H - 3.62 * inch,
                      f"The {N} largest US rental markets, ranked by the fundamentals")
    canvas.drawString(M, H - 3.82 * inch,
                      "that historically precede rent growth.")
    canvas.setFont("Inter", 10)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(M, H - 4.18 * inch,
                      f"A validated {HORIZON} outlook and a speculative 2026→"
                      f"2029 view, built entirely on free public data.")

    # ---- hero band: photography (author direction 2026-08-16) ----------------
    # Aerial multifamily photo, edge to edge, pre-cropped to the band's aspect
    # (Unsplash-licensed; credits in app/assets/photos/CREDITS.md). Falls back
    # to the generative cover art if the photo is absent.
    _photo = HERE / "assets" / "photos" / "cover_band.jpg"
    canvas.drawImage(str(_photo if _photo.exists() else P_COVER_ART),
                     0, 3.05 * inch, width=W, height=2.35 * inch, mask="auto",
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
    canvas.drawRightString(rx1, rail_y - 0.33 * inch,
                           "scored against realized rent growth")

    # ---- anchored stat row: each number carries its caveat inline (B-2) ------
    full_tau_row = bl.loc[bl["tau_3y"].idxmax()]
    band_h = 2.05 * inch
    canvas.setStrokeColor(C_INK)
    canvas.setLineWidth(1.1)
    canvas.line(M, band_h, W - M, band_h)
    # Cover caveat sublines removed by author override 2026-08-19 (logged in
    # decision-log.md); the shock-period and frozen-before-outcome disclosures
    # remain on the Track record page.
    stats = [
        (f"{float(full_tau_row['tau_3y']):.2f}", "POOLED TAU ON FINALIZED DATA",
         "RANDOM GUESSING SCORES ABOUT 0"),
        (f"{pp_pooled:+.1f} pp", "TOP-10 EDGE PER COMPLETED WINDOW", ""),
        (f"{N}", "MARKETS RANKED", ""),
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
        if l2:
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
    # Contact line: email and LinkedIn, both live links in the PDF.
    _contact_y = band_h - 1.66 * inch
    canvas.setFillColor(C_ACCENT)
    _email = "blarson5187@gmail.com"
    _li_label = "linkedin.com/in/blarson1105"
    canvas.drawString(M, _contact_y, _email)
    _ew = canvas.stringWidth(_email, "Inter", 8)
    canvas.setFillColor(C_MUTED)
    canvas.drawString(M + _ew + 4, _contact_y, "·")
    canvas.setFillColor(C_ACCENT)
    _lx = M + _ew + 10
    canvas.drawString(_lx, _contact_y, _li_label)
    _lw = canvas.stringWidth(_li_label, "Inter", 8)
    canvas.linkURL(f"mailto:{_email}", (M, _contact_y - 2, M + _ew, _contact_y + 9),
                   relative=0)
    canvas.linkURL("https://www.linkedin.com/in/blarson1105",
                   (_lx, _contact_y - 2, _lx + _lw, _contact_y + 9), relative=0)
    canvas.drawRightString(W - M, band_h - 1.34 * inch,
                           f"Model v{config.MODEL_VERSION}")
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

# The teaser keeps the site's reading order but states each section once,
# briefly: the cover hooks, four inside pages carry the method, the current
# ranking, and the graded record, and the closing page routes the reader to
# the site. Cut sections (the full 110-market table, the speculative outlook,
# Explore a market, data sourcing, full statistics) live on the site and in
# the methodology paper.

# ============================ 1. The method ==================================
story += [*section_header(
              "how_it_works", "Multifamily research · the method",
              "How it works")]

story += [Paragraph(f"The screen ranks every US metro area over 500,000 people with "
                    f"continuous rent data on eight measures of fundamentals that "
                    f"historically come before strong rent growth. Each measure is "
                    f"compared across markets within the same year (so nationwide "
                    f"swings cancel out), weighted by a fixed published share, and "
                    f"summed into one score. The same formula runs for every market; "
                    f"no market is ever hand-adjusted; the weights are set by "
                    f"judgment.", S["body"]),
          Image(str(P_PIPE), width=CW, height=CW * (0.9 / 7.0)),
          Paragraph("How the score is built, in five steps.", S["cap"])]

_cell_md = ParagraphStyle("cellmd", fontName="Inter-Md", fontSize=8, leading=10.5,
                          textColor=C_INK)
_cell = ParagraphStyle("cell", fontName="Inter", fontSize=8, leading=10.5,
                       textColor=C_INK)

THEMES = [
    ("Demand", "40%", "Net migration, job growth, and income growth. Markets that "
     "people and paychecks are moving into fill apartments first; migration is "
     "the screen's biggest bet."),
    ("Supply", "25%", "Building permits relative to existing housing, counted the "
     "opposite way: today's construction is tomorrow's competition."),
    ("Affordability", "20%", "Rent as a share of local income, and the cost of "
     "owning versus renting; when buying is far pricier, households stay renters "
     "longer."),
    ("Momentum", "10%", "Recent rent growth, deliberately held to a small weight: "
     "it decays and inverted badly in the 2020–22 shock."),
    ("Resilience", "5%", "Employment spread across industries; a one-sector "
     "economy carries more downside risk to rents."),
]
trows = [["Theme", "Weight", "The idea"]]
for _b, _share, _body in THEMES:
    trows.append([Paragraph(_b, _cell_md), _share, Paragraph(_body, _cell)])
story += [Paragraph("The five themes", S["h2"]),
          Image(str(P_WBAR), width=CW, height=CW * (0.72 / 7.0)),
          Spacer(1, 6),
          ruled_table(trows, [1.1 * inch, 0.7 * inch, 5.2 * inch],
                      body_size=8, align_right=(1,)),
          PageBreak()]

# ============================ 2. Key findings =================================
s1, s2 = data.top_strengths(top)
lift = " and ".join(s.lower() for s in (s1, s2) if s) or "balanced fundamentals"
lead_range = (f"; its 90% rank range is {int(top['rank_lo'])}–{int(top['rank_hi'])}"
              if pd.notna(top.get("rank_lo")) else "")
story += [*section_header(
              "home", "Multifamily research · the report", "Key findings",
              f"What the screen says right now: the {N} largest US rental markets, "
              "ranked by fundamentals that have historically come before strong rent "
              "growth.")]

story += [Paragraph(f"<b>{top_city} leads the current screen</b>, lifted most by "
                    f"{lift}{lead_range}.", S["bullet"], bulletText="•"),
          Paragraph(f"<b>The screen's top-10 markets out-grew the median market by "
                    f"{pp_pooled:+.1f} points of rent growth</b> across six completed "
                    f"windows; picking on recent rent growth alone earned "
                    f"{pp_mom:+.1f}.", S["bullet"], bulletText="•")]
if flag_on:
    story.append(Paragraph(
        f"Elevated-uncertainty flag: national rent growth in {YEAR} is {nat:+.1%}, "
        f"above the published rule; in the two years this flag fired historically "
        f"(2021 and 2022), the screen's accuracy broke down.", S["cap"]))

top3 = [t.split(",")[0].split("-")[0] for t in rank.head(3)["cbsa_title"]]
story += [Spacer(1, 6),
          Image(str(P_MAP), width=CW, height=CW * (560 / 980)),
          Paragraph(f"Green = above the average market (score 0), clay = below; the "
                    f"tiers group markets the data cannot separate. {top3[0]} leads; "
                    f"{top3[1]} and {top3[2]} round out the top three. The "
                    f"{YEAR}→{YEAR + 3} outlook.", S["cap"]),
          PageBreak()]

# ============================ 3. The top 10 ===================================
story += [Paragraph("The top 10", S["h2"])]
rows = [["Rank", "Metro", "What lifts it most"]]
for _, r in rank.head(10).iterrows():
    strengths = " · ".join(s for s in (r["strength_1"], r["strength_2"]) if s) \
        or "Broadly average"
    if int(r["n_indicators"]) < data.N_IND:
        strengths += f" · scored on {int(r['n_indicators'])} of {data.N_IND} measures"
    rng = (f"{int(r['rank'])}  ({int(r['rank_lo'])}–{int(r['rank_hi'])})"
           if pd.notna(r.get("rank_lo")) else f"{int(r['rank'])}")
    rows.append([rng, r["cbsa_title"], strengths])
story += [ruled_table(rows, [0.95 * inch, 2.75 * inch, 3.3 * inch], md_col=1),
          Paragraph("Rank (90% range: where the rank lands 90% of the time once "
                    "measurement noise is accounted for) and the themes lifting "
                    "each score most.", S["cap"])]

# ---- Why the leader leads (the site's surface card) -------------------------
case_bits = []
contribs = {b: top.get(f"bucket_{b}", 0.0) for b in data.BUCKETS}
for b in sorted(contribs, key=contribs.get, reverse=True)[:2]:
    if contribs[b] > 0.02:
        case_bits.append(f"{data.BUCKET_LABEL[b]} ({contribs[b]:+.2f})")
streak_txt = ""
_tr = d["rent_trend"]
_code = top["cbsa_code"]
if len(_tr) and (_tr.cbsa_code == _code).any():
    _mt = _tr[_tr.cbsa_code == _code].set_index("month")["yoy"]
    _us = _tr[_tr.cbsa_code == "US"].set_index("month")["yoy"]
    _j = pd.concat([_mt.rename("m"), _us.rename("u")], axis=1).dropna()
    _above = (_j["m"] > _j["u"]).tolist()
    _streak = 0
    for _v in reversed(_above):
        if not _v:
            break
        _streak += 1
    if _streak >= 3:
        streak_txt = (f" Its rents have out-grown the national median for "
                      f"{_streak} consecutive months.")
_case_head = ParagraphStyle("case_h", fontName="Serif-SB", fontSize=12.5,
                            leading=15.5, textColor=C_INK)
_case_tab = Table([[[
    Paragraph(f"Why {top_city} leads", _case_head),
    Spacer(1, 3),
    Paragraph(f"Strongest on "
              f"{' and '.join(case_bits) if case_bits else 'balanced fundamentals'} "
              f"(contribution to its score).{streak_txt} A #1 rank is a screening "
              f"result, not a verdict.", S["body"]),
    Paragraph(f"The full measure-by-measure case for {top_city}, and for every "
              f"other market, is on the companion site.", S["cap"])]]],
    colWidths=[CW])
_case_tab.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), C_SURFACE),
    ("BOX", (0, 0), (-1, -1), 0.8, C_LINE),
    ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
]))
story += [Spacer(1, 6), _case_tab, PageBreak()]

# ============================ 4. Track record =================================
story += [*section_header(
              "track_record", "Multifamily research · the fine print",
              "Track record",
              "Every published run is frozen with its scores, rankings, inputs, and "
              "settings, and never edited; the complete record, including the "
              "failures, is published. <b>The "
              "frozen 2025→2028 screen will be scored against realized rent growth "
              "when 2028 rent data closes (early 2029), whatever it shows.</b>")]

story += [Paragraph("The edge, in points of rent growth", S["h2"])]
piv = ew.pivot_table(index="pred_year", columns="strategy",
                     values="top10_pp_vs_median")
edge = piv[["Composite (model)", "Momentum (trailing rent)", "Equal weight",
            "Random (50-seed mean)"]].round(1)
erows = [["Window start", "This screen", "Rent momentum", "Equal weight", "Random"]]
edge_colors = []
for ri, (yr, r) in enumerate(edge.iterrows()):
    erows.append([f"{int(yr)}"] + [f"{v:+.1f}" for v in r.tolist()])
    for ci, v in enumerate(r.tolist()):
        edge_colors.append(("TEXTCOLOR", (ci + 1, ri + 1), (ci + 1, ri + 1),
                            C_POS if v > 0 else (C_NEG if v < 0 else C_INK)))
cm, mm = piv["Composite (model)"], piv["Momentum (trailing rent)"]
story += [ruled_table(erows, [1.3 * inch, 1.45 * inch, 1.45 * inch, 1.45 * inch,
                              1.35 * inch],
                      align_right=(0, 1, 2, 3, 4), extra=edge_colors),
          Paragraph(f"Percentage points of 3-year rent growth above the median "
                    f"market for each strategy's top-10; each call is frozen at "
                    f"publication and graded three years later. Pooled, this screen "
                    f"earned {cm.mean():+.1f} points (momentum {mm.mean():+.1f}); in "
                    f"the 2020–22 shock rows momentum flipped firmly negative while "
                    f"the screen held near flat. Rent data through July 2026.",
                    S["cap"])]

# ---- Honest limits ----------------------------------------------------------
story += [Paragraph("Honest limits",
                    ParagraphStyle("h2_tight", parent=S["h2"], spaceBefore=10)),
          Paragraph("The rent data measures asking rents, not signed leases; where "
                    "free-month move-in deals are common, asking rents understate the "
                    "true decline (one oversupplied market in mid-2026: asking rents "
                    "down about 2.6%, net of those deals about 7.2%).",
                    S["bullet"], bulletText="•"),
          Paragraph("No capital-markets or operating-cost data (sale prices, cap "
                    "rates, insurance, taxes); rent growth stands in for "
                    "profitability, and Florida's 2023–26 insurance-cost shock shows "
                    "what that misses.", S["bullet"], bulletText="•"),
          Paragraph("Measure weights are set by judgment and tested, not statistically "
                    "fitted.", S["bullet"], bulletText="•"),
          Paragraph("The supply measure reads permit levels in the scoring year, so "
                    "sharp turns in construction can show up with a lag.",
                    S["bullet"], bulletText="•"),
          Paragraph("In shock periods like 2020–22 the screen loses most of its edge; "
                    "treat it as a screen, not a forecast.", S["bullet"],
                    bulletText="•"),
          PageBreak()]

# ============================ 5. The companion site ===========================
story += [eyebrow("The companion site"),
          Paragraph("This report is the snapshot", S["h1"]), *hr(),
          Paragraph("The interactive site is the working product. On it:",
                    S["body"]),
          Paragraph(f"All {N} markets, ranked, tiered, and mapped, with each "
                    f"market's 90% rank range and its move versus the prior frozen "
                    f"edition.", S["bullet"], bulletText="•"),
          Paragraph("A detail page for every market: its score, the themes driving "
                    "it, and each measure in plain terms, with side-by-side "
                    "comparison.", S["bullet"], bulletText="•")]
if have_spec26:
    story.append(Paragraph(
        "A 2026→2029 outlook built on data through May 2026, labeled speculative "
        "throughout: that configuration failed validation.",
        S["bullet"], bulletText="•"))
story += [Paragraph("The full track record: every graded window, the interim reads "
                    "on the newer calls, and the frozen registry of every published "
                    "run.", S["bullet"], bulletText="•"),
          Paragraph("The data behind each measure, its source and vintage, and the "
                    "boundary corrections that rebuilt it.", S["bullet"],
                    bulletText="•")]
if config.SITE_URL:
    story += [Spacer(1, 4),
              Paragraph(f'Read it live: <link href="{config.SITE_URL}">'
                        f'<font color="{ACCENT}">{config.SITE_URL}</font></link>',
                        S["body"])]

# ---- About the author -------------------------------------------------------
# The site's author photo (app/assets/author.jpg), print edition: photo left,
# bio right, mirroring the How-it-works author block.
_author_photo = APP / "assets" / "author.jpg"
_author_text = [
    Paragraph("My name is <b>Ben Larson</b>, and I am a junior at <b>Indiana "
              "University</b> studying economics and applied math. My research "
              "interests center on quantitative market selection: applying data "
              "to identify optimal real estate markets across the U.S. and to "
              "help inform investment decisions across commercial real estate "
              "asset classes, including multifamily, industrial, retail, office, "
              "and data centers.", S["body"]),
    Paragraph(f'Contact: <link href="mailto:blarson5187@gmail.com">'
              f'<font color="{ACCENT}">blarson5187@gmail.com</font></link> · '
              f'<link href="https://www.linkedin.com/in/blarson1105">'
              f'<font color="{ACCENT}">linkedin.com/in/blarson1105</font></link>',
              S["body"]),
]
story += [Paragraph("About the author", S["h2"])]
if _author_photo.exists():
    _author_tab = Table(
        [[Image(str(_author_photo), width=1.25 * inch, height=1.5625 * inch),
          _author_text]],
        colWidths=[1.45 * inch, CW - 1.45 * inch])
    _author_tab.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 12),
    ]))
    story += [_author_tab]
else:
    story += _author_text

# ---- The fine print ---------------------------------------------------------
story += [Spacer(1, 24), *hr(),
          Paragraph("This report is a research screen built on free public data "
                    "(Census, IRS, BLS, BEA, Zillow, FRED). It is intended for "
                    "general information purposes only, is not investment advice, and "
                    "is not an offer or solicitation of any kind. Rankings reflect a "
                    "validated statistical screen of historical fundamentals; they "
                    "are not predictions of any individual market's performance, and "
                    "in shock periods the framework loses most of its edge. Verify "
                    "all figures against the primary sources before relying on them.",
                    S["cap"])]

print("building pdf...")
doc.build(story)
print(f"done: {OUT}")
