# Agent OS Governance

This standalone repo owns the Agent OS runtime and operational tooling.

Phase-1 split rules:
- MV remains the source of truth for `*-status.json`, agent charters, docs, research, decisions, and workbench data.
- Agent OS reads and writes that MV workspace through `MV_WORKSPACE_ROOT`.
- Mixed-ownership governance content stays split between the MV repo and this runtime repo until final doc separation is complete.
