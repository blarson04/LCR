# Multifamily Screener — V3 Plan & V2 Critique

*Companion to `decision-log.md`, `v2-plan.md` (the previous critique, now largely implemented),
`v2-findings.md`, `nowcast-validation.md`, and `paper-brief.md`. This document critiques v2 and the
live site honestly and lays out a prioritized v3 plan. Guiding principle unchanged: the project's
edge is transparency and honesty; v3 should make it **more valid in real time and more legible to
its audience**, not bigger. Measure before building. No black-box ML.*

---

## 1. Verdict on v2 (short)

The Tier-1 rigor plan was executed properly, and it did what rigor is supposed to do: it killed two
comfortable stories (the momentum edge, the indicator cuts) and the project reported that instead of
hiding it. The gates worked — three tempting additions were tested and rejected on evidence. The
de-duplicated 8-indicator scheme is the right call for the right reason (parsimony, not accuracy).
This is now a genuinely credible piece of methodological work.

The problems that remain are not about how the analysis was run. They are about **what the headline
numbers actually mean to someone using the tool today** — and one governance wobble on the nowcast.
Those are the attack surfaces below.

---

## 2. Research critique — what a referee attacks next

### R1 — Vintage inflation: the headline τ is not achievable in real time (the kill shot)

Your own documents contain the referee's strongest weapon, and the paper brief does not connect
them. The headline (pooled 3-yr τ 0.444, pre-COVID 0.588) is computed on **finalized data** —
including IRS migration with a ~2-year lag. No user of this model, at any point in history, could
have held that information set at decision time. The M3 pseudo-nowcast quantifies exactly what a
real-time user gets: **τ 0.332, i.e. 75% of the headline**. That is not a side experiment about a
provisional feature — it is the honest estimate of the model's *deployable* accuracy, and it
currently lives only in the nowcast doc while every headline surface reports 0.444.

A skeptical quant will say: "your backtest is vintage-inflated by ~25% and you knew it." The fix is
cheap and entirely in your ethos: every surface that shows a finalized-data τ must co-report the
real-time equivalent and label which vintage each number assumes. Better still, make the real-time
number the conservative headline and the finalized number the ceiling.

### R2 — The "current" ranking is a hindcast

