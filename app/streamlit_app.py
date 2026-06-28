"""
streamlit_app.py — the interactive screener website (M5).

Four views:
  1. Map        — every metro as a point, colored by composite score.
  2. Ranking    — the full sortable leaderboard with bucket subscores.
  3. Metro detail — pick a metro; see its rank, score, and each indicator's
                    value + percentile, so the score is fully explainable.
  4. Backtest & method — the walk-forward track record + methodology/limitations.

Run locally:
    .venv/Scripts/python.exe -m streamlit run app/streamlit_app.py

It reads the committed data/processed/ outputs and recomputes the (cheap)
indicator/score steps, so it works on Streamlit Community Cloud with no keys.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config                                   # noqa: E402
from src import indicators, normalize           # noqa: E402
from src import score as score_mod              # noqa: E402

SCORE_YEAR = score_mod.SCORE_YEAR
INDICATORS = config.INDICATORS
PRETTY = {                                       # display labels for the 10 indicators
    "net_migration": "Net domestic migration (rate)",
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

st.set_page_config(page_title="Multifamily Market Screener", layout="wide")

# Red -> yellow -> green CSS gradient (avoids a heavy matplotlib dependency that
# pandas' built-in background_gradient would require).
_GRAD_STOPS = [(0.0, (215, 48, 39)), (0.5, (255, 221, 120)), (1.0, (26, 152, 80))]


def _grad_css(t: float) -> str:
    """Map t in [0,1] to a 'background-color: rgb(...)' string; '' if missing."""
    if pd.isna(t):
        return ""
    t = max(0.0, min(1.0, float(t)))
    for (t0, c0), (t1, c1) in zip(_GRAD_STOPS, _GRAD_STOPS[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            rgb = tuple(int(c0[i] + (c1[i] - c0[i]) * f) for i in range(3))
            return f"background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]})"
    return ""


@st.cache_data
def load_data():
    """Compute + load everything once (cached across reruns)."""
    scored = score_mod.score()
    raw = indicators.compute_indicators()
    norm = normalize.normalize()
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    coords = pd.read_csv(config.PROCESSED_DIR / "metro_coords.csv",
                         dtype={"cbsa_code": str})
    backtest = pd.read_csv(config.PROCESSED_DIR / "backtest_summary.csv")
    return scored, raw, norm, panel, coords, backtest


scored, raw, norm, panel, coords, backtest = load_data()
rank_year = scored[scored["year"] == SCORE_YEAR].copy()
raw_year = raw[raw["year"] == SCORE_YEAR].set_index("cbsa_code")
norm_year = norm[norm["year"] == SCORE_YEAR].set_index("cbsa_code")
# direction-aware percentile (higher = better) from the normalized z-scores
pctile = norm_year[list(INDICATORS)].rank(pct=True) * 100

st.title("🏙️ Multifamily Market Screener")
st.caption(f"Ranking ~110 large US metros by 3-year forward rent-growth potential · "
           f"{SCORE_YEAR} cross-section · free public data · a screening framework, not a crystal ball")

tab_map, tab_rank, tab_detail, tab_method = st.tabs(
    ["🗺️ Map", "📊 Ranking", "🔍 Metro detail", "🧪 Backtest & method"])


# --------------------------------------------------------------------------
# 1. Map
# --------------------------------------------------------------------------
with tab_map:
    st.subheader(f"Composite score by metro — {SCORE_YEAR}")
    mp = rank_year.merge(coords, on="cbsa_code", how="left")
    fig = px.scatter_geo(
        mp, lat="lat", lon="lon", color="score", scope="usa",
        hover_name="cbsa_title", size=[10] * len(mp), size_max=12,
        color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
        custom_data=["rank", "score"],
    )
    fig.update_traces(hovertemplate="<b>%{hovertext}</b><br>rank %{customdata[0]} · "
                                    "score %{customdata[1]:.3f}<extra></extra>")
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Green = higher composite score (more attractive on fundamentals). "
               "Hover for rank and score.")


# --------------------------------------------------------------------------
# 2. Ranking
# --------------------------------------------------------------------------
with tab_rank:
    st.subheader(f"Full ranking — {len(rank_year)} metros")
    show = rank_year[["rank", "cbsa_title", "score", "bucket_Demand", "bucket_Supply",
                      "bucket_Affordability", "bucket_Momentum", "bucket_Resilience",
                      "n_indicators"]].rename(columns={
        "cbsa_title": "Metro", "score": "Score", "bucket_Demand": "Demand",
        "bucket_Supply": "Supply", "bucket_Affordability": "Afford.",
        "bucket_Momentum": "Momentum", "bucket_Resilience": "Resil.",
        "n_indicators": "Cov."})
    smin, smax = show["Score"].min(), show["Score"].max()
    st.dataframe(
        show.style.format({c: "{:+.3f}" for c in
                           ["Score", "Demand", "Supply", "Afford.", "Momentum", "Resil."]})
            .map(lambda v: _grad_css((v - smin) / (smax - smin)), subset=["Score"]),
        hide_index=True, use_container_width=True, height=560)
    st.caption("Columns are weighted z-score contributions per bucket. "
               "Cov. = how many of the 10 indicators the metro had (rest treated as neutral). "
               "Click a column header to sort.")


# --------------------------------------------------------------------------
# 3. Metro detail
# --------------------------------------------------------------------------
with tab_detail:
    metro = st.selectbox("Choose a metro", rank_year.sort_values("cbsa_title")["cbsa_title"])
    row = rank_year[rank_year["cbsa_title"] == metro].iloc[0]
    code = row["cbsa_code"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Rank", f"{int(row['rank'])} of {len(rank_year)}")
    c2.metric("Composite score", f"{row['score']:+.3f}")
    c3.metric("Indicator coverage", f"{int(row['n_indicators'])}/10")

    st.markdown("**Indicator detail** — raw value, and percentile vs all metros "
                "(100 = best on that indicator, direction already applied):")
    rows = []
    for key in INDICATORS:
        rawval = raw_year[key].get(code, float("nan"))
        pct = pctile[key].get(code, float("nan"))
        rows.append({"Indicator": PRETTY[key],
                     "Bucket": INDICATORS[key]["bucket"],
                     "Weight": f"{INDICATORS[key]['weight']*100:.0f}%",
                     "Raw value": rawval, "Percentile": pct})
    detail = pd.DataFrame(rows)
    st.dataframe(
        detail.style.format({"Raw value": "{:.4g}", "Percentile": "{:.0f}"})
              .map(lambda v: _grad_css(v / 100.0), subset=["Percentile"]),
        hide_index=True, use_container_width=True)

    # Rent history for context.
    hist = panel[panel["cbsa_code"] == code][["year", "zori"]].dropna()
    if len(hist):
        figh = px.line(hist, x="year", y="zori", markers=True,
                       title=f"{metro} — ZORI rent ($/mo)")
        figh.update_layout(height=320, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(figh, use_container_width=True)


# --------------------------------------------------------------------------
# 4. Backtest & method
# --------------------------------------------------------------------------
with tab_method:
    st.subheader("Does it actually work? Walk-forward backtest")
    st.markdown(
        "Each year's ranking is compared against **realized forward rent growth** "
        "(3-year primary, 1-year contrast), ranked across metros. The model never "
        "sees the future. Metric: top-weighted Kendall's τ (rewards getting the "
        "true top markets right) and precision@10 (share of the top 10 that landed "
        "in the realized top quartile).")
    st.dataframe(
        backtest.rename(columns={"horizon": "Horizon (yr)", "regime": "Regime",
                                 "n_windows": "Windows", "mean_tau": "Mean τ",
                                 "mean_precision@10": "Mean precision@10"})
            .style.format({"Mean τ": "{:.3f}", "Mean precision@10": "{:.2f}"}),
        hide_index=True, use_container_width=True)
    st.markdown(
        "**How to read it:** the framework is strong in the **pre-COVID** regime "
        "(τ≈0.6, ~88% precision) and **breaks down in the 2020–22 shock** — exactly "
        "as expected when fundamentals were distorted by stimulus and remote-work "
        "churn. We report this rather than hide it.\n\n"
        "**Limitations:** rent history starts ~2015, so there are few independent "
        "windows — results are *directional evidence, not statistical proof*. ZORI "
        "is asking (not executed) rent. No capital-markets data (cap rates, "
        "transaction volume); rent growth is the proxy for profitability. v1 weights "
        "are hand-set hypotheses, not fitted. Full reasoning lives in `decision-log.md`.")


st.divider()
st.caption("Built with free public data (Census, IRS, BLS/QCEW, BEA, Zillow, FRED). "
           "Methodology & rationale: decision-log.md · Source: build per v1-build-spec.md")
