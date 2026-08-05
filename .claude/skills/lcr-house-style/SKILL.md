---
name: lcr-house-style
description: Larson Capital Research house rules for ALL user-facing words and design. ALWAYS use this skill when writing or editing any copy, caption, chart label, table header, badge, tooltip, heading, footer, README-facing prose, or design element for the PDF report or the Streamlit site — including "small" tweaks to a single string. If the change ships words or pixels a reader sees, this skill applies. Self-check output against the forbidden patterns before committing.
---

# LCR house style — non-negotiable rules

These rules protect the project's core asset: credibility. Substance already beats
the industry comps; no copy or design change may trade substance for polish. If a
proposed change conflicts with a rule here, the rule wins and the change is dropped.

## The rules

1. **"Screen", never "forecast" in body copy.** Permitted exceptions ONLY:
   the badge phrase "Validated 2025→2028 forecast · proxied inputs", and sentences
   of the form "treat it as a screen, not a forecast." The PDF cover/gate list uses
   "2024–2027 forecast" / "2025–2028 forecast" inside the gate outcomes — those are
   grandfathered as gate-record language; do not add new instances.
2. **No em dashes anywhere.** " · " middle dot is the house separator. En dashes
   only inside numeric ranges (1–27, 2020–22). Arrows (→) only in edition labels
   (2025→2028).
3. **Numbers get context, not adjectives.** "+6.0 points across six windows" is
   house style. "Excellent", "impressive", "strong performance" applied to our own
   numbers is a bug. (Adjectives inside fixed template strings like "Strong
   migration & jobs" describe markets, not our accuracy, and are fine.)
4. **Negative results stay prominent.** No design change may reduce the visual
   weight of failures, shock-period losses, or the speculative page's warnings.
   The failed-gates list must remain at equal or greater visual prominence than
   the passes.
5. **Disclaimers: once per page body, one clause, plus the standing footer.**
   Never stack.
6. **Sentence case for all headings.**
7. **Every technical term defined on first use per page/section** (tau,
   percentile, P@10, proxied inputs, uncertainty flag).
8. **Imagery policy: data-as-art and geometric brand texture only.** No stock
   photography, no skyline or building imagery, no decorative icons, no emoji.
   Visual richness comes from (a) our own data rendered large and well, and
   (b) an abstract geometric texture system derived from the project's visual
   grammar (tier bands, freeze-grade rail, hairline grids). Informational marks
   that encode real content (gate ✕/✓ marks, tier bands, timeline rails) are
   encouraged; ornamental icons that encode nothing are not.
9. **Data vintages always shown** next to any accuracy or input figure.
10. **Never hand-adjust any market anywhere**, including in examples, spotlights,
    or captions.

## Vocabulary and phrasing

- Shock label is canonical: "the 2020–22 shock" / "shock (2020–22) windows".
  Never "2021–22 shock".
- Gate item 1 outcome: "Failed; never shipped." (not "Failed; not published" —
  the outcome IS published; the configuration never deployed).
- Failure count: THREE configurations failed gates and were published.
- Fractional name-match figures ("4.8 of 10") get "(averaged across the test
  windows)" at first use per artifact.
- Negative values use a true minus sign (−), not hyphen-minus, in rendered copy
  and chart labels.
- "Top-10 edge (points)", not "(pp)", in table headers.
- Gold (`--lcr-flag` / flag token) is reserved exclusively for
  speculative/unvalidated labeling. Green = validated, clay = negative/failed,
  gold = not validated. Never decorative.

## Self-check greps (run on your own output before committing)

FORBIDDEN — a match means fix before shipping:
- `forecast` outside the two allowed patterns above (badge phrase; "a screen, not
  a forecast"; grandfathered gate-record lines)
- `—` (em dash) anywhere
- `2021–22 shock` or `2021-22 shock`
- `two configurations failed`
- `; not investment advice` (correct form: "A research screen, not investment
  advice.")
- Self-praising adjectives adjacent to our accuracy numbers: excellent,
  impressive, remarkable, outstanding, strong performance
- Stock-photo, skyline, building, or icon assets in any diff

ALLOWED (do not "fix" these):
- "Validated 2025→2028 forecast · proxied inputs"
- "treat it as a screen, not a forecast"
- En dashes in numeric ranges; → in edition labels
- Template adjectives describing markets ("Strong migration & jobs")

The automated versions of these greps live in the smoke test
([tests/smoke_test.py](tests/smoke_test.py)); this skill exists so drafts comply
before the test catches them.
