# MV Workbench

Top-level workspace + orchestrator for three related products.

## Submodules

| Product | Path | Purpose |
| --- | --- | --- |
| **Ashen Hollow** | `ashen-hollow/` | Metroidvania game runtime, level editor, room data |
| **Sprite Workbench** | `sprite-workbench/` | 2D sprite and animation editor |
| **Agent OS** | `agent-os/` | Multi-agent runtime and tooling (reads this workspace via `MV_WORKSPACE_ROOT`) |

## Workspace state (lives in this repo)

- `*-status.json` — per-agent status files
- `agents/` — agent charters and per-agent directories
- `decisions/`, `research/`, `knowledge/`, `playbooks/`, `templates/` — operational governance
- `artifacts/` — generated deliverables
- `schemas/` — workspace schemas (status-file schema is also published from the Agent OS submodule per the phase-1 manifest)

`STYLE_GUIDE.md` at the repo root is a symlink to `sprite-workbench/STYLE_GUIDE.md`.

## Getting started

```bash
git clone --recurse-submodules <this-repo>
cd <this-repo>
git submodule update --init --recursive
```

See each submodule's `README.md` (where present) for per-product setup.

## Agent OS operation

Agent OS runs from the `agent-os/` submodule with `MV_WORKSPACE_ROOT` set to the orchestrator checkout path:

```bash
export MV_WORKSPACE_ROOT="$(pwd)"
./agent-os/Agent-OS-Dashboard.command
```

## Submodule remotes

Submodules are hosted as private repos under `github.com/tim-a-wood/` (HTTPS URLs in `.gitmodules`). Use SSH instead if you prefer: run `git config submodule.<name>.url git@github.com:tim-a-wood/<repo>.git` or edit `.gitmodules` and `git submodule sync`.
