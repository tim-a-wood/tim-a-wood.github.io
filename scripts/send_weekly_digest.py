#!/usr/bin/env python3
"""
Send the weekly founder digest via Resend API as a formatted HTML email.

Usage:
  python3 scripts/send_weekly_digest.py --file artifacts/weekly-digest-2026-03-28.md
  python3 scripts/send_weekly_digest.py < digest.md
  python3 scripts/send_weekly_digest.py --file body.md --attach docs/report.pdf
"""
import os
import sys
import re
import json
import base64
import argparse
import subprocess
import tempfile
from datetime import date
from typing import List, Optional

RESEND_API_URL = "https://api.resend.com/emails"

# Outbound email theme (light surfaces). Many clients strip dark backgrounds or force
# light mode; bright cyan on white fails WCAG. Dark teal body/headings on off-white
# keep brand adjacency without relying on in-app dark tokens (STYLE_GUIDE product UI).
EMAIL_BG_PAGE = "#eef2f0"
EMAIL_BG_CARD = "#ffffff"
EMAIL_TEXT = "#141d1b"
EMAIL_TEXT_SECONDARY = "#3d4f4a"
EMAIL_HEADING = "#0a2e28"
EMAIL_LINK = "#006656"
EMAIL_CODE_BG = "#e4ebe8"
EMAIL_CODE_BORDER = "#b8cec8"
EMAIL_RULE = "#c5d6d0"
EMAIL_TABLE_HEADER_BG = "#dceae6"
EMAIL_TABLE_STRIPE = "#f4f8f7"

# ── Markdown → HTML ──────────────────────────────────────────────────────────

