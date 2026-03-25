# Room Editor + Sprite Workbench Execution Plan

## Goal

Merge the room / level editor into Sprite Workbench without losing the current geometry-editing strengths of the room tool or the staged production flow of the workbench.

This plan assumes:

- Sprite Workbench remains the host application.
- The current file-backed project model remains the source of truth.
- The room editor is integrated as a project-scoped stage, not as a separate app with separate persistence.

## Desired End State

One project in the workbench should support this end-to-end flow:

1. Describe
2. Concepts
3. Character
4. Animations
5. Rooms
6. Review & Export

At the end of that flow, one workbench project should contain:

- the creative brief
- concept history
- approved character source
- animation clips
- room layout
- level validation output
- exportable runtime data

## Current Reality

Sprite Workbench already has:

- per-project storage under `tools/2d-sprite-and-animation/projects-data/<project_id>/`
- stage navigation
- persisted project metadata and artifacts
- bundle backup / import
- health report and manifest groundwork

The room editor still has:

- one global canonical JSON file
- one standalone server
- one standalone UI
- browser scratch save
- no project model

That means the first integration step is still persistence, not UI.

## Non-Goals

Do not do these now:

- do not redesign both tools at once
- do not add hosted cloud persistence
- do not re-platform the workbench server
- do not try to merge level graph, room editor, and viewer all in one pass
- do not block room integration on replacing Pixel Lab

## Merge Strategy

We should do the merge in four controlled phases.

### Phase 1: Project-Scoped Room Persistence

Objective:

Move room data into the workbench project system while keeping the existing room editor mostly intact.

Deliverables:

- add `room_layout.json` inside each workbench project
- add optional `room_layout_history.json`
- add `level_validation_report.json`
- add room-layout endpoints to [`/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py)
- keep the existing room editor UI, but point it at project routes instead of the global file

API target:

- `GET /api/projects/:id/room-layout`
- `POST /api/projects/:id/room-layout`
- `POST /api/projects/:id/room-layout/validate`
- `POST /api/projects/:id/room-layout/reset`
- `POST /api/projects/:id/room-layout/import`

Migration behavior:

- existing global [`/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json`](/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json) becomes a seed / import source only
- new projects start from either:
  - empty room layout scaffold
  - imported global canonical room layout

Exit criteria:

- room data is no longer coupled to `room-layout-data.json`
- room edits save into a specific workbench project
- duplicate / backup / import also preserve room layout

### Phase 2: Room Editor Rehost Inside the Workbench

Objective:

Stop treating the room editor as a separate application.

Deliverables:

- embed the room editor inside the workbench shell as a new `Rooms` stage
- reuse the current room editor canvas logic
- remove standalone save concepts like `Sync Canonical`
- replace them with workbench-style save / status / validation UI

Client work:

- extract room-editor state + canvas behavior out of the standalone page
- render that module in [`/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html`](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html)
- add `Rooms` to the stepper after `Animations`

UI cleanup required:

- remove room-editor assumptions about one canonical global JSON
- replace local disk language with project language
- keep advanced raw JSON import/export, but move it under an advanced section

Exit criteria:

- users can edit rooms from inside the workbench
- room state is project-scoped
- opening a project restores its room layout directly

### Phase 3: Finish the Merged Workflow

Objective:

Make the combined workflow feel like one product instead of two adjacent tools.

Deliverables:

- update completion logic so `Rooms` participates in:
  - `current_step`
  - `completed_steps`
  - `recommended_next_step`
  - `blocking_reasons`
- define a supported path for a level-ready project
- make Review & Export understand both character and room artifacts

Recommended completion logic:

- `Describe` complete when brief is valid
- `Concepts` complete when an approved concept exists
- `Character` complete when approved character source exists
- `Animations` complete when required clips exist
- `Rooms` complete when room layout is valid and saved
- `Review & Export` complete when export package passes validation

Validation in this phase:

- every room has valid polygon data
- room links are symmetric
- all required transitions resolve
- player start exists
- no broken references in layout entities

Exit criteria:

- the stepper reflects the real merged flow
- users can finish one project end-to-end without leaving the workbench

### Phase 4: Integrate the Surrounding Level Tools

Objective:

Bring in the rest of the level-design tooling after the core room stage is stable.

Possible additions:

- level graph artifact and editor
- level viewer integration
- validation overlays
- export hooks for gameplay/runtime

This phase is intentionally later because the room editor itself is already enough to justify the merge.

## Recommended Build Order

This is the exact order I would implement:

1. Add `room_layout.json` project artifact support in the workbench server.
2. Port the room editor API calls from global `/api/layout` to project-scoped room-layout routes.
3. Add migration / import from the global canonical room JSON.
4. Add a minimal `Rooms` step to the workbench shell.
5. Embed the room editor UI into that stage.
6. Remove standalone-only actions that no longer make sense.
7. Add room-layout validation and stage completion logic.
8. Update export / review so room artifacts ship with the project.

## Risks We Should Handle Explicitly

### Risk 1: Trying to modernize the room editor while integrating it

That will slow us down.

Approach:

- keep the existing editor behavior first
- modernize only after it is project-scoped and hosted in the workbench

### Risk 2: Confusing project export with runtime export again

Approach:

- room layout must live inside the editable project bundle
- runtime export remains a separate final packaging step

### Risk 3: Merging too many world-building surfaces at once

Approach:

- room layout first
- graph and viewer second

### Risk 4: Workflow ambiguity

Approach:

- define one supported merged path
- explicitly mark anything else as optional or deferred

## Definition of Done

We are done with this merge when:

- a workbench project stores room layout natively
- the room editor runs inside the workbench
- the stepper includes a functioning `Rooms` stage
- project backup / import includes room artifacts
- Review & Export understands room artifacts
- one project can move through the entire merged workflow without leaving the workbench

## Immediate Next Step

The first actual code step should be:

add project-scoped room-layout persistence and routes to [`/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py), while keeping the current room editor UI pointed at those new routes.

