#!/usr/bin/env python3
"""Validate the phase-1 Agent OS split manifest."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_os_split_manifest import PHASE1_COPY_PATHS, PHASE1_EXCLUDE_PREFIXES


def _resolve_manifest_path(rel: str) -> Path:
    """After reorg, phase-1 files may live under ``agent-os/`` instead of the orchestrator root."""
    direct = ROOT / rel
    if direct.exists():
        return direct
    nested = ROOT / "agent-os" / rel
    if nested.exists():
        return nested
    return direct


class AgentOsSplitManifestTests(unittest.TestCase):
    def test_manifest_paths_exist(self) -> None:
        for rel in PHASE1_COPY_PATHS:
            path = _resolve_manifest_path(rel)
            self.assertTrue(path.exists(), f"Missing manifest path: {rel}")

    def test_manifest_does_not_include_mv_source_of_truth_prefixes(self) -> None:
        for rel in PHASE1_COPY_PATHS:
            for prefix in PHASE1_EXCLUDE_PREFIXES:
                self.assertFalse(rel.startswith(prefix), f"{rel} must stay in MV, not bootstrap manifest")


if __name__ == "__main__":
    unittest.main()
