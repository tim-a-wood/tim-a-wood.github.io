#!/usr/bin/env python3
"""
Backfill modified_at and modified_by on every priority/opportunity item in
all agent status JSON files, using git log to determine when each item last
changed and who (agent slug or "founder") made the change.

Run from repo root:
  python3 scripts/backfill_modified_metadata.py
"""

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

STATUS_FILES = [f.name for f in REPO_ROOT.glob("*-status.json")]
STATUS_FILES.append("orchestration-status.json")
STATUS_FILES = sorted(set(STATUS_FILES))

# Map commit message prefix/keyword → agent slug
AGENT_PATTERNS = [
    (r"\bDesign\b",          "design"),
    (r"\bMarketing\b",       "marketing"),
    (r"\bStrategy\b",        "strategy"),
    (r"\bResearch\b",        "research"),
    (r"\bEngineering\b|\bDev\b", "engineering"),
    (r"\bAnimation\b",       "animation"),
    (r"\bLevel.?Design\b",   "level-design"),
    (r"\bQA\b",              "qa"),
    (r"\bGame.?Director\b",  "game-director"),
    (r"\bGame.?Systems\b",   "game-systems"),
    (r"\bFinance\b",         "finance"),
    (r"\bLegal\b",           "legal"),
    (r"\bCreative\b",        "creative"),
    (r"\bNarrative\b",       "narrative"),
    (r"\bAudio\b",           "audio"),
    (r"\bSupport\b",         "support"),
    (r"\bAnalytics\b",       "analytics"),
    (r"\bCybersecurity\b",   "cybersecurity"),
    (r"\bOrchestrat\w*\b",   "orchestrator"),
]


def infer_agent(commit_msg: str, file_slug: str) -> str:
    """Try to map commit message to an agent slug; fall back to file_slug or founder."""
    # Check leading prefix like "Design: ..." or "Marketing: ..."
    lead = commit_msg.split(":")[0].strip()
    for pattern, slug in AGENT_PATTERNS:
        if re.search(pattern, lead, re.IGNORECASE):
            return slug
    # No clear match — attribute to the owning agent (file slug)
    return file_slug if file_slug else "founder"


def file_slug_from_name(fname: str) -> str:
    """design-status.json → design; orchestration-status.json → orchestrator"""
    base = fname.replace("-status.json", "")
    if base == "orchestration":
        return "orchestrator"
    return base


def get_commit_log(fname: str) -> list[dict]:
    """Return list of {hash, iso_date, msg} for all commits touching fname, newest first."""
    try:
        out = subprocess.check_output(
            ["git", "log", "--format=%H|%aI|%s", "--", fname],
            cwd=REPO_ROOT,
            text=True,
        )
    except subprocess.CalledProcessError:
        return []
    commits = []
    for line in out.strip().splitlines():
        if "|" not in line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        commits.append({"hash": parts[0], "iso_date": parts[1], "msg": parts[2]})
    return commits


def get_file_at_commit(commit_hash: str, fname: str):
    """Read the JSON content of fname at a given commit (returns None on error)."""
    try:
        raw = subprocess.check_output(
            ["git", "show", f"{commit_hash}:{fname}"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return json.loads(raw)
    except Exception:
        return None


def item_fingerprint(item: dict) -> str:
    """Stable string representation of an item for change detection (excludes meta fields)."""
    skip = {"modified_at", "modified_by"}
    filtered = {k: v for k, v in item.items() if k not in skip}
    return json.dumps(filtered, sort_keys=True)


def find_last_change(item_id, array_key: str, commits: list, fname: str):
    """
    Walk the commit log to find the newest commit where this item last changed.
    Returns the commit dict or None.
    """
    prev_fp = None
    for i, commit in enumerate(commits):
        data = get_file_at_commit(commit["hash"], fname)
        if data is None:
            continue
        items = data.get(array_key, [])
        match = next(
            (it for it in items if str(it.get("id", "")) == str(item_id)),
            None,
        )
        if match is None:
            # Item didn't exist in this commit — the previous commit added it
            if i > 0:
                return commits[i - 1]
            return commit
        fp = item_fingerprint(match)
        if prev_fp is not None and fp != prev_fp:
            # Changed between this commit and the previous one
            return commits[i - 1]
        prev_fp = fp
    # Reached the beginning of history — oldest commit that has the item
    return commits[-1] if commits else None


def backfill_file(fname: str) -> int:
    """Backfill modified_at/modified_by for all items in fname. Returns count updated."""
    fpath = REPO_ROOT / fname
    if not fpath.is_file():
        return 0

    slug = file_slug_from_name(fname)
    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [SKIP] Cannot parse {fname}: {e}")
        return 0

    commits = get_commit_log(fname)
    if not commits:
        print(f"  [SKIP] No git history for {fname}")
        return 0

    updated = 0
    for array_key in ("priorities", "opportunities"):
        items = data.get(array_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            # Skip if already stamped
            if item.get("modified_at") and item.get("modified_by"):
                continue
            item_id = item.get("id")
            if item_id is None:
                continue
            change_commit = find_last_change(item_id, array_key, commits, fname)
            if change_commit:
                item["modified_at"] = change_commit["iso_date"]
                item["modified_by"] = infer_agent(change_commit["msg"], slug)
            else:
                item["modified_at"] = commits[0]["iso_date"]
                item["modified_by"] = slug
            updated += 1

    if updated:
        fpath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  Updated {updated} item(s) in {fname}")
    else:
        print(f"  No items needed updating in {fname}")
    return updated


def main():
    total = 0
    for fname in STATUS_FILES:
        print(f"Processing {fname}…")
        total += backfill_file(fname)
    print(f"\nDone. {total} item(s) stamped with modified_at/modified_by.")


if __name__ == "__main__":
    main()
