"""
streamlit_app.py — the interactive screener website (M5, styled in M6).

Four views:
  1. Map         — every metro as a point, colored by composite score.
  2. Rankings    — the full sortable leaderboard with bucket subscores.
  3. Metro detail — pick a metro; its rank, score, and each indicator's value +
                    percentile, so the score is fully explainable.
  4. Methodology — the walk-forward track record + methodology/limitations.

The presentation follows an editorial-research / fintech design language
(serif masthead + Inter UI, a single teal accent, a muted diverging score
scale, KPI stat band, hidden Streamlit chrome).

Run locally:
    .venv/Scripts/python.exe -m streamlit run app/streamlit_app.py

Reads the committed data/processed/ outputs and recomputes the (cheap)
indicator/score steps, so it works on Streamlit Community Cloud with no keys.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config                                   # noqa: E402
from src import indicators, normalize           # noqa: E402
from src import score as score_mod              # noqa: E402

SCORE_YEAR = score_mod.SCORE_YEAR
INDICATORS = config.INDICATORS
PRETTY = {
    "net_migration": "Net domestic migration",
    "job_growth": "Job growth (YoY)",
    "income_growth": "Income growth (YoY)",
    "population_growth": "Population growth (YoY)",
    "permits_to_stock": "Permits ÷ housing stock",
    "mf_pipeline": "Multifamily pipeline",
    "rent_to_income": "Rent-to-income",
    "cost_to_own_vs_rent": "Cost-to-own vs rent",
    "trailing_rent_growth": "Trailing rent growth (YoY)",
    "employment_diversity": "Employment diversity",
}

# Plain-English (strength, watch-out) phrasing for each indicator — used to turn
# the numbers into a readable outlook for non-analysts.
OUTLOOK = {
    "net_migration": ("People are moving in faster than most metros",
                      "More residents are leaving than arriving"),
    "job_growth": ("Jobs are growing faster than most metros",
                   "Job growth is lagging the pack"),
    "income_growth": ("Local incomes are rising quickly",
                      "Income growth is sluggish"),
    "population_growth": ("The population is expanding",
                          "Population is flat or shrinking"),
    "permits_to_stock": ("Very little new building — tight supply supports rents",
                         "Heavy homebuilding raises oversupply risk"),
    "mf_pipeline": ("Few new apartments in the pipeline",
                    "A large apartment pipeline is adding competition"),
    "rent_to_income": ("Rents are affordable vs. local incomes, leaving room to grow",
                       "Rents already stretch local incomes"),
    "cost_to_own_vs_rent": ("Buying is far pricier than renting, keeping demand in rentals",
                            "Buying is relatively cheap, which can pull renters into ownership"),
    "trailing_rent_growth": ("Rents have been climbing lately",
                             "Recent rent growth has been weak"),
    "employment_diversity": ("A diverse job base makes it more resilient",
                             "The economy leans on just a few industries"),
}

# Approximate state-label positions (lat, lon) for putting abbreviations on the map.
STATE_CENTROIDS = {
    "AL": (32.8, -86.8), "AZ": (34.2, -111.7), "AR": (34.8, -92.4), "CA": (37.2, -119.5),
    "CO": (39.0, -105.5), "CT": (41.6, -72.7), "DE": (39.0, -75.5), "DC": (38.9, -77.0),
    "FL": (28.6, -81.7), "GA": (32.9, -83.4), "HI": (20.8, -156.3), "ID": (44.2, -114.5),
    "IL": (40.0, -89.2), "IN": (39.9, -86.3), "IA": (42.0, -93.5), "KS": (38.5, -98.4),
    "KY": (37.5, -85.3), "LA": (31.0, -92.0), "ME": (45.4, -69.2), "MD": (39.0, -76.8),
    "MA": (42.3, -71.9), "MI": (44.3, -85.0), "MN": (46.3, -94.3), "MS": (32.7, -89.7),
    "MO": (38.4, -92.5), "MT": (47.0, -109.6), "NE": (41.5, -99.8), "NV": (39.3, -116.6),
    "NH": (43.7, -71.6), "NJ": (40.1, -74.7), "NM": (34.4, -106.1), "NY": (42.9, -75.5),
    "NC": (35.5, -79.4), "ND": (47.5, -100.5), "OH": (40.3, -82.8), "OK": (35.6, -97.5),
    "OR": (43.9, -120.6), "PA": (40.9, -77.8), "RI": (41.7, -71.5), "SC": (33.9, -80.9),
    "SD": (44.4, -100.2), "TN": (35.8, -86.4), "TX": (31.3, -99.3), "UT": (39.3, -111.7),
    "VT": (44.1, -72.7), "VA": (37.6, -78.8), "WA": (47.4, -120.5), "WV": (38.6, -80.6),
    "WI": (44.6, -89.9), "WY": (43.0, -107.5),
}

# ---- Design tokens (dark theme) -------------------------------------------
INK = "#F1F5F9"        # headings / near-white
BODY = "#CBD5E1"       # body text
MUTED = "#8595A6"      # secondary text
ACCENT = "#2DD4BF"     # bright teal accent
HAIRLINE = "#1E2A38"   # subtle borders
PAGE_BG = "#0C1118"
CARD_BG = "#121A24"
# Muted diverging scale tuned for dark: red -> desaturated slate -> green.
SCORE_SCALE = [[0.0, "#D6504A"], [0.25, "#C2877F"], [0.5, "#9AA6B4"],
               [0.75, "#5FB78E"], [1.0, "#2E9E72"]]
GRAD_STOPS = [(0.0, (214, 80, 74)), (0.5, (154, 166, 180)), (1.0, (46, 158, 114))]

st.set_page_config(page_title="Multifamily Market Screener",
                   page_icon="◴", layout="wide")


# ---- Styling helpers ------------------------------------------------------
def inject_css() -> None:
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&display=swap');

      html, body, [class*="css"], .stApp {{
          font-family: 'Inter', -apple-system, system-ui, sans-serif;
          color: {BODY};
      }}
      .stApp {{ background: {PAGE_BG}; }}

      /* Hide Streamlit chrome for a product look */
      [data-testid="stHeader"], [data-testid="stToolbar"] {{ display: none; }}
      #MainMenu, footer {{ visibility: hidden; }}
      .block-container {{ padding: 1.4rem 2.6rem 4rem; max-width: 1240px; }}

      h1, h2, h3 {{ color: {INK}; letter-spacing: -0.01em; }}

      /* Masthead */
      .masthead {{ border-bottom: 1px solid {HAIRLINE}; padding-bottom: 1.1rem; margin-bottom: 1.5rem; }}
      .kicker {{ font-size: .72rem; font-weight: 600; letter-spacing: .16em;
                 text-transform: uppercase; color: {ACCENT}; margin-bottom: .35rem; }}
      .wordmark {{ font-family: 'Source Serif 4', Georgia, serif; font-weight: 600;
                   font-size: 2.35rem; line-height: 1.1; color: {INK}; margin: 0; }}
      .subhead {{ color: {MUTED}; font-size: 1.02rem; margin-top: .45rem; max-width: 760px; }}
      .subhead b {{ color: {BODY}; }}
      .badge {{ display:inline-block; font-size:.72rem; font-weight:600; color:{ACCENT};
                background:rgba(45,212,191,.10); border:1px solid rgba(45,212,191,.30);
                border-radius:999px; padding:.18rem .6rem; letter-spacing:.02em; }}

      /* KPI stat band */
      .statband {{ display:flex; gap:14px; margin:0 0 1.6rem; flex-wrap:wrap; }}
      .stat {{ flex:1; min-width:170px; background:{CARD_BG}; border:1px solid {HAIRLINE};
               border-radius:12px; padding:.95rem 1.1rem; }}
      .stat .lab {{ font-size:.7rem; font-weight:600; letter-spacing:.1em;
                    text-transform:uppercase; color:{MUTED}; }}
      .stat .val {{ font-size:1.65rem; font-weight:700; color:{INK}; line-height:1.15;
                    margin-top:.25rem; font-variant-numeric: tabular-nums; }}
      .stat .sub {{ font-size:.8rem; color:{MUTED}; margin-top:.1rem; }}

      /* Nav (radio styled as tabs) */
      [data-testid="stRadio"] {{ margin-bottom: 1.4rem; }}
      [data-testid="stRadio"] > div {{ gap: 0 !important; }}
      [data-testid="stRadio"] [role="radiogroup"] {{ gap: 1.8rem; border-bottom:1px solid {HAIRLINE}; }}
      [data-testid="stRadio"] label {{ padding:.45rem 0 !important; margin:0 !important; }}
      [data-testid="stRadio"] label > div:first-child {{ display:none !important; }}  /* hide the circle */
      [data-testid="stRadio"] label p {{ color:{MUTED}; font-weight:600; font-size:.98rem; }}
      [data-testid="stRadio"] label:has(input:checked) p {{ color:{INK}; }}
      [data-testid="stRadio"] label:has(input:checked) {{ border-bottom:2px solid {ACCENT}; }}

      /* Section headers */
      .sec {{ font-family:'Source Serif 4',Georgia,serif; font-size:1.35rem; font-weight:600;
              color:{INK}; margin:.2rem 0 .15rem; }}
      .secsub {{ color:{MUTED}; font-size:.9rem; margin-bottom:1rem; }}

      /* Metric cards (detail tab) */
      [data-testid="stMetric"] {{ background:{CARD_BG}; border:1px solid {HAIRLINE};
          border-radius:12px; padding:.9rem 1.1rem; }}
      [data-testid="stMetricLabel"] p {{ font-size:.72rem; font-weight:600;
          letter-spacing:.08em; text-transform:uppercase; color:{MUTED}; }}
      [data-testid="stMetricValue"] {{ color:{INK}; font-weight:700; }}

      [data-testid="stDataFrame"] {{ border:1px solid {HAIRLINE}; border-radius:12px; }}
      .cap {{ color:{MUTED}; font-size:.82rem; margin-top:.5rem; }}
      hr {{ border-color:{HAIRLINE}; }}

      /* Pro/con outlook cards */
      .outlook {{ background:{CARD_BG}; border:1px solid {HAIRLINE}; border-radius:12px;
                  padding:1rem 1.2rem; height:100%; }}
      .ohead {{ font-weight:700; font-size:.95rem; margin-bottom:.55rem; }}
      .ohead.good {{ color:#34D399; }} .ohead.bad {{ color:#F08C84; }}
      .olist {{ list-style:none; padding:0; margin:0; }}
      .olist li {{ margin:.45rem 0; color:{BODY}; font-size:.92rem; line-height:1.4; }}
      .ic {{ font-weight:700; margin-right:.55rem; }}
      .ic.good {{ color:#34D399; }} .ic.bad {{ color:#F08C84; }}
    </style>
    """, unsafe_allow_html=True)


