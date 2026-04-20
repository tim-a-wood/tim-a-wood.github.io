# MV Workbench — Orchestrator Rules

This is the top-level orchestrator repo. It serves two roles:

1. **MV workspace root** — owns operational state: agent charters, status JSONs, decisions, research, knowledge base, artifacts, and cross-cutting docs.
2. **Submodule host** — three products live as git submodules:
   - `ashen-hollow/` — metroidvania game runtime and level editor
   - `sprite-workbench/` — 2D sprite and animation editor
   - `agent-os/` — multi-agent runtime and tooling (reads this workspace via `MV_WORKSPACE_ROOT`)

Before editing anything inside a submodule, read that submodule's own instruction files: `AGENTS.md` (where present) and `CLAUDE.md`. Those wrap canonical shared bootstrap from the `agent-os` submodule (`../agent-os/AGENTS.md` and `../agent-os/CLAUDE.md` when nested in MV).

## Orchestrator-level rules

- Workspace state (status JSONs, charters, decisions, research, knowledge, templates, playbooks, artifacts) lives at the orchestrator root per the Phase-1 split contract (`scripts/agent_os_split_manifest.py` here; mirrored in the `agent-os` submodule).
- Do not duplicate workspace state inside any submodule.
- Do not commit product-specific files to the orchestrator root except workspace state and shared governance.
- Orchestrator scripts are for cross-cutting automation; single-product scripts belong in that product's submodule.

## Style guide

Frontend work must follow the canonical style guide. At the workspace root, `STYLE_GUIDE.md` is a symlink to `sprite-workbench/STYLE_GUIDE.md`.

## Agent OS runtime

Agent OS is launched with `MV_WORKSPACE_ROOT` pointing at this repo. The runtime reads status files, charters, and workspace docs from this workspace; it does not own that state.

## Submodule operations

- Update submodules: `git submodule update --remote --merge`
- Status: `git submodule status`
- After pulling: `git submodule update --init --recursive`

## Changes spanning multiple products

- Land submodule changes first (in each product repo).
- Then bump submodule pointers in one orchestrator commit.