The validated product ranks the **2023 cross-section**, published **July 2026**, predicting rent
growth over **2024–2026** — a window that is roughly 80% elapsed. The one edition that would rank
*current* conditions failed its gate. So as of today, the validated tool tells a user which metros
*were* well-positioned two and a half years ago. That is a research artifact, not a screen. The
paper can survive this (backtests are backward by nature); the *product* cannot — see §4 and the
Tier-1 plan. State the staleness plainly wherever the 2023 ranking is shown ("scored on 2023
fundamentals; forecast window 2024–26").

### R3 — The bootstrap CIs answer the wrong question

The metro-cluster bootstrap resamples metros **conditional on the six observed (overlapping)
windows**. It captures cross-sectional sampling noise and nothing else. But look at your own
per-window table: 3-yr τ ranges from **−0.02 to 0.63**. The dominant uncertainty is *temporal* —
which regime the next window lands in — and the CI [0.357, 0.502] is silent about it. A referee
will call the CI misleadingly narrow, and they'll be right: it reads as "we know τ to ±0.07" when
the honest statement is "τ was 0.5–0.6 in four calm windows and ~0 to 0.3 in two shock windows,
and we cannot bootstrap our way out of n=6."

Fixes: (a) demote the pooled CI — label it "cross-sectional uncertainty, conditional on observed
history"; (b) make the per-window range the primary uncertainty statement; (c) add a
jackknife-over-windows sensitivity (drop each window, report the τ range); (d) related — metros are
not independent (Sun Belt co-moves; five of your redundancy pairs are supply/demand co-movement),
so run a state- or region-cluster bootstrap as a sensitivity. If the equal-weight edge
(+0.039, CI [+0.008, +0.069]) survives region clustering, say so; if not, the one "reliable"
model-vs-baseline win gets weaker.

### R4 — Regime conditioning is ex post

"Strong in normal regimes" is only a usable claim if "normal" is identifiable **at scoring time**.
The regime labels (pre-COVID / shock / normalization) were assigned with hindsight. The site has a
regime/confidence flag (good, it was W8), but I see no validation of it: what rule defines it, from
what data available on the scoring date, and would it have fired in 2020–21? Without that, the
conditional claim is unfalsifiable — a referee will say you're conditioning on the outcome. This is
testable with what you have (P6 in the plan).

### R5 — The momentum question is half-answered

v2 honestly reports the model is not reliably better than trailing rent growth at 3y, framed as
"comparable to momentum, plus interpretability and diversification." But *diversification* is an
empirical claim and no evidence is shown. The natural tests are all missing:

- **Per-window model vs momentum.** I ran a model-free check on `panel.csv`: ranking metros by
  trailing 1-yr ZORI growth, the momentum top-10's 3-yr forward rent growth beat the median metro
  by **+6 to +11 pp** in every pre-COVID window — and flipped to **−1.5 pp (2021)** and
  **−4.3 pp (2022)** in the shock. Momentum didn't just decay in the shock; it inverted. The
  question that decides the framing: did the composite's top-10 hold up better in exactly those
  windows? (Precision@10 of 0.40/0.10 suggests not by much — but the pp comparison, side by side,
  is the honest answer either way.)
- **Orthogonality.** Partial rank correlation of the composite with forward growth, controlling for
  trailing growth. If the fundamentals sleeve adds signal beyond momentum, this shows it directly;
  if it doesn't, the "diversification" framing needs to soften.
- **The blend baseline.** A 50/50 momentum + composite blend is the obvious practitioner move; the
  model should be compared against it, not only against each alone.

### R6 — No economic effect size anywhere

τ and precision@10 mean nothing to the paper's actual audiences (investors, recruiters). Nowhere is
the model's skill translated into **percentage points of rent growth**. The check above shows the
momentum baseline is worth ~6–11 pp of 3-yr outperformance in calm regimes — that is the bar, in
units people understand. Report, for the model and every baseline, per window: *top-10 mean 3-yr
forward rent growth vs universe median, in pp*. One table, computed from data you already have.
This is probably the highest communication-value-per-hour item in this entire document.

### R7 — Metric choices need a robustness footnote

Top-weighted τ with weights from the *realized* rank is defensible for a screener (you care about
getting the winners right) but nonstandard — and it mechanically rewards exactly the thing you're
claiming. Report plain Kendall's τ and Spearman alongside it once, in an appendix, to show the story
doesn't depend on the weighting. Same for winsorization: show 0/100 and 5/95 sensitivity once.
Precision@10 on n=110 moves in lumps of 0.1; fine as a headline, but don't lean on single-window
differences of one hit.

### R8 — Multiple comparisons across the rigor pass

P1–P7 generated dozens of 95% CIs. At that rate, ~1 in 20 "reliable" findings is noise. The two
load-bearing reliable results (beats equal-weight, +0.039 CI barely excluding 0; migration
indispensable, comfortably clear) should be flagged accordingly: migration is robust; the
equal-weight edge is real-but-fragile and shouldn't be leaned on rhetorically.

### R9 — The expense side is invisible, and the output shows it

Rent growth proxies revenue, not profitability — acknowledged. But the 2023 ranking makes the
omission concrete: Florida metros appear in the top 15 (Port St. Lucie, Deltona) *and* bottom 10
(Lakeland), while the state's insurance-cost shock — arguably the dominant multifamily P&L story of
2023–26 — appears nowhere in the framework. A practitioner reader will spot this immediately. You
don't need to model it (paid data); you need one honest paragraph naming operating-cost shocks
(insurance, taxes) as an unmodeled dimension, with Florida as the worked example.

---

## 3. The nowcast call — was shipping it right?

Short answer: **the labeling is close to adequate; the process was not.** The distinction matters
more than the outcome.

The pre-committed gate (2026-07-02) specified not just thresholds but a **consequence**: "If it
fails, v2.1 ships as an internal experiment." It failed. The decision log then records, in
sequence: (1) internal experiment only, M5 gated off; (2) a "final disposition" leaving it out of
production; (3) a same-week reversal surfacing it as a labeled experimental tab, with the argument
that "a transparently-disclosed experimental view is not the same as a validated publication."

That argument is respectable — but it is a **reinterpretation of the gate's consequence after
seeing the result**, which is precisely the move pre-registration exists to prevent. If
"speculative-with-banner" was an acceptable failure outcome, the gate should have said so before M3
ran. The saving graces: the reversal is documented, dated, and honestly reasoned in the log, and the
validated ranking stayed the default. So this is a wobble, not a breach of the ethos — but a
referee (or a sharp recruiter) reading the log will notice, and the packet itself contradicts the
validation doc ("internal experiment only" vs "shipped as speculative edition"). Reconcile them.

**Is the labeling itself adequate?** The banner discloses that the edition fails the bar and cites
the 75% retention. Not sufficient. The number a user actually needs is the per-year ranking
divergence: in **2023, the most recent comparable year, the provisional top-10 shared only 3 names
with the finalized top-10**. "Fails an internal statistical bar" reads as pedantry; "7 of these 10
names would likely change" reads as what it is. Put the per-year overlap (and 6.1/10 mean) on the
banner itself, not behind a link.

**Also: rename the page.** "Accurate vs Speculative" overclaims the validated edition — it is not
"accurate" (τ 0.44 pooled, near-zero in the shock; that honesty is your brand). "Validated vs
Provisional (experimental)" says the true thing.

**Recommended resolution (pick one, log it):**
- *(a) Pull it* until the CES fix is built and the gate is re-run — cleanest for the
  pre-registration story; or
- *(b) Keep it*, but: (i) add a dated log entry formally amending the gate taxonomy
  (validated / provisional-experimental / internal), acknowledging it's an amendment; (ii) put the
  per-year overlap numbers on the banner; (iii) rename the editions; (iv) **pre-commit the CES
  re-run as one-shot** — same thresholds, verbatim, one attempt. Iterating proxies until one passes
  would convert the gate into decoration.

The log's own earlier reasoning ("forcing a marginal pass with noisier data would cut against
rigor-over-reach") was the right instinct. Hold yourself to it on the re-run.

---

## 4. The product — page by page

*(Two audiences per page: (a) investor/analyst, (b) recruiter with 60 seconds.)*

**About / landing (01, 10).** Substantive, honest, and well-written — and structured backwards for
a 60-second reader. The page front-loads framing prose and the weight table; **no performance
number appears anywhere on the landing page.** A recruiter leaves without ever learning the model
was validated at all. Add a **"one-minute version" block above the fold**: three numbers (pre-COVID
τ / precision@10, the shock breakdown, the pp effect size once built), one small per-window chart,
links to Rankings and Track Record. Two wording traps: (i) *"nothing is hand-picked"* sits three
sentences after a table of hand-set weights and directly above *"weights are set by judgment"* —
you mean the formula applies uniformly across markets, but a hostile reader quotes the
contradiction; rephrase ("the same formula runs for every market; no market is hand-adjusted").
(ii) The About-me section is genuinely good — specific, modest, motivated — keep it.

**Rankings (02, 09).** The vintage is honestly stated ("a 2023→2026 screen scored on the latest
complete data (2023)") — better than I'd credited. What's missing is the *implication*: nothing
tells the reader that mid-2026 means the forecast window is ~80% elapsed. One clause fixes it.
Bigger problem: **the regime/confidence flag assesses 2023, not today** — "Market conditions in
2023 look typical… operating within its validated range" is a statement about conditions three
years ago. The flag exists to warn users about *current* reliability (that was W8); evaluated at
the vintage year it inherits the staleness problem instead of mitigating it. Also: the Top-10 list
shows point ranks with no rank ranges — the ranges exist (metro detail shows "2 (1–11)") but the
page most people screenshot doesn't carry the uncertainty. Dark mode is clean.

**Metro detail (03).** The strongest page — rank ranges, the plain-language "why" line, percentile
bars with direction pre-applied, strengths/watch-outs. Two real issues. (i) **The History rank
chart contradicts the header**: the header says Rank 2 (finalized 2023) while the chart's line
continues through 2024–25 and the caption reads "slipped 37 places since 2015" — the finalized
edition's chart is silently mixing in provisional years. Either truncate the chart at the edition's
vintage or visually mark the provisional segment (dashed line + amber dot). (ii) The chart also
exposes **rank whipsaw** (Akron swings roughly #1 ↔ #65 between adjacent years) — this is W7 made
visible but never explained or quantified. A skeptical viewer sees that volatility and discounts
the whole screen; either add a rank-stability stat with an explanation of why year-to-year ranks
move (cross-sectional z-scores reshuffle), or smooth the display. Don't leave it unexplained.

**Compare (04).** Fine — and quietly instructive: Charleston "1 (1–13)" vs Akron "2 (1–11)" shows
the top of the table is statistically indistinguishable. Consider saying that out loud ("these two
are within each other's rank ranges — the screen cannot separate them"); it's exactly the kind of
honesty the site is selling.

**Accurate vs Speculative (05).** Rename (see §3) — and note the "Accurate" label is not confined
to this page: it's in the **global sidebar edition toggle on every page**, so the overclaim is
sitewide. The page concept is good, and the intro sentence ("differences mix real market change
with… added uncertainty — read big moves as directional, not precise") is honest as far as it goes.
But the disclosure describes the *cause* (preliminary data, will be revised) and never the
*measured consequence*: nothing on this page — or anywhere on the site — says the provisional
configuration **failed a pre-committed validation gate**, retained 75% of the signal, and matched
the finalized top-10 on only 6.1/10 names on average (3/10 in 2023). The Move column shows
Madison −56 and Chattanooga −33 to a reader who has no way to know how much of that is noise —
your own backtest quantifies it, and the number is withheld. Put the gate result inline, framed as
what it is: an experiment with a published negative result and a named fix.

**Speculative rankings & metro detail (07, 08).** The amber badge and sidebar note are present and
prominent — good — but say only "uses preliminary and proxy data that will be revised" (cause, not
consequence; same fix as above). One new issue from the detail page: the measures table shows
values like "Job growth −0.2% a year" with **no indication of which measures are live, proxied, or
carried forward** — and carried-forward jobs/income is precisely the input your decomposition
blames for the gate failure. Add per-measure provenance tags (live / proxy / carried-forward) in
the provisional edition; it's the single most useful transparency feature this edition could have.

**Track record (06).** Potentially the most credible page; currently the weakest relative to its
job. Three gaps. (i) **No baselines** — the P1 work was v2's biggest rigor win, and the site never
shows it: τ 0.44 is presented with nothing to beat, which is your own W1 critique recreated at the
product level. Add the baseline rows (momentum, equal-weight, persistence, random). (ii) No
uncertainty — the paper has CIs and per-window ranges; the site shows bare pooled numbers. (iii)
The frozen record lists two runs, both scoring year 2023 — fine, but nothing tells the reader
*when* these calls get scored; pre-announce the scoring date so the ledger is visibly armed. Also
separate "backtest (retrospective, finalized data)" from "frozen live predictions" visually. The
"Honest limits" list is excellent — the fourth bullet ("treat it as a screen, not a forecast") is
the best sentence on the site.

**Cross-cutting.** (i) The `*.streamlit.app` URL and default chrome read "student project" before a
word is read; a custom domain is ~$12. (ii) **Branding — correction to my earlier note:** the site
itself is branded "The Rent-Growth Screener / Multifamily research," which is clean and makes no
capital-management claim; the "Larson Capital Research" issue lives only in the repo name (LCR) and
any paper/LinkedIn branding. Decide the name once — the site's current plain-descriptive title is
honestly a strong default — and make repo, paper, and site match before publication. (iii) The
public repo is part of the product: pinned environment, one-command reproduce, CI smoke test, and a
**data-redistribution audit** (Zillow Research terms — verify; IRS/Census/BLS fine) before LinkedIn
traffic arrives. (iv) The headshot on About is appropriate (correction: the loose IMG_2528 files in
the critique folder are that headshot's source, not a stray — still worth removing from shared
packets).

---

## 5. The story — weakest link, and the one addition

**Weakest part of the narrative:** the tool's validated output is a hindcast (R2), and the edition
that ranks *current* conditions failed its own validation. As a portfolio piece the honest summary
today is "a rigorous method, honestly validated — with no live, validated product." Everything else
(the τ-vs-momentum nuance, the short history) is survivable framing; this one is structural. A
close second: nothing anywhere translates the model's skill into units a recruiter or investor
understands (R6).

**The one addition that most raises credibility: ship the CES employment/wage proxy and re-run the
gate — one shot, pre-committed.** Your own decomposition says this single input takes retention
from 75% to ~96%. If it passes, the story transforms: *"pre-registered a validation gate, failed
it, published the negative result, identified the cause, fixed it, passed"* — that is a complete
scientific arc, it produces a **current, validated 2025/26 ranking** (killing the staleness
problem), and it is a better interview story than any accuracy number. If it fails, you publish
that too, and the pre-registration ethos is *strengthened* — the gate visibly has teeth. It is the
only item on the roadmap that wins either way.

(The cheap consolation if CES stalls: the pp-effect-size table (R6/P5) — one afternoon, and it makes
the paper legible to its actual audience.)

---

## 6. V3 plan (tiered)

### Tier 1 — Real-time validity (do first; these are the referee kill-shots)

- **P1 — CES nowcast fix, one-shot gate.** Pull current-year metro employment + wages via FRED's
  SAE series; rebuild M2/M3. **Before running M3: log a dated entry re-committing the original gate
  verbatim (≥85% retention AND ≥7/10 mean overlap), one attempt, both outcomes published.** Pass →
  provisional 2025/26 edition becomes the validated current screen (and the §3 problem dissolves).
  Fail → documented negative result #2; provisional edition is pulled or kept per the amended
  taxonomy, but no further proxy iterations without a new pre-registered spec.
- **P2 — Vintage-honest reporting.** Every surface (paper, About, Rankings, Track Record) that
  shows a finalized-data τ co-reports the real-time (pseudo-nowcast) equivalent and labels the
  vintage. Candidate framing: real-time number as the conservative headline, finalized as the
  ceiling. Add the staleness line to the 2023 ranking everywhere it appears.
- **P3 — Temporal-uncertainty honesty.** Demote pooled CIs to "cross-sectional, conditional on
  observed windows"; promote per-window ranges to the primary uncertainty statement; add
  jackknife-over-windows and a region/state-cluster bootstrap sensitivity (does the equal-weight
  edge survive?). Pure analysis, no new data.

### Tier 2 — Sharpen the value claim (analysis only, data already in the panel)

- **P4 — Momentum orthogonality.** Per-window model-vs-momentum table in both τ and pp; partial
  rank correlation of the composite controlling for trailing rent growth; error correlation between
  the two; add a 50/50 blend to the baseline set. Decide the final framing ("comparable to
  momentum, diversifying" vs "fundamentals confirm momentum") from the result, not the hope.
  Key exhibit: momentum's top-10 pp spread flipped negative in 2021–22 — show side-by-side whether
  the composite's did too.
- **P5 — Economic effect size.** For the model and every baseline, per window: top-10 mean 3-yr
  forward rent growth vs universe median, in pp. Adopt as a headline communication metric next to
  precision@10, in the paper and on the site.
- **P6 — Validate the regime flag ex ante.** Write down the flag's rule using only
  scoring-date-available data; backtest it 2015–2025: does it fire in 2020–21, stay quiet
  pre-COVID, and what's the false-positive rate? Publish the rule with the flag.

### Tier 3 — Product & story (parallel; several are hours, not days)

- **P7 — Rename the editions** ("Validated" / "Provisional — experimental"); per-year top-10
  overlap numbers on the provisional banner; reconcile the packet/validation-doc contradiction; add
  the gate-amendment entry to the decision log.
- **P8 — 60-second landing layer** on About; reorder to claim → evidence → limitations.
- **P9 — Branding & domain.** Finalize the name (drop "Capital"), buy the custom domain, restyle
  the Streamlit chrome. Do this **before** the LinkedIn publication, not after.
- **P10 — Live ledger on Track Record.** Visually separate backtest from frozen registry entries;
  show the 2026-07-01 freeze as ledger entry #1 with a pre-announced scoring date.
- **P11 — Repo hardening.** Pinned environment, one-command reproduce, CI smoke test, data-license
  audit, scrub stray files.

### Sequencing

P1 decides everything downstream of the nowcast (§3's resolution, half the story in §5) — start it
first. P2/P3 are prerequisites for the paper draft. Tier 2 feeds the paper's findings section.
Tier 3 runs in parallel, but P7 and P9 must land before LinkedIn publication.

---

## 7. Guardrails (updated)

- **No black-box ML.** Unchanged; the accuracy landscape is flat (P4 of v2) — nothing to gain,
  everything to lose.
- **No gate-shopping.** Every gate now specifies threshold **and consequence and number of
  attempts**; amendments only via dated log entries written *before* the re-run.
- **Vintage rule.** No accuracy number is published without stating the data vintage it assumes.
- **The sensitivity explorer stays framed** as transparency, with the canonical weights disclosed.
- **Negative results keep getting published.** They are, at this point, the project's most
  distinctive asset.

---

## 8. Open questions for v3

- **Pull vs keep** the provisional edition while P1 is in flight (§3 options a/b)?
- **Quarterly frequency** (carried from v2's open questions): more overlapping windows won't create
  independence, but quarterly rent data would sharpen the momentum/orthogonality analysis (P4) and
  the regime flag (P6) — worth re-costing after Tier 1.
- **Headline choice** once P2 lands: real-time-first or finalized-first? (Recommendation:
  real-time-first; it is the number a user can actually have.)
- **The name.** Decide it once, before publication, and stop paying the ambient cost.
