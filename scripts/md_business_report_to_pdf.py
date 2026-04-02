#!/usr/bin/env python3
"""
Convert a simple Markdown business report to a plain PDF (Helvetica, no external deps except fpdf2).

Usage:
  python3 scripts/md_business_report_to_pdf.py docs/reports/initial-business-plan-2026-04-01.md out.pdf
"""
import re
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("ERROR: pip install fpdf2", file=sys.stderr)
    sys.exit(1)


class ReportPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def strip_inline_md(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def for_pdf(text: str) -> str:
    """Core PDF fonts (Helvetica) are Latin-1; map common Unicode punctuation to ASCII."""
    return (
        text.replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u2026", "...")
        .replace("\u00a0", " ")
    )


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: md_business_report_to_pdf.py INPUT.md OUTPUT.pdf", file=sys.stderr)
        sys.exit(1)
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    if not src.is_file():
        print(f"ERROR: not found: {src}", file=sys.stderr)
        sys.exit(1)

    lines = src.read_text(encoding="utf-8").splitlines()
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_left_margin(18)
    pdf.set_right_margin(18)

    i = 0
    while i < len(lines):
        line = lines[i]
        raw = line.rstrip()

        if not raw:
            pdf.ln(4)
            i += 1
            continue

        if raw.strip() == "---":
            pdf.set_draw_color(180, 190, 186)
            pdf.line(18, pdf.get_y(), pdf.w - 18, pdf.get_y())
            pdf.ln(8)
            i += 1
            continue

        if raw.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(10, 46, 40)
            pdf.multi_cell(0, 8, for_pdf(strip_inline_md(raw[2:].strip())))
            pdf.ln(4)
            i += 1
            continue

        if raw.startswith("## "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(10, 46, 40)
            pdf.multi_cell(0, 7, for_pdf(strip_inline_md(raw[3:].strip())))
            pdf.ln(2)
            i += 1
            continue

        if raw.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(40, 60, 55)
            pdf.multi_cell(0, 6, for_pdf(strip_inline_md(raw[4:].strip())))
            pdf.ln(1)
            i += 1
            continue

        if raw.startswith("|") and "|" in raw[1:]:
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if re.match(r"^\|[-| :]+\|$", row):
                    i += 1
                    continue
                cells = [c.strip() for c in row.strip("|").split("|")]
                rows.append(cells)
                i += 1
            pdf.set_text_color(30, 40, 38)
            usable_w = pdf.w - pdf.l_margin - pdf.r_margin
            for ri, cells in enumerate(rows):
                pdf.set_font("Helvetica", "B" if ri == 0 else "", 9)
                line = "  |  ".join(for_pdf(strip_inline_md(c)) for c in cells)
                pdf.multi_cell(usable_w, 5, line)
            pdf.ln(4)
            continue

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(25, 35, 32)
        pdf.multi_cell(0, 6, for_pdf(strip_inline_md(raw)))
        pdf.ln(2)
        i += 1

    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
