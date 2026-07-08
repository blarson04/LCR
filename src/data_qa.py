"""
data_qa.py — the panel-level QA regime (P0, decision-log 2026-07-08).

The gates validate CONFIGURATIONS; until now nothing validated the PANEL.
Nine corrupted metros shipped inside a "validated" edition, and the #1 slot
was held by an artifact twice (Dayton neutral-fill, Fresno boundary break)
and nearly a third time (Hartford's +5-sigma income splice). This module
brings the panel under the same discipline as everything downstream of it:
every check that caught one of those bugs by hand is automated here, and
publication is BLOCKED until the report is green or every blocker carries a
disposition tied to a dated decision-log entry.

Checks (each emits flags; BLOCKER flags gate publication, WARN flags inform):
  1. cross-source growth diffs — every measure with an independent sister
     series: QCEW jobs vs CES, BEA income vs QCEW wages, ZHVI vs FHFA HPI,
     ACS population vs Census PEP. Flag when the within-year median-centered
     divergence exceeds 4pp or 3 sigma of the cross-sectional diff
     distribution (centering stops instrument-level offsets — e.g. transfer
     income in shock years — from blanket-flagging a whole year).
  2. distributional outlier gate — any metro-year input growth beyond 4 sigma
     of its within-year cross-section (z against the metro median, matching
     the D4b Hartford precedent) is BLOCKED until dispositioned.
  3. boundary watchlist — the current delineation's county membership per
     CBSA is diffed against a committed reference; any composition change
     flags the CBSA. Tests the CLASS of bug behind D3/D6, not the instances.
  4. top-10 anomaly review — no new top-10 entrant (or mover of >15 ranks
     into the top 10) publishes without a logged anomaly review.
  5. golden-metro regression — hand-verified input values for five metros
     (Albany, Fresno, Hartford, Dayton + Columbus as the clean control; the
     values that survived the D1-D6 cross-source and boundary verification)
     are asserted on every rebuild.

Artifacts (data/processed/qa/):
  qa_report_<stamp>.md / .json / qa_flags_<stamp>.csv   one set per run
  qa_dispositions.csv    flag_id -> disposition + decision-log entry date
  cbsa_membership_reference.csv, golden_metros.csv      committed references

Publication gate: registry.freeze_run and the vintage/nowcast freeze paths
call assert_publication_clear(), which requires the newest report to (a)
match the current panel.parquet hash and (b) have zero undispositioned
blockers. "Validated" on the site now means BOTH the configuration gate PASS
and this data-QA signoff.

    .venv/Scripts/python.exe src/data_qa.py                 # full QA run
    .venv/Scripts/python.exe src/data_qa.py --init-golden   # (re)freeze goldens
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config          # noqa: E402
from src import crosswalk  # noqa: E402

QA_DIR = config.PROCESSED_DIR / "qa"
QA_DIR.mkdir(parents=True, exist_ok=True)

MEMBERSHIP_REF = QA_DIR / "cbsa_membership_reference.csv"
GOLDEN_CSV = QA_DIR / "golden_metros.csv"
DISPOSITIONS_CSV = QA_DIR / "qa_dispositions.csv"
PANEL_PATH = config.PROCESSED_DIR / "panel.parquet"

# Thresholds (decision-log 2026-07-08, P0 — change only by dated entry).
CROSS_SOURCE_PP = 0.04     # flag when centered divergence exceeds 4pp ...
CROSS_SOURCE_SIGMA = 3.0   # ... or 3 sigma of the within-year diff distribution
OUTLIER_SIGMA = 4.0        # input growth beyond 4 sigma of its year cross-section
TOP10_MOVER_RANKS = 15     # mover of >15 ranks into the top 10 needs review
GOLDEN_RTOL = 1e-4

# Inputs whose YoY growth feeds the model or a proxy; all get the outlier gate.
GROWTH_INPUTS = ["total_emp", "per_capita_income", "population", "housing_units",
                 "zori", "zhvi", "avg_annual_pay"]

# Golden metros: the four artifact/repair sites plus one clean control.
GOLDEN_METROS = {"10580": "Albany", "23420": "Fresno", "25540": "Hartford",
                 "19430": "Dayton", "18140": "Columbus"}
GOLDEN_YEARS = (2022, 2023, 2024)
GOLDEN_COLS = ["population", "housing_units", "rental_vacancy", "net_migration",
               "permits_total", "permits_mf", "total_emp", "avg_annual_pay",
               "emp_hhi", "per_capita_income", "zori", "zhvi"]


# --------------------------------------------------------------------------
# Plumbing
# --------------------------------------------------------------------------
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _flag_id(check: str, cbsa: str, year, measure: str) -> str:
    """Stable id so a disposition given once survives re-runs."""
    key = f"{check}|{cbsa}|{year}|{measure}"
    return hashlib.sha1(key.encode()).hexdigest()[:10]


def _flag(check: str, severity: str, measure: str, detail: str, *,
          cbsa: str = "", title: str = "", year="") -> dict:
    return {"flag_id": _flag_id(check, cbsa, year, measure), "check": check,
            "severity": severity, "cbsa_code": cbsa, "cbsa_title": title,
            "year": year, "measure": measure, "detail": detail}


def load_panel() -> pd.DataFrame:
    return pd.read_parquet(PANEL_PATH)


def _yoy_long(panel: pd.DataFrame, col: str, out_name: str) -> pd.DataFrame:
    """[cbsa_code, year, <out_name>] YoY growth using the EXACT prior year."""
    prev = panel[["cbsa_code", "year", col]].copy()
    prev["year"] += 1
    m = panel[["cbsa_code", "year", col]].merge(
        prev.rename(columns={col: "_prev"}), on=["cbsa_code", "year"], how="left")
    m[out_name] = m[col] / m["_prev"] - 1.0
    return m[["cbsa_code", "year", out_name]].dropna(subset=[out_name])


_TITLES: dict[str, str] = {}


def _title(cbsa: str) -> str:
    return _TITLES.get(str(cbsa), "")


# --------------------------------------------------------------------------
# Check 1 — cross-source growth diffs (the D6 detection protocol, systematized)
# --------------------------------------------------------------------------
def _diff_flags(check: str, merged: pd.DataFrame, a: str, b: str) -> list[dict]:
    """Flag metro-years where growth series `a` and `b` diverge beyond the
    thresholds, after centering each year's diffs at the cross-sectional
    median (so instrument-level offsets don't flag whole years)."""
    flags = []
    merged = merged.copy()
    merged["diff"] = merged[a] - merged[b]
    for yr, g in merged.groupby("year"):
        med, sd = g["diff"].median(), g["diff"].std(ddof=0)
        centered = g["diff"] - med
        z = centered / sd if sd > 0 else centered * 0.0
        hit = g[(centered.abs() > CROSS_SOURCE_PP) | (z.abs() > CROSS_SOURCE_SIGMA)]
        for _, r in hit.iterrows():
            c = centered.loc[r.name]
            flags.append(_flag(
                check, "BLOCKER", a, cbsa=str(r["cbsa_code"]),
                title=_title(r["cbsa_code"]), year=int(yr),
                detail=(f"{a} {r[a]:+.1%} vs {b} {r[b]:+.1%} "
                        f"(centered diff {c:+.1%}, z {z.loc[r.name]:+.1f}); "
                        f"verify boundary/source before publishing")))
    return flags


def cross_source_flags(panel: pd.DataFrame) -> list[dict]:
    flags: list[dict] = []

    # Jobs: QCEW vs CES (the check that caught the six D6 boundary breaks).
    try:
        from src.ingest import bls_ces
        ces = bls_ces.build_ces_job_growth_panel()
        qcew_g = _yoy_long(panel, "total_emp", "qcew_job_growth")
        m = qcew_g.merge(ces, on=["cbsa_code", "year"], how="inner")
        flags += _diff_flags("cross_source_jobs", m, "qcew_job_growth", "ces_job_growth")
    except Exception as e:
        flags.append(_flag("cross_source_jobs", "WARN", "qcew_job_growth",
                           f"sister series unavailable, check skipped: {e}"))

    # Income: BEA per-capita income vs QCEW average pay (both already in panel).
    inc_g = _yoy_long(panel, "per_capita_income", "bea_income_growth")
    pay_g = _yoy_long(panel, "avg_annual_pay", "qcew_pay_growth")
    m = inc_g.merge(pay_g, on=["cbsa_code", "year"], how="inner")
    flags += _diff_flags("cross_source_income", m, "bea_income_growth", "qcew_pay_growth")

    # Home values: Zillow ZHVI vs FHFA all-transactions HPI.
    try:
        from src.ingest import fhfa
        hpi = fhfa.build_hpi_annual_panel()
        zhvi_g = _yoy_long(panel, "zhvi", "zhvi_growth")
        hpi_g = _yoy_long(hpi, "fhfa_hpi", "fhfa_hpi_growth")
        m = zhvi_g.merge(hpi_g, on=["cbsa_code", "year"], how="inner")
        flags += _diff_flags("cross_source_home_values", m, "zhvi_growth", "fhfa_hpi_growth")
    except Exception as e:
        flags.append(_flag("cross_source_home_values", "WARN", "zhvi_growth",
                           f"sister series unavailable, check skipped: {e}"))

    # Population: ACS vs Census PEP.
    try:
        from src.ingest import census_pep
        pep = census_pep.build_pep_population_panel()[["cbsa_code", "year", "pep_pop"]]
        acs_g = _yoy_long(panel, "population", "acs_pop_growth")
        pep_g = _yoy_long(pep, "pep_pop", "pep_pop_growth")
        m = acs_g.merge(pep_g, on=["cbsa_code", "year"], how="inner")
        flags += _diff_flags("cross_source_population", m, "acs_pop_growth", "pep_pop_growth")
    except Exception as e:
        flags.append(_flag("cross_source_population", "WARN", "acs_pop_growth",
                           f"sister series unavailable, check skipped: {e}"))

    return flags


# --------------------------------------------------------------------------
# Check 2 — distributional outlier gate (the D4b Hartford tripwire)
# --------------------------------------------------------------------------
def outlier_flags(panel: pd.DataFrame) -> list[dict]:
    flags = []
    for col in GROWTH_INPUTS:
        g = _yoy_long(panel, col, "growth")
        for yr, grp in g.groupby("year"):
            med, sd = grp["growth"].median(), grp["growth"].std(ddof=0)
            if not sd or np.isnan(sd):
                continue
            z = (grp["growth"] - med) / sd
            for _, r in grp[z.abs() > OUTLIER_SIGMA].iterrows():
                flags.append(_flag(
                    "outlier_gate", "BLOCKER", f"{col}_growth",
                    cbsa=str(r["cbsa_code"]), title=_title(r["cbsa_code"]),
                    year=int(yr),
                    detail=(f"{col} growth {r['growth']:+.1%} is "
                            f"{z.loc[r.name]:+.1f} sigma vs the {yr} metro median "
                            f"({med:+.1%}); blocked until dispositioned")))
    return flags


# --------------------------------------------------------------------------
# Check 3 — boundary watchlist (the class of bug behind D3/D6)
# --------------------------------------------------------------------------
def boundary_flags(universe: set[str]) -> list[dict]:
    xw = crosswalk.load()[["cbsa_code", "cbsa_title", "county_fips"]].sort_values(
        ["cbsa_code", "county_fips"]).reset_index(drop=True)
    if not MEMBERSHIP_REF.exists():
        xw.to_csv(MEMBERSHIP_REF, index=False)
        return [_flag("boundary_watchlist", "WARN", "membership_reference",
                      f"reference initialized from the current delineation "
                      f"({len(xw)} county rows); future runs diff against it")]

    ref = pd.read_csv(MEMBERSHIP_REF, dtype=str)
    cur = {c: set(g["county_fips"]) for c, g in xw.groupby("cbsa_code")}
    old = {c: set(g["county_fips"]) for c, g in ref.groupby("cbsa_code")}
    flags = []
    for cbsa in sorted(set(cur) | set(old)):
        added = cur.get(cbsa, set()) - old.get(cbsa, set())
        removed = old.get(cbsa, set()) - cur.get(cbsa, set())
        if not added and not removed:
            continue
        sev = "BLOCKER" if cbsa in universe else "WARN"
        title = (xw[xw["cbsa_code"] == cbsa]["cbsa_title"].iloc[0]
                 if (xw["cbsa_code"] == cbsa).any() else "")
        parts = []
        if added:
            parts.append("adds " + ", ".join(sorted(added)))
        if removed:
            parts.append("loses " + ", ".join(sorted(removed)))
        flags.append(_flag(
            "boundary_watchlist", sev, "county_membership", cbsa=cbsa, title=title,
            detail=(f"county composition changed vs reference: {'; '.join(parts)}. "
                    f"Every series derived from this CBSA's area files must be "
                    f"boundary-verified before publishing (D6 protocol)")))
    return flags


def update_membership_reference() -> None:
    """Accept the current delineation as the new reference (call only after
    the boundary flags are dispositioned in the decision log)."""
    xw = crosswalk.load()[["cbsa_code", "cbsa_title", "county_fips"]].sort_values(
        ["cbsa_code", "county_fips"]).reset_index(drop=True)
    xw.to_csv(MEMBERSHIP_REF, index=False)


# --------------------------------------------------------------------------
# Check 4 — top-10 anomaly review rule
# --------------------------------------------------------------------------
def top10_flags(current: pd.DataFrame, prior: pd.DataFrame, label: str) -> list[dict]:
    """Flag new top-10 entrants and >15-rank movers into the top 10, current
    edition vs the prior published (frozen) edition."""
    cur = current.set_index("cbsa_code")["rank"]
    old = prior.set_index("cbsa_code")["rank"]
    flags = []
    top10 = current[current["rank"] <= 10]
    for _, r in top10.iterrows():
        c = str(r["cbsa_code"])
        prior_rank = old.get(c)
        if prior_rank is None or np.isnan(prior_rank):
            move = "not in the prior edition"
        elif prior_rank > 10 and (prior_rank - r["rank"]) > TOP10_MOVER_RANKS:
            move = f"moved {int(prior_rank)} -> {int(r['rank'])}"
        elif prior_rank > 10:
            move = f"entered the top 10 ({int(prior_rank)} -> {int(r['rank'])})"
        else:
            continue
        flags.append(_flag(
            "top10_review", "BLOCKER", label, cbsa=c,
            title=r.get("cbsa_title", _title(c)), year=label,
            detail=(f"{move}; rank #{int(r['rank'])} may not publish without a "
                    f"logged anomaly review of its input values (P0 rule 4)")))
    return flags


def _edition_rankings() -> list[tuple[str, int, pd.DataFrame]]:
    """The edition ranking files staged for publication: [(label, score_year, df)]."""
    out = []
    for p in sorted(config.PROCESSED_DIR.glob("vintage/vintage_*_ranking.csv")):
        yr = int(p.stem.split("_")[1])
        out.append((p.stem, yr, pd.read_csv(p, dtype={"cbsa_code": str})))
    for p in sorted(config.PROCESSED_DIR.glob("nowcast/provisional_*_ranking.csv")):
        yr = int(p.stem.split("_")[1])
        out.append((p.stem, yr, pd.read_csv(p, dtype={"cbsa_code": str})))
    return out


def _prior_frozen_ranking(score_year: int, index: pd.DataFrame) -> pd.DataFrame | None:
    """Latest frozen registry ranking for the same score year, else the latest
    frozen run overall (a brand-new score year is compared against the most
    recent published edition — that IS the edition-to-edition churn)."""
    same = index[index["score_year"] == score_year]
    pick = same.iloc[-1] if len(same) else (index.iloc[-1] if len(index) else None)
    if pick is None:
        return None
    path = config.PREDICTIONS_DIR / pick["timestamp_utc"] / "ranking.csv"
    return pd.read_csv(path, dtype={"cbsa_code": str}) if path.exists() else None


# --------------------------------------------------------------------------
# Check 5 — golden-metro regression tests
# --------------------------------------------------------------------------
def init_golden(panel: pd.DataFrame | None = None) -> pd.DataFrame:
    """Freeze the current (D1-D6 verified) input values for the golden metros.
    Re-run ONLY after a dispositioned golden failure — never to silence one."""
    if panel is None:
        panel = load_panel()
    rows = panel[panel["cbsa_code"].isin(GOLDEN_METROS)
                 & panel["year"].isin(GOLDEN_YEARS)]
    long = rows.melt(id_vars=["cbsa_code", "cbsa_title", "year"],
                     value_vars=GOLDEN_COLS, var_name="column", value_name="value")
    long = long.sort_values(["cbsa_code", "year", "column"]).reset_index(drop=True)
    long.to_csv(GOLDEN_CSV, index=False)
    return long


def golden_flags(panel: pd.DataFrame | None = None) -> list[dict]:
    """Assert the panel still carries the hand-verified golden values.
    Network-free (committed CSV vs committed parquet) — also run by the CI
    smoke test on every build."""
    if panel is None:
        panel = load_panel()
    if not GOLDEN_CSV.exists():
        return [_flag("golden_metros", "WARN", "golden_reference",
                      "golden_metros.csv not initialized; run --init-golden")]
    golden = pd.read_csv(GOLDEN_CSV, dtype={"cbsa_code": str})
    cur = panel.melt(id_vars=["cbsa_code", "cbsa_title", "year"],
                     value_vars=GOLDEN_COLS, var_name="column", value_name="value")
    m = golden.merge(cur, on=["cbsa_code", "year", "column"],
                     how="left", suffixes=("_golden", ""))
    flags = []
    for _, r in m.iterrows():
        gv, cv = r["value_golden"], r["value"]
        if pd.isna(gv) and pd.isna(cv):
            continue
        ok = (pd.notna(gv) and pd.notna(cv)
              and np.isclose(gv, cv, rtol=GOLDEN_RTOL, equal_nan=False))
        if not ok:
            flags.append(_flag(
                "golden_metros", "BLOCKER", r["column"], cbsa=str(r["cbsa_code"]),
                title=r["cbsa_title_golden"], year=int(r["year"]),
                detail=(f"verified value {gv!r} became {cv!r}; either a source "
                        f"revision (verify, then re-freeze via --init-golden with "
                        f"a log entry) or a regression (fix the pipeline)")))
    return flags


# --------------------------------------------------------------------------
# Dispositions + the publication gate
# --------------------------------------------------------------------------
def load_dispositions() -> pd.DataFrame:
    if DISPOSITIONS_CSV.exists():
        return pd.read_csv(DISPOSITIONS_CSV, dtype=str)
    return pd.DataFrame(columns=["flag_id", "report", "disposition",
                                 "decision_log_date", "note"])


def latest_report() -> dict | None:
    metas = sorted(QA_DIR.glob("qa_report_*.json"))
    if not metas:
        return None
    return json.loads(metas[-1].read_text())


def publication_gate() -> tuple[bool, str]:
    """(ok, message). Publication requires the newest QA report to match the
    current panel hash and carry zero undispositioned BLOCKER flags."""
    meta = latest_report()
    if meta is None:
        return False, ("no QA report found — run src/data_qa.py before "
                       "freezing/publishing (P0, decision-log 2026-07-08)")
    if meta["panel_sha256"] != _sha256(PANEL_PATH):
        return False, (f"QA report {meta['stamp']} was produced from a different "
                       f"panel build — re-run src/data_qa.py on the current panel")
    flags = pd.read_csv(QA_DIR / f"qa_flags_{meta['stamp']}.csv", dtype=str)
    blockers = flags[flags["severity"] == "BLOCKER"]
    open_ids = set(blockers["flag_id"]) - set(load_dispositions()["flag_id"])
    if open_ids:
        sample = blockers[blockers["flag_id"].isin(open_ids)].head(5)
        lines = "; ".join(f"{r['check']}:{r['cbsa_code']}/{r['year']}/{r['measure']}"
                          for _, r in sample.iterrows())
        return False, (f"{len(open_ids)} undispositioned blocker(s) in QA report "
                       f"{meta['stamp']} (e.g. {lines}) — disposition each in "
                       f"data/processed/qa/qa_dispositions.csv, backed by a dated "
                       f"decision-log entry, before publishing")
    return True, f"QA report {meta['stamp']}: clear for publication"


def assert_publication_clear() -> None:
    ok, msg = publication_gate()
    if not ok:
        raise RuntimeError(f"DATA-QA PUBLICATION BLOCK: {msg}")


# --------------------------------------------------------------------------
# The full run + report artifact
# --------------------------------------------------------------------------
def run() -> Path:
    global _TITLES
    panel = load_panel()
    _TITLES = dict(zip(panel["cbsa_code"].astype(str), panel["cbsa_title"]))
    universe = set(panel["cbsa_code"].astype(str))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    print("Data-QA run (P0 regime, decision-log 2026-07-08)\n")
    all_flags: list[dict] = []
    print("  1/5 cross-source growth diffs ...")
    all_flags += cross_source_flags(panel)
    print("  2/5 distributional outlier gate ...")
    all_flags += outlier_flags(panel)
    print("  3/5 boundary watchlist ...")
    all_flags += boundary_flags(universe)
    print("  4/5 top-10 anomaly review ...")
    try:
        index = pd.read_csv(config.PREDICTIONS_DIR / "registry_index.csv")
        for label, yr, ranking in _edition_rankings():
            prior = _prior_frozen_ranking(yr, index)
            if prior is not None:
                all_flags += top10_flags(ranking, prior, label)
    except Exception as e:
        all_flags.append(_flag("top10_review", "WARN", "edition_rankings",
                               f"could not compare editions: {e}"))
    print("  5/5 golden-metro regression ...")
    all_flags += golden_flags(panel)

    flags = pd.DataFrame(all_flags, columns=["flag_id", "check", "severity",
                                             "cbsa_code", "cbsa_title", "year",
                                             "measure", "detail"])
    dispositioned = set(load_dispositions()["flag_id"])
    flags["dispositioned"] = flags["flag_id"].isin(dispositioned)
    n_block = int(((flags["severity"] == "BLOCKER") & ~flags["dispositioned"]).sum())
    n_warn = int((flags["severity"] == "WARN").sum())
    status = "GREEN" if n_block == 0 else "NEEDS DISPOSITION"

    flags.to_csv(QA_DIR / f"qa_flags_{stamp}.csv", index=False)
    meta = {"stamp": stamp, "panel_sha256": _sha256(PANEL_PATH), "status": status,
            "n_blockers_open": n_block,
            "n_blockers_total": int((flags["severity"] == "BLOCKER").sum()),
            "n_warns": n_warn,
            "checks": ["cross_source", "outlier_gate", "boundary_watchlist",
                       "top10_review", "golden_metros"]}
    (QA_DIR / f"qa_report_{stamp}.json").write_text(json.dumps(meta, indent=2))

    lines = [f"# Data-QA report — {stamp}", "",
             f"Panel: `data/processed/panel.parquet` (sha256 `{meta['panel_sha256'][:12]}…`)",
             f"Status: **{status}** — {n_block} open blocker(s), "
             f"{meta['n_blockers_total'] - n_block} dispositioned, {n_warn} warning(s)", "",
             "Publication is blocked until every BLOCKER carries a disposition in",
             "`qa_dispositions.csv` backed by a dated decision-log entry (P0 regime,",
             "decision-log 2026-07-08).", ""]
    for check, g in flags.groupby("check"):
        lines.append(f"## {check} ({len(g)} flag(s))\n")
        for _, r in g.iterrows():
            mark = "~" if r["dispositioned"] else ("**BLOCKER**" if r["severity"] == "BLOCKER" else "warn")
            where = " ".join(str(x) for x in [r["cbsa_title"] or r["cbsa_code"], r["year"]] if x)
            lines.append(f"- [{r['flag_id']}] {mark} {where} — {r['detail']}")
        lines.append("")
    if not len(flags):
        lines.append("No flags. Panel is clean under all five checks.")
    report = QA_DIR / f"qa_report_{stamp}.md"
    report.write_text("\n".join(lines), encoding="utf-8")

    print(f"\nStatus: {status}")
    print(f"  blockers open/total : {n_block}/{meta['n_blockers_total']}")
    print(f"  warnings            : {n_warn}")
    print(f"  report              : {report.relative_to(config.ROOT)}")
    return report


if __name__ == "__main__":
    if "--init-golden" in sys.argv:
        g = init_golden()
        print(f"Golden values frozen: {len(g)} rows -> {GOLDEN_CSV.relative_to(config.ROOT)}")
    else:
        run()