That gives us the correct data boundary before we touch the workbench UI.

## Detailed Action Plan

This is the execution checklist in the order we should actually build it.

### Track 1: Project-Scoped Room Persistence

#### Step 1. Add canonical room-layout artifacts to the workbench project model

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py)

Work:

- add helper paths for:
  - `room_layout.json`
  - `room_layout_history.json`
  - `level_validation_report.json`
- add default scaffold payload for a new room layout
- include room-layout artifacts in project load/save hydration
- include room-layout artifacts in project health + manifest output

Definition of done:

- every project can have a room-layout artifact family
- loading a project never crashes if room artifacts are missing
- manifest and health report know about the new artifacts

#### Step 2. Add project-scoped room-layout API routes

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py)

Routes to add:

- `GET /api/projects/:id/room-layout`
- `POST /api/projects/:id/room-layout`
- `POST /api/projects/:id/room-layout/validate`
- `POST /api/projects/:id/room-layout/import`
- `POST /api/projects/:id/room-layout/reset`

Behavior:

- `GET` returns current project-scoped room data
- `POST` saves room data into the project
- `validate` returns structural issues only at first
- `import` accepts uploaded or pasted room JSON
- `reset` replaces current room layout with the default scaffold or imported seed

Definition of done:

- room editor no longer needs the standalone `/api/layout` route
- a project ID fully determines which room layout is loaded and saved

#### Step 3. Add migration from the legacy global room file

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py)
- legacy source: [`/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json`](/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json)

Work:

- add a migration/import helper that reads the global file
- allow a project to initialize from that file once
- store migration provenance in history

Definition of done:

- existing room work is not stranded in the old tool
- new work is saved only in project scope

#### Step 4. Add tests for room persistence

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/tests/test_sprite_workbench.py`](/Users/timwood/Desktop/projects/PWA/MV/tests/test_sprite_workbench.py)

Tests:

- create project includes default room-layout artifact behavior
- save/load room layout round-trips
- import from legacy JSON works
- validation route catches malformed payloads
- bundle backup/import preserves room artifacts

Definition of done:

- room persistence changes are covered at the server level

### Track 2: Rehost the Existing Room Editor

#### Step 5. Point the standalone room editor at project-scoped APIs

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html`](/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html)

Work:

- replace `./room-layout-data.json` assumptions
- replace `/api/layout` calls with `/api/projects/:id/room-layout`
- require a project ID in the editor URL or query string
- remove or downgrade global-only actions like `Sync Canonical`

Definition of done:

