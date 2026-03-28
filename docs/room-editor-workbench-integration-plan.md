# Room Editor + Sprite Workbench Integration Plan

## Goal

Integrate the room / level editor into Sprite Workbench in a way that is durable, project-based, and extensible for future world-building work.

This is not just a UI merge. The correct objective is:

1. keep the Sprite Workbench project system as the source of truth for authoring state,
2. migrate room editing onto that project model,
3. preserve the room editor's geometry-editing strengths,
4. add a room / level stage to the workbench without breaking the current character pipeline.

## Executive Summary

The two tools are at very different maturity levels:

- Sprite Workbench is a project-oriented application with:
  - per-project directories,
  - persisted workflow state,
  - a wizard / stage model,
  - API-backed mutations,
  - history and artifact storage.
- The room editor is a standalone canvas tool with:
  - one canonical root JSON file,
  - one thin local server,
  - browser scratch save,
  - no project model,
  - no concept of downstream assets, review state, or integration contracts.

Because of that, the right path is not "embed `room-layout-editor.html` inside the workbench." The right path is:

1. define a room-authoring contract inside workbench projects,
2. move room data into per-project storage,
3. port the room editor onto the workbench server and project APIs,
4. then surface it as a new stage in the workbench shell.

## Audit

### Sprite Workbench: Current State

Primary files:

- `/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`
- `/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html`

What is already strong:

- Per-project storage under `tools/2d-sprite-and-animation/projects-data/<project_id>/`
- Durable project metadata in `project.json`
- Separate persisted artifacts such as:
  - `brief.json`
  - `history.json`
  - `pixellab_character.json`
  - `pixellab_animations.json`
  - canonical downstream JSONs
- Wizard state with:
  - `current_step`
  - `completed_steps`
  - `recommended_next_step`
  - `blocking_reasons`
- Existing project lifecycle operations:
  - create
  - duplicate
  - archive
  - update step state
- API-backed UI model already designed for staged authoring

What matters for integration:

- The workbench already has the right persistence pattern.
- It already knows how to attach multiple subsystems to one project.
- It is the right host for a room editor stage.

Current weakness:

- The workbench is still strongly character-pipeline shaped.
- Its stepper and project summary model assume character-first production.
- There is no existing world / level / room artifact family in the project contract.

### Room / Level Tooling: Current State

Primary files:

- `/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html`
- ~~`scripts/layout_editor_server.py`~~ (removed — canonical layout API is on `sprite_workbench_server.py`)
- `/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json`
- `/Users/timwood/Desktop/projects/PWA/MV/level-viewer.html`
- `/Users/timwood/Desktop/projects/PWA/MV/map-graph-viewer.html`

What is already strong:

- The room editor already solves the hard local editing interactions:
  - room polygon editing
  - platform placement
  - door placement
  - moving platforms
  - keys / abilities
  - player start
  - global map placement
  - edge linking / snapping
- The canonical room JSON already has a meaningful schema:
  - `rooms[]`
  - `polygon`
  - `platforms`
  - `doors`
  - `keys`
  - `abilities`
  - `movingPlatforms`
  - `edgeLinks`
  - `removedEdges`
  - `playerStart`
  - `global`
  - `size`
- The map graph and level-viewer provide useful planning / validation context.

Current weaknesses:

- Persistence is global, not project-based.
- Server is extremely thin:
  - `GET /api/layout`
  - `POST /api/layout`
- No project ID, no versioning, no review state, no history, no artifact folders.
- Browser scratch-save and canonical file sync are useful locally, but wrong as the long-term workbench model.
- UI is standalone and does not share workbench state, navigation, or validation primitives.

### Level Tooling Around the Editor

The surrounding files show there are really three distinct world-design surfaces today:

1. graph / topology planning
2. room geometry authoring
3. runtime / viewer validation

That matters because "integrate the room editor" should not mean "ignore graph planning." We should plan for:

- a future map / progression stage,
- a room layout stage,
- shared project-level level-design data.

## Key Architectural Conclusion

The integration seam is **project persistence**, not **HTML embedding**.

If we try to merge the UIs first:

- we will keep the room editor bound to `room-layout-data.json`,
- we will end up with duplicated save concepts,
- we will have brittle state syncing between the two tools,
- and we will make future level pipeline work harder.

If we unify the data model first:

- the room editor becomes another workbench authoring surface,
- every room layout becomes project-scoped,
- history, duplication, export, and review all become natural,
- future integration with graph planning and gameplay validation becomes straightforward.

## Recommended Target Architecture

### 1. Add a Level Design domain inside each workbench project

Each workbench project should gain a `level_design` artifact family.

Recommended initial files:

- `level_graph.json`
- `room_layout.json`
- `level_design_history.json`
- `level_validation_report.json`

Optional later:

- `encounter_layout.json`
- `room_art_hooks.json`
- `spawn_tables.json`

### 2. Move room editor data from repo-global to project-local

Current:

- `/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json`

Target:

- `/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/<project_id>/room_layout.json`

This is the single most important integration step.

