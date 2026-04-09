#!/usr/bin/env python3
"""Tests for scripts/archive_policy_document.py"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class ArchivePolicyDocumentTests(unittest.TestCase):
    def test_rejects_invalid_and_blocks_readme(self) -> None:
        from scripts.archive_policy_document import archive_policy_document, is_archivable

        ok, err = is_archivable("../etc/passwd")
        self.assertFalse(ok)
        ok2, _ = is_archivable("README.md")
        self.assertFalse(ok2)
        r = archive_policy_document(REPO, "README.md")
        self.assertFalse(r.get("ok"))

    def test_archive_moves_file_in_temp_repo(self) -> None:
        from scripts.archive_policy_document import ARCHIVE_DIR, archive_policy_document

        tmp = Path(__file__).resolve().parent / "_tmp_archive_policy_test_repo"
        if tmp.exists():
            import shutil

            shutil.rmtree(tmp)
        tmp.mkdir()
        try:
            docs = tmp / "docs"
            docs.mkdir()
            pol = docs / "z-test-archive-policy-only.md"
            pol.write_text("# Test policy\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test"],
                cwd=tmp,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "test"],
                cwd=tmp,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "add", "-A"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"],
                cwd=tmp,
                check=True,
                capture_output=True,
            )

            out = archive_policy_document(tmp, "docs/z-test-archive-policy-only.md", reason="unit test")
            self.assertTrue(out.get("ok"), msg=out.get("error"))
            self.assertFalse(pol.is_file())
            arch_root = tmp / ARCHIVE_DIR
            self.assertTrue(arch_root.is_dir())
            self.assertTrue((arch_root / "manifest.json").is_file())
            moved = list(arch_root.glob("*__docs__z-test-archive-policy-only.md"))
            self.assertEqual(len(moved), 1)
            reports = list(arch_root.glob("*__references.txt"))
            self.assertGreaterEqual(len(reports), 1)
        finally:
            import shutil

            if tmp.exists():
                shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
