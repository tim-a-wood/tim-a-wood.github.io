# Sprite Workbench Stabilization Plan

## Goal

Get the **current Sprite Workbench implementation** production-ready enough to use end-to-end before attempting the larger room-editor integration.

This plan focuses on two things only:

1. **persistence completeness**
2. **overall workflow completeness**

It does **not** propose a major architecture merge, PWA rewrite, or room-editor integration in this phase.

## Scope

In scope:

- the existing file-backed workbench project model
- the current 5-step Pixel Lab workflow:
  - Describe
  - Concepts
  - Character
  - Animations
  - Review & Export
- project durability
- project recovery
- project backup / restore
- stage completion logic
- user-facing workflow clarity

Out of scope:

- room editor merge
- level graph merge
- replacing the current server
- hosted cloud persistence
- redesigning the legacy non-Pixel-Lab extraction pipeline

## Current-State Audit

## What already exists

The current workbench already has real persistence, just not complete product-grade persistence.

Key strengths in the current implementation:

- per-project filesystem storage under:
  - `/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/<project_id>/`
- project metadata persisted in:
  - `project.json`
  - `brief.json`
  - `history.json`
- concept persistence:
  - concept JSON records
  - concept PNGs
  - imported / processed source images
- Pixel Lab artifact persistence:
  - `pixellab_character.json`
  - `pixellab_animations.json`
  - skeleton and direction images
- runtime/export packaging already exists
- duplicate/archive project flows already exist
- wizard step state already exists:
  - `wizard_state`
  - `recommended_next_step`
  - `blocking_reasons`

So this is not a blank persistence problem. It is a **completeness and reliability** problem.

## Current persistence gaps

### 1. No project-level backup / restore contract

The workbench can export runtime assets, but that is not the same as exporting the full editable project.

Today:

- `last_export` refers to runtime/export bundles
- there is no first-class **project bundle** export
- there is no first-class **project import** flow

Impact:

- users can work locally, but cannot reliably back up, transfer, or restore a project as a whole
- deployment portability is weak

### 2. No explicit project integrity / repair layer

The loader hydrates many artifacts, but there is no dedicated project health pass that answers:

- which required files are missing
- which files are stale
- which files disagree with each other
- which issues can be auto-repaired

Impact:

- project failures show up indirectly and late
- recovery is harder than it should be

### 3. No canonical versioned project manifest

The project folder is already effectively a bundle, but there is no explicit bundle manifest that says:

- what belongs to the project
- artifact versions
- schema version
- compatibility expectations

Impact:

- harder import/export later
- harder migrations later

### 4. Export and persistence are conceptually mixed

The current export path packages runtime assets, but users will naturally interpret “export” as “save my project.”

Those are different concerns:

- **project persistence** = editable authoring state
- **runtime export** = publishable game asset package

Impact:

- confusing UX
- wrong recovery expectations

## Current workflow gaps

### 1. The happy path is present, but not sharply defined

The intended flow is clear in the UI, but the tool still supports enough side paths and legacy branches that it is easy for users to end up in an ambiguous state.

The product needs one explicit supported workflow.

Recommended supported v1 workflow:

1. create / open project
2. describe character
3. generate or import concept
4. approve concept
5. create character
6. approve character
7. generate idle and walk
8. build canonical clips
9. run QA
10. export runtime package

Anything else should be either:

- clearly marked optional
- clearly marked experimental
- or hidden for now

### 2. The stepper is stronger than the board-level completion rules

The system already computes:

- `step_statuses`
- `blocking_reasons`
- `recommended_next_step`

But the product still needs tighter board-level behavior:

- clearer “why blocked”
- clearer “what unblocks this”
- clearer “done” state per stage

### 3. Persistence and workflow are not surfaced together

The workbench saves continuously into project folders, but the user is not given a complete mental model of:

- what is already saved
- what is approved
- what is exportable
- what is recoverable

### 4. Project portability is missing from the workflow

