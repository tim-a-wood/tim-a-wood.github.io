#!/usr/bin/env python3
"""
Archive a policy/guide document out of the active tree into docs/archived-policies/,
record a manifest entry, and produce a reference report (git grep) for manual cleanup.

Used by Agent OS POST /api/archive-document and usable from CLI:
  python3 scripts/archive_policy_document.py agents/marketing/charter.md --reason "superseded"
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ARCHIVE_DIR = "docs/archived-policies"
MANIFEST_NAME = "manifest.json"

GOVERNANCE_ROOT_FILES = frozenset({
    "AGENTS.md",
    "CLAUDE.md",
    "STYLE_GUIDE.md",
})

ARCHIVEABLE_PREFIXES = (
    "docs/",
    "agents/",
    "prompts/",
    "decisions/",
    "research/",
    "knowledge/",
    "playbooks/",
    "templates/",
    "tests/",
    "artifacts/",
    "tools/2d-sprite-and-animation/docs/",
    ".cursor/rules/",
)

ALLOWED_SUFFIXES = frozenset({".md", ".html", ".mdc"})

BLOCKED_EXACT = frozenset({
    "README.md",
    "docs/os-document-library.html",
    "docs/os-documentLibrary.manifest.json",
})


def _norm_rel(p: str) -> str:
    r = p.replace("\\", "/").lstrip("/")
    return r


def is_archivable(
    rel: str,
    *,
    confirm_governance_root: bool = False,
) -> tuple[bool, str]:
    r = _norm_rel(rel)
    if not r or ".." in r or r.startswith("/"):
        return False, "Invalid path"
    low = r.lower()
    if low.startswith("docs/archived-policies/"):
        return False, "Already under archived-policies"
    if r in BLOCKED_EXACT:
        return False, "This path cannot be archived via the dashboard"
    if r.endswith("manifest.json") and "archived-policies" in r:
        return False, "Cannot archive archive manifest"
    suf = Path(r).suffix.lower()
    if suf not in ALLOWED_SUFFIXES:
        return False, "Only .md, .html, and .mdc can be archived"
    if r in GOVERNANCE_ROOT_FILES:
        if not confirm_governance_root:
            return (
                False,
                "Root governance file: set confirmGovernanceRoot true in API body or --i-understand on CLI",
            )
        return True, ""
    if not any(r.startswith(prefix) for prefix in ARCHIVEABLE_PREFIXES):
        return False, "Path is not under an allowed policy/doc prefix"
    return True, ""


def _archive_filename(archive_id: str, original_rel: str) -> str:
    safe = original_rel.replace("/", "__")
    return f"{archive_id}__{safe}"


def _git_grep_refs(repo: Path, rel: str) -> list[str]:
    """Lines 'path:line:match' from working tree; excludes self-file and archive dir."""
    patterns = [rel]
    out_lines: list[str] = []
    try:
        r = subprocess.run(
            [
                "git",
                "grep",
                "-n",
                "-I",
                "--fixed-strings",
                rel,
                "--",
                ".",
                ":!docs/archived-policies",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.stdout:
            for line in r.stdout.strip().splitlines():
                file_part = line.split(":", 2)[0]
                if file_part == rel:
                    continue
                out_lines.append(line)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return sorted(set(out_lines))


def archive_policy_document(
    repo_root: Path,
    rel: str,
    *,
    reason: str = "",
    confirm_governance_root: bool = False,
) -> dict:
    repo_root = repo_root.resolve()
    rel = _norm_rel(rel)
    ok, err = is_archivable(rel, confirm_governance_root=confirm_governance_root)
    if not ok:
        return {"ok": False, "error": err}

    src = (repo_root / rel).resolve()
    try:
        src.relative_to(repo_root)
    except ValueError:
        return {"ok": False, "error": "Path escapes repository"}

    if not src.is_file():
        return {"ok": False, "error": "File not found"}

    refs_before = _git_grep_refs(repo_root, rel)

    archive_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_root = repo_root / ARCHIVE_DIR
    archive_root.mkdir(parents=True, exist_ok=True)

    archived_name = _archive_filename(archive_id, rel)
    dest = archive_root / archived_name
    if dest.exists():
        return {"ok": False, "error": "Archive target already exists"}
    shutil.move(str(src), str(dest))

    manifest_path = archive_root / MANIFEST_NAME
    entries: list[dict] = []
    if manifest_path.is_file():
        try:
            prev = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = list(prev.get("entries", []))
        except json.JSONDecodeError:
            entries = []

    report_name = f"{archive_id}__references.txt"
    report_path = archive_root / report_name
    report_body = (
        f"# Reference hits for archived path\n\n"
        f"- Original: `{rel}`\n"
        f"- Archived as: `{ARCHIVE_DIR}/{archived_name}`\n"
        f"- Id: `{archive_id}`\n\n"
        f"These lines still mention the old path. Update or remove them in a follow-up commit.\n\n"
    )
    if refs_before:
        report_body += "\n".join(refs_before) + "\n"
    else:
        report_body += "(No matches from git grep, or git unavailable. Search manually.)\n"
    report_path.write_text(report_body, encoding="utf-8")

    entry = {
        "id": archive_id,
        "original_path": rel,
        "archived_relative": f"{ARCHIVE_DIR}/{archived_name}",
        "reason": reason or None,
        "archived_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reference_report": f"{ARCHIVE_DIR}/{report_name}",
        "reference_hits_count": len(refs_before),
    }
    entries.append(entry)
    manifest_path.write_text(
        json.dumps({"version": 1, "entries": entries}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    readme = archive_root / "README.md"
    if not readme.is_file():
        readme.write_text(
            "# Archived policies\n\n"
            "Files here were removed from their original locations via the Agent OS "
            "`POST /api/archive-document` action or `scripts/archive_policy_document.py`.\n\n"
            "- **manifest.json** — machine list of archives\n"
            "- **`*__references.txt`** — `git grep` hits for the old path to clean up\n"
            "- Regenerate the document library: `python3 scripts/build_os_document_library.py`\n",
            encoding="utf-8",
        )

    return {
        "ok": True,
        "archive_id": archive_id,
        "original_path": rel,
        "archived_path": str(Path(ARCHIVE_DIR) / archived_name),
        "reference_report": str(Path(ARCHIVE_DIR) / report_name),
        "reference_hits": refs_before[:200],
        "reference_hits_truncated": len(refs_before) > 200,
        "next_steps": [
            "Review reference_report and edit or delete stale mentions",
            "git add -A && git commit (include archive + any reference fixes)",
            "python3 scripts/build_os_document_library.py",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Archive a policy document into docs/archived-policies/")
    ap.add_argument("path", help="Repo-relative path, e.g. agents/marketing/charter.md")
    ap.add_argument("--reason", default="", help="Optional reason note")
    ap.add_argument(
        "--i-understand",
        action="store_true",
        help="Required when archiving AGENTS.md, CLAUDE.md, or STYLE_GUIDE.md",
    )
    args = ap.parse_args()
    repo = Path(__file__).resolve().parent.parent
    rel = _norm_rel(args.path)
    gov = rel in GOVERNANCE_ROOT_FILES
    payload = archive_policy_document(
        repo,
        rel,
        reason=args.reason,
        confirm_governance_root=args.i_understand if gov else True,
    )
    if not payload.get("ok"):
        print(payload.get("error", "error"), file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
