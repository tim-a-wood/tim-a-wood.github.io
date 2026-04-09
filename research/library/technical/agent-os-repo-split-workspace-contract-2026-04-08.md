---
title: Agent OS repo split workspace contract
type: technical
date: 2026-04-08
author: Research Agent
status: final
tags: agent-os, repo-split, workspace-root, migration, contracts
summary: Defines the app-root versus workspace-root contract for the Agent OS split and records the move/stay/split phase-1 boundary.
---

# Agent OS Repo Split Workspace Contract

## What changed

The codebase now supports an explicit `MV_WORKSPACE_ROOT` compatibility mode for Agent OS. This is the first executable step toward separating Agent OS into its own repo without moving the MV workspace source of truth yet.

## Contract

- **App root** owns the Agent OS runtime and tooling.
- **Workspace root** owns MV operational state, docs, charters, and workbench runtime/data.
- If `MV_WORKSPACE_ROOT` is unset, Agent OS behaves exactly as it does today.
- If `MV_WORKSPACE_ROOT` is set, Agent OS reads and writes the MV workspace through the same route and payload contracts.
- MV launchers may set `AGENT_OS_APP_ROOT` to run Agent OS from a separate checkout while keeping MV as the workspace.

## Phase-1 move boundary

### Move

- `os-dashboard.html`
- `scripts/os_dashboard_supervisor.py`
- document-library and markdown/archive tooling
- status validation tooling
- Agent OS launchers
- Agent OS digest/update scripts
- Agent OS-specific tests
- Agent OS dashboard standards and directives:
  - `agents/design/dashboard-standard.md`
  - `agents/directives/dashboard-standard.md`
  - `agents/directives/plain-language-dashboards.md`
  - `agents/directives/task-completion-update.md`

### Stay

- repo-root `*-status.json`
- `agents/*/charter.md`
- `knowledge/`, `playbooks/`, `templates/`, `research/`, `decisions/`
- workbench runtime/data
- product artifacts and feature docs

### Split

- `AGENTS.md`
- likely `README.md`
- likely `CLAUDE.md`

## QA gate evidence

The workspace-root compatibility slice is validated in both default and explicit-root modes with:

- status-file validation
- Agent OS dashboard/chat/document-library tests
- My Actions aggregation tests
- workbench-local-control tests
- home-internal snapshot test

The phase-1 bootstrap scaffold is also validated:

- `scripts/bootstrap_agent_os_repo.py` produces an external Agent OS checkout
- required runtime files exist in the scaffold
- MV-owned status files are intentionally not copied into the scaffold

## Why this matters

This avoids the main migration failure mode: conflating “where Agent OS code lives” with “where MV operating state lives.” The split now has a concrete compatibility contract instead of relying on path co-location.

**Recommendation:** Continue phase 2 by routing every remaining Agent OS path-sensitive script through the same app-root versus workspace-root contract, then bootstrap the external repo around that interface.
**Risks:** Hidden absolute paths still remain in some non-Agent-OS scripts and operator docs. Treat any new duplicate copy of status files, charters, research, or decisions as a blocker.
**Confidence:** High. The contract is now partially implemented in code and covered by the current baseline QA checks.
**Founder approval needed:** No.
**Next actions:** Engineering — extend the same root split to the remaining extraction surfaces. QA — keep running baseline checks in unset/set modes. Research — maintain this document as the migration reference if the move boundary changes.
