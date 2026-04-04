#!/usr/bin/env python3
"""
Check HTML tool pages for required structural elements and forbidden patterns.

Checks (per docs/reports/agent-guardrail-enforcement-audit-2026-04-02.md):
  HS-1  Content-Security-Policy meta tag present              (E-5)
  HS-2  Required Google Fonts loaded                          (A-5)
  HS-3  :focus-visible rule present in <style> block          (A-12, amended: all pages, not just new)
  HS-4  canvas elements have image-rendering: pixelated        (A-10)
  HS-5  No framework script imports                            (A-7)
  HS-6  No build artifact patterns                             (A-8)
  HS-7  innerHTML site inventory (warn only — not a block)    (E-6)

Scans all .html files in the repo root and tools/ directory.

Usage:
  python3 scripts/check_html_structure.py              # all tool HTML pages
  python3 scripts/check_html_structure.py file.html    # specific file(s)
  python3 scripts/check_html_structure.py --warn-only  # exit 0 even on failures
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FONTS = ["Bebas+Neue", "Plus+Jakarta+Sans", "DM+Mono"]

FORBIDDEN_FRAMEWORKS = re.compile(
    r'<script[^>]+src=["\'][^"\']*'
    r'(react|vue|angular|jquery|svelte|lodash|bootstrap|tailwind)'
    r'[^"\']*["\']',
    re.IGNORECASE,
)

FORBIDDEN_BUILD = re.compile(
    r'(webpack|vite\.config|rollup\.config|babel\.config|dist/bundle|\.bundle\.js)',
    re.IGNORECASE,
)

RE_CANVAS = re.compile(r'<canvas\b[^>]*>', re.IGNORECASE)
RE_INNER_HTML = re.compile(r'\.innerHTML\s*(?:=|\+=)', re.IGNORECASE)
RE_CSP = re.compile(r'<meta[^>]+http-equiv=["\']Content-Security-Policy["\']', re.IGNORECASE)
RE_FOCUS_VISIBLE = re.compile(r':focus-visible', re.IGNORECASE)


def check_canvas_rendering(html: str, filename: str) -> list[str]:
    """
    For each <canvas> element, check whether image-rendering: pixelated is set.
    We check:
      1. Inline style on the canvas tag itself
      2. A canvas { image-rendering: pixelated } rule anywhere in <style> blocks
      3. A .classname rule where classname is one of the canvas's classes
    This is a best-effort static check — dynamic class assignment can't be caught.
    """
    violations: list[str] = []

    # Collect all style block content
    style_content = " ".join(
        m.group(1)
        for m in re.finditer(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE)
    )
    has_canvas_rule = bool(re.search(
        r'canvas\s*\{[^}]*image-rendering\s*:\s*pixelated',
        style_content, re.IGNORECASE | re.DOTALL
    ))

    lines = html.split('\n')
    for i, line in enumerate(lines):
        for m in RE_CANVAS.finditer(line):
            tag = m.group(0)
            lineno = i + 1

            # Check inline style
            inline = re.search(r'style=["\']([^"\']*)["\']', tag)
            if inline and 'image-rendering' in inline.group(1).lower():
                continue

            # Check if there's a canvas { } rule in stylesheets
            if has_canvas_rule:
                continue

            # Check id/class-based rules
            id_m = re.search(r'id=["\']([^"\']+)["\']', tag)
            class_m = re.search(r'class=["\']([^"\']+)["\']', tag)
            selector_hit = False
            if id_m:
                eid = id_m.group(1)
                if re.search(rf'#{re.escape(eid)}\s*\{{[^}}]*image-rendering', style_content, re.IGNORECASE | re.DOTALL):
                    selector_hit = True
            if class_m and not selector_hit:
                for cls in class_m.group(1).split():
                    if re.search(rf'\.{re.escape(cls)}\s*\{{[^}}]*image-rendering', style_content, re.IGNORECASE | re.DOTALL):
                        selector_hit = True
                        break

            if not selector_hit:
                violations.append(
                    f"{filename}:{lineno}  HS-4  <canvas> missing 'image-rendering: pixelated' "
                    f"(check inline style, canvas rule, or class/id rule in stylesheet)"
                )

    return violations


def check_file(path: Path) -> tuple[list[str], list[str]]:
    """Return (blocking_violations, warnings)."""
    violations: list[str] = []
    warnings: list[str] = []

    try:
        html = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"{path}: cannot read — {exc}"], []

    try:
        rel = str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        rel = str(path)

    # HS-1: Content-Security-Policy
    if not RE_CSP.search(html):
        violations.append(
            f"{rel}  HS-1  No Content-Security-Policy meta tag found"
        )

    # HS-2: Required fonts
    for font in REQUIRED_FONTS:
        if font not in html:
            violations.append(
                f"{rel}  HS-2  Required Google Font not loaded: {font!r}"
            )

    # HS-3: :focus-visible
    if not RE_FOCUS_VISIBLE.search(html):
        violations.append(
            f"{rel}  HS-3  No ':focus-visible' rule found — required on all tool pages"
        )

    # HS-4: canvas image-rendering
    violations.extend(check_canvas_rendering(html, rel))

    # HS-5: framework imports
    m = FORBIDDEN_FRAMEWORKS.search(html)
    if m:
        line_no = html[:m.start()].count('\n') + 1
        violations.append(
            f"{rel}:{line_no}  HS-5  Forbidden framework import detected: {m.group()[:80]!r}"
        )

    # HS-6: build artifact patterns
    m = FORBIDDEN_BUILD.search(html)
    if m:
        line_no = html[:m.start()].count('\n') + 1
        violations.append(
            f"{rel}:{line_no}  HS-6  Build tooling reference detected: {m.group()!r}"
        )

    # HS-7: innerHTML inventory (warn only)
    lines = html.split('\n')
    for i, line in enumerate(lines):
        for m in RE_INNER_HTML.finditer(line):
            warnings.append(
                f"{rel}:{i+1}  HS-7  innerHTML assignment — verify user strings go through escapeHtml(): "
                f"{line.strip()[:100]}"
            )

    return violations, warnings


def tool_html_files() -> list[Path]:
    """Return all .html files in repo root and tools/ — excludes index.html (game runtime)."""
    candidates = (
        list(REPO_ROOT.glob("*.html"))
        + list(REPO_ROOT.glob("tools/**/*.html"))
    )
    # index.html is the game canvas runtime, not a tool page — exclude from tool checks
    return [
        f for f in candidates
        if f.name != "index.html" or "tools" in str(f)
    ]


def main(argv: list[str]) -> int:
    warn_only = "--warn-only" in argv
    paths_raw = [a for a in argv if not a.startswith("--")]

    if paths_raw:
        files = [Path(p).resolve() for p in paths_raw]
    else:
        files = tool_html_files()

    if not files:
        print("check_html_structure: no HTML files found", file=sys.stderr)
        return 0

    total_violations = 0
    total_warnings = 0

    for path in files:
        violations, warnings = check_file(path)
        if violations or warnings:
            try:
                rel = str(path.relative_to(REPO_ROOT))
            except ValueError:
                rel = str(path)
            if violations:
                print(f"\n{rel}  [{len(violations)} blocking violation(s)]")
                for v in violations:
                    print(f"  {v}")
            if warnings:
                print(f"\n{rel}  [{len(warnings)} innerHTML warning(s)]")
                for w in warnings:
                    print(f"  WARN  {w}")
        else:
            try:
                rel = str(path.relative_to(REPO_ROOT))
            except ValueError:
                rel = str(path)
            print(f"{rel}  OK")

        total_violations += len(violations)
        total_warnings += len(warnings)

    print(f"\n{total_violations} blocking violation(s), {total_warnings} innerHTML warning(s) across {len(files)} file(s).")

    if total_violations:
        return 0 if warn_only else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