### 3. Rehost room-editor APIs inside `sprite_workbench_server.py`

Instead of a separate editor server owning one file, the workbench server should own:

- `GET /api/projects/:id/room-layout`
- `POST /api/projects/:id/room-layout`
- `POST /api/projects/:id/room-layout/validate`
- `POST /api/projects/:id/room-layout/reset-from-canonical`
- `POST /api/projects/:id/room-layout/import`

Optional but desirable:

- `GET /api/projects/:id/level-graph`
- `POST /api/projects/:id/level-graph`

### 4. Add a new workbench stage for world-building

Recommended top-level flow:

1. Describe
2. Concepts
3. Character
4. Animations
5. Rooms / Level
6. Review & Export

Do not put room editing inside Character or Animations. It deserves its own stage.

### 5. Treat the current room editor canvas as a reusable authoring module

The room editor should be refactored into reusable client logic:

- not a full standalone app,
- but a room-layout board that can render inside workbench stage chrome.

The workbench shell should own:

- project selection
- stage navigation
- save / dirty state
- validation summaries
- review / export integration

The embedded room editor should own:

- geometry interaction
- selection tools
- edge linking
- canvas rendering

## What We Should Not Do

### Do not do a straight iframe or raw-page embed

That would preserve the current bad boundary:

- separate persistence
- separate API
- separate UI state
- duplicated save controls

### Do not keep `room-layout-data.json` as the canonical long-term source

It is fine as a migration source, but not as the integrated model.

### Do not couple room editing directly to the character pipeline internals

The room editor should consume project-level outputs where useful, but it should not be implemented as a character subfeature.

## Detailed Plan

## Phase 0: Freeze the Integration Boundary

Objective:

Agree on what "integrated" means before touching implementation.

Deliverables:

- Define `level_design` as a first-class project domain.
- Decide the initial stage name:
  - `Rooms`
  - or `Level`
- Decide whether graph editing ships in v1 integration or later.

Recommendation:

- Ship `Rooms` first.
- Keep map graph visualization linked but not fully embedded in v1.

Exit criteria:

- We have a written artifact contract for `room_layout.json`.
- We have a stage placement decision in the workbench flow.

## Phase 1: Define the Canonical Project-Level Room Layout Contract

Objective:

Turn the current room JSON into an explicit project artifact with versioning and room for metadata.

Work:

1. Define `room_layout.json` shape.
2. Wrap the current `rooms[]` payload in project-level metadata.
3. Add migration fields.

Recommended schema:

```json
{
  "project_id": "example-project",
  "version": 1,
  "updated_at": "ISO-8601",
  "meta": {
    "worldWidth": 1600,
    "worldHeight": 1200,
    "grid": 32,
    "notes": ""
  },
  "graph_ref": null,
  "rooms": []
}
```

Keep the existing room object structure mostly intact for v1.

Add later only if needed:

- room review state
- per-room tags
- encounter metadata
- visual theming hooks

Exit criteria:

- A migration function can convert `room-layout-data.json` to `room_layout.json`.
- The workbench server can load and save it deterministically.

## Phase 2: Add Room Layout Persistence to the Workbench Server

Objective:

Make room layouts project-scoped and API-backed under the existing workbench server.

Work:

1. Add artifact helpers:
   - `room_layout_path(project_dir)`
   - `load_room_layout(project_dir)`
   - `save_room_layout(project_dir, payload)`
2. Add endpoints:
   - `GET /api/projects/:id/room-layout`
   - `POST /api/projects/:id/room-layout`
3. Add project hydration fields:
   - `project["room_layout"]`
   - `project["level_validation_report"]`
4. Add history events:
   - `room_layout_imported`
   - `room_layout_saved`
   - `room_layout_validated`
5. Add duplicate/archive handling so room artifacts travel with projects.

Important constraint:

Do not remove the old standalone server until the new path works end-to-end.

Exit criteria:

- A workbench project can own a room layout.
- Duplicate project also duplicates room layout.
- Project API returns room layout as part of integrated state.

## Phase 3: Extract the Room Editor into a Reusable Client Module

Objective:

Separate room editing logic from its standalone shell.

Work:

1. Pull the room editor script into a reusable JS module or isolated embedded component block.
2. Separate:
   - canvas logic
   - editor state
   - persistence calls
   - shell-specific controls
3. Replace direct assumptions about:
   - `/api/layout`
   - `./room-layout-data.json`
   - browser scratch save as primary persistence

New editor interface should accept:

- current layout payload
- project ID
- callbacks for save / validate / dirty-state updates

Keep optional local affordances later:

- export raw JSON
- import JSON

Exit criteria:

- The editor can run against project-scoped endpoints.
- The standalone `layout_editor_server.py` was removed; use `sprite_workbench_server.py` only.

## Phase 4: Add a Rooms Stage to the Workbench UI

Objective:

Expose the editor inside the workbench flow.

Work:

1. Add a new step to the wizard / stage model.
2. Add a `Rooms` panel board in `index.html`.
3. Show:
   - current layout status
   - validation summary
   - last updated
   - import/export actions
   - open full-canvas editing mode
