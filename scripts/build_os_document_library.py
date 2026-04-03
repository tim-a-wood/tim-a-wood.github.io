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
})
SKIP_PATH_FRAGMENTS = (
    ".claude/worktrees/",
    "/.git/",
    "tools/miniconda3/",
    "/miniconda3/",
    "tools/ComfyUI/",
    "/site-packages/",
    "/.venv/",
    "tools/2d-sprite-and-animation/projects-data/",
)
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
    "business_brand": {
        "label": "Business, brand & positioning",
        "description": "Executive brand charter, business brand guide, stakeholder reviews.",
    },
    "agent_charters": {
        "label": "Agent charters",
        "description": "Per-role operating charters for the Agent OS.",
    },
    "coding_governance": {
        "label": "Coding governance",
        "description": "Repository-wide rules for humans and AI coding agents (AGENTS, CLAUDE, workbench rules).",
    },
    "project_direction": {
        "label": "Project direction",
        "description": "Plans, overview, README, constraints that define product scope.",
    },
    "playbooks_knowledge": {
        "label": "Playbooks & knowledge",
        "description": "Repeatable procedures, founder knowledge base, templates.",
    },
    "design_system": {
        "label": "Design system",
        "description": "Canonical UI tokens and patterns for tools.",
    },
    "map_mvp": {
        "label": "Map, progression & MVP",
        "description": "World graph, gates, map MVP constraints, playtest logs.",
    },
    "product_engineering": {
        "label": "Product & engineering specs",
        "description": "Room editor, wizard, sprite workbench integration and specs.",
    },
    "sprite_tool_docs": {
        "label": "Sprite workbench (tool docs)",
        "description": "Authoring docs living under tools/2d-sprite-and-animation/docs.",
    },
    "reports_memos": {
        "label": "Reports & memos",
        "description": "Point-in-time reviews, syntheses, and audit memos under docs/reports/.",
    },
    "research": {
        "label": "Research",
        "description": "Research dashboard index, library entries, findings.",
    },
    "decisions": {
        "label": "Decision log",
        "description": "Logged decisions under decisions/.",
    },
    "quality_testing": {
        "label": "Quality & testing",
        "description": "Acceptance tests, test handbook, QA-facing docs.",
    },
    "artifacts_memos": {
        "label": "Artifacts (memos)",
        "description": "Markdown artifacts (email drafts, exports) — not binary assets.",
    },
    "other": {
        "label": "Other",
        "description": "Additional tracked documents that did not match a tighter category.",
    },
}

DISPLAY_ORDER = [
    "business_brand", "agent_charters", "coding_governance", "project_direction",
    "playbooks_knowledge", "design_system", "map_mvp", "product_engineering",
    "sprite_tool_docs", "reports_memos", "research", "decisions",
    "quality_testing", "artifacts_memos", "other",
]


def _should_skip_dir(path: Path) -> bool:
    for p in path.parts:
        if p in SKIP_DIR_NAMES:
            return True
    s = str(path.as_posix())
    for frag in SKIP_PATH_FRAGMENTS:
        if frag in s:
            return True
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
        if _should_skip_dir(rel.parent):
            continue
        suf = p.suffix.lower()
        if suf not in TEXT_SUFFIXES:
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
    if r.startswith("agents/") and r.endswith("/charter.md"):
        return "agent_charters"
    if r in ("AGENTS.md", "CLAUDE.md"):
        return "coding_governance"
    if r.startswith(".cursor/rules/") and r.endswith(".mdc"):
        return "coding_governance"
    if r.startswith("docs/brand-charter") or "mv-business-brand-guide" in low:
        return "business_brand"
    if r.startswith("docs/reports/business-brand-guide"):
        return "business_brand"
    if r.startswith("prompts/"):
        return "project_direction"
    if r == "README.md" or r.startswith("tests/README.md"):
        return "project_direction"
    if r.startswith("playbooks/"):
        return "playbooks_knowledge"
    if r.startswith("knowledge/"):
        return "playbooks_knowledge"
    if r.startswith("templates/"):
        return "playbooks_knowledge"
    if r == "STYLE_GUIDE.md":
        return "design_system"
    if any(r.startswith(f"docs/{name}") for name in (
        "map-", "gate-", "progression-", "branch-", "navigation-",
        "readability-", "room-layout-iteration",
    )):
        return "map_mvp"
    if r.startswith("docs/room-") or r.startswith("docs/sprite-workbench") or r.startswith("docs/cross-tool"):
        return "product_engineering"
    if r.startswith("docs/analytics-") or r.startswith("docs/design/"):
        return "product_engineering"
    if r.startswith("tools/2d-sprite-and-animation/docs/"):
        if "/archive/" in r:
            return "sprite_tool_docs"
        return "sprite_tool_docs"
    if "initial-business-plan" in low or r.startswith("docs/initial-business"):
        return "business_brand"
    if r.startswith("docs/reports/"):
        return "reports_memos"
    if r.startswith("docs/diagrams/"):
        return "product_engineering"
    if r.startswith("docs/room-environment"):
        return "product_engineering"
    if r.startswith("research/"):
        return "research"
    if r.startswith("decisions/"):
        return "decisions"
    if r.startswith("tests/acceptance") or r.startswith("tests/test_report"):
        return "quality_testing"
    if r.startswith("artifacts/") and low.endswith((".md", ".mdc")):
        return "artifacts_memos"
    if r.startswith("docs/") and low.endswith((".md", ".mdc", ".html")):
        return "other"
    return "other"


