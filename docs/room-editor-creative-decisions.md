# Room editor — creative decisions (living doc)

This file records product/architecture choices so Sprint work and specs stay aligned. Update it when decisions change.

## Level design vs sprite workbench (2026-03-27)

**Decision:** Level design is **not** part of the existing Sprite Workbench workflow (no extra `FLIGHTDECK_PHASE` / stage panel in `tools/2d-sprite-and-animation/` for now).

**Direction:** Treat level layout as a **separate tool** (the room layout editor and related flows). The **room wizard** is product-facing for **novice/solo** creators: **global map** stays the one place to maintain the whole world; **adding a new room** should launch the **guided room flow** (see `docs/room-creation-wizard-plan.md`).

**Implication:** Sprint 4 “Workbench Integration” does **not** mean embedding Level Design into the sprite phase rail. Optional: a simple cross-link from docs or README to `room-layout-editor.html` is fine; deep UI integration is deferred.

## Export actions (2026-03-27)

**Decision:** **Two** export actions in the room editor:

1. **Raw / git-friendly JSON** — current behavior (full editor document, human diffable). Keep as primary for version control and hand edits.
2. **Runtime / package export** — structured multi-file bundle (manifest + per-room JSON + optional world graph) for game integration. Separate control; does **not** replace the raw export.

**Implementation:** Pure logic lives in `room-layout-export-package.js` (`generateExportPackage`). The editor loads it and triggers **Export runtime** (`downloadExportPackage` in `room-layout-editor.html`).

## Movers field name (2026-03-27)

**Canonical name for runtime-compatible layout:** `movingPlatforms`.

**Evidence:** `index.html` normalizes and reads `room.movingPlatforms`; `room-layout-data.json` uses `"movingPlatforms"`. The editor already uses this key internally.

**Spec samples** that used `movers` should be treated as **documentation drift** — runtime export must emit `movingPlatforms` unless the game loader is changed (not planned).

## Room creation wizard

**Plan:** `docs/room-creation-wizard-plan.md` — **product vision**, **Sprite Workbench–style phase rail**, **five phases**, **no skip wizard** for new rooms, **uneven terrain** (Terrain), **objects + assets** (import + future Asset Workbench sync), **per-tab preview** (embedded + placeholder player), **neighbor alignment**.

**Product bullets:** Global map = maintain world; **Add Room** = always enter wizard; plain-language UX; Advanced JSON for maintenance only.

**References:** `tools/2d-sprite-and-animation/app/core-helpers.js` (`FLIGHTDECK_PHASES`), `workflow-shell.js` (wizard state).
