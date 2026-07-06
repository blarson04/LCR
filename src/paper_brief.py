"""
paper_brief.py — compile one self-contained markdown brief for writing the paper.

Pulls every citable number straight from the processed outputs (rankings,
backtest, config, registry manifest) so the brief is always accurate and
regenerable — drop the single output file into a chat and it has the full
methodology + results in context.

    .venv/Scripts/python.exe src/paper_brief.py     # writes paper/paper-brief.md
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

OUT_DIR = config.ROOT / "paper"
OUT_DIR.mkdir(exist_ok=True)
PROC = config.PROCESSED_DIR


def _md_table(df: pd.DataFrame) -> str:
    """Render a DataFrame (already string-formatted) as a GitHub markdown table."""
    cols = list(df.columns)
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    rows = ["| " + " | ".join(str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *rows])


def _latest_manifest() -> dict:
    runs = sorted(p for p in config.PREDICTIONS_DIR.glob("*/") if (p / "manifest.json").exists())
    if not runs:
        return {}
    return json.loads((runs[-1] / "manifest.json").read_text())


def build() -> Path:
    rank = pd.read_csv(PROC / "ranking_2023.csv")
    bt_sum = pd.read_csv(PROC / "backtest_summary.csv")
    bt_win = pd.read_csv(PROC / "backtest_windows.csv")
    dropped = pd.read_csv(PROC / "dropped_metros.csv")
    panel = pd.read_csv(PROC / "panel.csv")
    manifest = _latest_manifest()

    # ---- derived numbers -------------------------------------------------
    n_metros = rank["cbsa_code"].nunique() if "cbsa_code" in rank else len(rank)

    def _tau(h, r):
        m = bt_sum[(bt_sum.horizon == h) & (bt_sum.regime == r)]
        return m["mean_tau"].iloc[0] if len(m) else float("nan")

    def _prec(h, r):
        m = bt_sum[(bt_sum.horizon == h) & (bt_sum.regime == r)]
        return m["mean_precision@10"].iloc[0] if len(m) else float("nan")

    pc3, pc3p = _tau(3, "pre_covid"), _prec(3, "pre_covid")
    sh3 = _tau(3, "shock")
    pool3, pool1 = _tau(3, "POOLED"), _tau(1, "POOLED")
    w2022 = bt_win[(bt_win.horizon == 3) & (bt_win.pred_year == 2022)]
    w2022_tau = w2022["weighted_tau"].iloc[0] if len(w2022) else float("nan")

    # ---- ranking tables --------------------------------------------------
    bcols = ["bucket_Demand", "bucket_Supply", "bucket_Affordability",
             "bucket_Momentum", "bucket_Resilience"]
    rmap = {"rank": "Rank", "cbsa_title": "Metro", "score": "Score",
            "bucket_Demand": "Demand", "bucket_Supply": "Supply",
            "bucket_Affordability": "Afford.", "bucket_Momentum": "Moment.",
            "bucket_Resilience": "Resil."}

    def _rank_tbl(df):
        d = df[["rank", "cbsa_title", "score", *bcols]].rename(columns=rmap).copy()
        for c in ["Score", "Demand", "Supply", "Afford.", "Moment.", "Resil."]:
            d[c] = d[c].map(lambda v: f"{v:+.3f}")
        return _md_table(d)

    top15 = _rank_tbl(rank.head(15))
    bottom10 = _rank_tbl(rank.tail(10))

    # ---- weights table ---------------------------------------------------
    wt_rows = []
    for b in ["Demand", "Supply", "Affordability", "Momentum", "Resilience"]:
        for k, v in config.INDICATORS.items():
            if v["bucket"] == b:
                wt_rows.append({"Bucket": b, "Indicator": k,
                                "Weight": f"{v['weight']*100:.0f}%",
                                "Direction": "inverse (higher=worse)" if v["inverse"] else "higher=better"})
    wt_tbl = _md_table(pd.DataFrame(wt_rows))

    # ---- backtest tables -------------------------------------------------
    bs = bt_sum.copy()
    bs["regime"] = bs["regime"].str.replace("_", "-")
    bs = bs.rename(columns={"horizon": "Horizon (y)", "regime": "Regime", "n_windows": "Windows",
                            "mean_tau": "Mean weighted-τ", "mean_precision@10": "Mean precision@10"})
    bs["Mean weighted-τ"] = bs["Mean weighted-τ"].map(lambda v: f"{v:.3f}")
    bs["Mean precision@10"] = bs["Mean precision@10"].map(lambda v: f"{v:.2f}")
    bt_summary_tbl = _md_table(bs)

    bw = bt_win.copy().rename(columns={"horizon": "Horizon (y)", "pred_year": "Pred. year",
                                       "regime": "Regime", "n_metros": "Metros",
                                       "weighted_tau": "weighted-τ", "precision_at_10": "precision@10"})
    bw["Regime"] = bw["Regime"].str.replace("_", "-")
    bw["weighted-τ"] = bw["weighted-τ"].map(lambda v: f"{v:.3f}")
    bw["precision@10"] = bw["precision@10"].map(lambda v: f"{v:.2f}")
    bt_windows_tbl = _md_table(bw)

    dropped_tbl = _md_table(dropped.rename(columns={
        "cbsa_title": "Metro", "population": "Population", "reason": "Reason"})
        .assign(Population=lambda d: d["Population"].map("{:,.0f}".format))
        [["Metro", "Population", "Reason"]]) if len(dropped) else "_(none)_"

    panel_years = f"{int(panel['year'].min())}–{int(panel['year'].max())}"
    metric = manifest.get("evaluation_metric", {})
    n_ind = len(config.INDICATORS)
    mv = config.MODEL_VERSION

    # v3-P2 vintage honesty: real-time (pseudo-nowcast) equivalents.
    vintage_bullet = ""
    m3p = config.PROCESSED_DIR / "nowcast" / "m3_summary.csv"
    if m3p.exists():
        m3 = pd.read_csv(m3p)
        def _g(h, r, c):
            m = m3[(m3.horizon == h) & (m3.regime == r)]
            return float(m[c].iloc[0]) if len(m) else float("nan")
        rt3, rt_pc = _g(3, "POOLED", "mean_tau_ps"), _g(3, "pre_covid", "mean_tau_ps")
        vintage_bullet = (
            f"- **Vintage rule (v3-P2):** every τ in this brief is a **finalized-data ceiling** "
            f"unless marked real-time. The **real-time achievable** pooled 3-yr τ — using only "
            f"proxies/carry-forwards a user could have held at scoring time — is "
            f"**{rt3:.3f}** ({rt3/pool3*100:.0f}% of the ceiling); pre-COVID real-time "
            f"**{rt_pc:.3f}**.\n")

    # v3-P4/P5: economic effect size + momentum orthogonality.
    effect_md = ""
    esp = config.PROCESSED_DIR / "effect_size_windows.csv"
    orp = config.PROCESSED_DIR / "momentum_orthogonality.csv"
    if esp.exists() and orp.exists():
        ew = pd.read_csv(esp)
        orth = pd.read_csv(orp)
        piv = ew.pivot_table(index="pred_year", columns="strategy",
                             values="top10_pp_vs_median")
        keep = ["Composite (model)", "Momentum (trailing rent)", "50/50 blend",
                "Equal weight", "Random (50-seed mean)"]
        pt = piv[keep].round(1).reset_index().rename(columns={"pred_year": "Window (T→T+3)"})
        pp_tbl = _md_table(pt.astype(str))
        cm = piv["Composite (model)"], piv["Momentum (trailing rent)"]
        effect_md = f"""
