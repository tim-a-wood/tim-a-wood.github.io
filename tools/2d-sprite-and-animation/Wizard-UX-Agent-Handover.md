# Wizard UX Agent Handover

## Purpose

This document defines a UI/UX-specific iteration for the 2D sprite workbench.

The goal is to add a guided procedural wizard for creating a new sprite and animation package, while preserving the existing multi-panel workbench for ongoing project work, direct stage access, and power-user control.

This is a handoff spec for an AI agent. It is focused on information architecture, interaction design, state flow, and the minimum backend support needed to make the wizard coherent.

## Relationship To Other Specs

- This document is authoritative for wizard UI/UX work.
- [Next-Iteration-Agent-Handover.md](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/Next-Iteration-Agent-Handover.md) remains authoritative for concept backend, reference handling, refinement, history, metrics, and QA logic.
- If this document conflicts with the current `index.html`, follow this document.
- If this document conflicts with backend requirements in the broader handover, prefer the broader handover unless the conflict is purely presentational.

## Current UI Assessment

The current UI is materially better than the original dashboard, and the multi-panel workbench is still valuable, but it does not yet guide new sprite creation in a procedural way.

Observed strengths:

- project list and project switching exist
- structured brief inputs already exist
- concept review includes compare, run summaries, and zoom
- refinement is represented as a distinct stage
- maturity badges and honesty copy already exist
- the multi-panel layout is useful for returning to specific stages quickly

Observed problems:

- all major stages are visible at once, which creates cognitive overload
- the page does not strongly answer "what should I do next?"
- the primary action for the current stage is not always visually dominant
- downstream stages remain visible even when the user is not ready for them
- there is too much expert-level detail exposed before it is needed
- the user must understand the pipeline rather than being guided through it

## UX Objective

When creating a new sprite, the user should feel like the tool is leading them through a clear sequence:

1. start or resume a project
2. define the character brief
3. attach references
4. generate concept directions
5. compare, narrow, and approve one concept
6. refine until satisfied
7. run the downstream build stages
8. validate output
9. export

At no point during new-sprite creation should the user have to infer the recommended next action from a dense dashboard.

For existing projects and power use, the workbench should remain available as a direct-access mode.

## Design Principles

- `Progressive disclosure`: show only the current step in detail; collapse the rest into summaries.
- `One primary action`: each step gets one obvious main CTA.
- `Stateful guidance`: the tool should compute the current recommended step from project state.
- `Fast resumption`: reopening a project should drop the user back into the right step.
- `Honest gating`: blocked steps must explain why they are blocked.
- `Keep power available`: do not delete advanced capability; tuck it behind expandable advanced panels.
- `Use current visual language`: preserve the existing tone, typography, palette, and panel style rather than inventing a separate product aesthetic.
- `Hybrid interaction model`: keep the workbench and add the wizard as a guided creation flow, rather than replacing the workbench entirely.

## Required Experience Change

The product must become a hybrid UI with two explicit modes:

1. `Workbench`
2. `New Sprite Wizard`

The current multi-panel workbench remains part of the product.

The wizard is added specifically for the "create a new sprite" flow.

Required mode rules:

- the landing experience must prominently offer `Create New Sprite`
- `Create New Sprite` launches the wizard
- existing projects open in workbench mode by default
- projects with an incomplete wizard may show `Resume Wizard`
- the user must be able to switch between `Wizard` and `Workbench` for the active project

Allowed wizard implementation shapes:

- a stepper in the left rail with one expanded step in the main column
- a horizontal stepper with one active step panel
- a wizard shell with collapsed completed steps above the active step

Do not ship a redesign that removes the existing workbench in favor of wizard-only navigation.

## Mode Model

Define two explicit UI modes:

### `Workbench Mode`

Purpose:

- direct access to all major panels
- project inspection and editing
- power-user and return-visit workflows

Characteristics:

- retains multi-panel visibility
- keeps direct access to concept, refine, build, QA, and export sections
- remains the default mode when opening an existing project from the project list

### `Wizard Mode`

Purpose:

- guided creation of a new sprite and animation package
- progressive step-by-step flow
- reduced cognitive load for initial creation

