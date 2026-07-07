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
    assert config.NOWCAST_PUBLISHED is False, \
        "NOWCAST_PUBLISHED may only flip via a passed pre-registered gate"
    print("config: OK")

    # 2. The scoring pipeline reproduces a full ranking from committed data.
    from src import score as score_mod
    scored = score_mod.score()
    latest = scored[scored["year"] == score_mod.SCORE_YEAR]
    assert latest["cbsa_code"].nunique() == 110, f"expected 110 metros, got {latest['cbsa_code'].nunique()}"
    assert latest["rank"].min() == 1 and latest["rank"].max() == 110
    print(f"scoring: OK (110 metros ranked for {score_mod.SCORE_YEAR})")

    # 3. Every site page renders without exception, in both themes.
    from streamlit.testing.v1 import AppTest
    views = ["rankings", "metro_detail", "compare", "track_record", "methodology"]
    for view in views:
        for mode in ("Light", "Dark"):
            at = AppTest.from_file(str(ROOT / "app" / "views" / f"{view}.py"),
                                   default_timeout=180)
            at.session_state["ui_mode"] = mode
            at.run()
            assert not at.exception, f"{view} [{mode}]: {at.exception[0].value}"
        print(f"page {view}: OK")

    # 4. The router boots.
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=180)
    at.run()
    assert not at.exception, f"router: {at.exception[0].value}"
    print("router: OK")
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
