# ENV-003 — Editor results panel payload contract (v3 staged MVP)

**Surface:** Existing Environment **output summary** and preview area in `room-layout-editor.html` (`renderRoomWizardEnvironmentOutputSummary`, related helpers). **No new workspace.**

## Current v3 fields already consumed (baseline)

The editor already reads from `envState` (persisted `room.environment`):

| Area | Source keys | UI use today |
|------|-------------|--------------|
| Pipeline | `environment_pipeline_version` | “Pipeline: V3”, toggle sync |
| Assembly | `assembly_plan.slots`, `planner_coverage_summary`, `overlay_geometry` | “V3 assembly plan”, chips, overlay counts |
| Review | `review_state.validation_status`, `validation_plan`, `approval_status` | “Validation plan” line |
| Build | `runtime.bespoke_asset_manifest` | Slot counts, thumbs, runtime review screenshot, validation errors |

## Extensions required by the MVP plan

### Stylepack summary (proposal vs locked)

| Field | Type | UI |
|-------|------|-----|
| `stylepack.summary` | string (short) | One-line in output card |
| `stylepack.palette_profile.primary` | string[] or hex via tokens | Chip row “Palette” |
| `stylepack.status` | `draft` \| `locked` | Badge + disable/enable “Apply environment” per proposal-first rule |
| `stylepack.stylepack_id` | string | Shown in advanced/debug strip |

### Semantics counts + debug overlays

| Field | Type | UI |
|-------|------|-----|
| `room_semantics.summary` | object: counts per category | e.g. “Surfaces: 12 · Openings: 3 · Anchors: 8” |
| `room_semantics.overlay` | GeoJSON-like or existing `overlay_geometry` shape | Toggle “Semantics overlay” draws on preview canvas |
| `room_semantics.exclusion_zones` | polygons | Toggle “Exclusion zones” |
| `room_semantics.unresolved_surfaces` | list | Toggle highlights unresolved |

Server may embed semantics overlay inside `assembly_plan.overlay_geometry` during transition; target is a dedicated `room_semantics` block on the environment object.

### Kit summary

| Field | Type | UI |
|-------|------|-----|
| `environment_kit.summary` | structural / background / decor counts | Line in output card |
| `environment_kit.component_count_by_type` | map | Optional chip row |

### Manifest summary + layer toggles

| Field | Type | UI |
|-------|------|-----|
| `environment_manifest.layers.structural` | placements[] | Checkbox “Structural” |
| `environment_manifest.layers.background` | placements[] | Checkbox “Background” |
| `environment_manifest.layers.decor` | placements[] | Checkbox “Decor” |
| `environment_manifest.seed` | string/int | Display + regenerate-with-seed input |

### Validation report + severity

| Field | Type | UI |
|-------|------|-----|
| `validation_report.findings[]` | `{ severity: blocker|warning|info, code, message, ref? }` | Summary counts; expandable list |
| `validation_report.blocker_count` | int | Red badge |
| `validation_report.validation_highlights` | optional geometry refs | Toggle “Validation highlights” on preview |

### Reference pack (upload flow)

| Field | Type | UI |
|-------|------|-----|
| `reference_pack.status` | `draft` \| `ready` | Status text |
| `reference_pack.canonical_ids` | string[] | “Canonical refs: n” |
| Theme / notes / seed (may live on `reference_pack` or top-level env) | strings | Inputs: theme name, notes, seed |

## API response shape (target)

Staged POST responses should return a consistent envelope so the editor can refresh one object:

```json
{
  "ok": true,
  "environment": { "...": "merged room.environment + derived summaries" },
  "stage": "stylepack",
  "artifacts": {
    "reference_pack": {},
    "stylepack": {},
    "room_semantics": {},
    "environment_kit": {},
    "environment_manifest": {},
    "validation_report": {}
  }
}
```

During migration, partial stages may omit keys; the editor must tolerate missing sections (show “Not generated yet”).

## `editor_contract` module

`scripts/environment_v3/editor_contract.py` will centralize: building this merged payload, default empty sections, and field names so `room_environment_system` and the handler stay thin.
