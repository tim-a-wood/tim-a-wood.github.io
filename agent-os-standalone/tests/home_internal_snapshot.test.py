#!/usr/bin/env python3
"""Assert home_internal snapshot shape from repo status files (run: python3 tests/home_internal_snapshot.test.py)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import workbench_local_control as wlc
from scripts.workbench_local_control import build_home_internal_snapshot


def main() -> int:
    s = build_home_internal_snapshot()
    required = (
        "blocking_issue_count",
        "serious_issue_count",
        "founder_decisions_open",
        "priorities_in_progress",
        "tests_passing",
        "tests_failing",
        "broken_test_collections",
        "release_gate_label",
    )
    for k in required:
        assert k in s, f"missing key {k!r}"

    assert isinstance(s["blocking_issue_count"], int)
    assert isinstance(s["serious_issue_count"], int)
    assert isinstance(s["founder_decisions_open"], int)
    assert isinstance(s["priorities_in_progress"], int)
    assert isinstance(s["tests_passing"], int)
    assert isinstance(s["tests_failing"], int)
    assert isinstance(s["broken_test_collections"], int)
    assert isinstance(s["release_gate_label"], str)
    assert s["tests_passing"] >= 0
    assert s["tests_failing"] >= 0

    tr = s.get("test_last_run")
    assert tr is None or isinstance(tr, str)
    su = s.get("status_updated")
    assert su is None or isinstance(su, str)

    print("home_internal_snapshot.test: ok")
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "orchestration-status.json").write_text(
            '{"updated":"2026-04-08","priorities":[],"actions":[],"risks_p0":[],"risks_p1":[],"founder_decisions":[]}',
            encoding="utf-8",
        )
        (root / "qa-status.json").write_text(
            '{"updated":"2026-04-08","priorities":[],"actions":[],"founder_decisions":[],"bugs":{"p0":0},"test_suite":{"js_pass":1,"js_fail":0,"py_pass":2,"py_fail":0},"release_gate":{"label":"Green"},"metrics":{"broken_test_files":0}}',
            encoding="utf-8",
        )
        original = wlc.WORKSPACE_ROOT
        try:
            wlc.WORKSPACE_ROOT = root
            snap = build_home_internal_snapshot()
            assert snap["tests_passing"] == 3
            assert snap["release_gate_label"] == "Green"
        finally:
            wlc.WORKSPACE_ROOT = original
    print("home_internal_snapshot.workspace_override: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
