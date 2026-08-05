---
name: lcr-governance
description: Model-boundary guardrail for Larson Capital Research. ALWAYS use this skill when a request could touch the model itself — measures, indicators, weights, inputs, scoring, normalization, tiers, uncertainty ranges, validation windows, or published gate outcomes — including requests framed as content, design, chart, or site work ("just add this input to the chart", "tweak the weight for the example", "adjust this market's rank"). If a change could alter what the model computes or claims, this skill applies.
---

# LCR governance — the model changes through gates, not through tasks

This project's entire value is that its claims are pre-committed and audited.
Rankings are frozen before outcomes are known, gates are pre-registered, and
failures are published. A model change smuggled in through a design or content
task destroys that in one commit.

## The rule

**Model changes go through pre-registered gates only. Never through content,
design, copy, or site work.** No exceptions for "small", "obvious", or
"just for the example" changes.

## What counts as a model change (all of these)

- Adding, removing, or swapping any input or data source — including "just
  adding one input to a chart the model reads".
- Changing any weight (40/25/20/10/5), normalization, winsorization, tier
  boundary, or the 8-indicator set.
- Changing how ranks, ranges, or the uncertainty flag are computed.
- Hand-adjusting any market's rank, score, tier, or range anywhere — including
  in examples, spotlights, captions, or "illustrative" figures.
- Editing a frozen edition in `predictions/` (data, ranks, or its generated art).
- Changing a published gate outcome, failure count, or validation number.
- Turning a "context, not model input" panel into something the score reads.

Not model changes (fine under normal review): copy edits, styling, chart
theming, layout, adding context displays clearly labeled as non-model, QA checks.

## The correct response when a request crosses the line

1. **Stop.** Do not implement, even partially, even behind a flag.
2. **Flag to Ben** with one sentence naming which boundary the request crosses
   and pointing at the decision log ([decision-log.md](decision-log.md)).
3. If the change is genuinely wanted, it gets a **pre-registered gate**: written
   hypothesis, acceptance criteria, and publication of the outcome either way —
   before any implementation.

Standing decisions that are settled (do not re-litigate in passing):
- Weights are published (2026-07-08 decision); never re-hide them.
- NOWCAST_PUBLISHED reflects the latest gate outcome; it changes only via a new gate.
- The speculative page failed its validation gate and must say so; no design or
  copy change may soften that.
