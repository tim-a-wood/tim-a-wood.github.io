#!/usr/bin/env python3
"""Coverage for standalone bootstrap docs/templates."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bootstrap_agent_os_repo import main as bootstrap_main


class BootstrapAgentOsRepoTests(unittest.TestCase):
    def test_bootstrap_writes_standalone_docs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "agent-os"
            old = sys.argv[:]
            try:
                sys.argv = ["bootstrap_agent_os_repo.py", str(dest)]
                rc = bootstrap_main()
            finally:
                sys.argv = old
            self.assertEqual(rc, 0)
            self.assertTrue((dest / "README.md").is_file())
            self.assertTrue((dest / "AGENTS.md").is_file())
            self.assertTrue((dest / "CLAUDE.md").is_file())
            self.assertTrue((dest / ".gitignore").is_file())


if __name__ == "__main__":
    unittest.main()