def md_to_html(md: str) -> str:
    """Convert the digest markdown to clean HTML with inline styles."""
    lines = md.split("\n")
    html_lines = []
    i = 0

    def inline(text: str) -> str:
        """Convert inline markdown: bold, italic, code, links."""
        text = re.sub(
            r"`([^`]+)`",
            rf'<code style="font-family:\'DM Mono\',monospace;background:{EMAIL_CODE_BG};color:{EMAIL_TEXT};padding:2px 8px;border-radius:4px;font-size:12px;border:1px solid {EMAIL_CODE_BORDER}">\1</code>',
            text,
        )
        text = re.sub(r"\*\*([^*]+)\*\*", rf'<strong style="color:{EMAIL_TEXT}">\1</strong>', text)
        text = re.sub(r"\*([^*]+)\*", fr'<em style="color:{EMAIL_TEXT_SECONDARY}">\1</em>', text)
        text = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            rf'<a href="\2" style="color:{EMAIL_LINK};text-decoration:underline;text-underline-offset:2px;font-weight:600">\1</a>',
            text,
        )
        text = text.replace("→", "→")
        return text

    while i < len(lines):
        line = lines[i]

        # Blank line
        if not line.strip():
            html_lines.append("")
            i += 1
            continue

        # HR
        if re.match(r"^-{3,}$", line.strip()):
            html_lines.append(f'<hr style="border:none;border-top:1px solid {EMAIL_RULE};margin:24px 0">')
            i += 1
            continue

        # H1
        if line.startswith("# "):
            html_lines.append(
                f'<h1 style="font-family:\'Bebas Neue\',sans-serif;font-size:28px;font-weight:400;letter-spacing:0.06em;color:{EMAIL_HEADING};margin:0 0 4px 0;line-height:1.1">{inline(line[2:])}</h1>'
            )
            i += 1
            continue

        # H2
        if line.startswith("## "):
            html_lines.append(
                f'<h2 style="font-family:\'Bebas Neue\',sans-serif;font-size:18px;font-weight:400;letter-spacing:0.08em;color:{EMAIL_HEADING};margin:28px 0 10px 0;text-transform:uppercase;border-bottom:1px solid {EMAIL_RULE};padding-bottom:8px">{inline(line[3:])}</h2>'
            )
            i += 1
            continue

        # H3
        if line.startswith("### "):
            html_lines.append(
                f'<h3 style="font-size:13px;font-weight:700;color:{EMAIL_HEADING};margin:20px 0 6px 0;text-transform:uppercase;letter-spacing:0.06em">{inline(line[4:])}</h3>'
            )
            i += 1
            continue

        # Table — collect all table rows
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            # filter separator rows
            data_rows = [r for r in rows if not re.match(r"^\|[-| :]+\|$", r.strip())]
            table_html = ['<table style="width:100%;border-collapse:collapse;margin:12px 0;font-size:13px">']
            for ri, row in enumerate(data_rows):
                cells = [c.strip() for c in row.strip().strip("|").split("|")]
                tag = "th" if ri == 0 else "td"
                if ri == 0:
                    style_row = f'bgcolor="{EMAIL_TABLE_HEADER_BG.replace("#", "")}" style="background:{EMAIL_TABLE_HEADER_BG}"'
                else:
                    bg = EMAIL_TABLE_STRIPE if ri % 2 == 0 else EMAIL_BG_CARD
                    hex_attr = bg.replace("#", "")
                    style_row = f'bgcolor="{hex_attr}" style="background:{bg}"'
                table_html.append(f"<tr {style_row}>")
                for cell in cells:
                    if tag == "th":
                        cell_style = f'style="padding:8px 12px;border:1px solid {EMAIL_RULE};color:{EMAIL_TEXT};text-align:left;font-weight:700"'
                    else:
                        cell_style = f'style="padding:8px 12px;border:1px solid {EMAIL_RULE};color:{EMAIL_TEXT_SECONDARY};text-align:left"'
                    table_html.append(f'<{tag} {cell_style}>{inline(cell)}</{tag}>')
                table_html.append("</tr>")
            table_html.append("</table>")
            html_lines.append("\n".join(table_html))
            continue

        # Unordered list — collect consecutive list items
        if re.match(r"^[-*] ", line):
            items = []
            while i < len(lines) and re.match(r"^[-*] ", lines[i]):
                items.append(lines[i][2:])
                i += 1
            list_html = ['<ul style="margin:8px 0 12px 0;padding-left:20px">']
            for item in items:
                list_html.append(
                    f'<li style="color:{EMAIL_TEXT_SECONDARY};margin:4px 0;line-height:1.6">{inline(item)}</li>'
                )
            list_html.append("</ul>")
            html_lines.append("\n".join(list_html))
            continue

        # Checkbox list items
        if re.match(r"^- \[[ x]\]", line):
            items = []
            while i < len(lines) and re.match(r"^- \[[ x]\]", lines[i]):
                checked = "x" in lines[i][3]
                text = lines[i][6:]
                items.append((checked, text))
                i += 1
            list_html = ['<ul style="margin:8px 0 12px 0;padding-left:4px;list-style:none">']
            for checked, text in items:
                icon = "✅" if checked else "☐"
                color = "#1d6b3a" if checked else EMAIL_TEXT_SECONDARY
                list_html.append(f'<li style="color:{color};margin:4px 0;line-height:1.6">{icon} {inline(text)}</li>')
            list_html.append("</ul>")
            html_lines.append("\n".join(list_html))
            continue

        # Bold-prefixed line used as a labelled paragraph (e.g. "**Status: Green**")
        # Blockquote-style note (lines starting with *)
        if line.startswith("*") and not line.startswith("**") and line.endswith("*"):
            html_lines.append(
                f'<p style="color:{EMAIL_TEXT_SECONDARY};font-style:italic;font-size:13px;margin:4px 0 12px 0">{inline(line.strip("*"))}</p>'
            )
            i += 1
            continue

        # Indented item (→ lines)
        if line.strip().startswith("→"):
            html_lines.append(
                f'<p style="color:{EMAIL_TEXT_SECONDARY};font-size:13px;margin:2px 0 8px 16px">{inline(line.strip())}</p>'
            )
            i += 1
            continue

        # Plain paragraph
        html_lines.append(
            f'<p style="color:{EMAIL_TEXT};font-size:14px;line-height:1.7;margin:0 0 12px 0">{inline(line)}</p>'
        )
        i += 1

    return "\n".join(html_lines)


