#!/usr/bin/env python3
"""Light-theme assertions for scripts/send_weekly_digest.py (run: python3 tests/send_weekly_digest_email_theme_test.py)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "scripts" / "send_weekly_digest.py"


def load():
    spec = importlib.util.spec_from_file_location("send_weekly_digest", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    m = load()
    body = m.md_to_html("# Hello\n\n**Bold** and [a link](https://example.org)\n")
    full = m.wrap_html(body, "2099-01-01", "Subtitle")

    # Headings and body use dark text on light — not bright cyan in body HTML
    assert m.EMAIL_HEADING in body
    assert "color:#00e8c8" not in body, "avoid bright cyan in body (fails on white client backgrounds)"
    assert m.EMAIL_TEXT in body or m.EMAIL_TEXT_SECONDARY in body

    # Wrapper uses light page + card; cyan only as thin top strip
    assert m.EMAIL_BG_PAGE in full
    assert "height:4px;background:#00e8c8" in full
    assert 'meta name="color-scheme" content="light"' in full

    # STYLE_GUIDE dark export (PDF / Design-aligned)
    dark_body = m.md_to_html("# Title\n\n[link](https://example.org)\n", theme="styleguide")
    assert m.STYLEGUIDE_BG_PAGE not in dark_body  # body fragment only
    assert m.STYLEGUIDE_TEXT in dark_body or "cce8e0" in dark_body
    assert "color:#00e8c8" in dark_body, "styleguide links use accent"
    dark_full = m.wrap_html(dark_body, "2099-01-01", "Design — PDF mail", theme="styleguide")
    assert m.STYLEGUIDE_BG_PAGE in dark_full
    assert 'meta name="color-scheme" content="dark light"' in dark_full

    print("send_weekly_digest_email_theme_test: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
