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

    def test_rewrites_single_quoted_href(self) -> None:
        from scripts.render_markdown_view import _rewrite_markdown_anchor_hrefs

        guide = REPO / "STYLE_GUIDE.md"
        self.assertTrue(guide.is_file())
        inp = f"<p><a href='{guide}'>style</a></p>"
        out = _rewrite_markdown_anchor_hrefs(inp, "docs/foo.md", REPO)
        self.assertIn("/view/markdown?path=", out)

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

    def test_supervisor_markdown_query_param_case_insensitive(self) -> None:
        from urllib.parse import urlparse

        from scripts.os_dashboard_supervisor import _markdown_path_from_query

        self.assertEqual(
            _markdown_path_from_query(urlparse("/view/markdown?Path=STYLE_GUIDE.md")),
            "STYLE_GUIDE.md",
        )

    def test_md_to_fragment_renders_html_when_markdown_installed(self) -> None:
        try:
            import markdown  # noqa: F401
        except ImportError:
            self.skipTest("PyPI markdown not installed")
        from scripts.render_markdown_view import _md_to_fragment

        out = _md_to_fragment("# Title\n\n**bold**")
        self.assertIn("<h1", out)
        self.assertNotIn("md-fallback", out)


if __name__ == "__main__":
    unittest.main()
