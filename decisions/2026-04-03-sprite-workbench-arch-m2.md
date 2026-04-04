# Decision: Sprite workbench architecture dashboard (M2 shell)

**Date:** 2026-04-03  
**Status:** Accepted  
**Related:** `docs/sprite-workbench-architecture-visualization-master-plan.md`, `docs/sprite-workbench-architecture-visualization-plan.md` §4.1 (inspector I1/I2)

## Decision

Ship **M2** as a live Agent OS dashboard id **`sprite-arch`** with:

- Nav entry **Workbench architecture** under Product (sprite product context).
- **Stub** `artifacts/sprite-workbench-arch/manifest.json` checked in until P0 extractors replace it.
- Manifest loaded via **GET** path `/artifacts/sprite-workbench-arch/manifest.json` through the supervisor **static allowlist** (same mechanism as root `*-status.json` files).
- **No** new generic “serve any JSON under artifacts” rule—only this explicit path for predictable security review.

## Rejected / deferred

- **Dedicated `/api/...manifest` route** for v1: unnecessary while a single static path suffices; can add later for caching or auth.
- **Full inspector symbol extraction** in M2: deferred to M3+ per plan §4.1 (I1 exports after Structure is live).

## Follow-up

- M1/M3: real manifest from extractors; graph renderer; KPIs from real edge counts and analytics definitions.
