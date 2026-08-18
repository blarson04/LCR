"""
copy_qa.py: A-11 QA gates over all rendered copy (site + report).

Four checks, called from the smoke test:

  1. consistency_violations()  - forbidden phrases in any copy string
     (em dashes, "forecast" outside the permitted patterns, the deprecated
     shock label, stale failure count, the semicolon disclaimer)
  2. canonical_figure_mismatches() - the canonical-figures YAML vs values
     recomputed from the committed model outputs, plus gate-record strings
     that must appear verbatim in BOTH artifacts
  3. rank_range_violations()   - markets whose point rank falls outside
     their own 90% range must be allowlisted with a reason
  4. spelling_violations()     - en_US spellcheck over copy strings with a
     project allowlist (skips cleanly if pyspellchecker is not installed;
     CI installs it via requirements-dev.txt)

Copy strings are the non-docstring string literals (including f-string
constant parts) of the modules that render user-facing text. HTML tags and
format specs are stripped before word checks.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

# Every module whose string literals become user-facing copy.
COPY_FILES = sorted(
    list((ROOT / "app" / "views").glob("*.py"))
    + [ROOT / "app" / "streamlit_app.py",
       ROOT / "app" / "ui" / "data.py",
       ROOT / "app" / "ui" / "diagrams.py",
       ROOT / "app" / "ui" / "theme.py",
       ROOT / "report" / "build_pdf.py",
       ROOT / "report" / "build_methodology_paper.py"])

# "forecast" is permitted ONLY in these patterns (house rule 1):
FORECAST_ALLOWED = [
    re.compile(r"Validated .{0,20}forecast · "),  # the edition badge family
    re.compile(r"screen, not a forecast"),        # the standing line
    re.compile(r"not forecasts?\b"),              # explicit negation
    re.compile(r"does not\s+forecast"),
    re.compile(r"\(a 2024[–-]2027 forecast\)"),   # gate record, grandfathered
    re.compile(r"current 2025[–-]2028 forecast"), # gate record, grandfathered
]

FORBIDDEN = [
    ("em dash (house separator is ' · ')", re.compile(r"—")),
    ("deprecated shock label (canonical: 'the 2020–22 shock')",
     re.compile(r"2021[–-]22 shock")),
    ("stale failure count (three configurations failed)",
     re.compile(r"two configurations failed")),
    ("semicolon disclaimer (use 'A research screen, not investment advice.')",
     re.compile(r"; not investment advice")),
]

_TAG = re.compile(r"<[^>]*>")
_FMT = re.compile(r"\{[^{}]*\}")


def _copy_strings(path: Path):
    """Yield (lineno, text) for non-docstring string literals in a module.

    F-strings are yielded as one joined text with "{}" placeholders so that
    phrase patterns (the badge label, allowed-forecast contexts) can match
    across their constant parts.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    in_fstring = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                    in_fstring.add(id(v))
                else:
                    parts.append("{}")
            yield node.lineno, "".join(parts)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings and id(node) not in in_fstring:
            yield node.lineno, node.value


def _visible(text: str) -> str:
    """Strip HTML tags and format-spec placeholders from a copy string."""
    return _FMT.sub(" ", _TAG.sub(" ", text))


def _flat_yaml(path: Path) -> dict[str, str]:
    """Parse a flat 'key: value  # comment' YAML without a YAML dependency."""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, val = line.partition(":")
        # strip trailing comments only when preceded by whitespace, so values
        # containing '#' (none today) would survive
        val = re.split(r"\s+#", val.strip())[0].strip()
        out[key.strip()] = val
    return out


# ---- 1. consistency greps ---------------------------------------------------

def consistency_violations() -> list[str]:
    problems = []
    for path in COPY_FILES:
        rel = path.relative_to(ROOT)
        for lineno, text in _copy_strings(path):
            for label, rx in FORBIDDEN:
                if rx.search(text):
                    problems.append(f"{rel}:{lineno}: {label}: {text[:80]!r}")
            for m in re.finditer(r"forecast", text, re.IGNORECASE):
                ctx = text[max(0, m.start() - 60):m.end() + 40]
                if not any(rx.search(ctx) for rx in FORECAST_ALLOWED):
                    problems.append(
                        f"{rel}:{lineno}: 'forecast' outside permitted patterns: "
                        f"{ctx.strip()!r}")
    return problems