Right now, the workflow ends at runtime export. It should also support:

- backup project
- restore project
- duplicate project for branching

That is part of a complete authoring workflow.

## Stabilization Principles

## Principle 1: Finish the current Pixel Lab workbench path first

Do not broaden scope.

The primary supported path should be:

- Pixel Lab concepts
- Pixel Lab character
- Pixel Lab animations
- QA
- runtime export

## Principle 2: Treat the filesystem project folder as the canonical source of truth

Do not introduce a database in this phase.

Use the current project folder model and make it complete.

## Principle 3: Separate project persistence from runtime export

These need separate UX and separate artifacts.

## Principle 4: Reduce ambiguity by explicitly de-scoping weaker paths

If a path is not stable, do not present it as first-class.

## Target v1 Product Definition

The workbench is complete for this phase when a user can reliably do all of the following:

1. create a project
2. leave and come back later
3. reopen the project without broken state
4. complete the supported character workflow end-to-end
5. export a runtime asset package
6. export a full editable project backup
7. re-import that full project backup into another local instance
8. duplicate a project to branch
9. understand from the UI exactly what stage they are in and what is blocking them

## Detailed Plan

## Phase 1: Persistence Contract Cleanup

Objective:

Make the current file-backed project structure explicit and durable.

Work:

1. Define a project bundle manifest
   - add a canonical manifest file, for example:
     - `project_bundle_manifest.json`
   - include:
     - project id
     - schema version
     - created / updated timestamps
     - artifact list
     - artifact hashes where practical

2. Version the project schema
   - add `project_schema_version`
   - use it in `project.json` and bundle manifest

3. Formalize artifact classes
   - metadata artifacts
   - editable source artifacts
   - generated production artifacts
   - runtime export artifacts

4. Document the canonical project layout

Recommended minimum artifact groups:

- core:
  - `project.json`
  - `brief.json`
  - `history.json`
- concepts:
  - concept JSON + images
- character:
  - `pixellab_character.json`
  - direction images
  - skeleton
- animations:
  - `pixellab_animations.json`
  - generated frame folders
  - `animation_clips.json`
- outputs:
  - `exports/...`

Exit criteria:

- project layout is explicit and versioned
- future backup/import has a stable contract

## Phase 2: Project Health and Repair

Objective:

Make project loading robust and diagnosable.

Work:

1. Add a `project health` computation during load
2. Detect:
   - missing required JSON
   - missing images referenced by JSON
   - stale derived assets
   - mismatched counts / dimensions
   - partially completed stages
3. Add auto-repair where safe
4. Add explicit warnings where not safe

Recommended new server field:

- `project["health_report"]`

Suggested sections:

- `missing_artifacts`
- `stale_artifacts`
- `repair_actions_taken`
- `blocking_integrity_errors`

Examples of auto-repair candidates:

- rebuild prompt history from concept records
- normalize old wizard state
- rehydrate animation clip metadata from frame paths

Examples of hard failures:

- selected concept points to missing concept record
- approved character references missing east image
- animation metadata exists but frame directories are gone

Exit criteria:

- broken or partial projects fail clearly
- recoverable projects repair automatically where possible

## Phase 3: Full Project Export / Import

Objective:

Complete persistence as a product feature, not just an implementation detail.

Work:

1. Add `Export Project`
   - package the full editable project folder into a portable bundle
   - recommended format: `.zip`

2. Add `Import Project`
   - accept a project bundle
   - validate manifest
   - restore project into `projects-data`
   - handle project id collisions cleanly

3. Add `Restore as Copy`
   - importing should default to a copy unless explicitly replacing

4. Add bundle validation
   - schema version
   - required files
   - file hashes where available

Recommended UX:

- in sidebar or account area:
  - `Export Project Backup`
  - `Import Project Backup`

Important:

- this is **not** the same as runtime export
- do not bury this under Review & Export only

Exit criteria:

- a user can back up and restore a full editable project

