#!/usr/bin/env python3
"""Templates for standalone Agent OS scaffold files."""
from __future__ import annotations

STANDALONE_README = """# Agent OS

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
"""


STANDALONE_AGENTS = """# Agent OS Governance

This standalone repo owns the Agent OS runtime and operational tooling.

Phase-1 split rules:
- MV remains the source of truth for `*-status.json`, agent charters, docs, research, decisions, and workbench data.
- Agent OS reads and writes that MV workspace through `MV_WORKSPACE_ROOT`.
- Mixed-ownership governance content stays split between the MV repo and this runtime repo until final doc separation is complete.
"""


STANDALONE_CLAUDE = """# Agent OS Runtime Notes

This checkout is the standalone Agent OS runtime scaffold.

Use:
- `MV_WORKSPACE_ROOT` to point at the MV workspace
- `bash scripts/start_agent_os_dashboard.sh` to launch the dashboard

Do not treat this scaffold as the source of truth for MV status files or project docs in phase 1.
"""


STANDALONE_GITIGNORE = """.DS_Store
agent_os.env
__pycache__/
.pytest_cache/
node_modules/
"""
