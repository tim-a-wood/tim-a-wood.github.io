#!/usr/bin/env python3
"""
Build a PDF from markdown (same HTML pipeline as send_weekly_digest.py) and email it via Resend.

Uses Chrome/Chromium headless for PDF — no pandoc or WeasyPrint required.

Usage (from repo root, after sourcing .env.local):
  source .env.local
  python3 scripts/send_markdown_pdf_email.py \\
    --file research/library/technical/assurance-copilot-do178c-market-2026-04-02.md \\
    --subject "[MV Agent OS] Assurance Copilot research — PDF — 2026-04-02"

Optional:
  CHROME_BIN=/path/to/Google\\ Chrome  (default: macOS Google Chrome)
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIGEST_SCRIPT = Path(__file__).resolve().parent / "send_weekly_digest.py"


def _load_digest_module():
    spec = importlib.util.spec_from_file_location("send_weekly_digest", DIGEST_SCRIPT)
    if spec is None or spec.loader is None:
        print("ERROR: could not load send_weekly_digest.py", file=sys.stderr)
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def strip_yaml_frontmatter(md: str) -> str:
    if not md.startswith("---\n"):
        return md
    rest = md[4:]
    end = rest.find("\n---\n")
    if end == -1:
        return md
    return rest[end + 5 :].lstrip("\n")


def default_chrome_bin() -> str:
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.isfile(mac):
        return mac
    mac_c = "/Applications/Chromium.app/Contents/MacOS/Chromium"
    if os.path.isfile(mac_c):
        return mac_c
    return "google-chrome"


def html_to_pdf(chrome_bin: str, html_path: Path, pdf_path: Path) -> None:
    url = html_path.as_uri()
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not pdf_path.is_file() or pdf_path.stat().st_size < 100:
        err = (r.stderr or r.stdout or "").strip()
        print(f"ERROR: Chrome PDF failed (exit {r.returncode}): {err}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Markdown → PDF (Chrome) → Resend email")
    parser.add_argument(
        "--file",
        required=True,
        help="Path to markdown file (repo-relative or absolute)",
    )
    parser.add_argument("--subject", help="Email subject (default: derived from filename + date)")
    parser.add_argument(
        "--subtitle",
        default="Strategy · Research — PDF report",
        help="Email header subtitle",
    )
    parser.add_argument(
        "--body-intro",
        default="",
        help="Optional markdown prepended to the email body (not the PDF)",
    )
    args = parser.parse_args()

    md_path = Path(args.file).expanduser()
    if not md_path.is_absolute():
        md_path = (REPO / md_path).resolve()
    if not md_path.is_file():
        print(f"ERROR: file not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("RESEND_API_KEY", "")
    to_addr = os.environ.get("DIGEST_EMAIL_TO", "")
    sender = os.environ.get("DIGEST_EMAIL_FROM", "MV Agent OS <onboarding@resend.dev>")
    if not api_key:
        print("ERROR: RESEND_API_KEY not set (source .env.local).", file=sys.stderr)
        sys.exit(1)
    if not to_addr:
        print("ERROR: DIGEST_EMAIL_TO not set.", file=sys.stderr)
        sys.exit(1)

    digest = _load_digest_module()
    raw_md = md_path.read_text(encoding="utf-8")
    body_md = strip_yaml_frontmatter(raw_md)
    body_html = digest.md_to_html(body_md)

    today = date.today().strftime("%Y-%m-%d")
    subject = args.subject or f"[MV Agent OS] Report PDF — {md_path.stem} — {today}"

    # Full HTML document for PDF (print-friendly: drop outer email table chrome, use simple page)
    pdf_wrap = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=DM+Mono&display=swap" rel="stylesheet">
<style>
  @page {{ margin: 16mm; }}
  body {{ margin: 0; padding: 24px; background: #fff; color: #141d1b;
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; font-size: 11pt; line-height: 1.5; }}
  h1 {{ font-family: 'Bebas Neue', sans-serif; font-size: 22pt; letter-spacing: 0.06em; color: #0a2e28; margin-top: 0; }}
  h2 {{ font-family: 'Bebas Neue', sans-serif; font-size: 13pt; letter-spacing: 0.08em; color: #0a2e28;
    border-bottom: 1px solid #c5d6d0; padding-bottom: 6px; margin-top: 1.2em; text-transform: uppercase; }}
</style></head><body>
<p style="font-size:10pt;color:#3d4f4a;margin:0 0 16px 0">{md_path.name} · {today}</p>
{body_html}
</body></html>"""

    artifacts = REPO / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    safe_stem = urllib.parse.quote(md_path.stem, safe="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")[:80]
    pdf_name = f"{safe_stem}-{today}.pdf"

    chrome = os.environ.get("CHROME_BIN", default_chrome_bin())
    with tempfile.TemporaryDirectory(dir=str(artifacts)) as tmp:
        tmp_path = Path(tmp)
        html_file = tmp_path / "report.html"
        pdf_file = tmp_path / pdf_name
        html_file.write_text(pdf_wrap, encoding="utf-8")
        html_to_pdf(chrome, html_file, pdf_file)
        final_pdf = artifacts / pdf_name
        pdf_file.replace(final_pdf)

    intro = (args.body_intro.strip() + "\n\n") if args.body_intro.strip() else ""
    rel = str(md_path.relative_to(REPO))
    email_md = intro + f"PDF attached: **{pdf_name}**\n\n_Source markdown:_ `{rel}`\n"
    plain = intro + f"PDF attached: {pdf_name}\n\nSource markdown: {rel}\n"
    email_html = digest.wrap_html(digest.md_to_html(email_md), today, args.subtitle)

    print(f"Sending to {to_addr} with attachment {final_pdf.name} ({final_pdf.stat().st_size} bytes)...")
    digest.send(
        plain.strip(),
        email_html,
        subject,
        to_addr,
        sender,
        api_key,
        attachment_paths=[str(final_pdf)],
    )
    print(f"PDF saved at: {final_pdf}")


if __name__ == "__main__":
    main()
