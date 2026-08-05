---
name: lcr-report-build
description: Build pipeline for Larson Capital Research deliverables. ALWAYS use this skill when generating or editing the PDF report (report/build_pdf.py), the methodology paper, the one-pager, any chart or map rendering, hero/divider art, or site styling/theming — anything that runs the report builder, touches theme tokens, or renders figures. Covers where tokens live, how the theme is applied, the component inventory, smoke test and goldens, and the frozen-registry rule.
---

# LCR report and site build

## Pipeline map

- **PDF report**: [report/build_pdf.py](report/build_pdf.py) — reportlab
  (BaseDocTemplate + platypus flowables) for layout; matplotlib renders charts as
  300-dpi PNGs into `report/_build/`; fonts embedded from `report/fonts/`
  (Inter 400/500/600, Source Serif 4 400/600). Typographic hygiene via
  [report/typo.py](report/typo.py) (`smart()` — curly quotes, en dashes in ranges).
  Output: `report/Larson_Capital_Research-Report.pdf`.
  Run: `.venv/Scripts/python.exe report/build_pdf.py`.
- **Methodology paper**: [report/build_methodology_paper.py](report/build_methodology_paper.py), same stack.
- **Site**: Streamlit, entry [app/streamlit_app.py](app/streamlit_app.py), pages in
  `app/views/`, shared UI in `app/ui/` (`theme.py` tokens + `inject_css()`,
  `data.py` model outputs in bare mode — the PDF builder imports the same module,
  so report and site always read identical numbers).
- **Model outputs**: committed under `data/processed/`; the site and report
  recompute from these with no network or keys.

## Design tokens — single source of truth

All colors and type decisions flow from the tokens file (`theme/tokens.json` once
PR 2 lands; until then `app/ui/theme.py` mirrored by the constants block at the
top of `build_pdf.py`). **No hex codes anywhere outside the tokens module.** The
smoke test greps for stray hex; do not add any. Matplotlib and plotly both get
their theme from `theme/lcr_theme.py` (rcParams + plotly template) — never style
a figure ad hoc.

Chart rules (apply to every figure):
- Paper background, no top/right spines, horizontal-only hairline gridlines.
- Direct labels over legends when ≤ 3 series; bar values at bar ends in tabular figures.
- Diverging bars pine/clay anchored at 0 with a hairline zero axis.
- Every chart: eyebrow ("CHART N"), sentence-case takeaway title, one-line
  caption ending "Data through {vintage}."
- Speculative figures get the gold corner tag "speculative · failed validation"
  baked into the image (governance feature, required — screenshots must not be
  able to shed the warning).

## Component inventory (B-4) — use these, don't hand-roll

1. **Scorecard row** — N big stat callouts, each with one-line context including
   its caveat inline. Cover, top of Key findings, top of Track record.
2. **Glossary panel** — "How to read these numbers" tinted panel. Track record.
3. **Gate ledger** — five-gates list with ✕/✓ left rail; failures visually
   co-equal with passes.
4. **Tier band table** — ranked tables with per-row tier-colored left border,
   zebra tint, tabular figures, ranges in slate.
5. **Speculative frame** — 2px gold border + standing warning header around ALL
   speculative content. The only permitted gold surface.
6. **Freeze-grade rail** — parameterized timeline (solid dot = frozen, open
   circle = graded). Brand signature; used in dividers, Track record, header marks.

## Verification

- Smoke test: `python tests/smoke_test.py` — config invariants, data-QA gate,
  scoring reproduces 110 ranked metros, every site page renders in both themes,
  consistency greps (forbidden phrases), canonical-figures assertions.
- Canonical figures live in a YAML the report builder and site test both assert
  against (see tests/ once PR 1 lands) — when a headline number legitimately
  changes at an edition freeze, update the YAML in the same commit, never the
  assertions.
- Visual regression: report pages render to PNG goldens; diffs must be reviewed
  deliberately, not rubber-stamped.

## Frozen registry — hard rule

Frozen editions live under `predictions/<timestamp>/` with
`predictions/registry_index.csv` as the index. **Never edit a frozen edition** —
data, ranks, ranges, or its generated art (hero/divider assets are stored with
the edition so old editions keep their own art). One-pagers join the registry at
freeze and are equally immutable. A fix to a frozen artifact is a new edition,
not an edit.
