---
name: screener-site-design
description: Design system and rules for the multifamily screener Streamlit website. ALWAYS use this skill whenever creating or modifying ANYTHING the user sees in the web app — pages, layout, tables, charts, maps, colors, fonts, copy, badges, metrics, or navigation. This includes small tweaks ("make this chart bigger", "add a column"), new pages, and any work in app/ or on streamlit_app.py. If the change ships pixels, this skill applies.
---

# Screener Site Design System

The audience is an **investor or analyst deciding whether to trust a research tool.**
What earns that trust visually is restraint: a calm, report-like site that feels like the
research paper it accompanies. The enemy is both the default Streamlit look (reads as hobby
project) and dashboard-overload (reads as trying too hard). Every screen answers **one
question**; depth exists but is revealed progressively, never dumped.

Design mantra: **calm confidence.** If a page feels busy, it is wrong — remove, don't rearrange.

---

## 1. Design tokens (single source of truth)

Define these once (a `ui/theme.py` constants module) and import everywhere. Never hardcode a
hex value in page code.

**Palette**

| Token | Hex | Use |
| --- | --- | --- |
| `INK` | `#1B2A3B` | Headings, body text, table text |
| `PAPER` | `#FBFBF9` | Page background |
| `SURFACE` | `#FFFFFF` | Cards, table backgrounds |
| `LINE` | `#E4E6EA` | Hairline borders, dividers |
| `MUTED` | `#66707D` | Captions, secondary text, axis labels |
| `ACCENT` | `#2C6E63` | THE brand color: links, active states, primary chart series, map high end |
| `POS` | `#1E7F4F` | Positive data values ONLY (never decoration) |
| `NEG` | `#B3462E` | Negative data values ONLY (never decoration) |
| `PROVISIONAL` | `#8A6D1D` | Provisional/nowcast badge ONLY |

Rules: one accent, used sparingly — if a screen shows accent color in more than ~3 places,
cut back. Green/red are reserved for the *direction of data* (score signs, rent growth), never
for buttons or decoration. No gradients, no shadows heavier than `0 1px 3px rgba(27,42,59,.08)`.

**Typography**

- Headings: **Source Serif 4** (report gravitas; matches the paper).
- Body/UI/tables: **Inter**.
- Numbers in tables: Inter with `font-variant-numeric: tabular-nums` so columns align.
- Scale: page title 28px/600, section head 20px/600, body 15px/400, caption 13px `MUTED`.
  Nothing bigger than 28px except at most ONE hero number per page.

**Spacing**: base unit 8px. Sections separated by 40px minimum. When in doubt, add space,
not lines or boxes.

---

## 2. Streamlit implementation

**`.streamlit/config.toml`** (the baseline; CSS refines it):

```toml
[theme]
base = "light"
primaryColor = "#2C6E63"
backgroundColor = "#FBFBF9"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#1B2A3B"
font = "sans serif"
```

**Global CSS** lives in ONE function `inject_css()` in `ui/theme.py`, called at the top of
every page — never scatter `st.markdown(<style>...)` through page code. It should: import the
two Google Fonts; set heading/body families; hide Streamlit chrome (`#MainMenu`, `footer`,
the "deploy" button); tighten the default block padding (`.block-container {max-width: 1100px;
padding-top: 2.5rem}`); style tables per §4; define the `.badge-provisional` and
`.badge-final` classes.

**Page structure**: use `st.set_page_config(layout="centered")` for reading pages
(Methodology, Track Record) and `layout="wide"` ONLY where a table/map genuinely needs it
(Rankings). Multipage via the `pages/` folder with clear names: `Rankings`, `Metro detail`,
`Track record`, `Methodology`.

---

## 3. Layout principles

- **One question per screen.** Rankings answers "which markets look strongest?" Metro detail
  answers "why does this market rank where it does?" Track record answers "has this worked?"
  If a page starts answering two questions, split it.
- **Progressive disclosure.** Default view = the headline (top-10 list + map). Full 110-row
  table, indicator definitions, per-bucket breakdowns live behind `st.tabs` or `st.expander`
  ("See all 110 markets", "How this score is built"). An investor should get the point of any
  page in 10 seconds without scrolling.
- **Max 3 `st.metric`/stat cards per row, max one row of them per page.** More reads as
  dashboard-overload.
