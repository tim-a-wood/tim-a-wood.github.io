"""Unit tests for Agent OS / workbench dashboard helpers."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.workbench_local_control import _usage_ledger_json_path, keys_from_env


class KeysFromEnvTests(unittest.TestCase):
    def test_openai_key_set_when_present(self):
        env = {
            "PIXELLAB_API_KEY": "",
            "GEMINI_API_KEY": "x",
            "OPENAI_API_KEY": "sk-test",
            "RESEND_API_KEY": "",
        }
        keys = keys_from_env(env)
        self.assertTrue(keys["openai_key_set"])
        self.assertTrue(keys["gemini_key_set"])
        self.assertFalse(keys["pixellab_key_set"])

    def test_openai_key_set_false_when_blank(self):
        env = {"OPENAI_API_KEY": "   "}
        keys = keys_from_env(env)
        self.assertFalse(keys["openai_key_set"])


class UsageLedgerPathTests(unittest.TestCase):
    def test_prefers_canonical_sprite_workbench_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            can = root / "tools" / "2d-sprite-and-animation" / "projects-data"
            can.mkdir(parents=True)
            (can / "_usage_ledger.json").write_text(json.dumps({"entries": []}), encoding="utf-8")
            leg = root / "projects-data"
            leg.mkdir(parents=True)
            (leg / "_usage_ledger.json").write_text(json.dumps({"entries": [{"id": "legacy"}]}), encoding="utf-8")
            p = _usage_ledger_json_path(root)
            self.assertEqual(p, can / "_usage_ledger.json")

    def test_falls_back_to_legacy_when_canonical_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            leg = root / "projects-data"
            leg.mkdir(parents=True)
            target = leg / "_usage_ledger.json"
            target.write_text(json.dumps({"entries": []}), encoding="utf-8")
            self.assertEqual(_usage_ledger_json_path(root), target)

    def test_default_returns_canonical_when_no_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "tools" / "2d-sprite-and-animation" / "projects-data" / "_usage_ledger.json"
            self.assertEqual(_usage_ledger_json_path(root), expected)


if __name__ == "__main__":
    unittest.main()
