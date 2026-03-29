#!/usr/bin/env python3
"""
Send the weekly founder digest via Resend API as a formatted HTML email.

Usage:
  python3 scripts/send_weekly_digest.py --file artifacts/weekly-digest-2026-03-28.md
  python3 scripts/send_weekly_digest.py < digest.md
"""
import os
import sys
import re
import json
import argparse
import subprocess
from datetime import date

RESEND_API_URL = "https://api.resend.com/emails"

# ── Markdown → HTML ──────────────────────────────────────────────────────────

def md_to_html(md: str) -> str:
    """Convert the digest markdown to clean HTML with inline styles."""
    lines = md.split("\n")
    html_lines = []
    i = 0

    def inline(text: str) -> str:
        """Convert inline markdown: bold, italic, code, links."""
        text = re.sub(r"`([^`]+)`", r'<code style="font-family:\'DM Mono\',monospace;background:#0d1117;color:#00e8c8;padding:2px 6px;border-radius:4px;font-size:12px">\1</code>', text)
        text = re.sub(r"\*\*([^*]+)\*\*", r'<strong style="color:#cce8e0">\1</strong>', text)
        text = re.sub(r"\*([^*]+)\*", r'<em>\1</em>', text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" style="color:#00e8c8">\1</a>', text)
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
            html_lines.append('<hr style="border:none;border-top:1px solid rgba(0,232,200,0.15);margin:24px 0">')
            i += 1
            continue

        # H1
        if line.startswith("# "):
            html_lines.append(f'<h1 style="font-family:\'Bebas Neue\',sans-serif;font-size:28px;font-weight:400;letter-spacing:0.06em;color:#00e8c8;margin:0 0 4px 0;line-height:1.1">{inline(line[2:])}</h1>')
            i += 1
            continue

        # H2
        if line.startswith("## "):
            html_lines.append(f'<h2 style="font-family:\'Bebas Neue\',sans-serif;font-size:18px;font-weight:400;letter-spacing:0.08em;color:#cce8e0;margin:28px 0 10px 0;text-transform:uppercase;border-bottom:1px solid rgba(0,232,200,0.12);padding-bottom:6px">{inline(line[3:])}</h2>')
            i += 1
            continue

        # H3
        if line.startswith("### "):
            html_lines.append(f'<h3 style="font-size:13px;font-weight:700;color:#cce8e0;margin:20px 0 6px 0;text-transform:uppercase;letter-spacing:0.06em">{inline(line[4:])}</h3>')
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
                style_row = 'style="background:rgba(0,232,200,0.05)"' if ri == 0 else ('style="background:rgba(255,255,255,0.02)"' if ri % 2 == 0 else '')
                table_html.append(f'<tr {style_row}>')
                for cell in cells:
                    cell_style = 'style="padding:7px 12px;border:1px solid rgba(0,232,200,0.1);color:#cce8e0;text-align:left;font-weight:600"' if tag == "th" else 'style="padding:7px 12px;border:1px solid rgba(0,232,200,0.08);color:#a0c0b8"'
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
                list_html.append(f'<li style="color:#a0c0b8;margin:4px 0;line-height:1.6">{inline(item)}</li>')
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
                color = "#4ade80" if checked else "#5d7870"
                list_html.append(f'<li style="color:{color};margin:4px 0;line-height:1.6">{icon} {inline(text)}</li>')
            list_html.append("</ul>")
            html_lines.append("\n".join(list_html))
            continue

        # Bold-prefixed line used as a labelled paragraph (e.g. "**Status: Green**")
        # Blockquote-style note (lines starting with *)
        if line.startswith("*") and not line.startswith("**") and line.endswith("*"):
            html_lines.append(f'<p style="color:#5d7870;font-style:italic;font-size:13px;margin:4px 0 12px 0">{inline(line.strip("*"))}</p>')
            i += 1
            continue

        # Indented item (→ lines)
        if line.strip().startswith("→"):
            html_lines.append(f'<p style="color:#5d7870;font-size:13px;margin:2px 0 8px 16px">{inline(line.strip())}</p>')
            i += 1
            continue

        # Plain paragraph
        html_lines.append(f'<p style="color:#a0c0b8;font-size:14px;line-height:1.7;margin:0 0 10px 0">{inline(line)}</p>')
        i += 1

    return "\n".join(html_lines)


def wrap_html(body_html: str, week_of: str, subtitle: str = "Metroidvania Toolchain — Weekly Founder Digest") -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=DM+Mono&display=swap" rel="stylesheet">
</head>
<body style="margin:0;padding:0;background:#050709;font-family:'Plus Jakarta Sans',-apple-system,sans-serif">

  <!-- top accent bar -->
  <div style="height:3px;background:#00e8c8;width:100%"></div>

  <!-- outer wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#050709;padding:32px 16px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

        <!-- header -->
        <tr><td style="padding:0 0 24px 0">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:32px;font-weight:400;letter-spacing:0.08em;color:#00e8c8;line-height:1">AGENT OS</div>
                <div style="font-size:12px;color:#5d7870;letter-spacing:0.06em;text-transform:uppercase;margin-top:2px">{subtitle}</div>
              </td>
              <td align="right" style="vertical-align:top">
                <span style="display:inline-block;background:rgba(74,222,128,0.1);border:1px solid rgba(74,222,128,0.25);color:#4ade80;font-size:11px;font-family:'DM Mono',monospace;padding:4px 10px;border-radius:999px">● {week_of}</span>
              </td>
            </tr>
          </table>
          <div style="height:1px;background:rgba(0,232,200,0.15);margin-top:16px"></div>
        </td></tr>

        <!-- body -->
        <tr><td style="background:rgba(4,6,10,0.96);border:1px solid rgba(0,232,200,0.1);border-radius:18px;padding:32px 36px">
          {body_html}
        </td></tr>

        <!-- footer -->
        <tr><td style="padding:20px 0 0 0;text-align:center">
          <div style="font-size:11px;color:#2a3d38;font-family:'DM Mono',monospace">
            MV Toolchain · Agent OS · Generated by Orchestrator
          </div>
        </td></tr>

      </table>
    </td></tr>
  </table>

</body>
</html>"""


# ── Send ─────────────────────────────────────────────────────────────────────

def send(text: str, html: str, subject: str, to: str, sender: str, api_key: str) -> None:
    payload = json.dumps({
        "from": sender,
        "to": [to],
        "subject": subject,
        "text": text,
        "html": html,
    })

    result = subprocess.run(
        ["curl", "-s", "-X", "POST", RESEND_API_URL,
         "-H", f"Authorization: Bearer {api_key}",
         "-H", "Content-Type: application/json",
         "-d", payload],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    resp = json.loads(result.stdout)
    if "id" in resp:
        print(f"Sent. Email ID: {resp['id']}")
    else:
        print(f"ERROR: {result.stdout}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Path to digest markdown file (default: stdin)")
    parser.add_argument("--subject", help="Email subject override")
    parser.add_argument("--subtitle", help="Header subtitle override (default: Weekly Founder Digest)")
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
    send(text, full_html, subject, to, sender, api_key)


if __name__ == "__main__":
    main()