- the existing room editor can open and save a workbench project directly
- no more global canonical write dependency for normal editing

#### Step 6. Keep a temporary compatibility mode

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html`](/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html)
- [`/Users/timwood/Desktop/projects/PWA/MV/scripts/layout_editor_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/layout_editor_server.py)

Work:

- allow a fallback dev-only mode for the old file if no project ID is present
- clearly label it legacy

Definition of done:

- we can keep working during the migration without hard breakage
- but the new path is clearly the preferred one

### Track 3: Add a Rooms Stage to the Workbench

#### Step 7. Add `Rooms` to the workbench stage model

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html`](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html)
- [`/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py)

Work:

- add `Rooms` after `Animations`
- extend step completion logic
- extend `recommended_next_step`
- extend project summaries and blockers

Definition of done:

- the workbench recognizes `Rooms` as a first-class step
- project state can advance into and out of the room stage cleanly

#### Step 8. Embed the room editor inside the workbench shell

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html`](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html)

Work:

- add a `Rooms` panel
- either embed the room editor canvas logic directly or load it as a shared module
- keep workbench navigation, save/status, and project chrome around it

Important constraint:

- the workbench shell owns:
  - active project
  - step navigation
  - save state
  - validation summary
- the room editor owns:
  - canvas rendering
  - geometry editing
  - selection tools
  - snapping/linking

Definition of done:

- users can edit rooms from the workbench without switching apps

### Track 4: Validation and Workflow Completion

#### Step 9. Add room-layout validation

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py)

Validation rules for v1:

- `rooms` exists and is non-empty
- each room has:
  - `id`
  - valid polygon
  - valid global position
- edge links are structurally valid
- target rooms exist
- target edge indices exist
- player start exists somewhere

Store output in:

- `level_validation_report.json`

Definition of done:

- `Rooms` can be blocked or completed based on real validation

#### Step 10. Add room-layout history

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py)

Work:

- save change revisions or snapshots into `room_layout_history.json`
- append high-level room-edit events into project history

Definition of done:

- room edits are recoverable and visible in project history

#### Step 11. Integrate room artifacts into Review & Export

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html`](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html)
- [`/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/sprite_workbench_server.py)

Work:

- show room validation state in Review & Export
- include room artifacts in project backup/export manifests
- optionally include room runtime JSON in final runtime export package

Definition of done:

- room layout is part of the completed project, not a sidecar

### Track 5: Cleanup and De-risking

#### Step 12. Remove global-file assumptions from the product

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html`](/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html)
- [`/Users/timwood/Desktop/projects/PWA/MV/scripts/layout_editor_server.py`](/Users/timwood/Desktop/projects/PWA/MV/scripts/layout_editor_server.py)

Work:

- remove `room-layout-data.json` as the default editing source
- keep it only as:
  - legacy import source
  - fixture / sample file

Definition of done:

- the new merged workflow is the default path

#### Step 13. Add end-to-end workflow tests

Files:

- [`/Users/timwood/Desktop/projects/PWA/MV/tests/test_sprite_workbench.py`](/Users/timwood/Desktop/projects/PWA/MV/tests/test_sprite_workbench.py)

Minimum scenarios:

- create project -> save room layout -> reload project
- backup/export -> import -> room layout preserved
- invalid room layout blocks `Rooms`
- valid room layout clears blockers

Definition of done:

- we have confidence the merged workflow is stable

## Suggested Implementation Milestones

### Milestone A: Persistence Landed

Includes:

- Steps 1-4

User-visible result:

- room layouts are project-scoped, durable, and backup-safe

### Milestone B: Standalone Editor Rewired

Includes:

- Steps 5-6

User-visible result:

- the current room editor edits workbench project data directly

### Milestone C: Workbench Rooms Stage Live

Includes:

- Steps 7-8

User-visible result:

- room editing happens inside the workbench

### Milestone D: Merged Workflow Complete

Includes:

- Steps 9-13

User-visible result:

- one project can move end-to-end through character and room production

## Recommended Next Coding Step

Start with Milestone A only.

Specifically:

1. add `room_layout.json` helpers and default scaffold
2. add project-scoped room-layout routes
3. add tests for save/load/import/validate

That is the smallest correct step and it unlocks everything else cleanly.