Characteristics:

- one active step at a time
- collapsed summaries for completed steps
- sticky navigation and primary CTA
- explicit recommended next action

The same underlying project data must power both modes.

## Wizard Information Architecture

Implement these top-level steps in order:

1. `Project`
2. `Brief`
3. `References`
4. `Concepts`
5. `Review`
6. `Refine`
7. `Build`
8. `QA`
9. `Export`

These steps are distinct from backend stage names. The wizard may map multiple backend stages into a single user-facing step.

## Step Mapping To Current Pipeline

Map wizard steps to current project state like this:

### 1. `Project`

Purpose:

- create a new project and choose the starting path

Uses current features:

- existing project list
- duplicate
- archive
- create project

Completion rule:

- a new project is created for the wizard flow

Notes:

- resuming existing projects is primarily a workbench action
- wizard resumption happens only for projects that already carry wizard progress

### 2. `Brief`

Purpose:

- capture raw prompt plus structured art-direction fields

Uses current features:

- project name
- raw prompt
- role/archetype
- silhouette intent
- outfit/materials
- prop
- palette mood
- shape language
- mood/tone
- side-view constraints
- negative prompt

Completion rule:

- enough data exists to generate a normalized brief

### 3. `References`

Purpose:

- attach and categorize optional references

Uses current features:

- reference rows
- role typing
- weight
- file upload or local path

Completion rule:

- step can be completed with zero references
- if references are added, they must validate before continuing

### 4. `Concepts`

Purpose:

- run concept generation

Uses current features:

- backend status
- generate concepts action
- run summaries

Completion rule:

- at least one concept run exists for the project

### 5. `Review`

Purpose:

- compare concepts and approve one concept

Uses current features:

- concept cards
- compare left/right
- zoom modal
- approve
- favorite
- reject
- regenerate similar

Completion rule:

- one concept is approved and `selected_concept_id` exists

### 6. `Refine`

Purpose:

- optionally run refinement loops from the approved concept

Uses current features:

- selected concept
- attribute group
- target value
- refinement strength
- generate 4 refinements

Completion rule:

- user explicitly chooses either:
  - `Refine Again`
  - `Use Current Approved Concept`

This step is optional but must be explicit. Do not assume skipping just because a concept was approved.

### 7. `Build`

Purpose:

- run the downstream placeholder build path in a guided way

This step groups three current downstream stages:

- layer review
- rig review
- production render

Completion rule:

- placeholder layers are built and approved
- placeholder rig is built and approved
- idle and walk are rendered

### 8. `QA`

Purpose:

- run implemented validation and explain pass/fail

Uses current features:

- QA run
- implemented checks
- failure surfacing

Completion rule:

- QA has been run

Advancing to export requires pass.

### 9. `Export`

Purpose:

- export final artifacts

Uses current features:

- export action
- export file list

Completion rule:

- export completed successfully

## Step Status Model

Every wizard step must expose one of these states:

- `locked`
- `ready`
- `active`
- `complete`
- `attention`

Definitions:

- `locked`: cannot start yet because prerequisites are missing
- `ready`: can be started now
- `active`: the recommended current step
- `complete`: step requirements have been satisfied
- `attention`: user previously completed it, but later state changed and the step needs review

Examples:

- `Review` is `ready` once a concept run exists
- `Build` is `locked` until a concept is approved
- `Export` is `locked` until QA passes
- `QA` is `attention` if new renders are generated after the last QA run

## Shell Requirements

The page must support both workbench mode and wizard mode.

Wizard mode must use a dedicated wizard shell.

Required layout:

- persistent project rail or header with project switcher
- visible mode switcher for `Workbench` and `Wizard`
- visible stepper with statuses when in wizard mode
- one active step panel when in wizard mode
- collapsed summary cards for completed or future wizard steps
- sticky action footer for the active wizard step

The sticky action footer must include:

- primary CTA
- secondary CTA
- back
- save, exit, or open workbench if appropriate

Do not require the user to scroll to find the next-step action.

## Step Panel Requirements

Every step panel must contain:

