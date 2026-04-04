#!/usr/bin/env python3
"""Regression tests for scripts/extract_sprite_workbench_arch.py."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "extract_sprite_workbench_arch.py"
MANIFEST_PATH = REPO / "artifacts" / "sprite-workbench-arch" / "manifest.json"


class ExtractSpriteWorkbenchArchTests(unittest.TestCase):
    def test_script_runs_zero_exit(self) -> None:
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--check-stdout"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data.get("schema_version"), "0.2")
        self.assertIn("extract_sprite_workbench_arch", data.get("extractor_versions", {}))
        nodes = data["nodes"]
        edges = data["edges"]
        self.assertGreaterEqual(len(nodes), 38, "expect ~20 JS + ~20 Python")
        js = [n for n in nodes if n["kind"] == "browser_js"]
        py = [n for n in nodes if n["kind"] == "python"]
        self.assertGreaterEqual(len(js), 18)
        self.assertGreaterEqual(len(py), 18)
        for n in nodes[:3]:
            self.assertIn("exports", n)
            self.assertIn("exports_kind", n)
            self.assertIn("churn_30d", n)
        kinds = {e["kind"] for e in edges}
        self.assertIn("html_script_order", kinds)
        self.assertIn("python_import", kinds)
        html_edges = [e for e in edges if e["kind"] == "html_script_order"]
        self.assertEqual(len(html_edges), len(js) - 1)
        ids = {n["id"] for n in nodes}
        for e in edges:
            self.assertIn(e["source"], ids, e)
            self.assertIn(e["target"], ids, e)

    def test_committed_manifest_parseable(self) -> None:
        if not MANIFEST_PATH.is_file():
            self.skipTest("manifest not present")
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertTrue(data.get("nodes"))
        self.assertIsInstance(data["edges"], list)


if __name__ == "__main__":
    unittest.main()
