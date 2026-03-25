# Sprite Workbench Stage Audit And Action Plan

## Goal

Finish the current Sprite Workbench as a reliable standalone authoring tool by tightening the supported workflow, making project durability explicit, and removing avoidable operational risk.

This document does two things:

1. audits the current supported workflow one layer deeper than the high-level stabilization plan
2. turns that audit into an implementation order with concrete inputs, outputs, dependencies, and done conditions

## Supported Workflow

The supported workflow remains:

1. Describe
2. Concepts
3. Character
4. Animations
5. Review & Export

`Room Creation` is intentionally separate. It can persist against the same project, but it is not part of the sprite stepper.

## Stage Audit

### 1. Describe

Purpose:

- define the character brief
- create or update the project shell

Primary user inputs:

- project name
- prompt text
- silhouette intent
- role / archetype
- outfit / materials
- prop
- palette mood
- shape language
- mood / tone
- optional reference images
- backend mode / workflow mode toggles

Server inputs:

- `POST /api/projects`
- `POST /api/projects/:id/brief`
- `POST /api/projects/:id/wizard-state`

Primary stored outputs:

- `project.json`
- `brief.json`
- `history.json`
- `references/*`
- `wizard_state`

Completion signal:

- project exists
- brief is non-empty
- wizard step advances to `concepts`

Current risks:

- users do not have a very explicit sense of what is already saved vs just typed into the form
- reference state is persisted, but the UI does not strongly communicate that the project is already durable

Action:

- keep the current single-button confirm flow
- surface project health and backup nearby so persistence is visible from the start

### 2. Concepts

Purpose:

- establish the approved look for the character

Primary user inputs:

- approved brief
- source mode:
  - text generation
  - uploaded init image
  - manual import
- selected concept to iterate from
- iteration element
- requested change text

Server inputs:

- `POST /api/projects/:id/concepts/generate-pixellab`
- `POST /api/projects/:id/concepts/iterate-pixellab`
- `POST /api/projects/:id/concepts/iterate-gemini`
- `POST /api/projects/:id/concepts/:concept_id/approve`
- `POST /api/projects/:id/concepts/:concept_id/favorite`
- `POST /api/projects/:id/concepts/:concept_id/reject`

Primary stored outputs:

- `concepts/*.json`
- `concepts/*.png`
- processed preview images
- scaffold prompt metadata
- selected concept id on project
- history events

Completion signal:

- at least one concept exists
- one concept is approved / selected

Current risks:

- paid generation calls are easy to trigger repeatedly
- the UI does not clearly distinguish cheap actions from paid actions
- users cannot easily see cumulative generation activity/cost

Action:

- add usage ledger
- add safe mode / confirmations for paid actions
- keep the concept stage otherwise structurally unchanged

### 3. Character

Purpose:

- lock the approved concept into a usable character source

Primary user inputs:

- selected concept
- generation path:
  - east-only concept-as-character
  - Pixel Lab 4-dir / 8-dir character generation
- skeleton estimation
- character approval

Server inputs:

- `POST /api/projects/:id/pixellab/use-concept-character`
- `POST /api/projects/:id/pixellab/create-character`
- `POST /api/projects/:id/pixellab/estimate-skeleton`
- `POST /api/projects/:id/pixellab/approve-character`

Primary stored outputs:

- `pixellab_character.json`
- `character/*.png`
- `pixellab_skeleton.json`
- history events

Completion signal:

- character asset exists
- character approved

Current risks:

- the east-only path is reliable but can still be misunderstood as equivalent to multi-dir output
- character creation is a paid action with no persistent usage reporting

Action:

- leave the stage behavior alone
- add usage accounting and safer confirmations

### 4. Animations

Purpose:

- produce the core motion clips for the approved character

Primary user inputs:

- template animation choice
- custom animation description
- edit-animation instructions
- optional skeleton-driven animation request

Server inputs:

- `POST /api/projects/:id/pixellab/define-animation`
- `POST /api/projects/:id/pixellab/animate`
- `POST /api/projects/:id/pixellab/animate-custom`
- `POST /api/projects/:id/pixellab/animate-skeleton`
- `POST /api/projects/:id/pixellab/edit-animation`

Primary stored outputs:

- `pixellab_animations.json`
- `animations/<clip>/<direction>/frame_XX.png`
- `animation_clips.json`
- history events

Completion signal:

- required clips exist
- previews render successfully
- no missing-frame health failures

Current risks:

