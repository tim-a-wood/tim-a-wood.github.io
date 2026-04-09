#!/usr/bin/env python3
"""
Send the weekly founder digest via Resend API as a formatted HTML email.

Usage:
  python3 scripts/send_weekly_digest.py --file artifacts/weekly-digest-2026-03-28.md
  python3 scripts/send_weekly_digest.py < digest.md
  python3 scripts/send_weekly_digest.py --file body.md --attach docs/report.pdf

Tuesday marketing: update_dashboards.sh (noon cron) emails
artifacts/marketing-weekly-update-YYYY-MM-DD.md when present (same Resend env).
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
from typing import Dict, List, Optional

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

# STYLE_GUIDE.md §13 — dark PDF / toolchain-faithful exports (Design-owned tokens).
STYLEGUIDE_BG_PAGE = "#050709"
STYLEGUIDE_BG_CARD = "#07090c"
STYLEGUIDE_TEXT = "#cce8e0"
STYLEGUIDE_MUTED = "#5d7870"
STYLEGUIDE_HEADING = "#cce8e0"
STYLEGUIDE_ACCENT = "#00e8c8"
STYLEGUIDE_CODE_BG = "rgba(255,255,255,0.045)"
STYLEGUIDE_CODE_BORDER = "rgba(0,232,200,0.14)"
STYLEGUIDE_RULE = "rgba(0,232,200,0.10)"
STYLEGUIDE_TABLE_HEADER = "#0d1115"
STYLEGUIDE_TABLE_STRIPE = "#07090c"
STYLEGUIDE_TABLE_STRIPE_ALT = "#0a1210"
STYLEGUIDE_GOOD = "#4ade80"


def _theme_map(theme: str) -> Dict[str, str]:
    """Inline HTML colors for markdown + email shell. theme: email | styleguide."""
    if theme == "styleguide":
        return {
            "bg_page": STYLEGUIDE_BG_PAGE,
            "bg_card": STYLEGUIDE_BG_CARD,
            "text": STYLEGUIDE_TEXT,
            "text_secondary": STYLEGUIDE_MUTED,
            "heading": STYLEGUIDE_HEADING,
            "link": STYLEGUIDE_ACCENT,
            "code_bg": STYLEGUIDE_CODE_BG,
            "code_border": STYLEGUIDE_CODE_BORDER,
            "rule": STYLEGUIDE_RULE,
            "table_header_bg": STYLEGUIDE_TABLE_HEADER,
            "table_stripe": STYLEGUIDE_TABLE_STRIPE,
            "table_stripe_alt": STYLEGUIDE_TABLE_STRIPE_ALT,
            "chip_bg": "#0d1115",
            "good": STYLEGUIDE_GOOD,
        }
    if theme != "email":
        raise ValueError(f"unknown theme: {theme!r} (use 'email' or 'styleguide')")
    return {
        "bg_page": EMAIL_BG_PAGE,
        "bg_card": EMAIL_BG_CARD,
        "text": EMAIL_TEXT,
        "text_secondary": EMAIL_TEXT_SECONDARY,
        "heading": EMAIL_HEADING,
        "link": EMAIL_LINK,
        "code_bg": EMAIL_CODE_BG,
        "code_border": EMAIL_CODE_BORDER,
        "rule": EMAIL_RULE,
        "table_header_bg": EMAIL_TABLE_HEADER_BG,
        "table_stripe": EMAIL_TABLE_STRIPE,
        "table_stripe_alt": EMAIL_BG_CARD,
        "chip_bg": EMAIL_TABLE_HEADER_BG,
        "good": "#1d6b3a",
    }


# ── Markdown → HTML ──────────────────────────────────────────────────────────

def md_to_html(md: str, theme: str = "email") -> str:
    """Convert the digest markdown to clean HTML with inline styles.

    theme:
      email — light surfaces (max compatibility in mail clients)
      styleguide — STYLE_GUIDE.md dark tokens (PDF exports, Design-aligned artifacts)
    """
    C = _theme_map(theme)
    lines = md.split("\n")
    html_lines = []
    i = 0

    def inline(text: str) -> str:
        """Convert inline markdown: bold, italic, code, links."""
        text = re.sub(
            r"`([^`]+)`",
            rf'<code style="font-family:\'DM Mono\',ui-monospace,monospace;background:{C["code_bg"]};color:{C["text"]};padding:2px 8px;border-radius:8px;font-size:13px;border:1px solid {C["code_border"]}">\1</code>',
            text,
        )
        text = re.sub(r"\*\*([^*]+)\*\*", rf'<strong style="color:{C["text"]}">\1</strong>', text)
        text = re.sub(r"\*([^*]+)\*", fr'<em style="color:{C["text_secondary"]}">\1</em>', text)
        text = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            rf'<a href="\2" style="color:{C["link"]};text-decoration:underline;text-underline-offset:2px;font-weight:600">\1</a>',
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
            html_lines.append(f'<hr style="border:none;border-top:1px solid {C["rule"]};margin:24px 0">')
            i += 1
            continue

        # H1 — STYLE_GUIDE: display font, ~22–28px scale
        if line.startswith("# "):
            html_lines.append(
                f'<h1 style="font-family:\'Bebas Neue\',sans-serif;font-size:22px;font-weight:400;letter-spacing:0.06em;color:{C["heading"]};margin:0 0 8px 0;line-height:1.15">{inline(line[2:])}</h1>'
            )
            i += 1
            continue

        # H2
        if line.startswith("## "):
            html_lines.append(
                f'<h2 style="font-family:\'Bebas Neue\',sans-serif;font-size:18px;font-weight:400;letter-spacing:0.08em;color:{C["heading"]};margin:28px 0 12px 0;text-transform:uppercase;border-bottom:1px solid {C["rule"]};padding-bottom:8px">{inline(line[3:])}</h2>'
            )
            i += 1
            continue

        # H3 — font-size-sm + uppercase label pattern
        if line.startswith("### "):
            html_lines.append(
                f'<h3 style="font-family:\'Plus Jakarta Sans\',-apple-system,sans-serif;font-size:13px;font-weight:700;color:{C["text_secondary"]};margin:20px 0 8px 0;text-transform:uppercase;letter-spacing:0.12em">{inline(line[4:])}</h3>'
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
                    th = C["table_header_bg"].replace("#", "")
                    style_row = f'bgcolor="{th}" style="background:{C["table_header_bg"]}"'
                else:
                    bg = C["table_stripe"] if ri % 2 == 0 else C["table_stripe_alt"]
                    style_row = f'bgcolor="{bg.replace("#", "")}" style="background:{bg}"'
                table_html.append(f"<tr {style_row}>")
                for cell in cells:
                    if tag == "th":
                        cell_style = f'style="padding:8px 12px;border:1px solid {C["rule"]};color:{C["text"]};text-align:left;font-weight:700"'
                    else:
                        cell_style = f'style="padding:8px 12px;border:1px solid {C["rule"]};color:{C["text_secondary"]};text-align:left"'
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
                    f'<li style="color:{C["text_secondary"]};margin:4px 0;line-height:1.45">{inline(item)}</li>'
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
                color = C["good"] if checked else C["text_secondary"]
                list_html.append(f'<li style="color:{color};margin:4px 0;line-height:1.45">{icon} {inline(text)}</li>')
            list_html.append("</ul>")
            html_lines.append("\n".join(list_html))
            continue

        # Blockquote-style note (lines starting with *)
        if line.startswith("*") and not line.startswith("**") and line.endswith("*"):
            html_lines.append(
                f'<p style="color:{C["text_secondary"]};font-style:italic;font-size:13px;margin:4px 0 12px 0">{inline(line.strip("*"))}</p>'
            )
            i += 1
            continue

        # Indented item (→ lines)
        if line.strip().startswith("→"):
            html_lines.append(
                f'<p style="color:{C["text_secondary"]};font-size:13px;margin:2px 0 8px 16px">{inline(line.strip())}</p>'
            )
            i += 1
            continue

        # Plain paragraph — font-size-base 14px
        html_lines.append(
            f'<p style="color:{C["text"]};font-size:14px;line-height:1.45;margin:0 0 12px 0;font-family:\'Plus Jakarta Sans\',-apple-system,sans-serif">{inline(line)}</p>'
        )
        i += 1

    return "\n".join(html_lines)


def wrap_html(
    body_html: str,
    week_of: str,
    subtitle: str = "Metroidvania Toolchain — Weekly Founder Digest",
    theme: str = "email",
) -> str:
    """HTML shell for outbound mail. theme styleguide uses STYLE_GUIDE dark surfaces."""
    C = _theme_map(theme)
    page_bg = C["bg_page"].replace("#", "")
    card_bg = C["bg_card"].replace("#", "")
    color_scheme = "dark light" if theme == "styleguide" else "light"
    border_outer = C["rule"] if theme == "styleguide" else C["rule"]

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="{color_scheme}">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
</head>
<body bgcolor="{page_bg}" style="margin:0;padding:0;background:{C["bg_page"]};color:{C["text"]};font-family:'Plus Jakarta Sans',-apple-system,sans-serif">

  <div style="height:4px;background:#00e8c8;width:100%"></div>

  <table width="100%" cellpadding="0" cellspacing="0" bgcolor="{page_bg}" style="background:{C["bg_page"]};padding:32px 16px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" bgcolor="{card_bg}" style="max-width:600px;width:100%;background:{C["bg_card"]};border-radius:18px;border:1px solid {border_outer};overflow:hidden;box-shadow:0 6px 20px rgba(0,0,0,0.26)">

        <tr><td style="padding:24px 28px 0 28px;background:{C["bg_card"]}">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td>
                <div style="font-family:'Bebas Neue',sans-serif;font-size:32px;font-weight:400;letter-spacing:0.08em;color:{C["heading"]};line-height:1">AGENT OS</div>
                <div style="font-size:12px;color:{C["text_secondary"]};letter-spacing:0.06em;text-transform:uppercase;margin-top:4px;font-weight:700">{subtitle}</div>
              </td>
              <td align="right" style="vertical-align:top">
                <span style="display:inline-block;background:{C["chip_bg"]};border:1px solid {C["code_border"]};color:{C["heading"]};font-size:11px;font-family:'DM Mono',monospace;padding:4px 12px;border-radius:999px">● {week_of}</span>
              </td>
            </tr>
          </table>
          <div style="height:1px;background:{C["rule"]};margin-top:16px"></div>
        </td></tr>

        <tr><td style="background:{C["bg_card"]};padding:8px 28px 28px 28px">
          {body_html}
        </td></tr>

        <tr><td style="padding:0 24px 24px 24px;background:{C["bg_card"]};text-align:center">
          <div style="font-size:11px;color:{C["text_secondary"]};font-family:'DM Mono',monospace">
            MV Toolchain · Design system (STYLE_GUIDE.md) · Agent OS
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
        print(
            f"ERROR: curl exit {result.returncode}: {result.stderr!r} stdout={result.stdout[:800]!r}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)

    out = (result.stdout or "").strip()
    if not out:
        print(
            f"ERROR: empty response from Resend (curl ok). stderr={result.stderr!r}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)
    try:
        resp = json.loads(out)
    except json.JSONDecodeError as e:
        print(
            f"ERROR: Resend response was not JSON: {e}\nFirst 800 chars: {out[:800]!r}",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)
    if "id" in resp:
        print(f"Sent. Email ID: {resp['id']}", flush=True)
    else:
        print(f"ERROR: {out}", file=sys.stderr, flush=True)
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

    api_key = (os.environ.get("RESEND_API_KEY", "") or "").strip()
    to      = (os.environ.get("DIGEST_EMAIL_TO", "tim.a.wood@outlook.com") or "").strip()
    sender  = (os.environ.get("DIGEST_EMAIL_FROM", "MV Agent OS <onboarding@resend.dev>") or "").strip()

    if not api_key:
        print("ERROR: RESEND_API_KEY not set.", file=sys.stderr, flush=True)
        sys.exit(1)

    text = open(args.file).read() if args.file else sys.stdin.read()
    if not text.strip():
        print("ERROR: Empty digest body.", file=sys.stderr, flush=True)
        sys.exit(1)

    today    = date.today().strftime("%Y-%m-%d")
    subject  = args.subject or f"[MV Toolchain] Weekly Founder Digest — {today}"
    subtitle = args.subtitle or "Metroidvania Toolchain — Weekly Founder Digest"

    body_html = md_to_html(text)
    full_html = wrap_html(body_html, today, subtitle)

    print(f"Sending to {to}...", flush=True)
    send(text, full_html, subject, to, sender, api_key, attachment_paths=args.attachments)


if __name__ == "__main__":
    main()
