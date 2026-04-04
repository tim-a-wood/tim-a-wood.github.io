# Room environment pipeline — MVP adaptation

Implementation notes and contracts for adapting the staged **references → stylepack → semantics → kit → compose → validate** model into the existing room editor and `environment_pipeline_version = "v3"` path.

| Doc | Task | Purpose |
|-----|------|---------|
| [ENV-001-editor-api-flow.md](ENV-001-editor-api-flow.md) | ENV-001 | Map current HTTP API and editor flow to the new stages |
| [ENV-002-persistence-layout.md](ENV-002-persistence-layout.md) | ENV-002 | On-disk layout for derived artifacts under project storage |
| [ENV-003-editor-payload-contract.md](ENV-003-editor-payload-contract.md) | ENV-003 | Fields the results panel and toggles will consume |

**Code layout (target):** `scripts/environment_v3/` package with module boundaries described in the founder plan; `scripts/room_environment_v3.py` remains the compatibility bridge until migration completes.

**Branch:** `feature/room-environment-pipeline-mvp` (2026-04-04).