4. Make stage completion rules explicit.

Suggested v1 completion rule:

- stage is considered complete when:
  - a room layout exists, and
  - validation passes baseline structural checks

Recommended UX split:

- summary / controls inside standard stage card
- full editor canvas in expanded board region

Exit criteria:

- User can create/open a project and edit room layout inside the workbench.
- No separate editor server is required for normal use.

## Phase 5: Add Validation and Review Plumbing

Objective:

Make the room editor feel like part of a production tool, not a loose utility.

Work:

1. Port existing design constraints into a validator:
   - reachability
   - edge-link consistency
   - room existence
   - valid edge indices
   - player start presence
2. Add gameplay-oriented checks from existing docs where feasible:
   - step height
   - horizontal traversal gap
   - return path guarantees
3. Store result in `level_validation_report.json`.
4. Surface warnings in the workbench stage summary.

Recommended validation levels:

- Level 1: structural correctness
- Level 2: traversal sanity
- Level 3: progression / content sanity

Exit criteria:

- The room stage can fail clearly and explain why.
- Review & Export can eventually include room validation state.

## Phase 6: Migrate Existing Canonical Layout Data

Objective:

Bring the current room authoring work into the new system without losing it.

Work:

1. Add an import command / button:
   - import root `room-layout-data.json` into current project
2. Preserve original as legacy source during migration period.
3. Add one-time migration note in docs.

Recommendation:

- Do not auto-import globally.
- Make import explicit per project.

Why:

- The current global file may represent one snapshot of the game, not every project.

Exit criteria:

- Existing room layout can be attached to a workbench project in one action.

## Phase 7: Add Graph-to-Room Integration

Objective:

Connect topology planning with geometry authoring.

This should be phase 2 of the product, not the first merge step.

Work:

1. Define `level_graph.json`.
2. Import the map graph viewer data into project space.
3. Add graph summary panel in the Rooms stage or a separate `Map` stage.
4. Sync graph links with room `edgeLinks`.

Recommended rule:

- graph owns macro topology
- room layout owns geometry and room-local traversal

Exit criteria:

- Room links and graph connections can be reconciled from one project.

## Phase 8: Add Export and Runtime Integration

Objective:

Make room workbench output usable by the game/runtime pipeline.

Work:

1. Define runtime export shape.
2. Add export route for room / level data.
3. Add "open game with this project layout" path.
4. Stop relying on root `room-layout-data.json` for mainline testing.

This is where the integration becomes complete.

Exit criteria:

- The runtime can load a project-scoped room export.
- Workbench export bundles character + animation + room layout cleanly.

## Recommended Implementation Order

This is the exact order I would do the work:

1. Write `room_layout.json` contract and migration helpers.
2. Add room layout load/save/history support to `sprite_workbench_server.py`.
3. Copy current global room JSON into one test project and prove persistence.
4. Refactor room editor client code to use project APIs.
5. Add a `Rooms` stage in workbench UI.
6. Embed room editor board into that stage.
7. Add structural validation.
8. Add traversal validation.
9. Add project export path for room data.
10. Only then consider graph-stage integration.

## Concrete v1 Scope

To keep this shippable, v1 should include:

- project-scoped room layouts
- integrated room editor stage
- import existing canonical layout
- save / load / duplicate / archive support
- baseline validation
- workbench navigation and status integration

v1 should not include:

- full graph editor rewrite
- encounter authoring
- runtime procedural generation hooks
- automatic room art generation

## Risks

### Risk 1: Trying to merge shells before persistence

Effect:

- duplicated save logic
- hard-to-debug state drift

Mitigation:

- project artifact contract first

### Risk 2: Rewriting too much of the room editor interaction layer

Effect:

- regressions in the best part of the current tool

Mitigation:

- preserve canvas/editor logic
- refactor shell and persistence boundaries only

### Risk 3: Over-coupling character and room workflows

Effect:

- bloated stage logic
- confusing project completion rules

Mitigation:

- introduce a parallel project domain for level design

### Risk 4: Treating map graph and room geometry as the same artifact

Effect:

- bad schema and future friction

Mitigation:

- separate `level_graph.json` and `room_layout.json`

## Recommended Project Milestones

### Milestone 1: Persistence Unification

- project-scoped room artifact
- server endpoints
- migration import

### Milestone 2: Embedded Room Editing

- room stage
- integrated editor board
- workbench save/load flow

### Milestone 3: Validation + Export

- structural validation
- traversal validation
- runtime export

### Milestone 4: Graph Integration

- project-scoped graph
- graph/room synchronization
- macro-to-micro level design workflow

## Final Recommendation

Proceed with a **project-first integration**, not a page-first integration.

If the immediate goal is "iterate the room editor and integrate it into the workbench," the best next move is:

1. add `room_layout.json` to workbench projects,
2. move the room editor onto workbench APIs,
3. ship a `Rooms` stage,
4. then iterate validation and graph integration from there.

That gives us a clean path from today's standalone editor to a real integrated production tool without throwing away the editing work that already exists.
