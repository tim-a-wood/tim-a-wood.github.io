# Agent OS Workspace Contract

## Purpose

Agent OS now supports an explicit MV workspace root via `MV_WORKSPACE_ROOT`.
The MV launcher also supports `AGENT_OS_APP_ROOT` so this repo can start Agent OS from a separate checkout.

This separates:
- **Agent OS app root**: where the Agent OS runtime/scripts live
- **MV workspace root**: where Agent OS reads and writes founder-facing state and MV runtime data

In the current in-repo setup, both roots are the same directory. During the repo split, they will diverge.

## Environment

- `MV_WORKSPACE_ROOT`
  - Optional for current in-repo usage
  - Required when Agent OS runs from a separate checkout
  - If unset, Agent OS falls back to its own repo root for backward compatibility

- `AGENT_OS_APP_ROOT`
  - Optional when launching from MV wrappers
  - Points at the standalone Agent OS checkout to run
  - If unset, the launcher uses the current repo root for backward compatibility

## App Root Responsibilities

The Agent OS app root owns:
- `os-dashboard.html`
- `scripts/os_dashboard_supervisor.py`
- Agent OS launchers
- document-library tooling
- markdown preview/archive tooling
- status validation tooling
- Agent OS-specific tests
- Agent OS digest/update scripts

## Workspace Root Responsibilities

The MV workspace root remains the phase-1 source of truth for:
- repo-root `*-status.json`
- `agents/*/charter.md`
- `knowledge/`
- `playbooks/`
- `templates/`
- `research/`
- `decisions/`
- `artifacts/`
- `tools/2d-sprite-and-animation/projects-data/`
- `scripts/sprite_workbench_server.py`

## Compatibility Rules

- Current localhost defaults remain unchanged.
- Current route and payload shapes remain unchanged.
- Current dashboard behavior must remain the same with:
  - `MV_WORKSPACE_ROOT` unset
  - `MV_WORKSPACE_ROOT` set to the current MV checkout
- Status writes must continue to target the MV workspace only.
- Workbench start/stop ownership stays in MV in phase 1.

## Phase-1 File Classification

### Move to Agent OS repo

- `os-dashboard.html`
- `scripts/os_dashboard_supervisor.py`
- `scripts/build_os_document_library.py`
- `scripts/render_markdown_view.py`
- `scripts/archive_policy_document.py`
- `schemas/status-file.schema.json`
- `scripts/validate_status_files.py`
- Agent OS launchers
- Agent OS digest/update scripts
- Agent OS-specific tests

### Stay in MV

- all repo-root `*-status.json`
- all `agents/*/charter.md`
- `knowledge/`, `playbooks/`, `templates/`, `research/`, `decisions/`
- workbench runtime/data and product artifacts

### Split instead of move wholesale

- `AGENTS.md`
- likely `README.md`
- likely `CLAUDE.md`

## QA Baseline

The minimum parity gates for workspace-root compatibility are:

- `python3 scripts/validate_status_files.py`
- `python3 -m pytest tests/os_dashboard_agent_chat.test.py tests/os_dashboard_my_actions_chat.test.py tests/render_markdown_view.test.py tests/os_document_library.test.py -q`
- `node --test tests/my_actions_aggregate.test.js`
- `python3 -m pytest tests/test_workbench_local_control.py -q`
- `python3 tests/home_internal_snapshot.test.py`

Run those checks in both modes:
- default mode
- `MV_WORKSPACE_ROOT=/path/to/MV`

To scaffold the external app repo from the approved phase-1 move set:

```bash
python3 scripts/bootstrap_agent_os_repo.py /path/to/agent-os-repo
AGENT_OS_APP_ROOT=/path/to/agent-os-repo MV_WORKSPACE_ROOT=/path/to/MV bash scripts/start_agent_os_dashboard.sh
```

To smoke-test the externalized runtime on an alternate supervisor port:

```bash
python3 scripts/check_agent_os_split_smoke.py --workspace-root /path/to/MV --supervisor-port 8779
```

To run a side-by-side parity check between the in-repo Agent OS and a scaffolded external checkout:

```bash
python3 scripts/compare_agent_os_parity.py --workspace-root /path/to/MV --internal-port 8770 --external-port 8779
```

To run a shadow pass that repeats parity checks and stores artifacts:

```bash
python3 scripts/agent_os_shadow_run.py --workspace-root /path/to/MV --iterations 3
```

To switch the MV launcher to an external standalone Agent OS checkout:

```bash
python3 scripts/bootstrap_agent_os_repo.py ./agent-os-standalone
bash scripts/cutover_agent_os_external.sh ./agent-os-standalone
```

To roll back to the embedded launcher path:

```bash
bash scripts/rollback_agent_os_embedded.sh
```
