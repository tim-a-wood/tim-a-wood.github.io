#!/usr/bin/env python3
"""Unit coverage for Agent OS split smoke helper validation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_agent_os_split_smoke import _validate_payload


class CheckAgentOsSplitSmokeTests(unittest.TestCase):
    def test_validate_payload_accepts_expected_shape(self) -> None:
        payload = {
            "supervisor": True,
            "workbench_server_running": False,
            "workbench_port": 8766,
            "workbench_host": "127.0.0.1",
            "usage_charts": {},
            "usage_summary": {},
            "home_internal": {"release_gate_label": "Green"},
        }
        _validate_payload(payload, 8766)

    def test_validate_payload_rejects_missing_keys(self) -> None:
        with self.assertRaises(RuntimeError):
            _validate_payload({"supervisor": True}, 8766)


if __name__ == "__main__":
    unittest.main()
