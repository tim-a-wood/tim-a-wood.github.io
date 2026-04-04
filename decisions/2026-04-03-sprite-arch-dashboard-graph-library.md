# Decision: Sprite-arch dashboard graph rendering (vis-network)

**Date:** 2026-04-03  
**Context:** Agent OS `os-dashboard.html` sprite-arch view needs an interactive dependency graph (structure, relationship filters, change heat) without adding a bundler.

## Choice

- Load **vis-network 9.1.9** from **jsDelivr** (standalone UMD + stylesheet) on first visit to the sprite-arch dashboard, then build the graph from manifest JSON.
- **Supervisor-only** optional feature: `POST /api/sprite-arch-explain` (OpenAI JSON) with path allowlist under `tools/2d-sprite-and-animation/` and `scripts/`.
- **Workbench parity:** same POST route on `sprite_workbench_server.py` via lazy import of `_sprite_arch_explain` so same-origin calls work when the dashboard is opened from the workbench host.

## Rejected / deferred

- **Bundled vis-network in-repo** — avoids CDN dependency but adds asset maintenance and review surface; deferred until offline/air-gapped requirement appears.
- **Cytoscape.js / D3-only** — viable; vis-network chosen for faster box layout + interaction for ~40 nodes.
- **PNG export** — UI placeholder remains; not implemented in this pass.

## Follow-ups

- If CSP is tightened on dashboard hosts, allowlist jsDelivr or vendor the UMD build under `assets/`.
- Revisit hierarchical layout if multi-root graphs prove unreadable (fallback is already physics on non-structure tabs).
