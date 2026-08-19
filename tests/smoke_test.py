"""
CI smoke test — config validates, the model scores, every site page renders.

Runs with the app-only requirements (no API keys, no network): the model
recomputes from the committed data/processed outputs, exactly like the
deployed site. Exits non-zero on any failure.

    python tests/smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

def main() -> None:
    # 1. Config invariants.
    config.validate_weights()
    assert len(config.INDICATORS) == 8, "expected the v2 de-duplicated 8-indicator model"
    assert config.NOWCAST_PUBLISHED is True, \
        ("NOWCAST_PUBLISHED must match the latest gate outcome (v0.4 PASS, "
         "decision-log 2026-07-08); it may only change via a new gate")
    print("config: OK")

    # 2. P0 data-QA regime (decision-log 2026-07-08): a QA report exists for
    #    exactly this panel build, every blocker is dispositioned, and the
    #    golden-metro values (the D1-D6-verified inputs) still hold.
    from src import data_qa
    ok, msg = data_qa.publication_gate()
    assert ok, f"data-QA publication gate: {msg}"
    golden = data_qa.golden_flags()
    bad = [f for f in golden if f["severity"] == "BLOCKER"]
    assert not bad, f"golden-metro regression: {len(bad)} value(s) changed, e.g. {bad[0]['detail']}"
    print(f"data QA: OK ({msg}; golden metros hold)")

    # 3. The scoring pipeline reproduces a full ranking from committed data.
    from src import score as score_mod
    scored = score_mod.score()
    latest = scored[scored["year"] == score_mod.SCORE_YEAR]
    assert latest["cbsa_code"].nunique() == 110, f"expected 110 metros, got {latest['cbsa_code'].nunique()}"
    assert latest["rank"].min() == 1 and latest["rank"].max() == 110
    print(f"scoring: OK (110 metros ranked for {score_mod.SCORE_YEAR})")

    # 3b. A-11 QA gates: copy consistency, canonical figures, rank-vs-range,
    #     spelling. All rendered copy in both artifacts must comply.
    sys.path.insert(0, str(ROOT / "tests"))
    sys.path.insert(0, str(ROOT / "app"))
    import copy_qa
    from ui import data as site_data
    problems = copy_qa.consistency_violations()
    assert not problems, "copy consistency:\n  " + "\n  ".join(problems)
    print(f"copy consistency: OK ({len(copy_qa.COPY_FILES)} modules)")

    d = site_data.load()
    ed = site_data.edition(d)
    problems = copy_qa.canonical_figure_mismatches(
        ed["rank"], d["backtest"], config.PROCESSED_DIR, config.INDICATORS)
    assert not problems, "canonical figures:\n  " + "\n  ".join(problems)
    print("canonical figures: OK (YAML matches recomputed outputs + both artifacts)")

    problems = copy_qa.rank_range_violations(ed["rank"])
    assert not problems, "rank vs range:\n  " + "\n  ".join(problems)
    print("rank vs range: OK (every outlier allowlisted with a reason)")

    problems = copy_qa.stray_hex_violations() + copy_qa.config_toml_mismatches()
    assert not problems, "design tokens:\n  " + "\n  ".join(problems)
    print("design tokens: OK (no hex outside theme/tokens.json; config.toml in sync)")

    spelling = copy_qa.spelling_violations()
    if spelling is None:
        print("spelling: SKIPPED (pyspellchecker not installed; "
              "pip install -r requirements-dev.txt)")
    else:
        assert not spelling, "spelling:\n  " + "\n  ".join(spelling)
        print("spelling: OK")

    # 4. Every site page renders without exception.
    from streamlit.testing.v1 import AppTest
    views = ["home", "rankings", "metro", "how_it_works", "outlook_2026",
             "track_record"]
    for view in views:
        at = AppTest.from_file(str(ROOT / "app" / "views" / f"{view}.py"),
                               default_timeout=180)
        at.run()
        assert not at.exception, f"{view}: {at.exception[0].value}"
        print(f"page {view}: OK")

    # 5. The router boots.
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"router: {at.exception[0].value}"
    print("router: OK")
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