# ---- 2. canonical figures ---------------------------------------------------

def canonical_figure_mismatches(scored_latest, backtest, processed_dir,
                                indicators) -> list[str]:
    """Recompute each canonical figure from the committed outputs and compare.

    scored_latest: the current edition's ranked frame (with tier columns).
    backtest: the backtest summary frame. processed_dir: config.PROCESSED_DIR.
    indicators: config.INDICATORS.
    """
    import pandas as pd

    want = _flat_yaml(TESTS / "canonical_figures.yaml")
    got: dict[str, float] = {}

    p3 = backtest[(backtest.horizon == 3) & (backtest.regime == "POOLED")]
    got["pooled_tau_3y"] = round(float(p3["mean_tau"].iloc[0]), 2)
    pc = backtest[(backtest.horizon == 3) & (backtest.regime == "pre_covid")]
    got["precovid_p10_3y"] = round(float(pc["mean_precision@10"].iloc[0]), 2)

    ew = pd.read_csv(processed_dir / "effect_size_windows.csv")
    got["top10_edge_pp"] = round(float(
        ew[ew.strategy == "Composite (model)"]["top10_pp_vs_median"].mean()), 1)
    got["momentum_edge_pp"] = round(float(
        ew[ew.strategy == "Momentum (trailing rent)"]["top10_pp_vs_median"].mean()), 1)

    got["n_markets"] = int(scored_latest["cbsa_code"].nunique())
    if "tier" in scored_latest.columns:
        got["n_leading_cluster"] = int(
            (scored_latest["tier"] == "Leading cluster").sum())
        got["n_top10_in_cluster"] = int(
            (scored_latest.sort_values("rank").head(10)["tier"]
             == "Leading cluster").sum())

    g26 = pd.read_csv(processed_dir / "nowcast" / "gate2026_summary.csv").iloc[0]
    got["gate_retention_bar"] = float(g26["retention_bar"])
    got["gate_overlap_bar"] = int(g26["overlap_bar"])
    got["gate5_retention"] = round(float(g26["retention"]), 3)
    got["gate5_overlap"] = round(float(g26["mean_top10_overlap"]), 1)

    buckets: dict[str, float] = {}
    for spec in indicators.values():
        buckets[spec["bucket"]] = buckets.get(spec["bucket"], 0.0) + spec["weight"]
    for b, key in [("Demand", "weight_demand"), ("Supply", "weight_supply"),
                   ("Affordability", "weight_affordability"),
                   ("Momentum", "weight_momentum"),
                   ("Resilience", "weight_resilience")]:
        got[key] = round(buckets.get(b, 0.0) * 100)

    problems = []
    for key, val in want.items():
        if key.startswith("copy_"):
            continue
        if key not in got:
            problems.append(f"canonical figure {key!r}: no computed value")
            continue
        if abs(float(got[key]) - float(val)) > 1e-9:
            problems.append(f"canonical figure {key!r}: YAML says {val}, "
                            f"computed {got[key]}")

    # Gate-record figures: no machine source; asserted verbatim in the
    # artifacts that carry them. "copy_" keys must appear in BOTH the site's
    # copy and the report builder's; "copy_report_" keys in the report only
    # (the gate arc left the site's Track record page by author override,
    # decision-log 2026-08-18 — the report and decision log are the record's
    # load-bearing surfaces and these assertions keep them so).
    site_files = [p for p in COPY_FILES if "app" in p.parts]
    report_files = [p for p in COPY_FILES if "report" in p.parts]
    for key, val in want.items():
        if not key.startswith("copy_"):
            continue
        needle = val.rstrip("%")
        targets = ([("report", report_files)] if key.startswith("copy_report_")
                   else [("site", site_files), ("report", report_files)])
        for label, files in targets:
            if not any(needle in text for f in files
                       for _, text in _copy_strings(f)):
                problems.append(f"canonical figure {key!r} ({val}) missing "
                                f"from {label} copy")
    return problems


# ---- 3. rank vs range -------------------------------------------------------

