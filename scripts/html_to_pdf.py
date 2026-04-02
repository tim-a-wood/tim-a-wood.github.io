#!/usr/bin/env python3
"""
Render a local HTML file to PDF using Chrome/Chromium headless (background graphics preserved).

Usage (from repo root):
  python3 scripts/html_to_pdf.py docs/example.html artifacts/out.pdf

Optional:
  CHROME_BIN=/path/to/Google\\ Chrome
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def default_chrome_bin() -> str:
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.isfile(mac):
        return mac
    mac_c = "/Applications/Chromium.app/Contents/MacOS/Chromium"
    if os.path.isfile(mac_c):
        return mac_c
    return os.environ.get("CHROME_BIN", "google-chrome")


def html_to_pdf(chrome_bin: str, html_path: Path, pdf_path: Path) -> None:
    html_path = html_path.resolve()
    if not html_path.is_file():
        print(f"ERROR: HTML not found: {html_path}", file=sys.stderr)
        sys.exit(1)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    url = html_path.as_uri()
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not pdf_path.is_file() or pdf_path.stat().st_size < 100:
        err = (r.stderr or r.stdout or "").strip()
        print(f"ERROR: Chrome PDF failed (exit {r.returncode}): {err}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Usage: html_to_pdf.py <input.html> <output.pdf>",
            file=sys.stderr,
        )
        sys.exit(1)
    inp = Path(sys.argv[1])
    out = Path(sys.argv[2])
    if not inp.is_absolute():
        inp = REPO / inp
    if not out.is_absolute():
        out = REPO / out
    chrome = os.environ.get("CHROME_BIN", default_chrome_bin())
    html_to_pdf(chrome, inp, out)
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
