"""
v4_permit_momentum.py — V4-6 candidate construction: permit MOMENTUM (direction
of supply). Spec: decision-log 2026-08-16. CANDIDATE ONLY — nothing here touches
the frozen model, the panel build, or any published surface.

This module does the DATA work only (no outcome data, no accuracy):
  build      parse Census BPS county ANNUAL files 1990-2025 under ONE format
             rule, roll counties up to every metro on the fixed July-2023
             delineation (the screener's standing crosswalk), and build the
             four frozen momentum measures for the full universe.
  reconcile  full-universe checks, scripted, not hand-picked: exact match vs
             the screener's existing permits panel (2015-2025), FRED metro
             permit series annual sums (recent years), FRED national total.
  sanity     the three pre-committed sanity cases (values only).

The gate itself lives in src/v4_momentum_gate.py and may not run before
2026-08-17 (cooling-off rule).

    .venv/Scripts/python.exe src/v4_permit_momentum.py build
    .venv/Scripts/python.exe src/v4_permit_momentum.py reconcile
    .venv/Scripts/python.exe src/v4_permit_momentum.py sanity
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config            # noqa: E402
from src import crosswalk  # noqa: E402

BPS_RAW_DIR = config.RAW_DIR / "bps"
BPS_RAW_DIR.mkdir(parents=True, exist_ok=True)
_BASE = "https://www2.census.gov/econ/bps/County"

# Full available history. The gate only needs 2014+; earlier years are context
# and QC depth. County annual files verified 2026-08-16: every year 1990-2025
# exists and shares one layout (6 id columns, then four Bldgs/Units/Value
# triples of IMPUTED estimates, then the same four triples reported-only).
YEARS = range(1990, 2026)

# 0-indexed "Units" columns per structure size — imputed estimates, then the
# reported-only mirror. Same positions in every file year (verified 1990/2000/
# 2014/2024). We sum units, never buildings or valuation.
_ID = {"state": 1, "county": 2}
_UNITS = {"u1": 7, "u2": 10, "u34": 13, "u5": 16}
_UNITS_REP = {"u1": 19, "u2": 22, "u34": 25, "u5": 28}

MEASURES = ["permit_momentum_total", "permit_momentum_total_rate",
            "permit_momentum_mf", "permit_momentum_mf_rate"]
OUT_PANEL = config.PROCESSED_DIR / "v4_permit_panel.csv"
OUT_MOMENTUM = config.PROCESSED_DIR / "v4_permit_momentum.csv"
OUT_QC = config.PROCESSED_DIR / "v4_permit_momentum_qc.csv"
OUT_RECONCILE = config.PROCESSED_DIR / "v4_permit_reconcile_fred.csv"

IMPUTED_SHARE_FLAG = 0.25   # QC report threshold (report-only; no exclusions)


# ---------------------------------------------------------------------------
# Ingest — one parse rule for the whole history
# ---------------------------------------------------------------------------

def fetch_county_year(year: int, *, refresh: bool = False) -> pd.DataFrame:
    """One county annual file -> [county_fips, total_units, mf_units,
    total_units_reported, mf_units_reported, year]. Imputed estimates are the
    totals; reported-only is kept for the coverage QC."""
    name = f"co{year}a.txt"
    cache = BPS_RAW_DIR / name
    if cache.exists() and not refresh:
        text = cache.read_text()
    else:
        resp = requests.get(f"{_BASE}/{name}", timeout=120)
        if resp.status_code != 200:
            raise RuntimeError(f"BPS download failed for {name} (status {resp.status_code}).")
        text = resp.text
        cache.write_text(text)

    # Two header rows + one blank line precede the data in every vintage.
    raw = pd.read_csv(io.StringIO(text), header=None, skiprows=3,
                      names=range(30), usecols=range(30),
                      engine="python", skipinitialspace=True)
    # Guard: keep only rows with numeric state+county codes (drops any stray
    # footer/blank lines in older vintages).
    st = pd.to_numeric(raw[_ID["state"]], errors="coerce")
    co = pd.to_numeric(raw[_ID["county"]], errors="coerce")
    ok = st.notna() & co.notna()
    raw, st, co = raw[ok], st[ok], co[ok]

    def units(cols: dict[str, int]) -> pd.DataFrame:
        return pd.DataFrame({k: pd.to_numeric(raw[c], errors="coerce")
                             for k, c in cols.items()}).fillna(0)

    imp, rep = units(_UNITS), units(_UNITS_REP)
    out = pd.DataFrame({
        "county_fips": st.astype(int).map("{:02d}".format)
                       + co.astype(int).map("{:03d}".format),
        "total_units": imp.sum(axis=1),
        "mf_units": imp["u5"],
        "total_units_reported": rep.sum(axis=1),
        "mf_units_reported": rep["u5"],
    })
    # Some vintages carry literal duplicate rows under county-name spelling
    # variants (e.g. 2014 "St. Mary's"/"St. Marys", identical values). Dedup is
    # safe ONLY when the values agree; anything else is a format change.
    if out["county_fips"].duplicated().any():
        nunique = out.groupby("county_fips").transform("nunique")
        if (nunique > 1).any().any():
            bad = out[(nunique > 1).any(axis=1)]["county_fips"].unique()[:5]
            raise RuntimeError(f"{name}: conflicting duplicate county rows "
                               f"(e.g. {list(bad)}) — format change?")
        out = out.drop_duplicates("county_fips")
    out["year"] = year
    return out


def build_metro_permit_panel(*, refresh: bool = False) -> pd.DataFrame:
    """County files -> metro-year panel on the fixed 2023 delineation.
    Returns [cbsa_code, cbsa_title, year, total_units, mf_units,
    total_units_reported, mf_units_reported]."""
    frames = []
    for yr in YEARS:
        county = fetch_county_year(yr, refresh=refresh)
        metro = crosswalk.aggregate_counties_to_cbsa(
            county, "county_fips",
            ["total_units", "mf_units", "total_units_reported", "mf_units_reported"],
            how="sum")
        metro["year"] = yr
        frames.append(metro)
    panel = pd.concat(frames, ignore_index=True)
    return (panel.sort_values(["cbsa_code", "year"]).reset_index(drop=True))


# ---------------------------------------------------------------------------
# The four frozen measures (spec 2026-08-16) — one code path, all metros
# ---------------------------------------------------------------------------

def _universe() -> pd.DataFrame:
    """The screener's metro universe + housing stock, from the frozen panel."""
    p = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    return p[["cbsa_code", "cbsa_title", "year", "housing_units"]]