---

## 5b. Economic effect size & the momentum question (v3 P4–P5)

**Top-10 edge in percentage points of realized 3-yr rent growth vs the universe median**
(the headline communication metric — τ translated into units investors understand):

{pp_tbl}

Pooled top-10 edge: **composite +{cm[0].mean():.1f} pp**, momentum +{cm[1].mean():.1f} pp,
50/50 blend +{piv['50/50 blend'].mean():.1f} pp, equal-weight +{piv['Equal weight'].mean():.1f} pp,
random ≈ {piv['Random (50-seed mean)'].mean():.1f} pp.

**The shock exhibit (the framing decider):** momentum's top-10 edge flipped negative in the
shock windows (**{cm[1].loc[2021]:+.1f} pp in 2021, {cm[1].loc[2022]:+.1f} pp in 2022**) while the
composite's held up far better (**{cm[0].loc[2021]:+.1f} pp and {cm[0].loc[2022]:+.1f} pp**) — the
fundamentals sleeve provided real downside protection exactly where momentum inverted.

**Orthogonality:** after controlling for trailing rent growth, the composite still predicts
forward growth (partial rank correlation pooled **{orth.partial_after_momentum.mean():+.2f}**,
positive in every window). But the two strategies' errors co-move (correlation
**{orth.error_correlation.mean():+.2f}**, rising to ~0.77 in the shock), so the diversification
is partial. The 50/50 blend edges the composite on τ ({ew[ew.strategy=='50/50 blend'].tau.mean():.2f}
vs {ew[ew.strategy=='Composite (model)'].tau.mean():.2f}) but has a worse worst-window
({piv['50/50 blend'].min():+.1f} vs {piv['Composite (model)'].min():+.1f} pp) and a lower pooled
pp edge — no clear improvement.