def rank_range_violations(scored_latest) -> list[str]:
    import pandas as pd

    if "rank_lo" not in scored_latest.columns:
        return []
    allow = _flat_yaml(TESTS / "rank_range_allowlist.yaml")
    problems = []
    for _, r in scored_latest.iterrows():
        if pd.isna(r.get("rank_lo")):
            continue
        rank, lo, hi = int(r["rank"]), int(r["rank_lo"]), int(r["rank_hi"])
        if lo <= rank <= hi:
            continue
        code = str(r["cbsa_code"])
        if code not in allow:
            problems.append(
                f"{r['cbsa_title']} ({code}): rank {rank} outside its own 90% "
                f"range {lo}-{hi} and not allowlisted in "
                f"tests/rank_range_allowlist.yaml (add an entry with a reason "
                f"if intentional)")
    return problems


# ---- 3b. stray hex + config.toml drift (B-6) --------------------------------

_HEX = re.compile(r"#[0-9A-Fa-f]{3}\b|#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{8}\b")


def stray_hex_violations() -> list[str]:
    """No hex color anywhere in .py under app/, report/, or theme/ — every
    color flows from theme/tokens.json."""
    problems = []
    files = (list((ROOT / "app").rglob("*.py"))
             + list((ROOT / "report").glob("*.py"))
             + list((ROOT / "theme").glob("*.py")))
    for path in files:
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT)
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _HEX.search(line):
                problems.append(f"{rel}:{i}: hex color outside theme/tokens.json: "
                                f"{line.strip()[:80]}")
    return problems


def config_toml_mismatches() -> list[str]:
    """.streamlit/config.toml must mirror the tokens light palette."""
    import json
    tokens = json.loads((ROOT / "theme" / "tokens.json").read_text(encoding="utf-8"))
    light = tokens["light"]
    want = {"primaryColor": light["pine"], "backgroundColor": light["paper"],
            "secondaryBackgroundColor": light["surface"],
            "textColor": light["ink"]}
    text = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    problems = []
    for key, val in want.items():
        m = re.search(rf'{key}\s*=\s*"([^"]+)"', text)
        if not m:
            problems.append(f".streamlit/config.toml: {key} missing")
        elif m.group(1).lower() != val.lower():
            problems.append(f".streamlit/config.toml: {key} is {m.group(1)}, "
                            f"tokens.json says {val}")
    return problems


# ---- 4. spellcheck ----------------------------------------------------------

_WORD = re.compile(r"[A-Za-z][A-Za-z']{3,}")
# Strings that are code, CSS, or markup config rather than prose:
_NOT_PROSE = ("<style", "@import", "testid", "hovertemplate", "%{", "==",
              "font-variant", "rgba(", "px;")


def _is_prose(text: str) -> bool:
    if " " not in text.strip():
        return False               # identifiers, column names, keys
    return not any(m in text for m in _NOT_PROSE)


def spelling_violations() -> list[str] | None:
    """None means the spellchecker isn't installed (CI installs it)."""
    try:
        from spellchecker import SpellChecker
    except ImportError:
        return None
    checker = SpellChecker(language="en")
    allow_path = TESTS / "spelling_allowlist.txt"
    allow = set()
    if allow_path.exists():
        allow = {w.strip().lower() for w in
                 allow_path.read_text(encoding="utf-8").splitlines()
                 if w.strip() and not w.startswith("#")}
    problems = []
    for path in COPY_FILES:
        rel = path.relative_to(ROOT)
        for lineno, text in _copy_strings(path):
            if not _is_prose(text):
                continue
            words = {w.lower().split("'")[0] for w in
                     _WORD.findall(_visible(text))}
            words = {w for w in words if len(w) >= 4}
            unknown = {w for w in checker.unknown(words) if w not in allow}
            for w in sorted(unknown):
                problems.append(f"{rel}:{lineno}: unknown word {w!r}")
    return sorted(set(problems))


if __name__ == "__main__":
    for p in consistency_violations():
        print("CONSISTENCY:", p)
    sp = spelling_violations()
    for p in (sp or []):
        print("SPELLING:", p)
    if sp is None:
        print("(spellchecker not installed; spelling pass skipped)")
