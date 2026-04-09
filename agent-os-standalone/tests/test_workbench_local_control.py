"""Unit tests for Agent OS / workbench dashboard helpers."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.workbench_local_control import (
    APP_ROOT,
    _usage_ledger_json_path,
    keys_from_env,
    merged_usage_ledger_entries,
    run_pull_openai_personal_usage_cache,
)
from scripts import workbench_local_control as wlc


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


class RunPullOpenaiPersonalUsageTests(unittest.TestCase):
    def test_returns_ok_from_subprocess_exit_code(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            script = root / "scripts" / "pull_openai_organization_costs_cache.py"
            script.parent.mkdir(parents=True)
            script.write_text("# placeholder\n", encoding="utf-8")
            fake = mock.Mock()
            fake.returncode = 0
            fake.stdout = "ok\n"
            fake.stderr = ""
            with mock.patch("scripts.workbench_local_control.subprocess.run", return_value=fake) as pr:
                r = run_pull_openai_personal_usage_cache(repo_root=root, days=7)
            self.assertTrue(r["ok"])
            self.assertEqual(r["exit_code"], 0)
            pr.assert_called_once()
            args, kwargs = pr.call_args
            self.assertEqual(kwargs["cwd"], str(APP_ROOT))
            cmd = args[0]
            self.assertIn("--days", cmd)
            self.assertIn("7", cmd)


class WorkspaceRootTests(unittest.TestCase):
    def test_latest_daily_report_uses_workspace_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            art = root / "artifacts"
            art.mkdir(parents=True)
            (art / "daily-report-2026-04-08.md").write_text("ok\n", encoding="utf-8")
            original = wlc.WORKSPACE_ROOT
            try:
                wlc.WORKSPACE_ROOT = root
                self.assertEqual(wlc.latest_daily_report_name(), "daily-report-2026-04-08.md")
            finally:
                wlc.WORKSPACE_ROOT = original


class MergedUsageLedgerTests(unittest.TestCase):
    def test_merges_personal_cache_entries(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            can = root / "tools" / "2d-sprite-and-animation" / "projects-data"
            can.mkdir(parents=True)
            (can / "_usage_ledger.json").write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "created_at": "2026-01-01T00:00:00.000Z",
                                "provider": "gemini",
                                "usage_cost_usd": 0.01,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (can / "_personal_api_usage_cache.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": [
                            {
                                "created_at": "2026-01-02T00:00:00.000Z",
                                "provider": "openai",
                                "usage_cost_usd": 1.5,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            merged = merged_usage_ledger_entries(root)
            self.assertEqual(len(merged), 2)
            providers = {m.get("provider") for m in merged}
            self.assertEqual(providers, {"gemini", "openai"})


if __name__ == "__main__":
    unittest.main()