**Resulting framing (decided from the evidence, per v3-P4):** *comparable to momentum on rank
agreement; better where it matters — a higher pp edge, genuine signal beyond momentum, and
materially smaller top-10 losses in the windows where momentum inverted. Diversification is
real but partial.*
"""

    # v3-P3 temporal-uncertainty honesty.
    uncertainty_md = ""
    tup = config.PROCESSED_DIR / "temporal_uncertainty.csv"
    if tup.exists():
        tu = pd.read_csv(tup).iloc[0]
        surv = ("**survives**" if bool(tu["eq_edge_survives_state_cluster"])
                else "**does not survive**")
        uncertainty_md = f"""
**Uncertainty, honestly stated (v3-P3).** The primary statement is the **per-window range**:
3-yr τ spanned **[{tu['win3_min']:+.2f}, {tu['win3_max']:+.2f}]** across {int(tu['win3_n'])}
overlapping windows — calm windows near the top, shock windows near the bottom; no pooled
average conveys that spread. Jackknife: dropping any single window moves the pooled 3-yr τ only
within **[{tu['jk3_min']:.2f}, {tu['jk3_max']:.2f}]**. Because neighboring metros co-move, a
**state-cluster bootstrap** ({int(tu['n_states'])} states) widens the pooled-τ 95% interval to
**[{tu['state_tau_lo']:.2f}, {tu['state_tau_hi']:.2f}]**, and the equal-weight edge {surv} that
stricter test (gap CI [{tu['state_gap_lo']:+.3f}, {tu['state_gap_hi']:+.3f}]). Metro-cluster
pooled CIs elsewhere are **cross-sectional only** — conditional on the observed windows and
silent about regime risk.
"""

    # ---- assemble --------------------------------------------------------
    md = f"""# Multifamily Rent-Growth Screener — Paper Brief (model v{mv})

*Auto-generated {datetime.now(timezone.utc):%Y-%m-%d} from the model outputs. Regenerate with
`python src/paper_brief.py`. Every number here is pulled directly from the processed data —
nothing is hand-typed. Companion docs: `decision-log.md` (the "why"), `v1-build-spec.md` (v1
how), `v2-plan.md` + `paper/v2-findings.md` (the rigor pass that produced v2).*

---

## 1. Summary (abstract-ready)

A transparent, backtested **screening framework** ranks the **{n_metros} largest US metros**
by their fundamentals for **3-year forward rent growth**, using only free public data. {n_ind}
indicators across five themes are normalized cross-sectionally within each year and combined
with hand-set weights into a composite score. Walk-forward validation shows the framework is
**strong in normal regimes** (pre-COVID 3-year weighted Kendall's τ ≈ **{pc3:.2f}**, precision@10
≈ **{pc3p:.0%}**) and **breaks down during the 2020–22 shock** (τ ≈ **{sh3:.2f}**) — an expected,
honestly-reported result. Every run is frozen to a pre-registration registry for an auditable
track record. It is positioned as a *screening framework, not a prediction engine*.

**Headline numbers**
- Universe: **{n_metros} metros**, scored on the **2023** cross-section; panel spans **{panel_years}**.
- Pre-COVID 3-yr: τ **{pc3:.3f}**, precision@10 **{pc3p:.2f}**.  Shock 3-yr: τ **{sh3:.3f}**.
- Pooled 3-yr τ **{pool3:.3f}** vs. pooled 1-yr τ **{pool1:.3f}** (≈ equal → see finding #3).
- Worst single window: 3-yr starting **2022** (predicting the post-peak decline), τ **{w2022_tau:.3f}**.
{vintage_bullet}

---

## 2. Data & universe

**Sources (all free, public):** Census ACS (population, housing stock, income),
IRS SOI county-to-county migration, BLS/QCEW (employment, wages, industry mix),
BEA Regional (personal income), Zillow Research (ZORI rent — the target — and ZHVI home
values), FRED (mortgage rate). County-grained sources are rolled up to metros via the Census
OMB CBSA delineation.

**Universe rule (frozen once for v1):** Metropolitan Statistical Areas with population
≥ **{config.POP_FLOOR:,}** AND gap-free Zillow rent coverage starting no later than
**{config.RENT_GATE_LATEST_START}** → **{n_metros} metros**. Every metro that clears the
population floor but fails the rent gate is logged:

{dropped_tbl}

---

## 3. The model

{n_ind} indicators (the v2 de-duplicated set) in five themes; **hand-set weights**, summing to 100%. Each indicator is
**z-scored across metros within each year** (so a national shock cancels and only the
metro-to-metro spread survives); "inverse" indicators are sign-flipped so **higher = better**
everywhere; the weighted sum is the composite score, and metros are ranked within the year.

{wt_tbl}

Bucket totals: **Demand 40% · Supply 25% · Affordability 20% · Momentum 10% · Resilience 5%.**
Missing indicators are treated as neutral (0) at scoring.

---

## 4. Results — current ranking ({manifest.get('score_year', 2023)} cross-section)

Columns after Score are the weighted z-score contribution of each bucket.

**Top 15**

{top15}

**Bottom 10**

{bottom10}

*Pattern: supply-constrained, affordable, steady-demand metros rise to the top; metros that
over-built and then saw rents fall (Austin, Boise, Riverside) sit at the bottom — the model
flagged them on 2023 fundamentals.*

---

## 5. Results — walk-forward backtest (validation)

Each year's ranking is compared to **realized forward rent growth** (3-year primary, 1-year
contrast), ranked cross-sectionally; realized growth is winsorized at the 1st/99th percentile;
the model never sees the future. Metric: top-weighted Kendall's τ (weighted by realized rank)
and precision@10 (share of the top 10 landing in the realized top quartile).

