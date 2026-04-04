# ENV-001 — Current environment API, editor flow, and v3 touchpoints

**Scope:** Documentation only. No UI redesign. Maps the **today** integration to the **target** staged MVP mental model.

## Transport and handler

Room environment is implemented on the Sprite Workbench server (`scripts/sprite_workbench_server.py`): `ThreadingHTTPServer` + handler POST/GET routes. There is no separate Flask/FastAPI app for this surface.

Base pattern for room-scoped actions:

`/api/projects/{project_id}/rooms/{room_id}/environment/{action}`

## Endpoints in use today

| Action | Method | Python entry | Role in **current** v2/v3 flow | Maps to **target** MVP stage |
|--------|--------|--------------|----------------------------------|------------------------------|
| `adapt-template` | POST | `room_environment_system.adapt_room_template` | Align template context from art direction | Partially → reference/style context (until dedicated reference-pack stage exists) |
| `spec` | POST | `build_room_environment_spec` | LLM / structured environment spec + component schemas | Becomes **stylepack** input + fallback context; spec remains until stylepack lock fully replaces it |
| `component-prompts` | POST | `generate_room_environment_component_prompts` | Per-component prompts | Feeds preview/generation; later aligned to stylepack **prompt pack** |
| `previews` | POST | `generate_room_environment_previews` | Preview images under `room_environment_previews/{room_id}/` | Stays **preview** surface; reference-pack review may add parallel gallery |
| `revise` | POST | `revise_room_environment` | Revision pass after feedback | Same family as spec/previews |
| `approve-preview` | POST | `approve_room_environment_preview` | Locks chosen preview for downstream | Remains gate before **compose** / asset pack in compatibility mode |
| `generate-assets` | POST | `generate_room_environment_asset_pack` | Bespoke PNGs + manifest + runtime review | Target: **compatibility wrapper** that orchestrates kit + composition + validation |
| `feedback` | POST | `record_room_environment_feedback_event` | Helpfulness / telemetry | Unchanged |

Global:

- `GET /api/room-environment/archetypes` — archetype catalog for the editor.

## `environment_pipeline_version`

- Stored on `room.environment.environment_pipeline_version`, normalized in `_ensure_room_environment` via `scripts/room_environment_v3.normalize_pipeline_version` → `"v2"` or `"v3"`.
- **v3-only today:** `ensure_v3_metadata` / `sync_v3_metadata` attach `room_intent`, `component_contracts`, `assembly_plan`, `review_state` on the in-memory and persisted room payload.
- **v3 in asset generation:** `generate_room_environment_asset_pack` calls `envv3.build_generation_plan(...)` and writes `env["assembly_plan"]` instead of only the v2 planner path.

## Editor (frontend)

- **Primary:** `room-layout-editor.html` — `projectRoomEnvironmentApiUrl(roomId, action)` builds the `/environment/{action}` URL; sends `environment_pipeline_version` in spec / generate-assets payloads; v3 toggle sets `room.environment.environment_pipeline_version`.
- **Module:** `room-wizard-environment.js` — normalizes pipeline version and v3-specific scene/preview behavior.

## Target staged flow (replacement mental model for v3)

1. **Room layout** — existing editor (authoritative geometry).
2. **Reference pack** — upload + review (new; API to add: e.g. `reference-pack`).
3. **Stylepack** — derive + lock (new; API: `stylepack`; UI: lock state).
4. **Room semantics** — derived from room JSON (new; API: `semantics`).
5. **Environment kit** — taxonomy + curation (new; API: `kit`).
6. **Composition** — deterministic manifest/layers (new; API: `compose`; may fold into `generate-assets` wrapper).
7. **Validation + overlays** — existing **results** surface extended (API: `validate`; UI: toggles).

**Compatibility:** Keep existing routes working during migration; add staged routes or body `action` discriminators as implementation proceeds. `generate-assets` remains the single “do the heavy build” entry until narrowly scoped.

## Related files (anchors)

- `scripts/sprite_workbench_server.py` — route table (~8050+).
- `scripts/room_environment_system.py` — `_ensure_room_environment`, `build_room_environment_spec`, `generate_room_environment_previews`, `generate_room_environment_asset_pack`.
- `scripts/room_environment_v3.py` — v3 metadata, `build_generation_plan`, geometry extracts.