def _winsorize_within_year(s: pd.Series, year: pd.Series) -> pd.Series:
    lo, hi = config.WINSOR_LIMITS
    grp = s.groupby(year)
    return s.clip(grp.transform(lambda g: g.quantile(lo)),
                  grp.transform(lambda g: g.quantile(hi)))


def build_momentum(permits: pd.DataFrame | None = None) -> pd.DataFrame:
    """Return the candidate measure table for the SCREENER UNIVERSE only:
    [cbsa_code, cbsa_title, year, <4 winsorized measures>, <4 *_raw columns>].

    Definitions (scoring year T, exact prior year, decision-log 2026-08-16):
      permit_momentum_total      total units T / T-1 - 1   (NaN if prior 0/missing)
      permit_momentum_total_rate total/stock at T minus at T-1 (pp of stock)
      permit_momentum_mf         5+ units  T / T-1 - 1     (NaN if prior 0/missing)
      permit_momentum_mf_rate    mf/stock at T minus at T-1
    All four winsorized within-year at config.WINSOR_LIMITS across the
    universe cross-section — the one global lumpiness guard.
    """
    if permits is None:
        permits = pd.read_csv(OUT_PANEL, dtype={"cbsa_code": str})
    uni = _universe()
    universe_codes = uni["cbsa_code"].unique()

    df = permits[permits["cbsa_code"].isin(universe_codes)].copy()
    df = df.merge(uni[["cbsa_code", "year", "housing_units"]],
                  on=["cbsa_code", "year"], how="left")

    prev = df[["cbsa_code", "year", "total_units", "mf_units", "housing_units"]].copy()
    prev["year"] += 1
    df = df.merge(prev, on=["cbsa_code", "year"], how="left", suffixes=("", "_prev"))

    def ratio_growth(cur: pd.Series, prv: pd.Series) -> pd.Series:
        return (cur / prv.where(prv > 0) - 1.0)

    out = df[["cbsa_code", "cbsa_title", "year"]].copy()
    out["permit_momentum_total_raw"] = ratio_growth(df["total_units"], df["total_units_prev"])
    out["permit_momentum_mf_raw"] = ratio_growth(df["mf_units"], df["mf_units_prev"])
    out["permit_momentum_total_rate_raw"] = (
        df["total_units"] / df["housing_units"]
        - df["total_units_prev"] / df["housing_units_prev"])
    out["permit_momentum_mf_rate_raw"] = (
        df["mf_units"] / df["housing_units"]
        - df["mf_units_prev"] / df["housing_units_prev"])

    for m in MEASURES:
        out[m] = _winsorize_within_year(out[f"{m}_raw"], out["year"])
    return out.sort_values(["cbsa_code", "year"]).reset_index(drop=True)