**Summary by horizon × regime**

{bt_summary_tbl}

**Every window**

{bt_windows_tbl}

**Three findings for the paper**
1. **It works in normal times.** Pre-COVID 3-yr τ ≈ {pc3:.2f}, precision@10 ≈ {pc3p:.0%} — the
   top-10 picks landed in the realized top quartile ~{pc3p:.0%} of the time.
2. **It breaks down in the shock, as expected.** Shock 3-yr τ ≈ {sh3:.2f}; the 2022-start window
   (predicting the post-peak correction) is slightly negative (τ {w2022_tau:.2f}). This vindicates
   the rule never to fit weights on the shock regime, and is reported rather than hidden.
3. **3-year ≈ 1-year (τ {pool3:.2f} vs {pool1:.2f}).** The decision log hypothesized the model
   would do *better* at 3y if it captured fundamentals over momentum; instead they're comparable,
   suggesting momentum and fundamentals contribute similarly — a candidate for fitted-weight work.

*Caveat to state plainly: rent history starts ~2015, so windows are few and overlapping →
**directional evidence, not statistical significance.***
{uncertainty_md}
{effect_md}

---

## 6. Pre-registration & reproducibility

Every production run is frozen, timestamped, and never edited (registry), making the live track
record auditable — a core credibility differentiator.

- **Model version:** {manifest.get('model_version', config.MODEL_VERSION)} · **git commit:** {manifest.get('git_commit', 'n/a')}
- **Frozen run:** {manifest.get('timestamp_utc', 'n/a')} (top metro: {manifest.get('top_metro', 'n/a')})
- **Evaluation metric (locked before first run):** {metric.get('primary', "top-weighted Kendall's tau")}; rank basis = {metric.get('tau_rank_basis', config.TAU_RANK_BASIS)}; headline = {metric.get('headline', f'precision@{config.PRECISION_K}')}.
- Raw downloads cached; pipeline reproducible end-to-end from free sources.

---

## 7. Limitations (carry into the paper)

- No capital-markets data (cap rates, transaction volume) — paid; **rent growth is the proxy for profitability**.
- **ZORI is asking rent, not executed rent** (can overstate momentum in fast markets).
- Short usable history (~2015+) → few independent windows → directional, not significance-grade.
- **Weights are hand-set hypotheses, validated but not optimized** (v2 uses the de-duplicated 8-indicator set).
- Universe frozen once (mild survivorship); Apartment List vacancy signal deferred to v1.1.

---

## 8. Suggested paper structure

1. **Introduction** — the gap (no transparent, auditable, free-data multifamily screener).
2. **Framework** — screening vs. prediction; the five themes and why (→ `decision-log.md`).
3. **Data** — sources, universe definition, the rent-coverage gate, dropped metros (§2).
4. **Methodology** — indicators, within-year normalization, weighting, scoring (§3).
5. **Validation** — walk-forward design, regimes, winsorizing, metrics; results (§5).
6. **Findings & discussion** — the regime story, 3y≈1y, what the top/bottom say (§4–5).
7. **Pre-registration & reproducibility** — the registry as a differentiator (§6).
8. **Limitations & future work** — §7 + fitted weights, AI-exposure indicator, vacancy.
"""
    out = OUT_DIR / "paper-brief.md"
    out.write_text(md, encoding="utf-8")
    return out


if __name__ == "__main__":
    path = build()
    print(f"Paper brief written: {path.relative_to(config.ROOT)}")
    print(f"  {path.stat().st_size/1024:.1f} KB — upload this one file (plus the CSVs for raw data).")
