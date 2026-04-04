#!/usr/bin/env python3
"""
Security scanner: implements the automatable subset of escalation-rules.yaml
as actual deterministic checks.

Checks (per docs/reports/agent-guardrail-enforcement-audit-2026-04-02.md):
  SC-1  No credential files tracked by git         (E-2, F-1)
  SC-2  No API key literals in git-tracked files   (E-1, F-1)
  SC-3  .gitignore covers all required patterns    (E-2)
  SC-4  Rate limiting present in server code       (E-4, warn only)

Does NOT require trufflehog — uses stdlib only.

Usage:
  python3 scripts/check_escalation_conditions.py
  python3 scripts/check_escalation_conditions.py --warn-only
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# SC-3: patterns that must appear in .gitignore
REQUIRED_GITIGNORE_PATTERNS = [".env", ".env.*", "*.key", "*.pem", ".env.local"]

# SC-2: API key assignment patterns to scan for in tracked files
# Matches:  SOME_API_KEY = "sk-..."  or  apiKey: "AIza..."  etc.
# Intentionally avoids matching variable *names* used in error messages or comments
API_KEY_PATTERNS = [
    re.compile(r'GEMINI_API_KEY\s*=\s*["\'][A-Za-z0-9_\-]{10,}["\']'),
    re.compile(r'PIXELLAB_API_KEY\s*=\s*["\'][A-Za-z0-9_\-]{10,}["\']'),
    re.compile(r'OPENAI_API_KEY\s*=\s*["\'][A-Za-z0-9_\-]{10,}["\']'),
    re.compile(r'CURSOR_API_KEY\s*=\s*["\'][A-Za-z0-9_\-]{10,}["\']'),
    # Generic patterns: sk- prefix (OpenAI), AIza prefix (Google)
    re.compile(r'["\']sk-[A-Za-z0-9]{20,}["\']'),
    re.compile(r'["\']AIza[A-Za-z0-9_\-]{35,}["\']'),
]

# SC-1: file name patterns that should never be tracked
CREDENTIAL_FILE_PATTERNS = [
    re.compile(r'^\.env($|\.)'),
    re.compile(r'^agent_os\.env$'),
    re.compile(r'\.key$'),
    re.compile(r'\.pem$'),
    re.compile(r'\.p12$'),
    re.compile(r'\.pfx$'),
]

# SC-4: rate limiting indicators in Python server files
RATE_LIMIT_INDICATORS = [
    "flask_limiter",
    "slowapi",
    "rate_limit",
    "RateLimiter",
    "limiter.limit",
    "per_minute",
    "per_hour",
    "requests_per",
]

SERVER_FILES = [
    "scripts/sprite_workbench_server.py",
    "scripts/room_layout_copilot.py",
    "scripts/room_environment_v3.py",
]


def git_tracked_files() -> list[Path]:
    """Return list of all files currently tracked by git."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [REPO_ROOT / p for p in result.stdout.splitlines() if p.strip()]


def check_sc1(tracked: list[Path]) -> list[str]:
    """SC-1: No credential files tracked by git."""
    violations = []
    for path in tracked:
        name = path.name
        # .example and .sample files are intentionally committed as templates
        if name.endswith(".example") or name.endswith(".sample"):
            continue
        for pattern in CREDENTIAL_FILE_PATTERNS:
            if pattern.search(name):
                violations.append(
                    f"SC-1  Credential file tracked by git: {path.relative_to(REPO_ROOT)}"
                )
                break
    return violations


def check_sc2(tracked: list[Path]) -> list[str]:
    """SC-2: No API key literals in tracked source files."""
    violations = []
    scan_extensions = {".py", ".js", ".ts", ".html", ".htm", ".json", ".sh"}

    for path in tracked:
        if path.suffix.lower() not in scan_extensions:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        rel = path.relative_to(REPO_ROOT)
        for pattern in API_KEY_PATTERNS:
            m = pattern.search(text)
            if m:
                line_no = text[:m.start()].count('\n') + 1
                # Mask the matched value for safety
                matched = m.group(0)
                masked = matched[:8] + "***" + matched[-4:] if len(matched) > 12 else "***"
                violations.append(
                    f"SC-2  API key literal in tracked file {rel}:{line_no}  ({masked})"
                )
                break  # one violation per file is enough

    return violations


def check_sc3() -> list[str]:
    """SC-3: .gitignore covers all required credential patterns."""
    violations = []
    gitignore_path = REPO_ROOT / ".gitignore"

    if not gitignore_path.exists():
        return ["SC-3  .gitignore does not exist"]

    content = gitignore_path.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines() if line.strip() and not line.startswith('#')}

    for pattern in REQUIRED_GITIGNORE_PATTERNS:
        if pattern not in lines:
            violations.append(
                f"SC-3  .gitignore missing required pattern: {pattern!r} "
                f"(prevents accidental credential commits)"
            )

    return violations


def check_sc4() -> list[str]:
    """SC-4: Rate limiting present in server files (warn only)."""
    warnings = []
    for rel_path in SERVER_FILES:
        path = REPO_ROOT / rel_path
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        found = any(indicator in text for indicator in RATE_LIMIT_INDICATORS)
        if not found:
            warnings.append(
                f"SC-4  No rate limiting found in {rel_path} — "
                f"Copilot endpoint has no per-IP throttle (financial exposure risk)"
            )

    return warnings


def main(argv: list[str]) -> int:
    warn_only = "--warn-only" in argv

    print("Scanning git-tracked files...")
    tracked = git_tracked_files()
    if not tracked:
        print("  Warning: could not enumerate git-tracked files (is this a git repo?)", file=sys.stderr)

    violations: list[str] = []
    warnings: list[str] = []

    v = check_sc1(tracked)
    violations.extend(v)

    v = check_sc2(tracked)
    violations.extend(v)

    v = check_sc3()
    violations.extend(v)

    w = check_sc4()
    warnings.extend(w)

    if violations:
        print(f"\n{len(violations)} security violation(s):")
        for v in violations:
            print(f"  FAIL  {v}")

    if warnings:
        print(f"\n{len(warnings)} security warning(s):")
        for w in warnings:
            print(f"  WARN  {w}")

    if not violations and not warnings:
        print("Security scan: clean.")

    if violations:
        return 0 if warn_only else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