def build_qc(permits: pd.DataFrame) -> pd.DataFrame:
    """Reported-vs-imputed coverage per universe metro-year (report-only)."""
    uni_codes = _universe()["cbsa_code"].unique()
    qc = permits[permits["cbsa_code"].isin(uni_codes)].copy()
    qc["imputed_share_total"] = 1.0 - qc["total_units_reported"] / qc["total_units"].where(qc["total_units"] > 0)
    qc["flag_imputed_gt_25pct"] = qc["imputed_share_total"] > IMPUTED_SHARE_FLAG
    return qc


def cmd_build() -> None:
    print("V4-6 construction — county annual BPS 1990-2025 -> metro rollup -> momentum.\n")
    permits = build_metro_permit_panel()
    permits.to_csv(OUT_PANEL, index=False)
    print(f"  metro permit panel : {len(permits):,} metro-years, "
          f"{permits['cbsa_code'].nunique()} CBSAs, {permits['year'].min()}-{permits['year'].max()}")

    mom = build_momentum(permits)
    mom.to_csv(OUT_MOMENTUM, index=False)
    n_universe = mom["cbsa_code"].nunique()
    print(f"  momentum measures  : {len(mom):,} universe metro-years ({n_universe} metros)")

    print("\n  Coverage per measure (universe metros with a value, recent years):")
    for yr in range(2016, 2026):
        row = mom[mom["year"] == yr]
        cov = "  ".join(f"{m.split('permit_momentum_')[1]}:{row[m].notna().sum():>3}"
                        for m in MEASURES)
        print(f"    {yr}  {cov}  /{n_universe}")

    qc = build_qc(permits)
    qc.to_csv(OUT_QC, index=False)
    recent = qc[qc["year"] >= 2015]
    flagged = recent[recent["flag_imputed_gt_25pct"]]
    print(f"\n  QC (2015+): {len(flagged)} universe metro-years above "
          f"{IMPUTED_SHARE_FLAG:.0%} imputed share "
          f"({flagged['cbsa_code'].nunique()} metros) -> {OUT_QC.name}")
    if len(flagged):
        worst = (flagged.groupby("cbsa_title")["imputed_share_total"].max()
                 .sort_values(ascending=False).head(8))
        for title, share in worst.items():
            print(f"    {share:5.0%} max  {title}")
    print(f"\nWritten: {OUT_PANEL.name}, {OUT_MOMENTUM.name}, {OUT_QC.name} in data/processed/.")


# ---------------------------------------------------------------------------
# Reconciliation — scripted, full universe, no hand-picked metros
# ---------------------------------------------------------------------------

def _fred_key() -> str:
    from dotenv import load_dotenv
    load_dotenv(config.ROOT / ".env")
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FRED_API_KEY missing from .env")
    return key


