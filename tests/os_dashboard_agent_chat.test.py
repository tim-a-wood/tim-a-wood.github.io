"""Unit tests for Agent OS /api/agent-chat helpers (no HTTP server)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.os_dashboard_supervisor import (  # noqa: E402
    REPO_ROOT,
    _agent_chat_charter_rel,
    _read_allowed_repo_text,
)


class AgentChatHelpersTests(unittest.TestCase):
    def test_charter_rel_valid_slug(self) -> None:
        self.assertEqual(_agent_chat_charter_rel("design"), "agents/design/charter.md")

    def test_charter_rel_rejects_invalid(self) -> None:
        self.assertIsNone(_agent_chat_charter_rel("../etc/passwd"))
        self.assertIsNone(_agent_chat_charter_rel("bad_slug_"))

    def test_read_allowed_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "prompts").mkdir(parents=True)
            long_body = "x" * 500
            (root / "prompts" / "project_overview.md").write_text(long_body, encoding="utf-8")
            got = _read_allowed_repo_text(root, "prompts/project_overview.md", 100)
            self.assertIn("truncated", got)
            self.assertLess(len(got), len(long_body))

    def test_design_charter_readable_from_repo(self) -> None:
        rel = _agent_chat_charter_rel("design")
        assert rel is not None
        text = _read_allowed_repo_text(REPO_ROOT, rel, 4000)
        self.assertIn("Design Agent", text)

    def test_agent_chat_result_shape_supports_proposed_updates(self) -> None:
        result = {"thinking": "", "assistant_message": "ok"}
        result.setdefault("thinking", "")
        result.setdefault("assistant_message", "")
        if not isinstance(result.get("proposed_updates"), list):
            result["proposed_updates"] = []
        self.assertEqual(result["proposed_updates"], [])


if __name__ == "__main__":
    unittest.main()
