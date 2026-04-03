#!/usr/bin/env python3
"""Validate docs/os-documentLibrary.manifest.json paths and shape."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
MANIFEST = REPO / "docs" / "os-documentLibrary.manifest.json"


class OsDocumentLibraryTests(unittest.TestCase):
    def test_manifest_exists_and_schema(self) -> None:
        self.assertTrue(MANIFEST.is_file(), f"Missing {MANIFEST} — run scripts/build_os_document_library.py")
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(data.get("schema_version"), "1.0")
        self.assertIn("categories", data)
        self.assertIsInstance(data["categories"], list)
        self.assertGreater(len(data["categories"]), 3)
        seen: set[str] = set()
        for cat in data["categories"]:
            cid = cat.get("id")
            self.assertIsInstance(cid, str)
            self.assertNotIn(cid, seen)
            seen.add(cid)
            for item in cat.get("items", []):
                rel = item.get("path", "")
                self.assertIsInstance(rel, str)
                self.assertTrue(rel, "item.path must be non-empty")
                self.assertNotIn("miniconda", rel.lower())
                self.assertNotIn("/connector-conversations/", rel)
                p = REPO / rel
                self.assertTrue(p.is_file(), f"Missing file for catalog entry: {rel}")
        eb = next((c for c in data["categories"] if c.get("id") == "executive_brand"), None)
        self.assertIsNotNone(eb)
        self.assertTrue(eb.get("default_open"))

    def test_html_library_exists(self) -> None:
        html = REPO / "docs" / "os-document-library.html"
        self.assertTrue(html.is_file())
        text = html.read_text(encoding="utf-8")
        self.assertIn("Guides &amp; policies library", text)
        self.assertNotIn("transition: all", text.lower())
        self.assertIn("/view/markdown?path=", text)
        self.assertIn("../docs/brand-charter.html", text)
        self.assertIn("library-shell", text)
        self.assertIn("Sections", text)

    def test_doc_open_href_markdown_vs_html(self) -> None:
        from scripts.build_os_document_library import _doc_open_href

        self.assertEqual(
            _doc_open_href("agents/foo/charter.md", fmt="markdown"),
            "/view/markdown?path=agents%2Ffoo%2Fcharter.md",
        )
        self.assertTrue(_doc_open_href("docs/x.html", fmt="html").startswith("../"))


if __name__ == "__main__":
    unittest.main()