def _fred_json(path: str, **params) -> dict:
    params = {**params, "api_key": _fred_key(), "file_type": "json"}
    r = requests.get(f"https://api.stlouisfed.org/fred/{path}", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _norm_key(title: str) -> tuple[str, str]:
    """(first principal city, first state) — robust to delineation-era renames
    like Austin-Round Rock vs Austin-Round Rock-San Marcos."""
    name, _, state = title.partition(",")
    city = name.split("-")[0].strip().lower()
    st = state.strip().split("-")[0].split()[0] if state.strip() else ""
    return city, st[:2]


def _fred_metro_permit_series() -> pd.DataFrame:
    """Every FRED metro total-units permit series (id ends 'BPPRIV'), from the
    BPS release, with a (city, state) match key."""
    rel = _fred_json("series/release", series_id="LOSA106BPPRIV")["releases"][0]["id"]
    rows, offset = [], 0
    while True:
        page = _fred_json("release/series", release_id=rel, limit=1000, offset=offset)
        rows += page["seriess"]
        offset += 1000
        if offset >= page["count"]:
            break
    df = pd.DataFrame(rows)
    df = df[df["id"].str.endswith("BPPRIV")]      # total units, monthly, NSA
    # Titles read "... for <Metro Name>, <ST> (MSA)"
    metro_name = (df["title"].str.extract(r"(?:for|in)\s+(.+?)\s*\(MSA\)")[0]
                  .fillna(""))
    df, metro_name = df[metro_name != ""].copy(), metro_name[metro_name != ""]
    df["match_key"] = [_norm_key(t) for t in metro_name]
    return df[["id", "title", "match_key"]]


def cmd_reconcile() -> None:
    print("V4-6 reconciliation — full universe, scripted.\n")
    permits = pd.read_csv(OUT_PANEL, dtype={"cbsa_code": str})
    uni = _universe()[["cbsa_code", "cbsa_title"]].drop_duplicates()

    # -- 1. Exact match vs the screener's existing permits input (same files,
    #       same fixed crosswalk -> any diff is a construction bug).
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    merged = (panel[["cbsa_code", "cbsa_title", "year", "permits_total", "permits_mf"]]
              .merge(permits, on=["cbsa_code", "year"], how="left", suffixes=("", "_v4")))
    have = merged.dropna(subset=["permits_total", "total_units"])
    d_tot = (have["permits_total"] - have["total_units"]).abs().max()
    d_mf = (have["permits_mf"] - have["mf_units"]).abs().max()
    print(f"  [1] vs screener panel 2015-2025 ({have['cbsa_code'].nunique()} metros, "
          f"{len(have)} metro-years): max |diff| total={d_tot:.0f}, mf={d_mf:.0f} "
          f"{'OK' if d_tot == 0 and d_mf == 0 else '** INVESTIGATE **'}")

    # -- 2. National total vs FRED PERMITNSA (thousands of units, monthly NSA).
    from src.ingest import fred
    nat_fred = (fred.to_annual(fred.fetch_series("PERMITNSA"), how="mean") * 12 * 1000)
    checks = []
    print("\n  [2] national county-file sum vs FRED PERMITNSA annual units:")
    for yr in (2015, 2019, 2023, 2024):
        ours = fetch_county_year(yr)["total_units"].sum()
        theirs = nat_fred.get(yr, float("nan"))
        pct = ours / theirs - 1
        print(f"      {yr}: counties {ours:>12,.0f}   FRED {theirs:>12,.0f}   "
              f"{pct:+.1%} {'OK' if abs(pct) <= 0.03 else '** INVESTIGATE **'}")

    # -- 3. FRED metro series (annual sums, recent years), every metro FRED covers.
    print("\n  [3] vs FRED metro permit series (2023, 2024 annual sums, tol 3%):")
    fred_series = _fred_metro_permit_series()
    uni = uni.copy()
    uni["match_key"] = [_norm_key(t) for t in uni["cbsa_title"]]
    m = uni.merge(fred_series, on="match_key", how="left")
    matched = m.dropna(subset=["id"]).drop_duplicates("cbsa_code")
    print(f"      FRED total-units series: {len(fred_series)}; "
          f"matched to universe: {len(matched)}/{len(uni)}")
    ours = permits.set_index(["cbsa_code", "year"])["total_units"]
    for _, r in matched.iterrows():
        try:
            s = fred.fetch_series(r["id"])
        except Exception as e:
            checks.append({"cbsa_code": r["cbsa_code"], "cbsa_title": r["cbsa_title"],
                           "fred_id": r["id"], "year": None, "note": f"fetch failed: {e}"})
            continue
        annual = s.groupby(s.index.year).sum()
        months = s.groupby(s.index.year).count()
        for yr in (2023, 2024):
            if months.get(yr, 0) != 12:
                continue
            v_ours = ours.get((r["cbsa_code"], yr), float("nan"))
            v_fred = annual.get(yr, float("nan"))
            checks.append({"cbsa_code": r["cbsa_code"], "cbsa_title": r["cbsa_title"],
                           "fred_id": r["id"], "year": yr, "ours": v_ours,
                           "fred": v_fred, "pct_diff": v_ours / v_fred - 1
                           if v_fred and v_fred == v_fred else float("nan"),
                           "note": ""})
    rec = pd.DataFrame(checks)
    rec.to_csv(OUT_RECONCILE, index=False)
    good = rec[rec["note"] == ""].dropna(subset=["pct_diff"])
    off = good[good["pct_diff"].abs() > 0.03]
    print(f"      comparisons: {len(good)}; within 3%: {len(good) - len(off)}; "
          f"outside: {len(off)}")
    if len(off):
        print("      outside tolerance (investigate each — usually delineation vintage):")
        for _, r in off.sort_values("pct_diff", key=lambda s: s.abs(),
                                    ascending=False).iterrows():
            print(f"        {r['pct_diff']:+7.1%}  {r['year']}  {r['cbsa_title'][:44]}  ({r['fred_id']})")
    unmatched = m[m["id"].isna()]
    if len(unmatched):
        print(f"      no FRED series matched ({len(unmatched)} metros — listed, not skipped silently):")
        print("        " + "; ".join(sorted(unmatched['cbsa_title'].str[:28])))
    print(f"\nWritten: {OUT_RECONCILE.name}.")


# ---------------------------------------------------------------------------
# Sanity — the three pre-committed cases (values only; no outcome data)
# ---------------------------------------------------------------------------

def cmd_sanity() -> None:
    print("V4-6 sanity cases (pre-committed in the 2026-08-16 spec; values only).\n")
    mom = pd.read_csv(OUT_MOMENTUM, dtype={"cbsa_code": str})
    panel = pd.read_parquet(config.PROCESSED_DIR / "panel.parquet")
    p2s = panel[["cbsa_code", "cbsa_title", "year", "permits_total", "housing_units"]].copy()
    p2s["permits_to_stock"] = p2s["permits_total"] / p2s["housing_units"]
    latest = int(mom.dropna(subset=["permit_momentum_total"])["year"].max())
    y = mom[mom["year"] == latest].dropna(subset=["permit_momentum_total"]).copy()
    y["pct_rank"] = y["permit_momentum_total"].rank(pct=True)
    # Level context from the latest year with a housing-stock denominator
    # (the panel's stock ends a year before the newest permits file).
    lv_year = int(p2s.dropna(subset=["permits_to_stock"])["year"].max())
    lv = p2s[p2s["year"] == lv_year].copy()
    lv["level_rank"] = lv["permits_to_stock"].rank(pct=True)

    def show(code: str, label: str) -> None:
        r = y[y["cbsa_code"] == code]
        l = lv[lv["cbsa_code"] == code]
        if r.empty:
            print(f"  {label}: NO ROW — investigate")
            return
        r, lval = r.iloc[0], (l.iloc[0] if len(l) else None)
        lvl = (f"level {lval['permits_to_stock']:.2%} of stock in {lv_year} "
               f"(pctile {lval['level_rank']:.0%})" if lval is not None else "level n/a")
        print(f"  {label:<28} momentum {r['permit_momentum_total']:+.1%} "
              f"(pctile {r['pct_rank']:.0%}), MF {r['permit_momentum_mf']:+.1%}; {lvl}")

    print(f"  -- cross-section {latest} --")
    show("12420", "(a) Austin")
    risers = y.nlargest(3, "permit_momentum_total")
    print("  (b) largest positive momentum (must exist):")
    for _, r in risers.iterrows():
        print(f"        {r['permit_momentum_total']:+.1%}  {r['cbsa_title'][:44]}")
    show("10580", "(c) Albany, NY")

    print("\n  Austin full recent path (momentum vs level):")
    aus = (mom[mom["cbsa_code"] == "12420"].merge(
        p2s[["cbsa_code", "year", "permits_to_stock"]], on=["cbsa_code", "year"], how="left"))
    for _, r in aus[aus["year"] >= 2019].iterrows():
        mt = r["permit_momentum_total"]
        stock = r["permits_to_stock"]
        m_txt = f"{mt:+7.1%}" if mt == mt else "    n/a"
        l_txt = f"{stock:.2%} of stock" if stock == stock else "n/a (no stock row)"
        print(f"    {int(r['year'])}  momentum {m_txt}   level {l_txt}")
    print("\nExpectations: (a) strongly negative with an elevated level, (b) positive"
          "\nexists, (c) flat/low momentum with a low level. Surprises -> debug +"
          "\namendment entry BEFORE any gate run.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    {"build": cmd_build, "reconcile": cmd_reconcile, "sanity": cmd_sanity}[cmd]()
