#!/usr/bin/env python3
"""
Lint CSS files and <style> blocks in HTML files for design token violations.

Checks (per docs/reports/agent-guardrail-enforcement-audit-2026-04-02.md):
  CL-1  No hex color values outside :root token block  (A-1)
  CL-2  No off-grid spacing values at layout level     (A-2, amended: 9px/10px allowed in component spec)
  CL-3  No 'transition: all'                           (A-4)
  CL-4  No colored box-shadow (only rgba(0,0,0,x))    (A-13)
  CL-5  Hover translateY must not exceed -1px          (A-14)
  CL-6  font-family must use token variable            (A-5)
  CL-7  font-size px values must be named token values (A-5)

Amended rules per Design agent review (2026-04-02):
  - CL-1: hex values inside :root { } blocks are exempt (those ARE the token declarations)
  - CL-2: 9px and 10px are documented production values in component spec; only flag the
           strictly-forbidden list from CLAUDE.md: 5px, 7px, 11px, 13px, 15px
  - CL-7: allowed px font-size values are the full token scale:
           10px, 11px, 12px, 13px, 14px, 15px, 18px, 24px, 32px

Usage:
  python3 scripts/lint_css_tokens.py                    # scan all .css and .html in repo
  python3 scripts/lint_css_tokens.py file.css file.html # specific files
  python3 scripts/lint_css_tokens.py --warn-only        # exit 0 even on failures
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# CL-2: strictly forbidden spacing values (9px and 10px are documented exceptions per style guide)
FORBIDDEN_SPACING_PX = {"5px", "7px", "11px", "13px", "15px"}

# CL-6: forbidden font-family literal names (must use var(--font-*) instead)
FORBIDDEN_FONT_FAMILIES = re.compile(
    r'font-family\s*:\s*[\'"]?'
    r'(Inter|Roboto|Arial|Helvetica|sans-serif|Georgia|Times|monospace|Courier)'
    r'[\'"]?\s*[;,]',
    re.IGNORECASE,
)

# CL-7: allowed px font-size values (the full token scale)
ALLOWED_FONT_SIZE_PX = {
    "10px", "11px", "12px", "13px", "14px", "15px", "18px", "24px", "32px",
}

# CL-3
RE_TRANSITION_ALL = re.compile(r'\btransition\s*:\s*all\b', re.IGNORECASE)

# CL-5: translateY in a hover rule more negative than -1px
RE_TRANSLATE_Y = re.compile(r'translateY\(\s*(-?\d+(?:\.\d+)?)(px|em|rem)\s*\)')

# CL-1: hex color — matches #rgb, #rgba, #rrggbb, #rrggbbaa
RE_HEX_COLOR = re.compile(r'#[0-9a-fA-F]{3,8}\b')

# CL-4: box-shadow with a non-neutral color
# We accept only rgba(0,0,0,...) or transparent. Flag anything else.
RE_BOX_SHADOW_LINE = re.compile(r'\bbox-shadow\s*:', re.IGNORECASE)
RE_RGBA_NEUTRAL = re.compile(r'rgba\(\s*0\s*,\s*0\s*,\s*0\s*,', re.IGNORECASE)
RE_COLOR_IN_SHADOW = re.compile(
    r'(?:#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|hsl[a]?\([^)]*\)|[a-zA-Z]{3,}(?<!\bsolid\b)(?<!\binset\b)(?<!\bnone\b)(?<!\btransparent\b))',
    re.IGNORECASE,
)

# Spacing: property lines that carry pixel values
RE_SPACING_PROP = re.compile(
    r'(?:^|\s)(?:padding|margin|gap|column-gap|row-gap)\s*:[^;{]+',
    re.IGNORECASE | re.MULTILINE,
)
RE_PX_VALUE = re.compile(r'\b(\d+)px\b')

# font-size raw px
RE_FONT_SIZE = re.compile(r'\bfont-size\s*:\s*(\d+(?:\.\d+)?)(px)\b', re.IGNORECASE)


def extract_style_blocks(html: str) -> list[tuple[int, str]]:
    """Return list of (start_line, css_text) for each <style> block."""
    blocks = []
    for m in re.finditer(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE):
        start_line = html[:m.start()].count('\n') + 1
        blocks.append((start_line, m.group(1)))
    return blocks


def is_inside_root_block(css: str, match_start: int) -> bool:
    """Return True if match_start falls inside a :root { } block."""
    # Find all :root { } extents
    for rm in re.finditer(r':root\s*\{', css):
        brace_start = rm.end() - 1
        depth = 0
        for i, ch in enumerate(css[brace_start:], brace_start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    if brace_start <= match_start <= i:
                        return True
                    break
    return False


def lint_css(css: str, filename: str, line_offset: int = 0) -> list[str]:
    """Lint a CSS string. Returns list of 'filename:line  CHECK  message' strings."""
    violations: list[str] = []
    lines = css.split('\n')

    def loc(idx: int) -> str:
        return f"{filename}:{line_offset + idx + 1}"

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith('/*'):
            continue

        # CL-3: transition: all
        if RE_TRANSITION_ALL.search(line):
            violations.append(f"{loc(i)}  CL-3  'transition: all' is forbidden — name properties explicitly")

        # CL-6: forbidden font-family
        if FORBIDDEN_FONT_FAMILIES.search(line):
            violations.append(f"{loc(i)}  CL-6  font-family must use var(--font-*) token, not a literal name")

        # CL-7: raw px font-size
        for m in RE_FONT_SIZE.finditer(line):
            px_val = f"{m.group(1)}{m.group(2)}"
            if px_val not in ALLOWED_FONT_SIZE_PX:
                violations.append(
                    f"{loc(i)}  CL-7  font-size: {px_val} is not a named token value "
                    f"(allowed: {sorted(ALLOWED_FONT_SIZE_PX)})"
                )

        # CL-5: translateY in hover context — scan :hover blocks
        if ':hover' in line or 'translateY' in line:
            for m in RE_TRANSLATE_Y.finditer(line):
                val = float(m.group(1))
                unit = m.group(2)
                if unit == 'px' and val < -1:
                    violations.append(
                        f"{loc(i)}  CL-5  translateY({m.group(1)}px) exceeds max hover lift of -1px"
                    )

    # CL-1: hex colors outside :root block (whole-CSS scan)
    for m in RE_HEX_COLOR.finditer(css):
        if is_inside_root_block(css, m.start()):
            continue
        # also allow hex values in CSS comments
        line_num = css[:m.start()].count('\n')
        line_text = lines[line_num].strip()
        if line_text.startswith('/*') or line_text.startswith('//'):
            continue
        violations.append(
            f"{filename}:{line_offset + line_num + 1}  CL-1  "
            f"Hardcoded hex color {m.group()!r} outside :root token block — use var(--color-*)"
        )

    # CL-2: forbidden spacing px values
    for m in RE_SPACING_PROP.finditer(css):
        line_num = css[:m.start()].count('\n')
        prop_text = m.group()
        for px_m in RE_PX_VALUE.finditer(prop_text):
            px_str = f"{px_m.group(1)}px"
            if px_str in FORBIDDEN_SPACING_PX:
                violations.append(
                    f"{filename}:{line_offset + line_num + 1}  CL-2  "
                    f"Off-grid spacing value {px_str} (forbidden: {sorted(FORBIDDEN_SPACING_PX)}) — use 4px-grid value"
                )

    # CL-4: colored box-shadow
    for i, line in enumerate(lines):
        if not RE_BOX_SHADOW_LINE.search(line):
            continue
        # Gather the full value (may span multiple lines via continuation — take just this line for simplicity)
        # Flag if any color token that isn't rgba(0,0,0,...) or 'transparent' or 'none'
        value_part = line[line.index(':') + 1:] if ':' in line else line
        color_matches = RE_COLOR_IN_SHADOW.findall(value_part)
        for color in color_matches:
            c = color.strip().lower()
            if c in ('none', 'transparent', 'inherit', 'initial', 'unset', 'inset', 'solid'):
                continue
            # Allow CSS variable references — these can't be statically evaluated
            if c.startswith('var('):
                continue
            if RE_RGBA_NEUTRAL.match(color):
                continue
            # Hex or named color or non-neutral rgba
            violations.append(
                f"{filename}:{line_offset + i + 1}  CL-4  "
                f"Colored box-shadow {color!r} — only rgba(0,0,0,x) or transparent are allowed"
            )
            break  # one violation per line is enough

    return violations


def _rel(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def scan_file(path: Path) -> list[str]:
    path = path.resolve()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"{path}: cannot read — {exc}"]

    violations: list[str] = []
    suffix = path.suffix.lower()

    if suffix == '.css':
        violations.extend(lint_css(text, _rel(path)))
    elif suffix in ('.html', '.htm'):
        for start_line, block in extract_style_blocks(text):
            violations.extend(lint_css(block, _rel(path), line_offset=start_line))

    return violations


def main(argv: list[str]) -> int:
    warn_only = "--warn-only" in argv
    paths_raw = [a for a in argv if not a.startswith("--")]

    if paths_raw:
        files = [Path(p) for p in paths_raw]
    else:
        files = (
            sorted(REPO_ROOT.glob("**/*.css"))
            + sorted(REPO_ROOT.glob("**/*.html"))
        )
        # Exclude node_modules, .git, vendor-style dirs if any
        files = [
            f for f in files
            if '.git' not in f.parts and 'node_modules' not in f.parts
        ]

    total = 0
    for path in files:
        violations = scan_file(path)
        for v in violations:
            print(v)
        total += len(violations)

    if total:
        print(f"\n{total} violation(s) found.")
        return 0 if warn_only else 1

    print(f"CSS token lint: {len(files)} file(s) clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
