# Room Environment Editor Payload And Results Contract

**Date:** 2026-04-04
**Status:** Design contract for MVP extension
**Scope:** Room editor environment Results surface only
**Related source:** `room-layout-editor.html`, `room-wizard-environment.js`, `scripts/room_environment_v3.py`, `room-layout-export-package.js`

## Purpose

This contract defines the exact payload and display behavior for the existing room editor Results surface while it grows into the MVP extension requested for environment authoring.

The goals are:

1. keep the surface proposal-first
2. expose the authoring fields that matter for environment review
3. keep generated output staged and inspectable
4. keep debug/layer toggles out of the exported room payload

## Source Of Truth

The Results surface should continue to read from `room.environment` and its nested runtime slices. The new MVP fields belong in `room.environment.spec` so they survive export with the rest of the environment metadata.

### Canonical payload shape

```json
{
  "version": 2,
  "environment_pipeline_version": "v3",
  "themeId": "ruins",
  "tags": ["ruined-gothic", "stone-heavy", "threshold-clarity"],
  "spec": {
    "theme_id": "ruins",
    "theme_name": "Ruined Gothic Keep",
    "description": "Keep the shell heavy, keep the center lane calm.",
    "notes": "Prefer strong threshold reads and quiet center framing.",
    "seed": "RG-R2-184233",
    "lock_stylepack": true,
    "reference_uploads": [
      {
        "id": "ref-gate-01",
        "label": "Keep gate silhouette",
        "source_url": "/art/references/keep-gate.png",
        "status": "approved",
        "pinned_to": "stylepack"
      }
    ],
    "components": { },
    "component_schemas": { },
    "scene_schema": { }
  },
  "preview": { },
  "template_context": { },
  "runtime": {
    "asset_pack": { },
    "bespoke_asset_manifest": { }
  },
  "room_intent": { },
  "component_contracts": { },
  "assembly_plan": { },
  "review_state": { }
}
```

## Display Contract

### 1. Reference upload

The Results surface must show reference uploads as a pinned list above the staged summaries.

Display rules:

- show the count of uploaded references
- show the pinned reference first
- show each reference label, status, and target area
- if `lock_stylepack` is true, the pinned reference remains read-only until unlocked

Payload mapping:

- `room.environment.spec.reference_uploads[]`
- `room.environment.spec.lock_stylepack`

### 2. Theme name

The Results surface must show a human-readable theme name distinct from the machine theme id.

Display rules:

- show `theme_name` as the editor-facing label
- keep `themeId` visible in a smaller token row for provenance
- if `theme_name` is blank, fall back to the current `themeId` label

Payload mapping:

- `room.environment.spec.theme_name`
- `room.environment.themeId`

### 3. Notes

The Results surface must show a compact notes field that is editable in place.

Display rules:

- show the most recent notes text in the semantics summary
- keep notes short enough to scan in the Results sidebar
- notes are authoring metadata and should not be inferred from generated assets

Payload mapping:

- `room.environment.spec.notes`
- `room.environment.spec.description` as the generated summary / prompt companion

### 4. Seed

The Results surface must show a stable seed value alongside theme name and notes.

Display rules:

- seed is an authoring identifier, not a random UI token
- show the current seed in monospace
- if seed is empty, the UI must show an explicit unset state instead of hiding the field

Payload mapping:

- `room.environment.spec.seed`

### 5. Lock Stylepack

The Results surface must show a clear lock state for the stylepack bundle.

Display rules:

- when locked, the stylepack card shows a locked badge and reference updates become read-only
- when unlocked, the stylepack card shows an editable badge and reference uploads remain mutable
- the lock state must be visually distinct from validation or runtime status

Payload mapping:

- `room.environment.spec.lock_stylepack`

### 6. Staged summaries

The Results surface must present the generated state in five ordered sections:

1. Stylepack
2. Semantics
3. Kit
4. Manifest
5. Validation

Display rules:

- each section gets its own card, header, and status pill
- each section summarizes only its own source data
- the section order must not change between states
- the section headers should make it obvious whether the data is authoring input or generated output

Payload mapping:

- Stylepack: `spec.reference_uploads`, `spec.lock_stylepack`, `themeId`, `theme_name`
- Semantics: `spec.description`, `spec.notes`, `spec.seed`, `room_intent`
- Kit: `spec.component_schemas`, `spec.scene_schema`, `runtime.asset_pack`
- Manifest: `runtime.bespoke_asset_manifest`, `assembly_plan`
- Validation: `runtime.bespoke_asset_manifest.schema_validation`, `runtime.bespoke_asset_manifest.runtime_review`, `review_state`

### 7. Debug and layer toggles

The Results surface must expose debug and layer toggles as a secondary inspector group.

Display rules:

- toggles are secondary to the authoring metadata
- toggles affect overlay visibility, not the room payload
- toggles must never be confused with the stylepack lock state
- if a toggle persists locally, it should live in editor UI state only, not in exported room JSON

Payload contract:

- no room export fields required
- if persistence is needed later, store under editor-local UI state, not `room.environment`

## Results States

The QA handoff should validate these visible states in the Results surface:

1. Empty
- no references uploaded
- theme name blank
- seed blank
- stylepack unlocked
- no generated stage summaries

2. Draft
- theme name present
- notes present
- references uploaded but not pinned
- stylepack unlocked
- summaries present but manifest is not ready

3. Locked
- stylepack lock on
- reference list becomes read-only
- stage summaries continue to update from generated data

4. Generating
- wait state visible
- manifest and validation show running or pending states
- preview remains proposal-first

5. Partial
- at least one stage summary shows a warning or failure
- failed assets are called out explicitly
- runtime screenshot is missing or blocked

6. Ready
- manifest ready
- validation complete
- runtime screenshot available
- approval action available

7. Blocked
- validation or runtime review shows a hard failure
- the blocker text is visible
- the UI does not present the room as ready

## Interaction Rules

- Reference upload happens before build, not after runtime review.
- Theme name, notes, and seed are editable authoring inputs and must remain visible in Results.
- Lock Stylepack is a deliberate authoring control, not a status badge.
- Debug/layer toggles are optional diagnostics and should never replace the primary review copy.
- The Results surface should not auto-apply generated style changes without explicit user action.

## Non-Goals

- Implementing the real UI in `room-layout-editor.html`
- Changing the runtime export schema for `room.environment.preview` or `room.environment.runtime`
- Productizing debug toggles beyond the editor session
- Replacing the existing room wizard flow

## QA Handoff

Please validate the following exact states in the mockup and then in implementation:

- reference upload empty versus populated
- theme name blank versus filled
- notes blank versus filled
- seed blank versus filled
- stylepack unlocked versus locked
- each staged summary card showing an appropriate status pill
- manifest ready versus manifest blocked
- validation pass versus warning versus failure
- debug overlays on versus off

## Recommendation

Use this contract as the basis for implementation so the environment Results surface stays stable, reviewable, and proposal-first while the MVP extension lands.
