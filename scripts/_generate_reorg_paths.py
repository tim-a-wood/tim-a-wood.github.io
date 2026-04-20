#!/usr/bin/env python3
"""One-off generator for REORG-SPEC Phase 3 manifest and paths-*.txt (run from repo root)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.agent_os_split_manifest import PHASE1_COPY_PATHS

# P3.T7 decision: leave contract dashboards in orchestrator (spec option b).
PLAN_DASHBOARDS_ORCHESTRATOR = True

PHASE1 = tuple(p for p in PHASE1_COPY_PATHS if p != "README.md")
PHASE1_SET = set(PHASE1_COPY_PATHS)


def git_ls_files() -> list[str]:
    out = subprocess.check_output(["git", "-C", str(ROOT), "ls-files"], text=True)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def classify(path: str) -> tuple[str, str]:
    """Return (bucket, reason)."""
    if path in PHASE1_SET and path != "README.md":
        return "agent-os", "PHASE1_COPY_PATHS (agent_os_split_manifest.py)"
    if path == "README.md":
        return "orchestrator", "Workspace README (split artifact; STANDALONE_README in agent-os submodule)"

    # Sprite workbench (product tree + style guide)
    if path == "STYLE_GUIDE.md" or path.startswith("tools/2d-sprite-and-animation/"):
        return "sprite-workbench", "Sprite Workbench product tree / style ownership"

    # Ashen Hollow — game runtime + editor (explicit roots)
    ashen_prefixes = (
        "css/",
        "js/",
        "assets/",
        "icons/",
    )
    ashen_files = {
        "index.html",
        "room-layout-editor.html",
        "room-layout-data.json",
        "room-rules.md",
        "room-environment-preview-full.html",
        "level-viewer.html",
        "map-graph-viewer.html",
        "manifest.json",
    }
    if path in ashen_files or path.startswith(ashen_prefixes):
        return "ashen-hollow", "Game / level / PWA surface (reorg spec P3.T3)"

    # tools/ is only sprite-workbench in this repo
    if path.startswith("tools/"):
        return "sprite-workbench", "Under tools/ (sprite workbench only in this repo)"

    # Docs
    if path.startswith("docs/"):
        base = path.split("/")[-1].lower()
        if path in PHASE1_SET:
            return "agent-os", "PHASE1_COPY_PATHS"
        # Phase-1 doc paths (already covered by PHASE1_SET except README)
        phase1_docs = {
            "docs/agent-os-workspace-contract.md",
            "docs/os-document-library.html",
            "docs/os-documentLibrary.manifest.json",
            "docs/reports/os-document-library-dedupe-notes.md",
        }
        if path in phase1_docs:
            return "agent-os", "PHASE1_COPY_PATHS"
        if "sprite-workbench" in path.lower() or "pixel-art" in path.lower():
            return "sprite-workbench", "Sprite workbench / pixel art doc naming"
        if path.startswith("docs/mockups/agent-os") or path.startswith("docs/mockups/my-actions"):
            # Not in PHASE1_COPY_PATHS — keep in orchestrator so paths-agent-os.txt matches contract (P3.T11).
            return "orchestrator", "Agent OS–adjacent mockups (stay in workspace until contract extends)"
        if (
            path.startswith("docs/mockups/room-")
            or path.startswith("docs/mockups/room-environment")
            or "handover-room" in path
            or "handover-map" in path
        ):
            return "ashen-hollow", "Room / map product docs and mockups"
        if path.startswith("docs/qa/") and "room" in path.lower():
            return "ashen-hollow", "Room QA doc"
        if "room-environment" in path.lower() and "sprite" not in path.lower():
            return "ashen-hollow", "Room environment pipeline docs"
        if path.startswith("docs/diagrams/room-environment"):
            return "ashen-hollow", "Room environment diagrams"
        if path.startswith("docs/baselines/") or path.startswith("docs/plans/"):
            if "room" in path.lower() or "shell" in path.lower():
                return "ashen-hollow", "Room/shell baselines or plans"
        return "orchestrator", "Cross-cutting / workspace documentation"

    # Tests
    if path.startswith("tests/"):
        p1_tests = {
            "tests/archive_policy_document.test.py",
            "tests/home_internal_snapshot.test.py",
            "tests/my_actions_aggregate.test.js",
            "tests/os_dashboard_agent_chat.test.py",
            "tests/os_dashboard_my_actions_chat.test.py",
            "tests/os_document_library.test.py",
            "tests/render_markdown_view.test.py",
            "tests/test_workbench_local_control.py",
        }
        if path in p1_tests:
            return "agent-os", "PHASE1_COPY_PATHS tests"
        if "sprite_workbench" in path or path.startswith("tests/fixtures/sprite_workbench/"):
            return "sprite-workbench", "Sprite workbench tests/fixtures"
        if path.startswith("tests/fixtures/room_environment") or path.startswith("tests/fixtures/room_environment_v3"):
            return "ashen-hollow", "Room environment fixtures"
        low = path.lower()
        if any(
            x in low
            for x in (
                "room-wizard",
                "room_editor",
                "room-environment",
                "room_environment",
                "game-logic",
                "ashen_hollow",
                "unified_shell",
                "room_ai",
                "art_bible_swatches",
            )
        ):
            return "ashen-hollow", "Game / room test"
        orch_tests = {
            "tests/agent_os_split_manifest.test.py",
            "tests/check_agent_os_split_smoke.test.py",
            "tests/compare_agent_os_parity.test.py",
            "tests/bootstrap_agent_os_repo.test.py",
            "tests/test_pull_openai_organization_costs_cache.py",
            "tests/send_weekly_digest_email_theme_test.py",
        }
        if path in orch_tests:
            return "orchestrator", "Workspace / split-contract tests"
        if "sprite" in low and "workbench" in low:
            return "sprite-workbench", "Sprite workbench test"
        return "orchestrator", "Default orchestrator tests"

    # Scripts
    if path.startswith("scripts/"):
        p1_scripts = [p for p in PHASE1_COPY_PATHS if p.startswith("scripts/")]
        if path in p1_scripts:
            return "agent-os", "PHASE1_COPY_PATHS"
        name = Path(path).name
        if name in (
            "agent_os_split_manifest.py",
            "bootstrap_agent_os_repo.py",
            "agent_os_standalone_templates.py",
            "check_agent_os_split_smoke.py",
            "compare_agent_os_parity.py",
            "cutover_agent_os_external.sh",
            "rollback_agent_os_embedded.sh",
            "agent_os_shadow_run.py",
        ):
            return "orchestrator", "Split/bootstrap tooling (stays with workspace contract)"
        if name.startswith("ci_") or name in ("install_hooks.sh", "pre-commit"):
            return "orchestrator", "Repo CI / hooks"
        if name == "check_escalation_conditions.py":
            return "orchestrator", "Escalation policy (workspace)"
        sw_hits = (
            "sprite_workbench",
            "sprite",
            "pixellab",
            "workbench_",
            "extract_sprite",
            "verify_sprite",
            "gemini_prompt",
        )
        if any(x in path for x in sw_hits) and "room_layout" not in path and "room_environment" not in path:
            # workbench_* is mostly sprite; room_environment stays game
            if "room_environment" in path or "room_layout" in path:
                return "ashen-hollow", "Room tooling script"
            return "sprite-workbench", "Sprite / workbench script"
        if "room_environment" in path or "room_layout" in path or path.startswith("scripts/environment_v3/"):
            return "ashen-hollow", "Room / environment / level tooling"
        if name in ("capture_room_results_states.js", "capture_room_results_calibration.js", "parse_room_spec.js"):
            return "ashen-hollow", "Room capture / parse"
        if name == "generate-room-editor-chunks.py":
            return "ashen-hollow", "Room editor chunk generation"
        return "orchestrator", "Orchestrator / shared script"

    # Top-level HTML: agent-os dashboards vs orchestrator adjuncts
    if path in ("plan-dashboard.html", "my-actions-mockup.html") and PLAN_DASHBOARDS_ORCHESTRATOR:
        return "orchestrator", "P3.T7: stay in orchestrator (contract extension not applied)"

    # Default buckets by prefix
    if path.startswith("artifacts/"):
        return "orchestrator", "PHASE1_EXCLUDE_PREFIXES (contract)"
    if path.startswith("reporting/"):
        return "orchestrator", "P3.T6.g default — workspace escalation config (not in PHASE1_COPY_PATHS)"
    if path.startswith("issues/"):
        return "orchestrator", "Workspace issue notes"
    if path.startswith("samples/"):
        return "orchestrator", "Samples (cross-cutting)"
    if path.startswith("prompts/"):
        return "orchestrator", "Project prompts"
    if path.startswith("tmp/"):
        return "orchestrator", "tmp/ (tracked; P1.T6 deletion blocked by recent files)"

    if path.startswith("schemas/") and path != "schemas/status-file.schema.json":
        return "orchestrator", "Workspace schemas (status schema moves in P3.T4)"

    if path.startswith("agents/"):
        if path in (
            "agents/design/dashboard-standard.md",
            "agents/directives/dashboard-standard.md",
            "agents/directives/plain-language-dashboards.md",
            "agents/directives/task-completion-update.md",
        ):
            return "agent-os", "PHASE1_COPY_PATHS"
        return "orchestrator", "Agent charters (EXCLUDE_PREFIXES)"

    return "orchestrator", "Orchestrator default"


def to_filter_path(path: str) -> str:
    """Paths for git filter-repo: dirs end with /."""
    full = ROOT / path
    if full.is_dir():
        return path if path.endswith("/") else path + "/"
    return path


def main() -> int:
    files = git_ls_files()
    rows: list[tuple[str, str, str]] = []
    buckets: dict[str, list[str]] = {"agent-os": [], "ashen-hollow": [], "sprite-workbench": [], "orchestrator": [], "delete": []}

    for p in sorted(files):
        bucket, reason = classify(p)
        rows.append((p, bucket, reason))
        if bucket != "delete":
            buckets.setdefault(bucket, []).append(to_filter_path(p))

    # De-duplicate filter paths (shorter prefixes supersede)
    for b in ("agent-os", "ashen-hollow", "sprite-workbench"):
        lst = sorted(set(buckets[b]))
        buckets[b] = lst

    out_dir = ROOT / "docs" / "reorganization"
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Reorganization manifest",
        "",
        f"Generated (see scripts/_generate_reorg_paths.py)",
        "",
        "Buckets: orchestrator (= MV workspace root) | ashen-hollow | sprite-workbench | agent-os | delete",
        "",
        "| Path | Bucket | Reason |",
        "|------|--------|--------|",
    ]
    for path, bucket, reason in rows:
        lines.append(f"| `{path}` | {bucket} | {reason} |")

    (out_dir / "reorg-manifest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_paths(name: str, bucket: str) -> None:
        header = [
            f"# Auto-generated from reorg-manifest.md",
            "# Source: scripts/_generate_reorg_paths.py",
            "# Consumed by: git filter-repo --paths-from-file",
            "",
        ]
        body = "\n".join(p for p in buckets[bucket] if p)
        (out_dir / name).write_text("\n".join(header) + body + "\n", encoding="utf-8")

    write_paths("paths-agent-os.txt", "agent-os")
    write_paths("paths-ashen-hollow.txt", "ashen-hollow")
    write_paths("paths-sprite-workbench.txt", "sprite-workbench")

    uncovered = []
    # Top-level only check (P3.T8 style)
    top = set()
    for p in files:
        top.add(p.split("/")[0])
    manifest_paths = set()
    for p, b, _ in rows:
        if "/" not in p:
            manifest_paths.add(p)
        else:
            manifest_paths.add(p.split("/")[0] + "/")

    print("Wrote manifest and paths-*.txt")
    print("Bucket counts:", {k: len(v) for k, v in buckets.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
