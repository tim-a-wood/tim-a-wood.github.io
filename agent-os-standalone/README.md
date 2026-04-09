# Agent OS

Standalone Agent OS runtime for the MV founder operating system.

## Quick Start

1. Point Agent OS at an MV workspace:

```bash
export MV_WORKSPACE_ROOT=/absolute/path/to/MV
```

2. Start the dashboard:

```bash
bash scripts/start_agent_os_dashboard.sh
```

## Notes

- Agent OS owns the dashboard runtime, validation tooling, markdown/document tooling, and reporting jobs.
- The MV workspace remains the source of truth for status files, charters, docs, research, decisions, and workbench data in phase 1.
- `MV_WORKSPACE_ROOT` is required when this checkout is outside the MV repo.