- this is the easiest place to burn credits quickly
- edit flows can batch under the hood
- users do not see usage/cost impact in the UI

Action:

- add usage ledger entries for every paid animation path
- add confirmation guardrails before high-cost animation calls
- expose health if animation frames are missing

### 5. Review & Export

Purpose:

- verify the current project state
- export runtime assets
- back up the editable project

Primary user inputs:

- review/export click
- backup/export click
- import backup

Server inputs:

- existing runtime export endpoint(s)
- `GET /api/projects/:id/bundle-export`
- `POST /api/projects/import-bundle`

Primary stored outputs:

- `exports/*`
- `export_manifest.json`
- preview gifs
- `last_export`
- project bundle zip on demand

Completion signal:

- runtime export package exists and verifies cleanly
- project backup is available independently

Current risks:

- runtime export and project backup are conceptually mixed
- project health is not visible at the moment the user most needs it

Action:

- clearly split `Runtime Export` from `Project Backup`
- surface project health directly in the export/review panel

## Cross-Cutting Systems

### Project Durability

Inputs:

- all project artifact writes

Outputs:

- `project_bundle_manifest.json`
- `project_health.json`
- full bundle export/import

Required behavior:

- no silent drift between what the UI thinks exists and what is actually on disk

### Usage Safety

Inputs:

- every paid or potentially paid provider call

Outputs:

- local usage ledger
- API health summary for current usage/safety state
- user-facing safe mode / warning prompts

Required behavior:

- we can answer “where did credits go?” from the tool itself

### No-Credit Operability

Inputs:

- fixture projects

Outputs:

- demo import route
- UI affordance to load a known-good sample

Required behavior:

- the workbench can be exercised end-to-end without external credits

## Action Plan

### Milestone 1: Remove dead room-step residue

Inputs:

- current frontend helpers left over from embedded room workflow

Outputs:

- cleaner sprite workbench surface
- no hidden `rooms` assumptions in the stepper code

Tasks:

1. remove dead room-step helpers from the sprite frontend
2. remove unused room wizard completion helper from the server if no longer needed
3. keep project-scoped room persistence intact

Done when:

- sprite page contains no active or dead `rooms` step logic
- room persistence still works through the separate Room Creation tool

### Milestone 2: Surface persistence and health in the UI

Inputs:

- `project_health.json`
- project summaries
- bundle export/import routes

Outputs:

- visible health state on project cards
- active project health panel
- clearer backup/export copy

Tasks:

1. show health status on project cards
2. show active project health summary in the sidebar/status area
3. show missing-file / warning counts and recommended actions
4. make backup a clearly named project durability action
5. make runtime export a clearly separate delivery action

Done when:

- a user can tell which project is healthy, degraded, or missing artifacts without opening JSON

### Milestone 3: Add usage ledger and safety rails

Inputs:

- every paid generation route
- provider responses that include job ids / usage metadata

Outputs:

- `_usage_ledger.json`
- API health usage summary
- safe mode settings
- confirm-before-spend UI

Tasks:

1. create a local usage ledger file and append helper
2. record provider, endpoint, project, status, ids, and cost where available
3. add workbench settings for `safe_mode` and `confirm_paid_actions`
4. expose these in `/api/health`
5. add confirmation prompts in the frontend before paid calls

Done when:

- every paid action leaves a trace
- the user can keep the workbench in a no-spend mode

### Milestone 4: Add no-credit demo projects

Inputs:

- fixture matrix under `tests/fixtures/sprite_workbench`

Outputs:

- importable sample projects
- one-click no-credit workbench path

Tasks:

1. add a server route to import fixture projects as demo projects
2. re-home fixture project ids on import
3. add a sidebar `Demo Project` affordance
4. load into the existing flow with no design changes

Done when:

- a user with zero external credits can still open, inspect, and export a valid sample project

### Milestone 5: Harden Review & Export

Inputs:

- active project health
- runtime export state
- project backup route

Outputs:

- clearer end-state panel
- explicit backup vs runtime export separation

Tasks:

1. add backup action to review/export surface
2. add explicit runtime export section title and empty-state copy
3. show health blockers / missing artifacts next to export readiness
4. keep current export packaging behavior intact

Done when:

- the end of the workflow is unambiguous:
  - backup preserves editable work
  - runtime export produces game-ready outputs

## Implementation Order

Do the work in this order:

1. clean dead room-step residue
2. project health + backup clarity in UI
3. usage ledger + safety rails
4. demo project import
5. review/export hardening

This order keeps the current working path stable while making the tool easier to trust.