def _title_from_path(rel: Path) -> str:
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "agents" and rel.name == "charter.md":
        role = parts[1].replace("-", " ").replace("_", " ").title()
        return f"{role} charter"
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
        "docs/brand-charter.html is the concise executive anchor; docs/mv-business-brand-guide-pamphlet.html is the expanded operational system. They complement each other.",
        "docs/room-layout-validation.md and tools/2d-sprite-and-animation/docs/Room-Layout-Validation.md share a topic but are not byte-identical; keep both until converged.",
        "Agent charters (agents/*/charter.md) overlap thematically with AGENTS.md / CLAUDE.md at different altitudes: charters = role scope; AGENTS/CLAUDE = tool enforcement.",
        "Documents under .claude/worktrees/ are excluded from this catalog to avoid stale duplicates; treat repo-root paths as canonical.",
        "To retire a policy: use Archive on a card (supervisor) or scripts/archive_policy_document.py — files move to docs/archived-policies/ with a reference report; other files are not auto-edited.",
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
      padding: var(--space-5);
      max-width: 1120px;
      margin: 0 auto;
    }
    :focus-visible {
      outline: 2px solid rgba(0,232,200,0.35);
      outline-offset: 2px;
    }
    .page-head {
      margin-bottom: var(--space-6);
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
    .lede { color: var(--muted); font-size: var(--font-size-sm); max-width: 720px; margin-bottom: var(--space-4); }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-3);
      align-items: center;
      margin-bottom: var(--space-5);
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
      margin-bottom: var(--space-3);
      box-shadow: var(--shadow-md);
    }
    details.library-cat summary {
      list-style: none;
      cursor: pointer;
      padding: var(--space-4);
      font-family: var(--font-display);
      letter-spacing: 0.05em;
      font-size: var(--font-size-base);
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
      padding: 0 var(--space-4) var(--space-3);
      font-size: var(--font-size-sm);
      color: var(--muted);
    }
    .card-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: var(--space-3);
      padding: 0 var(--space-4) var(--space-4);
    }
    .doc-card {
      border: 1px solid var(--line);
      border-radius: var(--radius-tight);
      padding: var(--space-3);
      background: rgba(0,0,0,0.12);
      transition: border-color var(--transition-base), transform var(--transition-base);
    }
    .doc-card:hover {
      border-color: var(--line-strong);
      transform: translateY(-1px);
    }
    .doc-card.hidden { display: none; }
    .doc-card-title { font-weight: 600; font-size: var(--font-size-sm); margin-bottom: var(--space-2); }
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
      margin-bottom: var(--space-2);
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
<body class="view-grid">
  <header class="page-head">
    <p class="eyebrow">Agent OS</p>
    <h1>Guides &amp; policies library</h1>
    <p class="lede">Single index of charters, governance docs, product specs, and memos. Generated by <code>scripts/build_os_document_library.py</code>. <strong>Archive</strong> moves a document to <code>docs/archived-policies/</code>, writes a reference report for stale mentions, and removes it from this catalog after you rebuild. Does not auto-edit other files — clean up references from the report. Requires Agent OS supervisor (same origin as this page).</p>
    <div class="toolbar">
      <label class="visually-hidden" for="lib-filter">Filter documents</label>
      <input type="search" id="lib-filter" class="search" placeholder="Filter by title or path…" autocomplete="off" />
      <div class="view-toggle" role="group" aria-label="Document layout">
        <button type="button" class="view-toggle-btn" id="lib-view-grid" aria-pressed="true">Grid</button>
        <button type="button" class="view-toggle-btn" id="lib-view-list" aria-pressed="false">List</button>
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
    parts.append("Same name with different contents stays in the list — treat both as active until merged. ")
    parts.append("See also <code>docs/reports/os-document-library-dedupe-notes.md</code>.\n")
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
        parts.append(f'  <details class="library-cat" open data-category="{cid}">\n')
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
  <style>.visually-hidden { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); border:0; }</style>
  <script>
(function(){
  var input = document.getElementById('lib-filter');
  var cards = document.querySelectorAll('.doc-card');
  var stats = document.getElementById('lib-stats');
  var btnGrid = document.getElementById('lib-view-grid');
  var btnList = document.getElementById('lib-view-list');
  var LS_KEY = 'mv-doc-library-view';
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
    if (saved === 'list') setView(true);
    else setView(false);
  } catch (e) {
    setView(false);
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
