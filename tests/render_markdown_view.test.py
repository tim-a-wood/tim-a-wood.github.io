#!/usr/bin/env python3
"""Tests for Markdown viewer link rewriting and page build."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


class RenderMarkdownViewTests(unittest.TestCase):
    def test_rewrites_repo_absolute_path_in_href(self) -> None:
        from scripts.render_markdown_view import _rewrite_markdown_anchor_hrefs

        guide = REPO / "STYLE_GUIDE.md"
        self.assertTrue(guide.is_file(), "fixture STYLE_GUIDE.md missing")
        inp = f'<p><a href="{guide}">style</a></p>'
        out = _rewrite_markdown_anchor_hrefs(inp, "docs/reports/example.md", REPO)
        self.assertIn("/view/markdown?path=", out)
        self.assertNotIn(str(REPO), out)

    def test_rewrites_root_style_site_path(self) -> None:
        from scripts.render_markdown_view import _rewrite_markdown_anchor_hrefs

        inp = '<p><a href="/STYLE_GUIDE.md">style</a></p>'
        out = _rewrite_markdown_anchor_hrefs(inp, "docs/reports/example.md", REPO)
        self.assertIn("/view/markdown?path=STYLE_GUIDE.md", out.replace("%2F", "/"))

    def test_rewrites_relative_md_from_nested_doc(self) -> None:
        from scripts.render_markdown_view import _rewrite_markdown_anchor_hrefs

        inp = '<p><a href="../engineering/charter.md">eng</a></p>'
        out = _rewrite_markdown_anchor_hrefs(inp, "agents/design/charter.md", REPO)
        self.assertIn("agents%2Fengineering%2Fcharter.md", out)

    def test_viewer_body_uses_wider_max_width(self) -> None:
        from scripts.render_markdown_view import build_markdown_view_page

        html = build_markdown_view_page(
            title="T",
            repo_path="x.md",
            source="# Hi",
            repo_root=REPO,
        )
        self.assertIn("max-width: min(1240px", html)
        self.assertNotIn("52rem", html)


if __name__ == "__main__":
    unittest.main()
