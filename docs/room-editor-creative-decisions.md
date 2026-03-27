# Room editor — creative decisions (living doc)

This file records product/architecture choices so Sprint work and specs stay aligned. Update it when decisions change.

## Level design vs sprite workbench (2026-03-27)

**Decision:** Level design is **not** part of the existing Sprite Workbench workflow (no extra `FLIGHTDECK_PHASE` / stage panel in `tools/2d-sprite-and-animation/` for now).

**Direction:** Treat level layout as a **separate tool** (the room layout editor and related flows). A **dedicated wizard** for level design may be added later; **wizard steps are not fixed yet** — refine in a design pass before implementation.

**Implication:** Sprint 4 “Workbench Integration” does **not** mean embedding Level Design into the sprite phase rail. Optional: a simple cross-link from docs or README to `room-layout-editor.html` is fine; deep UI integration is deferred.

## Export actions (2026-03-27)

**Decision:** **Two** export actions in the room editor:

1. **Raw / git-friendly JSON** — current behavior (full editor document, human diffable). Keep as primary for version control and hand edits.
2. **Runtime / package export** — structured multi-file bundle (manifest + per-room JSON + optional world graph) for game integration. Separate control; does **not** replace the raw export.

## Movers field name (2026-03-27)

**Canonical name for runtime-compatible layout:** `movingPlatforms`.

**Evidence:** `index.html` normalizes and reads `room.movingPlatforms`; `room-layout-data.json` uses `"movingPlatforms"`. The editor already uses this key internally.

**Spec samples** that used `movers` should be treated as **documentation drift** — runtime export must emit `movingPlatforms` unless the game loader is changed (not planned).

## Future: level design wizard (TBD)

When we define the wizard, candidate dimensions to decide (not commitments):

- New layout vs edit existing / import
- World graph vs single room
- Validation gate (L1/L2/L3) before export
- Tileset / collision profile
- Playtest / embed preview

Refine steps in a short design note before building UI.