- **Every page opens with one plain-English sentence** stating what the page shows, in
  `MUTED` caption style. E.g. Rankings: "Markets ranked by fundamentals that historically
  precede rent growth — scored on the latest complete data (2023)."
- Sidebar carries only navigation and global controls (year, finalized/provisional toggle).
  No filters buried in the sidebar that change what a chart means without the user noticing.

---

## 4. Data presentation

**Tables**
- Default ranked table shows FIVE columns max: Rank, Metro, Score, Top strength, Top drag
  (the strength/drag derived from the largest positive/negative bucket contribution, shown as
  words: "Strong migration", "Heavy construction"). Everything else behind the expander view.
- Raw z-scores never appear in a default view — translate to plain language or percentile
  bars. In expanded/advanced views they may appear with a one-line explainer.
- Format: scores to 2 decimals with explicit sign (+0.53), populations with thousands
  separators, right-align numbers, `tabular-nums`. Zebra striping OFF; use generous row
  padding + hairline `LINE` dividers instead.

**Charts (Plotly)** — define ONE template in `ui/theme.py` and apply to every figure:
- `PAPER` background, no plot border, horizontal gridlines only in `LINE`, `MUTED`
  axis text, Inter font.
- One series gets `ACCENT`; context/comparison series get grays. Never more than 4 series.
- **Direct-label lines at their right end; kill the legend** whenever ≤4 series.
- Every chart gets a caption (13px `MUTED`) stating the takeaway in words: "Charleston has
  ranked in the top 20 since 2021."
- Choropleth map: sequential scale from `#E7ECEA` to `ACCENT`. NEVER a red-green or rainbow
  scale for score (red/green only if the variable is signed rent growth). Metro hover shows
  rank, score, one-line strength.

**Uncertainty & honesty in the UI**
- Ranks display as ranges where computed ("Rank 3 (2–6)"), with a tooltip: "Range reflects
  statistical uncertainty in the score."
- Provisional/nowcast data ALWAYS carries the `PROVISIONAL` badge ("Provisional — based on
  preliminary data") adjacent to any number it affects, plus the finalized/provisional toggle
  state visible at all times. Finalized views may carry a quiet "Finalized 2023" badge.
- The shock-regime caveat appears wherever backtest numbers are shown: one caption line,
  "Validation reflects normal market conditions; the framework underperforms in shocks
  (see Track record)."

---

## 5. Copy rules

- Plain language, active voice, sentence case everywhere (headings included).
- Define any term on first use per page, in-line and short: "weighted Kendall's tau (a
  rank-agreement score from −1 to +1)". Banned without definition: z-score, tau, winsorize,
  cross-sectional, CBSA.
- Numbers get context, not adjectives: "88% of top-10 picks landed in the top quarter of
  markets" — never "excellent accuracy".
- Buttons/controls say what they do: "Compare markets", "Show all 110", not "Go" / "Submit".
- The site never overclaims: the words "screening framework" appear on every page footer with
  the standing line: "A research screen, not investment advice."

---

## 6. Anti-patterns (never ship these)

- Default Streamlit chrome visible (hamburger, footer, red accent).
- A wall of 110 rows × 10 columns as the landing view.
- Rainbow/diverging-red-green choropleth for the composite score.
- More than one accent color, colored section backgrounds, emoji in headings or labels.
- Legends when direct labels fit; gridlines in both directions; chart titles restating the
  section heading.
- Raw column names (`permits_to_stock`) or raw z-scores in any default view.
- A provisional number shown anywhere without its badge.
- `st.balloons`, spinners with jokey text, or any playful flourish — wrong register for the
  audience.

---

## 7. Ship checklist (run before completing any UI task)

1. Does each touched page still answer exactly one question, stated in its opening caption?
2. Could an investor get the point in 10 seconds without scrolling? Is depth behind
   tabs/expanders rather than gone?
3. All colors/fonts pulled from `ui/theme.py` tokens — zero hardcoded hex in page code?
4. Every chart: template applied, ≤4 series, direct labels, takeaway caption?
5. Every number formatted (signs, decimals, tabular-nums) and every term defined on the page?
6. Provisional badge present wherever nowcast data appears? Footer disclaimer present?
7. Screenshot the page (or run it) and look: is there anything you could remove without
   losing meaning? Remove it.