def wrap_html(body_html: str, week_of: str, subtitle: str = "Metroidvania Toolchain — Weekly Founder Digest") -> str:
    page_bg = EMAIL_BG_PAGE.replace("#", "")
    card_bg = EMAIL_BG_CARD.replace("#", "")
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=DM+Mono&display=swap" rel="stylesheet">
</head>
<body bgcolor="{page_bg}" style="margin:0;padding:0;background:{EMAIL_BG_PAGE};color:{EMAIL_TEXT};font-family:'Plus Jakarta Sans',-apple-system,sans-serif">

  <!-- brand accent (thin strip only — avoids large cyan text on unpredictable backgrounds) -->
  <div style="height:4px;background:#00e8c8;width:100%"></div>

  <!-- outer wrapper: bgcolor helps Outlook / clients that ignore body background -->
  <table width="100%" cellpadding="0" cellspacing="0" bgcolor="{page_bg}" style="background:{EMAIL_BG_PAGE};padding:32px 16px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" bgcolor="{card_bg}" style="max-width:600px;width:100%;background:{EMAIL_BG_CARD};border-radius:18px;border:1px solid {EMAIL_RULE};overflow:hidden">

        <!-- header -->
        <tr><td style="padding:24px 28px 0 28px;background:{EMAIL_BG_CARD}">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:32px;font-weight:400;letter-spacing:0.08em;color:{EMAIL_HEADING};line-height:1">AGENT OS</div>
                <div style="font-size:12px;color:{EMAIL_TEXT_SECONDARY};letter-spacing:0.06em;text-transform:uppercase;margin-top:4px">{subtitle}</div>
              </td>
              <td align="right" style="vertical-align:top">
                <span style="display:inline-block;background:{EMAIL_TABLE_HEADER_BG};border:1px solid {EMAIL_CODE_BORDER};color:{EMAIL_HEADING};font-size:11px;font-family:'DM Mono',monospace;padding:4px 12px;border-radius:999px">● {week_of}</span>
              </td>
            </tr>
          </table>
          <div style="height:1px;background:{EMAIL_RULE};margin-top:16px"></div>
        </td></tr>

        <!-- body -->
        <tr><td style="background:{EMAIL_BG_CARD};padding:8px 28px 28px 28px">
          {body_html}
        </td></tr>

        <!-- footer -->
        <tr><td style="padding:0 24px 24px 24px;background:{EMAIL_BG_CARD};text-align:center">
          <div style="font-size:11px;color:{EMAIL_TEXT_SECONDARY};font-family:'DM Mono',monospace">
            MV Toolchain · Agent OS · Generated by Orchestrator
          </div>
        </td></tr>

      </table>
    </td></tr>
  </table>

</body>
</html>"""


# ── Send ─────────────────────────────────────────────────────────────────────

def send(
    text: str,
    html: str,
    subject: str,
    to: str,
    sender: str,
    api_key: str,
    attachment_paths: Optional[List[str]] = None,
) -> None:
    body: dict = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "text": text,
        "html": html,
    }
    if attachment_paths:
        atts = []
        for path in attachment_paths:
            if not os.path.isfile(path):
                print(f"ERROR: attachment not found: {path}", file=sys.stderr)
                sys.exit(1)
            with open(path, "rb") as f:
                raw = f.read()
            atts.append({
                "filename": os.path.basename(path),
                "content": base64.standard_b64encode(raw).decode("ascii"),
            })
        body["attachments"] = atts

    # Write JSON to a temp file so curl reads the body from disk (avoids ARG_MAX when
    # attachments base64-expand the payload; also matches prior curl-based delivery).
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
    ) as tf:
        json.dump(body, tf)
        tmp_path = tf.name
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-S",
                "-X",
                "POST",
                RESEND_API_URL,
                "-H",
                f"Authorization: Bearer {api_key}",
                "-H",
                "Content-Type: application/json",
                "-d",
                f"@{tmp_path}",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if result.returncode != 0:
        print(f"ERROR: curl exit {result.returncode}: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    out = result.stdout
    resp = json.loads(out)
    if "id" in resp:
        print(f"Sent. Email ID: {resp['id']}")
    else:
        print(f"ERROR: {out}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Path to digest markdown file (default: stdin)")
    parser.add_argument("--subject", help="Email subject override")
    parser.add_argument("--subtitle", help="Header subtitle override (default: Weekly Founder Digest)")
    parser.add_argument(
        "--attach",
        action="append",
        dest="attachments",
        metavar="PATH",
        default=None,
        help="Attach file via Resend (repeatable). Same API as dashboard notification emails.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("RESEND_API_KEY", "")
    to      = os.environ.get("DIGEST_EMAIL_TO", "tim.a.wood@outlook.com")
    sender  = os.environ.get("DIGEST_EMAIL_FROM", "MV Agent OS <onboarding@resend.dev>")

    if not api_key:
        print("ERROR: RESEND_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    text = open(args.file).read() if args.file else sys.stdin.read()
    if not text.strip():
        print("ERROR: Empty digest body.", file=sys.stderr)
        sys.exit(1)

    today    = date.today().strftime("%Y-%m-%d")
    subject  = args.subject or f"[MV Toolchain] Weekly Founder Digest — {today}"
    subtitle = args.subtitle or "Metroidvania Toolchain — Weekly Founder Digest"

    body_html = md_to_html(text)
    full_html = wrap_html(body_html, today, subtitle)

    print(f"Sending to {to}...")
    send(text, full_html, subject, to, sender, api_key, attachment_paths=args.attachments)


if __name__ == "__main__":
    main()