- a clear step title
- a one-paragraph explanation of the goal
- the minimum required inputs
- the primary CTA
- a short "what happens next" note
- blocked reasons when applicable
- a completion summary once done

Completed steps must collapse into summaries by default.

Each summary should show:

- what was chosen or generated
- when it was last updated
- a quick edit or reopen action

## Recommended Default Behavior

When a project opens in wizard mode, the UI must route the user to the recommended active step based on project state.

When a project opens in workbench mode, the UI should preserve the current multi-panel experience and optionally highlight the recommended step.

The active step should be computed in this order:

1. if no project selected -> `Project`
2. if brief is incomplete -> `Brief`
3. if concepts do not exist -> `Concepts`
4. if no approved concept -> `Review`
5. if concept approved but refine decision not acknowledged -> `Refine`
6. if downstream assets not built -> `Build`
7. if renders changed after last QA -> `QA`
8. if QA passed and no export exists -> `Export`
9. otherwise -> most recent incomplete or attention step

## Entry Points And Mode Switching

Required entry points:

- top-level primary CTA: `Create New Sprite`
- project card actions:
  - `Open Workbench`
  - `Resume Wizard` when applicable

Required switching behavior:

- from wizard mode, user can `Open Workbench`
- from workbench mode, user can `Resume Wizard` if the project has wizard progress
- mode switching must preserve project context
- mode switching must not discard unsaved wizard inputs

## Advanced Controls Policy

The wizard should not remove expert functionality, but it must hide it until needed.

Required rule:

- advanced controls must live inside expandable sections inside the relevant step

Examples:

- backend override settings inside `Brief` or `Concepts`
- raw run metadata inside `Concepts` and `Review`
- detailed QA JSON inside `QA`
- raw export manifest inside `Export`

Do not expose raw JSON as the main view for any step.

## Build Step Design

The `Build` step must feel guided, even though the downstream path is still placeholder-heavy.

Implement it as a three-part guided checklist inside one step:

1. `Build Layers`
2. `Build Rig`
3. `Render Animations`

Each substage must show:

- current status
- maturity badge
- warning copy if synthetic
- one primary action
- completion result

The user should not have to jump across separate distant sections to complete these tasks.

## Review Step Design

The `Review` step is the most important decision stage and must be optimized.

Required layout:

- concept run selector at top
- approved concept pinned area
- side-by-side compare panel
- concept grid below
- sticky review actions when a concept is selected

Required actions:

- approve
- favorite
- reject
- compare
- zoom
- regenerate similar

The review step must support rapid narrowing without leaving the step.

## Refine Step Design

The refine step must act like a loop in the wizard, not a dead-end form.

Required behavior:

- show the currently approved concept as the parent
- show a short summary of locked attributes
- ask one focused question:
  - "What do you want to change?"
- after refinement results load, allow:
  - approve one refinement and continue
  - run another refinement loop
  - keep the previous approved concept and continue

The refine step must make it obvious that refinement is optional but recommended when the initial approval is close, not final.

## QA Step Design

The QA step must translate technical results into user-understandable guidance.

Required presentation:

- overall status at top
- grouped issues by severity
- each failed check explained in plain language
- an explicit next action for each failure group

Examples:

- "Re-run build and render before QA again"
- "Export is locked until clipping failures are resolved"

Do not show a flat wall of check rows without guidance.

## Export Step Design

The export step should feel final and confirmatory.

Required elements:

- export readiness summary
- artifact list
- export location
- open artifact links
- one success state after export

If export is blocked, the step must clearly say:

- why it is blocked
- which earlier step needs attention
- a button to jump back to that step

## Navigation Rules

Required navigation behavior:

- clicking a step in the stepper moves there if the step is `ready`, `complete`, or `attention`
- locked steps are visible but not enterable
- `Next` moves to the recommended next step
- `Back` moves to the previous visible step
- `Open Workbench` exits wizard mode without losing wizard progress
- successful completion of a step should auto-advance only when the next step is obvious

Do not auto-advance away from concept review the moment a generation run finishes. The user should remain in the `Concepts` or `Review` step to inspect results.

