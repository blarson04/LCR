# v2.1 Nowcast — Validation (M1: proxy quality)

*Auto-generated 2026-07-02 by `src/nowcast/proxy_quality.py`.
Companion to `v2.1-nowcast-spec.md`. M3 (the pseudo-nowcast accuracy test) is added later.*

## Bottom line

The nowcast's linchpin — proxying the slow, indispensable `net_migration` (IRS, ~2y lag) with
Census PEP net domestic migration (~6mo lag) — **holds**: PEP tracks IRS at **level r ≈ 0.99** and
**rank ≈ 0.90** per year. More importantly, swapping PEP into the full v2 composite
barely moves the ranking (median Spearman **0.984**, median top-10 overlap **9/10**).
Carry-forward proxies are safe (housing stock persists perfectly; employment diversity strongly).
This clears the way for M2/M3; the accuracy cost is quantified in M3.

## 1. Linchpin — PEP vs IRS net domestic migration (per year)

| year | n | pearson_levels | spearman_rank |
| --- | --- | --- | --- |
| 2016 | 382 | 0.959 | 0.934 |
| 2017 | 382 | 0.989 | 0.907 |
| 2018 | 382 | 0.991 | 0.898 |
| 2019 | 382 | 0.993 | 0.920 |
| 2020 | 382 | 0.972 | 0.868 |
| 2021 | 382 | 0.988 | 0.867 |
| 2022 | 387 | 0.990 | 0.888 |
| 2023 | 387 | 0.988 | 0.922 |

Guide: rank corr ≥ 0.9 = strong; < 0.8 = weak (nowcast ceiling low). Observed ≈ 0.90, dipping only
in the volatile 2020–21 shock years.

## 2. Ranking substitution — PEP vs IRS in the full v2 composite (per year)

| year | n | spearman_rankings | top10_overlap |
| --- | --- | --- | --- |
| 2016 | 110 | 0.985 | 9/10 |
| 2017 | 110 | 0.983 | 7/10 |
| 2018 | 110 | 0.975 | 10/10 |
| 2019 | 110 | 0.990 | 8/10 |
| 2020 | 110 | 1.000 | 10/10 |
| 2021 | 110 | 0.969 | 9/10 |
| 2022 | 110 | 0.975 | 6/10 |
| 2023 | 110 | 0.992 | 9/10 |

Because `net_migration` is 20% of the composite and PEP tracks IRS at r≈0.99, the final ranking is
nearly unchanged — the nowcast should retain most of the model's accuracy.

## 3. Carry-forward proxies — year-over-year rank persistence

| proxy | median_yoy_rank_corr |
| --- | --- |
| employment_diversity (HHI) | 0.843 |
| housing stock | 1.000 |

Housing stock is perfectly persistent (carry-forward is exact); employment diversity is highly
persistent (0.84), so carrying forward a 5%-weight indicator one year is defensible.

## Next
M2 — assemble the provisional current-year (2025) nowcast panel (needs the CES job/wage proxy).
M3 — pseudo-nowcast backtest: rebuild history with proxies only and measure the accuracy cost vs
the finalized model, with a pre-committed go/no-go gate.


---

## M3 — Pseudo-nowcast backtest (accuracy cost)

Rebuilding history with the nowcast's proxies (PEP migration, carried-forward slow
indicators, live rent/permits) and running the standard walk-forward evaluation:

| h | regime | τ finalized | τ pseudo | P@10 fin | P@10 pseudo |
| --- | --- | --- | --- | --- | --- |
| 1 | pre-covid | 0.636 | 0.582 | 0.78 | 0.80 |
| 1 | shock | 0.349 | 0.239 | 0.45 | 0.25 |
| 1 | normalization | 0.256 | 0.224 | 0.60 | 0.30 |
| 1 | POOLED | 0.500 | 0.433 | 0.66 | 0.57 |
| 3 | pre-covid | 0.588 | 0.560 | 0.85 | 0.85 |
| 3 | shock | 0.157 | 0.008 | 0.25 | 0.30 |
| 3 | POOLED | 0.444 | 0.376 | 0.65 | 0.67 |

**3-yr pooled τ:** finalized **0.444** vs pseudo-nowcast **0.376** →
retention **84.7%**. Gap **+0.068**, 95% CI
[+0.013, +0.120] (metro-cluster bootstrap).

**Ranking agreement (pseudo vs finalized), per year:**

| year | spearman | top10_overlap |
| --- | --- | --- |
| 2016 | 0.937 | 9/10 |
| 2017 | 0.916 | 9/10 |
| 2018 | 0.878 | 8/10 |
| 2019 | 0.839 | 7/10 |
| 2021 | 0.769 | 4/10 |
| 2022 | 0.818 | 4/10 |
| 2023 | 0.881 | 6/10 |

Mean top-10 overlap **6.7/10**.

**Gate (pre-committed):** retain ≥ 85% of pooled 3-yr τ AND mean top-10
overlap ≥ 7/10 → **FAIL — published as a negative result; surfaced only as a provisional-experimental edition under the amended gate taxonomy (decision log 2026-07-06)**.

**Which proxy causes the loss? (attempt #1 decomposition, pre-CES)**

| variant | pooled τ | retention |
| --- | --- | --- |
| finalized (all real) | 0.444 | 100% |
| only migration proxied | 0.423 | 95% |
| pseudo but jobs+income finalized | 0.427 | 96% |
| full pseudo-nowcast | 0.332 | 75% |

(Attempt #1 context: this decomposition motivated the CES fix — the migration proxy costs ~nothing; the carried growth inputs drove the loss.)

### Decision
Gate **NOT MET on the pre-committed one-shot CES re-run** (decision log 2026-07-06). Per the binding consequence, the provisional edition is **pulled from the site**, and no further proxy iterations may run without a new pre-registered specification. This is published negative result #2.


---

## V — Lagged-vintage gate (v3.1 spec, 2026-07-07; one shot)

Configuration: all-finalized inputs, single substitution (PEP migration / ACS population).
Result: pooled 3-yr τ **0.424** vs finalized **0.444** → retention
**95.52%** (gate ≥ 85%); mean top-10 overlap **8.29/10**
(gate ≥ 7). Gap 95% CI [-0.003, +0.035].
**PASS — the 2024-vintage screen publishes as a VALIDATED current screen (2024→2027), vintage-labeled and registry-frozen.**