## Phase 4: Workflow Narrowing and Supported-Path Hardening

Objective:

Make the workbench feel complete by focusing on one supported flow.

Work:

1. Declare the supported path explicitly in the UI
2. De-emphasize or hide unstable branches
3. Make each stage require one clear completion event

Recommended completion events:

- Describe:
  - brief saved
- Concepts:
  - one concept approved
- Character:
  - character generated or east-only source selected, then approved
- Animations:
  - idle + walk generated, then canonical clips built
- Review & Export:
  - QA pass, then runtime export

Recommended de-scoping in this phase:

- legacy multi-stage extraction workflow if it is not being actively used
- niche alternate authoring branches unless they are stable

Exit criteria:

- one obvious happy path exists
- users can finish without wondering which of several branches is “real”

## Phase 5: Stage-by-Stage UX Completion

Objective:

Make the workflow understandable without reading docs.

Work:

1. Improve stage summaries
   - current state
   - saved state
   - approval state
   - next required action

2. Surface persistence status
   - “Saved to project”
   - “Project has backup export”
   - “Last project backup exported at …”

3. Improve blocking messages
   - not just “cannot continue”
   - but “approve character first” / “build canonical clips first”

4. Add completion affordances
   - `Use Latest Iteration`
   - `Approve Character`
   - `Build Canonical Clips`
   - `Run Checks`
   - `Export Package`
   should read like one clean path

5. Add a project recovery panel
   - show health warnings
   - offer repair / rebuild actions where available

Exit criteria:

- a user can infer the workflow from the UI itself

## Phase 6: Runtime Export Completion

Objective:

Make the final output path feel finished and trustworthy.

Work:

1. Keep runtime export separate from project backup
2. Ensure exported package clearly includes:
   - spritesheet
   - atlas
   - animation metadata
   - export manifest
3. Improve Review & Export summary
   - what will be exported
   - what passed QA
   - what clips are included

4. Add export artifact browsing in UI
   - open export folder
   - list recent exports

Exit criteria:

- runtime export is a clear final deliverable
- users do not confuse it with project persistence

## Phase 7: Deployment-Readiness for the Current Implementation

Objective:

Prepare the current server/filesystem workbench for first deploy or limited user testing.

Work:

1. Add project import/export before any hosted rollout
2. Make project IDs and duplicate behavior safe
3. Add better project listing state
   - archived
   - last updated
   - current step
   - backup/export state
4. Add basic project size accounting
5. Add pruning / cleanup rules for:
   - orphaned exports
   - stale generated temp files

Exit criteria:

- the current implementation can survive real usage without silent project loss

## Recommended Implementation Order

1. define project bundle manifest and schema version
2. add project health report
3. add full project export
4. add full project import
5. harden the supported 5-step Pixel Lab workflow
6. clean up stage messaging and completion rules
7. improve Review & Export clarity
8. add project recovery / repair UX

## Concrete Deliverables

### Persistence deliverables

- canonical project bundle manifest
- project schema versioning
- project health report
- export full project bundle
- import full project bundle
- collision-safe restore-as-copy behavior

### Workflow deliverables

- one documented supported path
- tighter stage completion rules
- clearer blocking reasons
- clearer persistence state in UI
- cleaner final export experience

## Suggested Acceptance Criteria

The current implementation is “complete enough” for this phase when:

1. a user can create a project and resume it later reliably
2. a user can export a full editable project bundle
3. a user can import that bundle on another machine and keep working
4. the Pixel Lab workflow works end-to-end without ambiguous branching
5. the Review & Export stage reflects true readiness
6. broken project states are surfaced clearly and repaired where possible

## Final Recommendation

Do not split attention between persistence redesign and room-editor integration right now.

Finish the current workbench as a coherent file-backed product first:

- complete project persistence
- complete project portability
- complete the supported workflow

Once that is solid, the room-editor merge becomes much easier because there will already be a trustworthy project system to plug into.
