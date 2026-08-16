# V4-6 reconciliation — dispositions (2026-08-16)

Companion to `v4_permit_reconcile_fred.csv`. Spec: decision-log 2026-08-16.

## Verdicts

1. **vs the screener's permits input (authoritative): EXACT.** 110 metros,
   1,186 metro-years (2015–2025), max |diff| = 0 units for both total and 5+
   series. Same county annual files, same fixed July-2023 crosswalk — the
   candidate inherits the panel input's already-QA'd construction.
2. **National (authoritative): EXACT.** County-file national sums match FRED
   PERMITNSA annual totals within 0.1% in every checked year (2015, 2019,
   2023, 2024). The national monthly series is benchmarked to the annual
   canvass, so this is an independent full-coverage check.
3. **vs FRED metro series (informational): 61 of 141 comparisons outside 3%,
   every investigated case FRED-side.** FRED mirrors the *published* metro
   files: unrevised monthly estimates on the delineation current at
   publication. Three documented failure modes account for the divergences,
   all of which the county-annual construction exists to avoid:
   - **Delineation vintage.** FRED observations before the Jan-2024 CBSA
     switch sit on old boundaries. New Orleans (ours ~37% below FRED
     2019–2023) is the St. Tammany Parish split — the same 2023-delineation
     change recorded in the D8 repairs. Our fixed-2023 rollup excludes it for
     all years, by design.
   - **FRED-side series breaks.** Allentown (+215% → −0.5%) and Pittsburgh
     (+151% → −11%) snap into agreement at the switch — level breaks inside
     the FRED history, smooth in ours.
   - **Monthly-vs-canvass.** Small residuals (Austin +1.6% to +6.8%, Durham
     ±10%) are late-reporter imputation: monthly sub-national estimates are
     never revised; the May final-annual canvass (our source) supersedes them.

No construction defect was found in any investigated metro. 39 universe
metros have no FRED total-units series (FRED covers ~115 large metros); they
are fully covered by checks 1–2.

## Coverage note (uniform, disclosed)

Hartford, Bridgeport, and New Haven have no county-file permits before the
2023 file (BPS adopted CT planning-region FIPS with the 2023 annual file), so
their momentum begins in 2024 — identical to the panel's existing permits
input, standard neutral fill downstream. Universe coverage in usable
prediction years is 107/110, above the ≥100/110 kill-rule.