## Progress Persistence

Wizard state must persist across reloads and project switches.

Add support for a persisted wizard state with at least:

- `current_step`
- `last_completed_step`
- `skipped_optional_steps`
- `last_refine_decision`
- `show_advanced`

Preferred storage model:

- persist in `project.json` for cross-session continuity
- mirror `current_step` in local storage for last-opened convenience
- persist `last_ui_mode` so the app can reopen in workbench or wizard intentionally

## Backend Support Requirements

This is a UI/UX task, but minimal backend support is required.

Add or extend backend support for:

- persisted `wizard_state` in project payloads
- server-computed `recommended_next_step`
- server-computed `step_statuses`
- server-computed `blocking_reasons`
- persisted `last_ui_mode`
- server indication of whether `Resume Wizard` should be shown

This logic may be computed server-side or client-side, but the final implementation must have one clear source of truth.

Recommended approach:

- compute canonical step state on the server
- let the client render from that state

## API Adjustments

Add one lightweight endpoint if needed:

- `POST /api/projects/<project_id>/wizard-state`

Supported fields:

- `current_step`
- `show_advanced`
- `last_refine_decision`
- `skipped_optional_steps`
- `last_ui_mode`

Do not add many wizard-only endpoints if current routes already support the underlying operations.

## Copy Direction

The tone of the wizard should be directive and concise.

Use copy patterns like:

- `Step 4 of 9: Generate Concepts`
- `Next: compare the six concept directions and approve one`
- `Blocked: approve a concept before refinement`
- `Optional: add references if you want stronger style control`

Avoid copy that reads like internal tooling jargon or implementation notes unless it is inside advanced panels.

## Visual Direction

Preserve the current visual language:

- dark atmospheric background
- serif-forward brand tone
- gold and blue accent balance
- card-based panels
- maturity badges

But shift the hierarchy so the user sees:

- one main task
- one main panel
- one obvious next action

Do not redesign this into a generic SaaS dashboard or a sterile form wizard.

## Mobile And Narrow Screen Behavior

The wizard must remain usable on narrow screens.

Required behavior:

- stepper collapses into a compact horizontal or dropdown navigator
- sticky footer remains reachable
- comparison views stack vertically
- step summaries remain readable without excessive scrolling

## Accessibility Requirements

Minimum required improvements:

- focus should move to the active step heading when navigation changes steps
- buttons and step states must have visible focus styles
- locked step reasons should be readable to screen readers
- status color must not be the only signal; include text labels

## Implementation Strategy

Prefer restructuring the current `index.html` rather than rewriting the tool from scratch.

Expected approach:

1. define wizard state model
2. map current project state to wizard steps
3. convert current sections into wizard step panels
4. add collapsed summaries
5. add sticky footer and step navigation
6. integrate step-specific guidance and blocked reasons
7. refine copy and advanced disclosure

## Files Likely To Change

- `tools/2d-sprite-and-animation/index.html`
- `scripts/sprite_workbench_server.py`
- `tools/2d-sprite-and-animation/stage-maturity.json`
- `README.md`

## Non-Goals

- do not redesign the backend concept pipeline in this task
- do not replace the one-page app with a framework
- do not remove power-user actions
- do not remove the multi-panel workbench
- do not promise production readiness where backend stages remain experimental or placeholder
- do not introduce a separate route-per-step application shell

## Acceptance Criteria

This wizard iteration is done when all of these are true:

- the app supports both a multi-panel workbench and a guided `Create New Sprite` wizard
- the workbench remains available for direct stage access and existing-project workflows
- the wizard is the guided path for starting a new sprite project
- the user can always tell the current step, the next step, and why blocked steps are blocked
- completed steps collapse into summaries
- the `Build` step groups layer, rig, and render actions into one guided flow
- the `Review` step is optimized for compare, approve, and narrow actions
- refinement behaves like an optional loop with a clear exit decision
- wizard state persists across reloads and project switching
- mode switching between wizard and workbench preserves project context
- the UI still exposes advanced details, but only inside step-local advanced panels
- the current visual language is preserved while the interaction model becomes much more guided
