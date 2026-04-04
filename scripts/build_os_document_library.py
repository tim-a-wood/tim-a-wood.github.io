#!/usr/bin/env python3
"""
Scan the repo for policy-like documents (charters, guides, plans, reports),
assign categories, detect duplicate basenames / identical content, and emit:
  - docs/os-documentLibrary.manifest.json
  - docs/os-document-library.html
  - docs/reports/os-document-library-dedupe-notes.md

Run from repo root:
  python3 scripts/build_os_document_library.py
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parent.parent
MANIFEST_OUT = REPO / "docs" / "os-documentLibrary.manifest.json"
HTML_OUT = REPO / "docs" / "os-document-library.html"
DEDUPE_MD_OUT = REPO / "docs" / "reports" / "os-document-library-dedupe-notes.md"

SKIP_DIR_NAMES = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache",
})
SKIP_PATH_FRAGMENTS = (
    ".claude/worktrees/",
    "/.git/",
    "tools/miniconda3/",
    "/miniconda3/",
    "tools/ComfyUI",
    "/site-packages/",
    "/.venv/",
    "tools/2d-sprite-and-animation/projects-data/",
)
# Excluded from the policy library index (working notes, redundant exports, sprite archive pages).
LIBRARY_EXCLUDE_SUBSTRINGS = (
    "tools/2d-sprite-and-animation/docs/archive/",
    "/room-environment-v3-slot-checkpoint-",
    "/room-environment-v3-planner-checkpoint-",
    "agent-review-request-",
    "-checkpoint-packet-",
    "agent-review-index-room-environment",
    "docs/reports/os-document-library-dedupe-notes.md",
    ".cursor/connector-conversations/",
    "issues/",
    "samples/",
    "tests/fixtures/",
)
# Only these HTML entries are catalogued (operational dashboards are not policy documents).
LIBRARY_HTML_ALLOW = frozenset({
    "docs/brand-charter.html",
    "docs/mv-business-brand-guide-pamphlet.html",
})
# Only these artifact markdowns are catalogued (rest are transient exports / digests).
ARTIFACT_INDEX_ALLOW = frozenset({
    "artifacts/ashen-hollow-art-bible-v0.2.md",
})
# Shared filenames that are intentionally repeated across directories (not organizational duplicates).
IGNORE_DUP_BASE = frozenset({
    "charter.md",
    "readme.md",
    "license.md",
    "index.html",
    "meta.json",
})
MAX_BYTES = 4_000_000
TEXT_SUFFIXES = frozenset({".md", ".mdc", ".html"})

CATEGORY_META: dict[str, dict[str, str]] = {
    "executive_brand": {
        "label": "Executive & brand",
        "description": "Company charter, brand guide, business plan, stakeholder sign-offs, art bible — formal business-facing documents.",
    },
    "repository_governance": {
        "label": "Repository governance",
        "description": "Root rules for humans and AI tools: AGENTS, Claude, style guide, Cursor IDE rules.",
    },
    "agent_charters": {
        "label": "Agent operating charters",
        "description": "Per-role scope for Agent OS specialists (scoped below repository governance).",
    },
    "strategy_product": {
        "label": "Strategy & product direction",
        "description": "Prompts, README, world map / progression / MVP constraints — product intent and planning.",
    },
    "engineering_specs": {
        "label": "Engineering & delivery specs",
        "description": "Room tooling, pipelines, diagrams, integration specs — how the product is built.",
    },
    "sprite_tooling": {
        "label": "Sprite workbench documentation",
        "description": "Authoring docs for the 2D sprite tool (excludes archived design rounds).",
    },
    "research": {
        "label": "Research",
        "description": "Research library, findings, dashboard inputs.",
    },
    "decisions": {
        "label": "Decision log",
        "description": "Logged decisions under decisions/.",
    },
    "operations": {
        "label": "Operations & procedures",
        "description": "Playbooks, templates, internal knowledge base articles.",
    },
    "quality_testing": {
        "label": "Quality & acceptance",
        "description": "Acceptance criteria and test documentation (not day-to-day test run logs).",
    },
    "reports_reference": {
        "label": "Audits & significant reports",
        "description": "Durable reviews, audits, and syntheses — not working-session checkpoint drafts.",
    },
    "other": {
        "label": "Other",
        "description": "Remaining indexed documents; consider recategorizing or archiving.",
    },
}

DISPLAY_ORDER = [
    "executive_brand",
    "repository_governance",
    "agent_charters",
    "strategy_product",
    "engineering_specs",
    "sprite_tooling",
    "research",
    "decisions",
    "operations",
    "quality_testing",
    "reports_reference",
    "other",
]

DEFAULT_OPEN_CATEGORIES = frozenset({"executive_brand", "repository_governance"})

# Formal display titles for executive and critical documents (path -> title).
FORMAL_DISPLAY_TITLES: dict[str, str] = {
    "docs/brand-charter.html": "Company brand charter (executive summary)",
    "docs/mv-business-brand-guide-pamphlet.html": "Business brand guide (operational handbook)",
    "docs/reports/business-brand-guide-v0.2-stakeholder-reviews-2026-04-02.md": (
        "Business brand guide v0.2 — specialist stakeholder sign-off record"
    ),
    "docs/reports/initial-business-plan-2026-04-01.md": "Initial business plan (working draft)",
    "docs/reports/agent-guardrail-enforcement-audit-2026-04-02.md": (
        "Agent guardrail enforcement — audit memorandum"
    ),
    "docs/reports/design-review-ashen-hollow-art-bible-v0.2.md": (
        "Design review memorandum — Ashen Hollow art bible v0.2"
    ),
    "docs/reports/room-environment-v3-executive-summary-2026-04-01.md": (
        "Room environment pipeline v3 — executive summary"
    ),
    "docs/reports/room-environment-v3-engineering-review-2026-04-01.md": (
        "Room environment v3 — engineering review memorandum"
    ),
    "docs/reports/room-environment-v3-design-review-2026-04-01.md": (
        "Room environment v3 — design review memorandum"
    ),
    "docs/reports/room-environment-v3-qa-review-2026-04-01.md": (
        "Room environment v3 — QA review memorandum"
    ),
    "docs/reports/room-environment-v3-creative-review-2026-04-01.md": (
        "Room environment v3 — creative review memorandum"
    ),
    "docs/reports/room-environment-v3-game-director-review-2026-04-01.md": (
        "Room environment v3 — game director review memorandum"
    ),
    "docs/reports/room-environment-v3-orchestrator-synthesis-2026-04-01.md": (
        "Room environment v3 — orchestrator synthesis"
    ),
    "docs/reports/room-environment-v3-stakeholder-review-kickoff-2026-04-01.md": (
        "Room environment v3 — stakeholder review kickoff record"
    ),
    "artifacts/ashen-hollow-art-bible-v0.2.md": "Art bible — Ashen Hollow v0.2 (authoritative text)",
    "docs/pixel-art-quality-standards.md": (
        "Pixel art quality standards — production gate (Animation)"
    ),
    "AGENTS.md": "Repository governance — agent operating system rules",
    "CLAUDE.md": "Repository governance — Claude Code rules",
    "STYLE_GUIDE.md": "Design system — canonical UI style guide",
    "README.md": "Project overview — Ashen Hollow & toolchain",
    "tests/README.md": "Testing — handbook (tests/)",
    "tests/acceptance_tests.md": "Quality — acceptance test specification",
}


def _should_skip_dir(path: Path) -> bool:
    for p in path.parts:
        if p in SKIP_DIR_NAMES:
            return True
    s = str(path.as_posix())
    for frag in SKIP_PATH_FRAGMENTS:
        if frag in s:
            return True
    return False


def _library_exclude_path(rp: str) -> bool:
    if rp == "tests/test_report.md":
        return True
    if rp.startswith(".claude/"):
        return True
    if rp.startswith(".cursor/") and not rp.startswith(".cursor/rules/"):
        return True
    low = rp.lower()
    for frag in LIBRARY_EXCLUDE_SUBSTRINGS:
        if frag.lower() in low:
            return True
    if rp.startswith("artifacts/"):
        return rp not in ARTIFACT_INDEX_ALLOW
    return False


def _iter_doc_files() -> list[Path]:
    out: list[Path] = []
    for p in REPO.rglob("*"):
        if p.is_dir():
            continue
        try:
            rel = p.relative_to(REPO)
        except ValueError:
            continue
        rp = rel.as_posix()
        if rp.startswith("docs/archived-policies/"):
            continue
        if _library_exclude_path(rp):
            continue
        if _should_skip_dir(rel.parent):
            continue
        suf = p.suffix.lower()
        if suf not in TEXT_SUFFIXES:
            continue
        if suf == ".html" and rp not in LIBRARY_HTML_ALLOW:
            continue
        if p.stat().st_size > MAX_BYTES:
            continue
        out.append(p)
    return sorted(out, key=lambda x: str(x).lower())


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def categorize(rel_posix: str) -> str:
    r = rel_posix
    low = r.lower()
    if r in ARTIFACT_INDEX_ALLOW or (
        r.startswith("docs/brand-charter")
        or "mv-business-brand-guide" in low
        or r.startswith("docs/reports/business-brand-guide")
        or "initial-business-plan" in low
        or r.startswith("docs/initial-business")
    ):
        return "executive_brand"
    if r in ("AGENTS.md", "CLAUDE.md", "STYLE_GUIDE.md"):
        return "repository_governance"
    if r.startswith(".cursor/rules/") and r.endswith(".mdc"):
        return "repository_governance"
    if r.startswith("agents/") and r.endswith("/charter.md"):
        return "agent_charters"
    if r.startswith("agents/"):
        return "operations"
    if r.startswith("reporting/"):
        return "operations"
    if r == "room-rules.md":
        return "engineering_specs"
    if r.startswith("tools/2d-sprite-and-animation/") and r.endswith("README.md"):
        return "sprite_tooling"
    if r.startswith("prompts/"):
        return "strategy_product"
    if r == "README.md" or r.startswith("tests/README.md"):
        return "strategy_product"
    if any(r.startswith(f"docs/{name}") for name in (
        "map-", "gate-", "progression-", "branch-", "navigation-",
        "readability-", "room-layout-iteration",
    )):
        return "strategy_product"
    if r == "docs/pixel-art-quality-standards.md":
        return "sprite_tooling"
    if r.startswith("docs/room-") or r.startswith("docs/sprite-workbench") or r.startswith("docs/cross-tool"):
        return "engineering_specs"
    if r.startswith("docs/analytics-") or r.startswith("docs/design/"):
        return "engineering_specs"
    if r.startswith("docs/diagrams/"):
        return "engineering_specs"
    if r.startswith("docs/room-environment"):
        return "engineering_specs"
    if r.startswith("tools/2d-sprite-and-animation/docs/"):
        return "sprite_tooling"
    if r.startswith("research/"):
        return "research"
    if r.startswith("decisions/"):
        return "decisions"
    if r.startswith("playbooks/") or r.startswith("knowledge/") or r.startswith("templates/"):
        return "operations"
    if r.startswith("tests/acceptance"):
        return "quality_testing"
    if r.startswith("docs/reports/"):
        return "reports_reference"
    if r.startswith("docs/") and low.endswith((".md", ".mdc")):
        return "engineering_specs"
    return "other"


def _title_from_path(rel: Path) -> str:
    rp = rel.as_posix()
    if rp in FORMAL_DISPLAY_TITLES:
        return FORMAL_DISPLAY_TITLES[rp]
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "agents" and rel.name == "charter.md":
        role = parts[1].replace("-", " ").replace("_", " ").title()
        return f"Operating charter — {role}"
    stem = rel.stem.replace("-", " ").replace("_", " ")
    return stem[:1].upper() + stem[1:] if stem else str(rel)


def _doc_open_href(target_rel_posix: str, *, fmt: str) -> str:
    """Href for opening a catalog entry in the browser (supervisor origin)."""
    if fmt == "html":
        return "../" + target_rel_posix
    return "/view/markdown?path=" + quote(target_rel_posix, safe="")


def build() -> dict:
    files = _iter_doc_files()
    by_cat: dict[str, list[dict]] = defaultdict(list)
    basename_map: dict[str, list[str]] = defaultdict(list)

    for p in files:
        rel = p.relative_to(REPO)
        rp = rel.as_posix()
        basename_map[rel.name].append(rp)
        cat = categorize(rp)
        by_cat[cat].append({
            "id": re.sub(r"[^a-z0-9]+", "-", rp.lower()).strip("-"),
            "title": _title_from_path(rel),
            "path": rp,
            "format": "html" if p.suffix.lower() == ".html" else "markdown",
            "date_modified": datetime.fromtimestamp(
                p.stat().st_mtime, tz=timezone.utc
            ).strftime("%Y-%m-%d"),
        })

    for cat in by_cat:
        by_cat[cat].sort(key=lambda x: (x["title"].lower(), x["path"]))

    duplicate_groups: list[dict] = []
    for name, paths in sorted(basename_map.items()):
        if len(paths) < 2:
            continue
        if name.lower() in IGNORE_DUP_BASE:
            continue
        hashes = {}
        for rp in paths:
            h = _hash_file(REPO / rp)
            hashes.setdefault(h, []).append(rp)
        if len(hashes) == 1:
            h = next(iter(hashes))
            lst = hashes[h]
            pick = min(lst, key=lambda x: (len(x), x))
            duplicate_groups.append({
                "basename": name,
                "same_content": True,
                "canonical_path": pick,
                "paths": lst,
            })
        else:
            duplicate_groups.append({
                "basename": name,
                "same_content": False,
                "paths": paths,
                "note": "Same filename, different contents — review both; do not assume parity.",
            })

    relationship_notes = [
        "Executive tier: docs/brand-charter.html (summary) and docs/mv-business-brand-guide-pamphlet.html (handbook) are paired; stakeholder sign-offs live under docs/reports/business-brand-guide-*.md.",
        "Repository governance (AGENTS.md, CLAUDE.md, STYLE_GUIDE.md, .cursor/rules) constrains all agents; operating charters (agents/*/charter.md) define per-role scope beneath that layer.",
        "This index excludes sprite tool archive HTML, room-environment checkpoint working papers, agent “review request” shells, day-to-day test_report.md, and most artifacts/ exports — rebuild after policy changes.",
        "Documents under .claude/worktrees/ are excluded; repo-root paths are canonical.",
        "To retire a policy: Archive on a card or scripts/archive_policy_document.py — files move to docs/archived-policies/; rebuild the library to refresh this page.",
    ]

    categories_out = []
    for cid in DISPLAY_ORDER:
        meta = CATEGORY_META[cid]
        items = by_cat.get(cid, [])
        if not items:
            continue
        categories_out.append({
            "id": cid,
            **meta,
            "default_open": cid in DEFAULT_OPEN_CATEGORIES,
            "items": items,
        })

    manifest = {
        "schema_version": "1.0",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo_root_note": "Paths are relative to repository root.",
        "categories": categories_out,
        "duplicate_groups": duplicate_groups,
        "relationship_notes": relationship_notes,
        "stats": {
            "files_indexed": sum(len(c["items"]) for c in categories_out),
            "categories_non_empty": len(categories_out),
        },
    }
    return manifest


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_html(manifest: dict) -> str:
    parts = []
    parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Agent OS — Guides &amp; policies library</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #050709;
      --panel: rgba(4,6,10,0.96);
      --accent: #00e8c8;
      --accent-soft: rgba(0,232,200,0.08);
      --text: #cce8e0;
      --muted: #5d7870;
      --stroke: rgba(0,232,200,0.07);
      --line: rgba(0,232,200,0.10);
      --line-strong: rgba(0,232,200,0.18);
      --good: #4ade80;
      --good-soft: rgba(74,222,128,0.12);
      --warning: #d29922;
      --warning-soft: rgba(210,153,34,0.16);
      --error: #f85149;
      --error-soft: rgba(248,81,73,0.16);
      --font-sans: "Plus Jakarta Sans", -apple-system, sans-serif;
      --font-display: "Bebas Neue", sans-serif;
      --font-mono: "DM Mono", ui-monospace, monospace;
      --font-size-xs: 11px;
      --font-size-sm: 13px;
      --font-size-base: 14px;
      --font-size-lg: 18px;
      --space-2: 8px;
      --space-3: 12px;
      --space-4: 16px;
      --space-5: 24px;
      --space-6: 32px;
      --radius-tight: 14px;
      --radius-card: 18px;
      --radius-full: 999px;
      --shadow-md: 0 6px 20px rgba(0,0,0,0.26);
      --transition-base: 200ms ease;
    }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: var(--font-sans);
      font-size: var(--font-size-base);
      line-height: 1.45;
      padding: var(--space-4) var(--space-4) var(--space-6);
      margin: 0 auto;
      max-width: min(1480px, calc(100vw - 24px));
    }
    .library-shell {
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
      gap: var(--space-4);
      align-items: start;
    }
    .library-nav {
      position: sticky;
      top: var(--space-4);
      align-self: start;
      border: 1px solid var(--stroke);
      border-radius: var(--radius-card);
      background: rgba(255,255,255,0.02);
      padding: var(--space-3);
      max-height: calc(100vh - 32px);
      overflow-y: auto;
    }
    .library-nav-title {
      font-size: var(--font-size-xs);
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: var(--space-3);
    }
    .library-nav ul { list-style: none; }
    .library-nav li { margin-bottom: 4px; }
    .library-nav a {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: var(--space-2);
      padding: 8px 10px;
      border-radius: var(--radius-tight);
      color: var(--text);
      text-decoration: none;
      font-size: var(--font-size-sm);
      transition: background var(--transition-base);
    }
    .library-nav a:hover { background: rgba(255,255,255,0.06); }
    .library-nav .nav-count {
      font-family: var(--font-mono);
      font-size: var(--font-size-xs);
      color: var(--muted);
      flex-shrink: 0;
    }
    .library-main { min-width: 0; }
    @media (max-width: 900px) {
      .library-shell { grid-template-columns: 1fr; }
      .library-nav {
        position: static;
        max-height: none;
      }
    }
    :focus-visible {
      outline: 2px solid rgba(0,232,200,0.35);
      outline-offset: 2px;
    }
    .page-head {
      margin-bottom: var(--space-4);
    }
    .eyebrow {
      font-size: var(--font-size-xs);
      font-weight: 700;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: var(--space-2);
    }
    h1 {
      font-family: var(--font-display);
      font-size: var(--font-size-lg);
      font-weight: 400;
      letter-spacing: 0.06em;
      margin-bottom: var(--space-3);
    }
    .lede { color: var(--muted); font-size: var(--font-size-sm); margin-bottom: var(--space-3); max-width: none; }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-3);
      align-items: center;
      margin-bottom: var(--space-4);
    }
    .search {
      flex: 1;
      min-width: 200px;
      min-height: 44px;
      padding: 10px 12px;
      border-radius: var(--radius-tight);
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      font-family: var(--font-sans);
      font-size: var(--font-size-sm);
      transition: border-color var(--transition-base), background var(--transition-base);
    }
    .search:hover { border-color: var(--line-strong); }
    .meta-chip {
      font-family: var(--font-mono);
      font-size: var(--font-size-xs);
      color: var(--muted);
      padding: 8px 12px;
      border-radius: var(--radius-full);
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.03);
    }
    .callout {
      border-left: 3px solid var(--accent);
      padding: var(--space-3) var(--space-4);
      margin-bottom: var(--space-5);
      background: var(--accent-soft);
      border-radius: 0 var(--radius-tight) var(--radius-tight) 0;
      font-size: var(--font-size-sm);
    }
    .callout-warn {
      border-left-color: var(--warning);
      background: var(--warning-soft);
    }
    details.library-cat {
      border: 1px solid var(--stroke);
      border-radius: var(--radius-card);
      background: rgba(255,255,255,0.02);
      margin-bottom: var(--space-2);
      box-shadow: var(--shadow-md);
    }
    details.library-cat summary {
      list-style: none;
      cursor: pointer;
      padding: var(--space-3) var(--space-4);
      font-family: var(--font-display);
      letter-spacing: 0.05em;
      font-size: var(--font-size-sm);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-3);
      transition: background var(--transition-base);
    }
    details.library-cat summary::-webkit-details-marker { display: none; }
    details.library-cat summary:hover { background: rgba(255,255,255,0.04); }
    .cat-count {
      font-family: var(--font-mono);
      font-size: var(--font-size-xs);
      color: var(--muted);
      padding: 4px 8px;
      border-radius: var(--radius-full);
      border: 1px solid var(--line);
    }
    .cat-desc {
      padding: 0 var(--space-4) var(--space-2);
      font-size: var(--font-size-xs);
      color: var(--muted);
      line-height: 1.4;
    }
    .card-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: var(--space-2);
      padding: 0 var(--space-4) var(--space-3);
    }
    .doc-card {
      border: 1px solid var(--line);
      border-radius: var(--radius-tight);
      padding: var(--space-2) var(--space-3);
      background: rgba(0,0,0,0.12);
      transition: border-color var(--transition-base), transform var(--transition-base);
    }
    .doc-card:hover {
      border-color: var(--line-strong);
      transform: translateY(-1px);
    }
    .doc-card.hidden { display: none; }
    .doc-card-title { font-weight: 600; font-size: var(--font-size-xs); margin-bottom: var(--space-2); line-height: 1.35; }
    .doc-card-title a { color: var(--accent); text-decoration: none; }
    .doc-card-title a:hover { text-decoration: underline; }
    .doc-card-path {
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--muted);
      word-break: break-all;
      margin-bottom: var(--space-2);
    }
    .badges { display: flex; flex-wrap: wrap; gap: 8px; }
    .badge {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 4px 8px;
      border-radius: var(--radius-full);
      border: 1px solid var(--line);
      color: var(--muted);
    }
    .badge-html { color: var(--good); border-color: rgba(74,222,128,0.35); background: var(--good-soft); }
    .dup-note { font-size: var(--font-size-xs); color: var(--warning); margin-top: var(--space-2); }
    footer { margin-top: var(--space-6); font-size: var(--font-size-xs); color: var(--muted); font-family: var(--font-mono); }
    .view-toggle {
      display: inline-flex;
      border: 1px solid var(--line);
      border-radius: var(--radius-tight);
      overflow: hidden;
      flex-shrink: 0;
    }
    .view-toggle-btn {
      min-height: 44px;
      min-width: 72px;
      padding: 10px 12px;
      border: none;
      border-radius: 0;
      background: rgba(255,255,255,0.04);
      color: var(--text);
      font-family: var(--font-sans);
      font-size: var(--font-size-sm);
      font-weight: 600;
      cursor: pointer;
      transition: background var(--transition-base), color var(--transition-base),
        box-shadow var(--transition-base);
    }
    .view-toggle-btn + .view-toggle-btn { border-left: 1px solid var(--line); }
    .view-toggle-btn:hover { background: rgba(255,255,255,0.08); }
    .view-toggle-btn[aria-pressed="true"] {
      background: rgba(0,232,200,0.12);
      color: var(--accent);
      box-shadow: inset 0 0 0 1px rgba(0,232,200,0.08);
    }
    .doc-card-date {
      display: none;
      font-family: var(--font-mono);
      font-size: var(--font-size-xs);
      color: var(--muted);
      margin-top: var(--space-2);
    }
    body.view-list .card-grid {
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
    }
    body.view-list .doc-card {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      grid-template-rows: auto auto auto;
      align-items: start;
      column-gap: var(--space-4);
      row-gap: 0;
    }
    body.view-list .doc-card:hover { transform: none; }
    body.view-list .doc-card-title {
      grid-column: 1;
      grid-row: 1;
      margin-bottom: 4px;
      font-size: var(--font-size-sm);
    }
    body.view-list .doc-card-path {
      grid-column: 1;
      grid-row: 2;
      margin-bottom: 0;
    }
    body.view-list .doc-card-date {
      display: block;
      grid-column: 1;
      grid-row: 3;
      margin-top: var(--space-2);
    }
    .doc-card-actions {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: var(--space-2);
      margin-top: var(--space-2);
    }
    body.view-list .doc-card-actions {
      grid-column: 2;
      grid-row: 1 / span 3;
      align-self: center;
      margin-top: 0;
    }
    .doc-archive-btn {
      min-height: 36px;
      padding: 8px 12px;
      border-radius: var(--radius-tight);
      border: 1px solid var(--error);
      background: var(--error-soft);
      color: var(--error);
      font-family: var(--font-sans);
      font-size: var(--font-size-xs);
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      cursor: pointer;
      transition: background var(--transition-base), border-color var(--transition-base),
        transform var(--transition-base);
    }
    .doc-archive-btn:hover {
      background: var(--error-soft);
      border-color: var(--line-strong);
      transform: translateY(-1px);
    }
    body.view-list .dup-note {
      grid-column: 1 / -1;
      grid-row: 4;
      margin-top: var(--space-2);
    }
    body.view-list .doc-card .dup-note:first-of-type { margin-top: var(--space-2); }
  </style>
</head>
""")

    parts.append('<body class="view-list">\n')
    parts.append('  <div class="library-shell">\n')
    parts.append('  <nav class="library-nav" aria-label="Document categories">\n')
    parts.append('    <div class="library-nav-title">Sections</div>\n    <ul>\n')
    for nav_cat in manifest.get("categories", []):
        nc_id = _escape(nav_cat["id"])
        nc_label = _escape(nav_cat["label"])
        nc_n = len(nav_cat.get("items", []))
        parts.append(
            f'      <li><a href="#cat-{nc_id}">{nc_label} '
            f'<span class="nav-count" aria-label="{nc_n} documents">{nc_n}</span></a></li>\n'
        )
    parts.append("    </ul>\n  </nav>\n")
    parts.append('  <main class="library-main">\n')
    parts.append("""  <header class="page-head">
    <p class="eyebrow">Agent OS</p>
    <h1>Guides &amp; policies library</h1>
    <p class="lede">Curated index of executive, governance, and delivery documents (noise such as dashboard HTML, Cursor chat exports, and working-session checkpoints is omitted). Generated by <code>scripts/build_os_document_library.py</code>. <strong>Archive</strong> retires a file to <code>docs/archived-policies/</code>; rebuild this page after changes. Use the same origin as the Agent OS supervisor for links.</p>
    <div class="toolbar">
      <label class="visually-hidden" for="lib-filter">Filter documents</label>
      <input type="search" id="lib-filter" class="search" placeholder="Filter by title or path…" autocomplete="off" />
      <div class="view-toggle" role="group" aria-label="Document layout">
        <button type="button" class="view-toggle-btn" id="lib-view-grid" aria-pressed="false">Grid</button>
        <button type="button" class="view-toggle-btn" id="lib-view-list" aria-pressed="true">List</button>
      </div>
      <span class="meta-chip" id="lib-stats"></span>
    </div>
  </header>
""")

    gen = _escape(manifest.get("generated", ""))
    stats = manifest.get("stats", {})
    parts.append(f'  <p class="meta-chip" style="margin-bottom:16px">Generated {gen} · {stats.get("files_indexed", 0)} files · {stats.get("categories_non_empty", 0)} categories</p>\n')

    parts.append('  <div class="callout callout-warn" role="note">\n')
    parts.append("    <strong>Deduping:</strong> identical files that share a filename are flagged per card. ")
    parts.append("Same name with different contents stays in the list until merged. ")
    parts.append("Regenerate dedupe notes with <code>python3 scripts/build_os_document_library.py</code>.\n")
    parts.append("  </div>\n")

    dup_by_path: dict[str, list[dict]] = defaultdict(list)
    for g in manifest.get("duplicate_groups", []):
        for p in g.get("paths", []):
            dup_by_path[p].append(g)

    for cat in manifest.get("categories", []):
        cid = _escape(cat["id"])
        label = _escape(cat["label"])
        desc = _escape(cat["description"])
        n = len(cat.get("items", []))
        open_attr = " open" if cat.get("default_open") else ""
        parts.append(
            f'  <details class="library-cat"{open_attr} id="cat-{cid}" data-category="{cid}">\n'
        )
        parts.append(f"    <summary>{label} <span class=\"cat-count\">{n}</span></summary>\n")
        parts.append(f'    <p class="cat-desc">{desc}</p>\n')
        parts.append('    <div class="card-grid">\n')
        for item in cat.get("items", []):
            href = _escape(_doc_open_href(item["path"], fmt=item.get("format", "markdown")))
            title = _escape(item["title"])
            path_e = _escape(item["path"])
            fmt = item.get("format", "markdown")
            badge_class = "badge badge-html" if fmt == "html" else "badge"
            badge_txt = "HTML" if fmt == "html" else "MD"
            mod = _escape(item.get("date_modified", "—"))
            search_blob = _escape((item["path"] + " " + item["title"]).lower())
            dups = dup_by_path.get(item["path"])
            dup_html = ""
            if dups:
                for dg in dups:
                    if len(dg.get("paths", [])) < 2:
                        continue
                    others = [x for x in dg["paths"] if x != item["path"]]
                    if not others:
                        continue
                    if dg.get("same_content"):
                        dup_html += '<p class="dup-note">Duplicate of same bytes: ' + ", ".join(_escape(o) for o in others[:4]) + ("…" if len(others) > 4 else "") + "</p>"
                    else:
                        dup_html += '<p class="dup-note">Same filename, different content as: ' + ", ".join(_escape(o) for o in others[:3]) + ("…" if len(others) > 3 else "") + "</p>"
            path_attr = _escape(item["path"])
            parts.append(
                f'      <article class="doc-card" data-search="{search_blob}" data-doc-path="{path_attr}">\n'
                f'        <div class="doc-card-title"><a href="{href}" target="_blank" rel="noopener">{title}</a></div>\n'
                f'        <div class="doc-card-path">{path_e}</div>\n'
                f'        <span class="doc-card-date">Modified {mod}</span>\n'
                f'        <div class="doc-card-actions">\n'
                f'          <div class="badges"><span class="{badge_class}">{badge_txt}</span></div>\n'
                f'          <button type="button" class="doc-archive-btn" data-archive-path="{path_attr}" data-archive-title="{title}">Archive</button>\n'
                f'        </div>\n'
                f"{dup_html}"
                "      </article>\n"
            )
        parts.append("    </div>\n")
        parts.append("  </details>\n")

    parts.append("""  <section style="margin-top:32px" aria-labelledby="rel-notes">
    <h2 id="rel-notes" class="eyebrow" style="margin-bottom:12px">Related document tiers</h2>
    <ul style="margin-left:20px; color:var(--muted); font-size:var(--font-size-sm); max-width:720px;">
""")
    for note in manifest.get("relationship_notes", []):
        parts.append(f"      <li style=\"margin-bottom:8px\">{_escape(note)}</li>\n")
    parts.append("""    </ul>
  </section>
  <footer>Manifest: docs/os-documentLibrary.manifest.json · Regenerate after adding policy docs.</footer>
  </main>
  </div>
  <style>.visually-hidden { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); border:0; }</style>
  <script>
(function(){
  var input = document.getElementById('lib-filter');
  var cards = document.querySelectorAll('.doc-card');
  var stats = document.getElementById('lib-stats');
  var btnGrid = document.getElementById('lib-view-grid');
  var btnList = document.getElementById('lib-view-list');
  var LS_KEY = 'mv-doc-library-view-v2';
  function countVisible() {
    var n = 0;
    cards.forEach(function(c) { if (!c.classList.contains('hidden')) n++; });
    return n;
  }
  function sync() {
    var q = (input.value || '').toLowerCase().trim();
    cards.forEach(function(c) {
      var hay = c.getAttribute('data-search') || '';
      var show = !q || hay.indexOf(q) !== -1;
      c.classList.toggle('hidden', !show);
    });
    document.querySelectorAll('details.library-cat').forEach(function(d) {
      var vis = d.querySelectorAll('.doc-card:not(.hidden)').length;
      d.style.display = vis ? '' : 'none';
    });
    if (stats) stats.textContent = 'Showing ' + countVisible() + ' / ' + cards.length;
  }
  function setView(list) {
    document.body.classList.toggle('view-list', list);
    document.body.classList.toggle('view-grid', !list);
    if (btnGrid) btnGrid.setAttribute('aria-pressed', list ? 'false' : 'true');
    if (btnList) btnList.setAttribute('aria-pressed', list ? 'true' : 'false');
    try { localStorage.setItem(LS_KEY, list ? 'list' : 'grid'); } catch (e) {}
  }
  if (btnGrid) btnGrid.addEventListener('click', function() { setView(false); });
  if (btnList) btnList.addEventListener('click', function() { setView(true); });
  try {
    var saved = localStorage.getItem(LS_KEY);
    if (saved === 'grid') setView(false);
    else setView(true);
  } catch (e) {
    setView(true);
  }
  input.addEventListener('input', sync);
  sync();

  var GOV_ROOT = { 'AGENTS.md': 1, 'CLAUDE.md': 1, 'STYLE_GUIDE.md': 1 };
  document.querySelectorAll('.doc-archive-btn').forEach(function(btn) {
    btn.addEventListener('click', function(ev) {
      ev.preventDefault();
      var p = btn.getAttribute('data-archive-path') || '';
      var t = btn.getAttribute('data-archive-title') || p;
      if (!p) return;
      if (!window.confirm('Archive this document?\\n\\n' + p + '\\n\\nIt will move to docs/archived-policies/ and disappear from the active tree. You must commit and fix references from the generated report.')) return;
      var confirmGov = false;
      if (GOV_ROOT.hasOwnProperty(p)) {
        if (!window.confirm('This is a root governance file. Archiving may break agent workflows until you replace it. Continue?')) return;
        if (!window.confirm('Final confirmation: archive ' + p + '?')) return;
        confirmGov = true;
      }
      var reason = window.prompt('Optional reason (logged in manifest):', '') || '';
      btn.disabled = true;
      fetch('/api/archive-document', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: p, reason: reason, confirmGovernanceRoot: confirmGov })
      }).then(function(r) { return r.json().then(function(j) { return { ok: r.ok, j: j }; }); })
      .then(function(x) {
        btn.disabled = false;
        if (!x.ok || !x.j.ok) {
          window.alert(x.j.error || x.j.message || 'Archive failed');
          return;
        }
        var msg = 'Archived to ' + (x.j.archived_path || '') + '\\n\\nReference report: ' + (x.j.reference_report || '') + '\\n\\nHits (sample): ' + (x.j.reference_hits || []).slice(0, 8).join('\\n');
        if (x.j.reference_hits_truncated) msg += '\\n… (truncated in response; see report file)';
        window.alert(msg);
        var card = btn.closest('.doc-card');
        if (card) card.parentNode.removeChild(card);
        sync();
      }).catch(function(err) {
        btn.disabled = false;
        window.alert('Request failed: ' + (err && err.message ? err.message : String(err)));
      });
    });
  });
})();
  </script>
</body>
</html>
""")
    return "".join(parts)


def write_dedupe_md(manifest: dict) -> None:
    lines = [
        "# OS document library — dedupe notes",
        "",
        f"Generated: `{manifest.get('generated', '')}`",
        "",
        "## Relationship tiers (not duplicates)",
        "",
    ]
    for n in manifest.get("relationship_notes", []):
        lines.append(f"- {n}")
    lines.extend(["", "## Filename clusters", ""])
    for g in manifest.get("duplicate_groups", []):
        lines.append(f"### `{g['basename']}`")
        same = "identical bytes" if g.get("same_content") else "different bytes"
        lines.append(f"- **{same}**")
        for p in g.get("paths", []):
            lines.append(f"  - `{p}`")
        if g.get("note"):
            lines.append(f"- {g['note']}")
        lines.append("")
    DEDUPE_MD_OUT.parent.mkdir(parents=True, exist_ok=True)
    DEDUPE_MD_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    manifest = build()
    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_OUT.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    HTML_OUT.write_text(render_html(manifest), encoding="utf-8")
    write_dedupe_md(manifest)
    print(f"Wrote {MANIFEST_OUT.relative_to(REPO)}")
    print(f"Wrote {HTML_OUT.relative_to(REPO)}")
    print(f"Wrote {DEDUPE_MD_OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
