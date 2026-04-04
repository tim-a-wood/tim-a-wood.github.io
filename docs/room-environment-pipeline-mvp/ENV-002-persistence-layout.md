# ENV-002 — MVP persistence layout for derived artifacts

**Principle:** Room layout JSON stays authoritative for geometry. New artifacts are **environment-owned** siblings under existing project directories, referenced by IDs on `room.environment` without changing the core room schema beyond lightweight pointers.

## Project root (existing)

Sprite Workbench project data lives under:

`tools/2d-sprite-and-animation/projects-data/{project_id}/`

(Resolved in code as `PROJECTS_ROOT / project_id` in `room_environment_system`.)

## Existing environment-related trees (unchanged paths)

| Path | Purpose |
|------|---------|
| `room_environment_previews/{room_id}/` | Preview PNGs + metadata |
| `room_environment_assets/{room_id}/bespoke/` | Generated bespoke slot PNGs |
| `room_environment_assets/{room_id}/review/` | Runtime capture, layout JSON, screenshot QA |

## Derived artifact files (per room)

**Implemented (2026-04-04, v3):** `room_environment_assets/{room_id}/derived/v3/*.json` — colocated with bespoke/review so one room folder owns environment outputs.

**Earlier doc draft (optional alternate):** `room_environment_derived/{room_id}/` — still valid for upload blobs if you prefer a parallel tree; `reference_pack.json` entries use project-relative paths either way.

| File | Content | Notes |
|------|---------|-------|
| `reference_pack.json` | `reference_pack_id`, uploads metadata, notes, provenance, canonical selections, status lifecycle | Binary uploads stay on disk with stored relative paths + hashes |
| `stylepack.json` | `stylepack_id`, palette profile, vocabularies, prompt pack, review checklist, lock state | Merges upload-derived rules with project art-direction fallback |
| `room_semantics.json` | Surfaces, openings, corners, cavities, safe/exclusion zones, anchors, overlay geometry | Derived only from room JSON + same rules as server |
| `environment_kit.json` | Taxonomy entries, provenance, deterministic + AI candidate metadata | |
| `environment_manifest.json` | Per-layer placements, transforms, seed, kit references | Deterministic replay contract |
| `validation_report.json` | Geometry, readability, drift, unresolved surfaces; severity model | |

**Upload blobs:** e.g. `room_environment_derived/{room_id}/references/{upload_id}.png` (or original extension), with entries in `reference_pack.json` pointing to repo-relative paths under the project.

## In-memory / saved room payload (`room.environment`)

Add optional pointers (exact names TBD in implementation; keep backward compatible):

- `reference_pack_id`, `stylepack_id`, `semantics_revision`, `kit_revision`, `manifest_revision`
- `stylepack_locked_at`, `stylepack_locked_by` (or single `stylepack_status: draft|locked`)
- `environment_derived_artifact_paths` map filename → relative path (optional cache for fast load)

**v2 coexistence:** v2 rooms ignore these keys. v3 rooms may populate them incrementally as each milestone lands.

## Loader behavior (target)

- `scripts/environment_v3/persistence.py` (planned) owns read/write, atomic replace where possible, and version stamps.
- On room open, server merges disk artifacts into the response payload for the editor **results** contract (see ENV-003).

## Migration / bridge (ENV-028 preview)

- Legacy v3 fields (`room_intent`, `assembly_plan`, `review_state`, `runtime.bespoke_asset_manifest`, etc.) remain until trust in new artifacts is established.
- Bridge maps old manifest slots to `environment_manifest.json` shape where 1:1; logs gaps in `validation_report.json` as informational.
