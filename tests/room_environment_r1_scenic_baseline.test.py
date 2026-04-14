#!/usr/bin/env python3
"""Validate the R1 room-environment scenic baseline fixture (§228). CI-safe — no PNG reads."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "room_environment_r1_scenic_baseline.json"


class RoomEnvironmentR1ScenicBaselineTests(unittest.TestCase):
    def test_fixture_contract_and_paths(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(data.get("contract"), "room_environment_r1_scenic_shell")
        self.assertIn("locked_at", data)
        self.assertIsInstance(data.get("decisions"), list)
        self.assertIn("226", data["decisions"])
        self.assertIn("227", data["decisions"])
        self.assertIn("228", data["decisions"])

        proj = data.get("project") or {}
        self.assertEqual(proj.get("project_id"), "room-ai-helpfulness-qa-67562113")
        self.assertEqual(proj.get("room_id"), "R1")

        pipe = data.get("pipeline_contract") or {}
        self.assertEqual(pipe.get("background_far_plate_gemini_references"), "guide_only")

        arts = data.get("canonical_artifacts_relative") or {}
        for key in (
            "runtime_review_png",
            "background_bespoke_png",
            "unified_shell_png",
            "midground_png",
        ):
            self.assertIn(key, arts)
            rel = arts[key]
            self.assertIsInstance(rel, str)
            self.assertTrue(rel.startswith("tools/2d-sprite-and-animation/projects-data/"))
            self.assertIn("R1", rel)


if __name__ == "__main__":
    unittest.main()