def grad_css(t: float) -> str:
    """Map t in [0,1] to a colored cell, picking black/white text for contrast."""
    if pd.isna(t):
        return ""
    t = max(0.0, min(1.0, float(t)))
    for (t0, c0), (t1, c1) in zip(GRAD_STOPS, GRAD_STOPS[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            rgb = tuple(int(c0[i] + (c1[i] - c0[i]) * f) for i in range(3))
            lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
            txt = "#0B1118" if lum > 150 else "#FFFFFF"
            return f"background-color: rgb{rgb}; color: {txt};"
    return ""


def section(title: str, sub: str = "") -> None:
    st.markdown(f"<div class='sec'>{title}</div>"
                + (f"<div class='secsub'>{sub}</div>" if sub else ""),
                unsafe_allow_html=True)


def style_fig(fig: go.Figure, height: int = 540) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=8, b=0),
        font=dict(family="Inter, sans-serif", color=BODY, size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(font_family="Inter, sans-serif", bgcolor=CARD_BG,
                        font_color=INK, bordercolor=HAIRLINE),
    )
    return fig


# ---- Data -----------------------------------------------------------------
@st.cache_data
def load_data():
    scored = score_mod.score()
    raw = indicators.compute_indicators()
    norm = normalize.normalize()
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    coords = pd.read_csv(config.PROCESSED_DIR / "metro_coords.csv", dtype={"cbsa_code": str})
    backtest = pd.read_csv(config.PROCESSED_DIR / "backtest_summary.csv")
    return scored, raw, norm, panel, coords, backtest


inject_css()
scored, raw, norm, panel, coords, backtest = load_data()
rank_year = scored[scored["year"] == SCORE_YEAR].copy()
raw_year = raw[raw["year"] == SCORE_YEAR].set_index("cbsa_code")
norm_year = norm[norm["year"] == SCORE_YEAR].set_index("cbsa_code")
pctile = norm_year[list(INDICATORS)].rank(pct=True) * 100

# ---- Masthead -------------------------------------------------------------
top_metro = rank_year.sort_values("rank").iloc[0]["cbsa_title"].split("-")[0].split(",")[0]
pc = backtest[(backtest["horizon"] == 3) & (backtest["regime"] == "pre_covid")]
pc_tau = pc["mean_tau"].iloc[0] if len(pc) else float("nan")

st.markdown(f"""
<div class="masthead">
  <div class="kicker">Multifamily Research · v{config.MODEL_VERSION}</div>
  <h1 class="wordmark">The Rent-Growth Screener</h1>
  <div class="subhead">A transparent, backtested framework ranking the {len(rank_year)} largest US
  metros by their fundamentals for <b>3-year forward rent growth</b> — built entirely on free public
  data. A screening framework, not a crystal ball.</div>
  <div style="margin-top:.7rem"><span class="badge">{SCORE_YEAR} cross-section</span></div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="statband">
  <div class="stat"><div class="lab">Metros screened</div><div class="val">{len(rank_year)}</div>
       <div class="sub">≥ 500k population, full rent history</div></div>
  <div class="stat"><div class="lab">Indicators</div><div class="val">10</div>
       <div class="sub">across 5 fundamental buckets</div></div>
  <div class="stat"><div class="lab">Backtest accuracy</div><div class="val">τ {pc_tau:.2f}</div>
       <div class="sub">pre-COVID 3-yr, weighted Kendall&#39;s τ</div></div>
  <div class="stat"><div class="lab">Top-ranked market</div><div class="val">{top_metro}</div>
       <div class="sub">strongest {SCORE_YEAR} fundamentals</div></div>
</div>
""", unsafe_allow_html=True)

# Stateful nav: unlike st.tabs (which resets to the first tab on every rerun),
# a keyed radio remembers the selected view in session_state, so changing the
# metro dropdown keeps you on the Metro-detail view. Styled as tabs via CSS.
page = st.radio(
    "View", ["Map", "Rankings", "Metro detail", "Methodology"],
    horizontal=True, key="nav", label_visibility="collapsed")


# ---- 1. Map ---------------------------------------------------------------
if page == "Map":
    section("Composite score by metro",
            f"{SCORE_YEAR} cross-section · green = stronger fundamentals · hover for rank & score")
    mp = rank_year.merge(coords, on="cbsa_code", how="left")
    fig = px.scatter_geo(
        mp, lat="lat", lon="lon", color="score", scope="usa",
        hover_name="cbsa_title", size=[8] * len(mp), size_max=13,
        color_continuous_scale=SCORE_SCALE, color_continuous_midpoint=0,
        custom_data=["rank", "score"])
    fig.update_traces(
        marker=dict(line=dict(width=0.5, color="rgba(255,255,255,0.35)")),
        hovertemplate="<b>%{hovertext}</b><br>Rank %{customdata[0]} · "
                      "score %{customdata[1]:.3f}<extra></extra>")
    fig.update_geos(showland=True, landcolor="#17202B", showlakes=False,
                    subunitcolor="#2A3744", countrycolor="#2A3744",
                    bgcolor="rgba(0,0,0,0)", showframe=False, coastlinecolor="#2A3744")
    # Faint state abbreviations at state centroids for geographic context.
    fig.add_trace(go.Scattergeo(
        lat=[v[0] for v in STATE_CENTROIDS.values()],
        lon=[v[1] for v in STATE_CENTROIDS.values()],
        text=list(STATE_CENTROIDS), mode="text",
        textfont=dict(family="Inter, sans-serif", size=9, color="#55657A"),
        hoverinfo="skip", showlegend=False))
    fig.update_layout(coloraxis_colorbar=dict(title="Score", thickness=12, len=0.7),
                      showlegend=False)
    st.plotly_chart(style_fig(fig, 560), use_container_width=True)


# ---- 2. Rankings ----------------------------------------------------------
if page == "Rankings":
    section(f"Full ranking — {len(rank_year)} metros",
            "Weighted z-score contribution per bucket · click a header to sort")
    show = rank_year[["rank", "cbsa_title", "score", "bucket_Demand", "bucket_Supply",
                      "bucket_Affordability", "bucket_Momentum", "bucket_Resilience",
                      "n_indicators"]].rename(columns={
        "rank": "Rank", "cbsa_title": "Metro", "score": "Score", "bucket_Demand": "Demand",
        "bucket_Supply": "Supply", "bucket_Affordability": "Afford.",
        "bucket_Momentum": "Moment.", "bucket_Resilience": "Resil.",
        "n_indicators": "Data"})
    smin, smax = show["Score"].min(), show["Score"].max()
    num_cols = ["Score", "Demand", "Supply", "Afford.", "Moment.", "Resil."]
    styler = (show.style
              .format({c: "{:+.3f}" for c in num_cols} | {"Data": "{:.0f}/10"})
              .map(lambda v: grad_css((v - smin) / (smax - smin)), subset=["Score"])
              .set_properties(subset=num_cols, **{"font-variant-numeric": "tabular-nums"})
              .set_properties(subset=["Metro"], **{"font-weight": "600", "color": INK}))
    st.dataframe(styler, hide_index=True, use_container_width=True, height=600,
                 column_config={"Rank": st.column_config.NumberColumn(width="small")})


# ---- 3. Metro detail ------------------------------------------------------
if page == "Metro detail":
    metro = st.selectbox("Select a metro", rank_year.sort_values("cbsa_title")["cbsa_title"],
                         label_visibility="collapsed")
    row = rank_year[rank_year["cbsa_title"] == metro].iloc[0]
    code = row["cbsa_code"]
    section(metro, f"Composite rank and the fundamentals behind it · {SCORE_YEAR}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Rank", f"#{int(row['rank'])}", help=f"of {len(rank_year)} metros")
    c2.metric("Composite score", f"{row['score']:+.3f}")
    c3.metric("Indicator coverage", f"{int(row['n_indicators'])}/10")

    # Plain-English outlook auto-generated from this metro's percentiles.
    PRO_T, CON_T = 65, 35
    pros, cons = [], []
    for k in INDICATORS:
        p = pctile[k].get(code, float("nan"))
        if pd.isna(p):
            continue
        if p >= PRO_T:
            pros.append((OUTLOOK[k][0], p))
        elif p <= CON_T:
            cons.append((OUTLOOK[k][1], p))
    pros = [t for t, _ in sorted(pros, key=lambda x: -x[1])][:5]
    cons = [t for t, _ in sorted(cons, key=lambda x: x[1])][:5]

    def _bullets(items, kind, empty):
        if not items:
            return f"<li style='color:{MUTED}'>{empty}</li>"
        mark = "✓" if kind == "good" else "✕"
        return "".join(f"<li><span class='ic {kind}'>{mark}</span>{i}</li>" for i in items)

    st.markdown("<div class='cap' style='margin:.6rem 0 .4rem'><b>The quick read</b> — "
                "auto-generated from how this metro ranks across the 10 indicators.</div>",
                unsafe_allow_html=True)
    oc1, oc2 = st.columns(2)
    oc1.markdown(f"<div class='outlook'><div class='ohead good'>Strengths</div>"
                 f"<ul class='olist'>{_bullets(pros, 'good', 'No standout strengths this year.')}"
                 f"</ul></div>", unsafe_allow_html=True)
    oc2.markdown(f"<div class='outlook'><div class='ohead bad'>Watch-outs</div>"
                 f"<ul class='olist'>{_bullets(cons, 'bad', 'No major red flags this year.')}"
                 f"</ul></div>", unsafe_allow_html=True)
    st.write("")

    rows = []
    for key in INDICATORS:
        rows.append({"Indicator": PRETTY[key], "Bucket": INDICATORS[key]["bucket"],
                     "Weight": INDICATORS[key]["weight"] * 100,
                     "Value": raw_year[key].get(code, float("nan")),
                     "Percentile": pctile[key].get(code, float("nan"))})
    detail = pd.DataFrame(rows)
    st.markdown("<div class='cap'>Percentile vs all metros (100 = best on that indicator; "
                "direction already applied so higher is always better).</div>",
                unsafe_allow_html=True)
    dstyler = (detail.style
               .format({"Weight": "{:.0f}%", "Value": "{:.4g}", "Percentile": "{:.0f}"})
               .map(lambda v: grad_css(v / 100.0), subset=["Percentile"])
               .set_properties(subset=["Indicator"], **{"font-weight": "600", "color": INK}))
    st.dataframe(dstyler, hide_index=True, use_container_width=True, height=395)

    hist = panel[panel["cbsa_code"] == code][["year", "zori"]].dropna()
    if len(hist):
        figh = px.line(hist, x="year", y="zori", markers=True)
        figh.update_traces(line=dict(color=ACCENT, width=2.5),
                           marker=dict(color=ACCENT, size=6))
        figh.update_xaxes(showgrid=False, title=None, dtick=1)
        figh.update_yaxes(showgrid=True, gridcolor=HAIRLINE, title="ZORI rent ($/mo)")
        st.markdown("<div class='cap' style='margin-top:1rem'><b>Rent history</b> — "
                    "Zillow Observed Rent Index</div>", unsafe_allow_html=True)
        st.plotly_chart(style_fig(figh, 300), use_container_width=True)


# ---- 4. Methodology -------------------------------------------------------
if page == "Methodology":
    section("How the screener works", "From raw public data to a single ranking — in plain English")
    st.markdown("""
The screener scores all **110 metros** on **10 fundamental indicators**, grouped into five
themes. For each indicator it compares every metro **against all the others in the same year**,
so a nationwide swing cancels out and only a metro's *relative* standing counts. Measures where
"more is worse" (like heavy homebuilding, or rent that already eats up local incomes) are
flipped, so **higher always means better**. Each indicator is then multiplied by a fixed weight
and summed into one **composite score**, and metros are ranked by it. The same formula runs for
every metro — nothing is hand-picked.""")

    bucket_order = ["Demand", "Supply", "Affordability", "Momentum", "Resilience"]
    brows = []
    for b in bucket_order:
        ks = [k for k in INDICATORS if INDICATORS[k]["bucket"] == b]
        w = sum(INDICATORS[k]["weight"] for k in ks)
        brows.append({"Theme": b, "Weight": f"{w*100:.0f}%",
                      "What it captures": " · ".join(PRETTY[k] for k in ks)})
    st.dataframe(
        pd.DataFrame(brows).style.set_properties(
            subset=["Theme"], **{"font-weight": "600", "color": INK})
        .set_properties(subset=["Weight"], **{"color": ACCENT, "font-weight": "600"}),
        hide_index=True, use_container_width=True)
    st.markdown("<div class='cap'>Demand leads at 40% — the framework bets that who's moving in, "
                "hiring, and earning matters most over a 3-year horizon, with a heavy supply "
                "penalty (25%) as the contrarian edge. Weights are hand-set hypotheses for v1, "
                "tested below.</div>", unsafe_allow_html=True)

    st.write("")
    section("Does it actually work?", "Walk-forward backtest — the model never sees the future")
    st.markdown(
        "Each year's ranking is compared against **realized forward rent growth** "
        "(3-year primary, 1-year contrast), ranked across metros. Metric: top-weighted "
        "Kendall's τ (rewards getting the true top markets right) and precision@10 "
        "(share of the top 10 that landed in the realized top quartile).")
    bt = backtest.rename(columns={"horizon": "Horizon", "regime": "Regime",
                                  "n_windows": "Windows", "mean_tau": "Mean τ",
                                  "mean_precision@10": "Precision@10"})
    bt["Regime"] = bt["Regime"].str.replace("_", "-").str.title()
    st.dataframe(
        bt.style.format({"Mean τ": "{:.3f}", "Precision@10": "{:.2f}", "Horizon": "{:.0f}y"})
          .set_properties(subset=["Mean τ", "Precision@10"], **{"font-variant-numeric": "tabular-nums"}),
        hide_index=True, use_container_width=True)

    cols = st.columns(2)
    with cols[0]:
        st.markdown(f"""<div class='sec' style='font-size:1.05rem'>How to read it</div>
        The framework is strong in the **pre-COVID** regime (τ ≈ {pc_tau:.2f}, ~88% precision)
        and **breaks down during the 2020–22 shock**, when stimulus and remote-work churn
        distorted fundamentals. We report that openly — a model that claimed to work
        everywhere would be the less credible one.""", unsafe_allow_html=True)
    with cols[1]:
        st.markdown("""<div class='sec' style='font-size:1.05rem'>Limitations</div>
        Rent history starts ~2015 → few independent windows, so results are **directional
        evidence, not statistical proof**. ZORI is asking (not executed) rent. No
        capital-markets data (cap rates, transaction volume); rent growth is the proxy for
        profitability. v1 weights are hand-set hypotheses, not fitted.""", unsafe_allow_html=True)


st.markdown(f"""<hr style='margin-top:2.5rem'>
<div class='cap'>Built on free public data — Census · IRS · BLS/QCEW · BEA · Zillow · FRED.
Methodology &amp; rationale in <code>decision-log.md</code>. Model v{config.MODEL_VERSION}.</div>
""", unsafe_allow_html=True)
