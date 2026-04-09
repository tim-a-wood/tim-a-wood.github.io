#!/usr/bin/env python3
"""Unit coverage for Agent OS parity helpers."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.compare_agent_os_parity import _aggregate_my_actions, _normalize_dashboard_payload


class CompareAgentOsParityTests(unittest.TestCase):
    def test_normalize_dashboard_payload_keeps_core_keys(self) -> None:
        raw = {
            "supervisor": True,
            "workbench_server_running": False,
            "workbench_port": 8766,
            "workbench_host": "127.0.0.1",
            "usage_charts": {"a": 1},
            "usage_summary": {"b": 2},
            "home_internal": {"release_gate_label": "Green", "tests_passing": 3},
            "ignored": "x",
        }
        out = _normalize_dashboard_payload(raw)
        self.assertEqual(out["supervisor"], True)
        self.assertEqual(out["home_internal"]["release_gate_label"], "Green")
        self.assertNotIn("ignored", out)

    def test_aggregate_my_actions_counts(self) -> None:
        statuses = {
            "engineering-status.json": {
                "founder_decisions": [{"title": "Decide", "blocking": False}],
                "priorities": [{"id": 1, "title": "Review", "status": "needs-review"}],
            },
            "orchestration-status.json": {
                "founder_decisions": [{"title": "Block", "blocking": True}],
            },
        }
        self.assertEqual(_aggregate_my_actions(statuses), {"blocking": 1, "decision": 1, "review": 1})


if __name__ == "__main__":
    unittest.main()
