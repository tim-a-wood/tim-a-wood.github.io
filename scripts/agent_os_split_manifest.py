#!/usr/bin/env python3
"""Phase-1 file manifest for bootstrapping the standalone Agent OS repo."""
from __future__ import annotations

PHASE1_COPY_PATHS: tuple[str, ...] = (
    "Agent-OS-Dashboard.command",
    "README.md",
    "agent_os.env.example",
    "docs/agent-os-workspace-contract.md",
    "docs/os-document-library.html",
    "docs/os-documentLibrary.manifest.json",
    "docs/reports/os-document-library-dedupe-notes.md",
    "os-dashboard.html",
    "requirements-agent-os.txt",
    "schemas/status-file.schema.json",
    "scripts/agent_os_roots.py",
    "scripts/archive_policy_document.py",
    "scripts/build_os_document_library.py",
    "scripts/daily_product_report.sh",
    "scripts/os_dashboard_supervisor.py",
    "scripts/pull_openai_organization_costs_cache.py",
    "scripts/render_markdown_view.py",
    "scripts/send_weekly_digest.py",
    "scripts/start_agent_os_dashboard.sh",
    "scripts/update_dashboards.sh",
    "scripts/validate_status_files.py",
    "scripts/weekly_digest.sh",
    "scripts/workbench_local_control.py",
    "scripts/workbench_persistence.py",
    "tests/archive_policy_document.test.py",
    "tests/home_internal_snapshot.test.py",
    "tests/my_actions_aggregate.test.js",
    "tests/os_dashboard_agent_chat.test.py",
    "tests/os_dashboard_my_actions_chat.test.py",
    "tests/os_document_library.test.py",
    "tests/render_markdown_view.test.py",
    "tests/test_workbench_local_control.py",
)

PHASE1_EXCLUDE_PREFIXES: tuple[str, ...] = (
    "agents/",
    "artifacts/",
    "decisions/",
    "knowledge/",
    "playbooks/",
    "research/",
    "templates/",
    "tools/2d-sprite-and-animation/projects-data/",
)
