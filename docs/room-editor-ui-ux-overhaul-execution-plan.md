# Room Editor UI/UX Overhaul Execution Plan

## Summary
This plan is optimized for direct agent execution.

- Reframe the Room Editor so the main page becomes a lighter orchestration shell.
- Move detailed room editing into a large focused overlay workspace.
- Reclaim vertical space, simplify copy, remove redundant or obsolete UI, and give supporting panels clearer roles.

This plan preserves the room editor's strongest asset: the canvas and the core geometry-editing workflow.

---

## Evidence Base

### Internal evidence
- [room-layout-editor.html](/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html)
- [docs/room-editor-overhaul-plan.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-editor-overhaul-plan.md)
- [docs/room-editor-workbench-integration-plan.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-editor-workbench-integration-plan.md)
- [docs/room-creation-wizard-plan.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-creation-wizard-plan.md)
- [docs/mockups/room-editor-compact-workbench-mockup.html](/Users/timwood/Desktop/projects/PWA/MV/docs/mockups/room-editor-compact-workbench-mockup.html)
- [research/dashboard.md](/Users/timwood/Desktop/projects/PWA/MV/research/dashboard.md)
- [research/library/findings/codebase-scan-2026-04-01.md](/Users/timwood/Desktop/projects/PWA/MV/research/library/findings/codebase-scan-2026-04-01.md)

### External primary guidance
- W3C APG Dialog (Modal) Pattern: [w3.org](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
- W3C Modal Dialog Example, updated March 4, 2026: [w3.org](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/examples/dialog/)
- Apple HIG Layout: [developer.apple.com](https://developer.apple.com/design/human-interface-guidelines/layout)
- Apple HIG Toolbars: [developer.apple.com](https://developer.apple.com/design/human-interface-guidelines/toolbars)
- Apple HIG Panels: [developer.apple.com](https://developer.apple.com/design/human-interface-guidelines/panels)

### Why these sources matter
- The repo evidence shows the current editor is vertically congested, shell-heavy, and mixing orchestration with hands-on editing.
- The W3C guidance anchors the overlay/modal accessibility contract.
- The Apple HIG sources help shape the composition of large visual workspaces, toolbars, and contextual panels.
- For this problem, stable primary sources are more useful than trend-driven UI commentary.

---

## Global Execution Protocol

### 1. Specialist subagents are mandatory
For each slice, the implementing agent must use at least these specialist subagents:
- `Design`
- `QA`
- `Level Design`
- `Developer`

The implementing agent owns orchestration, synthesis, conflict resolution, and founder-facing reporting.

### 2. Each specialist must work in this order
Each specialist must complete these steps before implementation decisions are locked:
1. Scope memo
2. Targeted research and repo audit
3. Research evidence bundle
4. Approach recommendation
5. Execution

### 3. Research source policy
All specialists must use this source hierarchy:
1. official documentation
2. repo code and existing project plans
3. standards and technical reports
4. high-quality engineering or design writeups
5. only then secondary commentary

### 4. Research evidence requirements
At the end of each slice, the implementing agent must include a compact evidence section with:
- specialist name
- scoped task
- sources used
- source dates
- why each source mattered
- what changed because of the research
- unresolved questions, if any

### 5. QA gating is mandatory
No slice is ready for founder review until QA signs off the QA gate.

### 6. Design lock is mandatory before implementation
This is non-trivial UI work. Per [AGENTS.md](/Users/timwood/Desktop/projects/PWA/MV/AGENTS.md), implementation must not begin until there is an approved hi-fi mockup or an explicit founder waiver.

### 7. Stop rule
Do not stop mid-slice for founder input unless:
- founder approval is explicitly required by this plan
- a blocker appears
- the environment is broken
- evidence shows the approved slice scope is insufficient and a new founder decision is required

---

## Product Direction

### Core architectural move
- The main Room Editor page becomes a lighter orchestration shell.
- The actual room-editing experience moves into a large focused popup overlay.

### Main page responsibilities
- project and room selection
- world or room overview
- current room summary
- validation snapshot
- review and runtime entry points
- explicit launch points into detailed editing

### Overlay responsibilities
- canvas as the dominant surface
- tool rail
- contextual inspector or task drawer
- local room-editing actions
- context-specific validation and selection detail

### Principles
- preserve the existing canvas interaction model
- stop sacrificing canvas height to stacked setup UI
- reduce navigation redundancy
- move secondary information into clearer secondary surfaces
- use concise, action-first copy

---

## Slice 0

### Goal
Lock the information architecture and visual direction before implementation.

### Slice 0 Specialist Tasking
- `Design`
  - define the new shell model and hi-fi mockups
  - map retained, demoted, and removed UI surfaces
- `QA`
  - define the acceptance pack for overlay behavior, responsive states, and accessibility
- `Level Design`
  - confirm the new task model preserves spatial reasoning and authoring clarity
- `Developer`
  - inventory DOM, state, and event dependencies in the current shell

### Required Output
1. Approved hi-fi mockups for:
   - main orchestration shell
   - large room-edit overlay
   - overlay with active selection or contextual side panel
   - environment or review state
   - laptop-height state
2. Retained, demoted, and removed feature inventory.
3. Navigation model with reduced redundancy.
4. Dependency inventory for the existing [room-layout-editor.html](/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html) shell.

### Slice 0 QA Gate
QA must explicitly sign off all of the following:
- mockups cover the full core workflow
- overlay focus and keyboard behavior are specified
- the 1440x900 viewport has a deliberate layout
- removed or demoted features are listed with rationale
- no implementation starts without mockup approval or founder waiver

### Slice 0 Founder Approval Criteria
These must be reported back in plain English:
1. We defined a clear new editor structure before changing code.
2. We confirmed the main page will become a simpler control surface instead of trying to be the full editor.
3. We confirmed the popup editor will become the main place where room editing happens.
4. We agreed which current features stay prominent, which move into secondary panels, and which are removed.

### Slice 0 Founder Approval Interview
1. “Do you approve the new IA where the main page is orchestration and the room editor opens as a large focused overlay?”
2. “Do you approve the mockup direction for the overlay workspace and contextual side panels?”
3. “Do you approve the proposed list of features to keep prominent, demote, or remove before implementation starts?”

---

## Slice 1

### Goal
Build the overlay workspace foundation without changing the underlying room-edit behavior.

### Slice 1 Specialist Tasking
- `Design`
  - validate implementation fidelity against the approved mockup
- `QA`
  - validate focus, keyboard, overlay open or close behavior, and editing-state preservation
- `Level Design`
  - confirm the new overlay still supports low-friction spatial editing
- `Developer`
  - implement the large room-edit overlay and migrate the existing canvas, tool rail, and contextual inspector into it

### Required Implementation
1. Reuse the current overlay or dialog pattern already present in [room-layout-editor.html](/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html) as the accessibility and structural basis.
2. Move the room canvas, editing tools, and contextual inspector into a large focused overlay.
3. Keep current tool state, selection state, zoom, pan, and unsaved edits intact when the overlay opens or closes.
4. Keep the overlay top bar concise:
   - room identity
   - state indicator
   - save and close actions
   - only the most important room-local actions
5. Move lower-priority header actions into a secondary action area.

### Slice 1 QA Gate
QA must explicitly sign off all of the following:
- opening and closing the overlay does not lose user work or state
- focus is trapped correctly
- `Escape` works intentionally
- focus returns to the opener
- canvas editing still works inside the overlay
- playtest or runtime preview surfaces do not conflict with the editor overlay
- implementation matches the approved mockup closely enough

### Slice 1 Founder Approval Criteria
These must be reported back in plain English:
1. We moved room editing into a focused popup workspace.
2. We confirmed the popup keeps the user’s current tool, selection, and camera position.
3. We confirmed the popup is easier to work in than the old inline editing area.
4. We confirmed the popup can be opened and closed safely without losing work.

### Slice 1 Founder Approval Interview
1. “Do you agree the new overlay workspace is the right foundation for room editing?”
2. “Do you agree the overlay preserves the editing flow without feeling more cumbersome?”
3. “Do you approve continuing to the shell-density and context-window pass?”

---

## Slice 2

### Goal
Reclaim vertical space and give context windows and supporting panels clearer jobs.

### Slice 2 Specialist Tasking
- `Design`
  - simplify the main page composition and supporting panel hierarchy
- `QA`
  - validate the shorter, clearer shell and confirm no critical workflows became hidden
- `Level Design`
  - ensure context windows improve room-authoring clarity rather than hiding important spatial information
- `Developer`
  - move supporting surfaces into the right containers and reduce vertical competition on the main page

### Required Implementation
1. Remove the current vertical competition between wizard, canvas, active-room panel, validation surfaces, and supporting panels.
2. Keep world or project context on the main shell and room-edit context inside the overlay.
3. Convert always-visible side content into contextual panels, drawers, or bounded summaries.
4. Give secondary windows or surfaces clearer jobs:
   - global map for world context
   - runtime or review as dedicated preview surface
   - validation as summary plus drill-down
   - inspector as context-aware, not generic and always-on
5. Ensure the main page reads clearly on a 1440x900 laptop-height viewport.

### Slice 2 QA Gate
QA must explicitly sign off all of the following:
- the main page is materially shorter and easier to scan
- no critical workflow becomes hidden or inaccessible
- context windows appear because of mode or selection, not because users must hunt for them
- the room-editing flow remains clear for both rectangular and concave rooms
- validation and review are still discoverable
- implementation remains faithful to the approved design direction

### Slice 2 Founder Approval Criteria
These must be reported back in plain English:
1. We reduced wasted vertical space on the main editor page.
2. We confirmed the main page now highlights the right information instead of trying to show everything at once.
3. We confirmed the extra panels and windows now have clearer jobs.
4. We confirmed the full room-authoring workflow is still supported.

### Slice 2 Founder Approval Interview
1. “Do you agree the main page now uses space better, especially vertically?”
2. “Do you agree the supporting panels and windows now have clearer roles?”
3. “Do you approve moving into the copy cleanup and feature-pruning slice?”

---

## Slice 3

### Goal
Make the editor friendlier, clearer, and less noisy without removing important capability.

### Slice 3 Specialist Tasking
- `Design`
  - rewrite key copy and ensure the final UX reads clearly and confidently
- `QA`
  - validate copy clarity, dead-path removal, and accessibility polish
- `Level Design`
  - ensure tool prominence still reflects room-authoring priorities
- `Developer`
  - remove redundant UI, consolidate duplicate actions, and add final interaction polish

### Required Implementation
1. Replace long explanatory blocks with concise, action-first copy.
2. Remove placeholder or obsolete primary UI that creates dead ends or erodes trust.
3. Consolidate duplicate actions where the distinction is not meaningful.
4. Add missing accessibility polish already flagged by research, especially visible `:focus-visible`.
5. Keep the final implementation closely aligned to the approved mockups.

### Slice 3 QA Gate
QA must explicitly sign off all of the following:
- no dead buttons, orphaned labels, or broken selectors remain
- copy is shorter and clearer while preserving necessary workflow guidance
- keyboard and accessibility behavior are improved, not merely preserved
- visible focus states are present where needed
- the final implementation matches the approved mockup closely enough

### Slice 3 Founder Approval Criteria
These must be reported back in plain English:
1. We made the copy easier to understand.
2. We removed or reduced redundant and obsolete UI without breaking important features.
3. We confirmed the editor still feels powerful and useful after the cleanup.
4. We confirmed the final experience is strong enough to become the new baseline.

### Slice 3 Founder Approval Interview
1. “Do you agree the copy is now clearer and more user friendly?”
2. “Do you agree the removed or demoted features were safe to reduce?”
3. “Do you agree the final Room Editor experience is strong enough to adopt as the new default?”
4. “Do you want a follow-up slice for post-launch polish, or do you approve closing this UI/UX pass?”

---

## Cross-Slice Acceptance Criteria

These criteria apply across the full effort:
- the canvas gets materially more usable space during room editing
- the main page no longer tries to act as the full editor
- room editing feels like entering a focused workspace
- global map, runtime preview, and supporting review surfaces each have clearer homes
- copy is shorter and friendlier
- keyboard and focus behavior are explicit and visible
- the implementation stays faithful to approved mockups
- no critical room-authoring workflow regresses

---

## Research Evidence Output Format

At the end of each slice, include a compact section for each specialist with:
- Specialist
- Scoped task
- Sources consulted
- Source dates
- Why the sources were relevant
- What the specialist changed in their approach because of the research
- Any unresolved questions that remained after research

---

## Slice Completion Rule

A slice is only complete when:
- specialist scope memos are done
- specialist research evidence is done
- implementation is done
- QA gate is signed off
- founder approval criteria are summarized
- founder approval interview is ready

---

## Decision Summary

- **Recommendation:** Execute this as a design-first overhaul with a mandatory Slice 0 mockup and IA approval gate, then implement in three code slices: overlay foundation, shell-density and context-window cleanup, and copy or pruning or polish.
- **Risks:** The main risks are implementing before design lock, preserving too many existing rails and panels out of convenience, breaking overlay keyboard or focus behavior, and pruning UI that still has hidden dependencies in the current editor monolith.
- **Confidence:** High, because the repo evidence, specialist reviews, and primary UI and accessibility guidance all point to the same root problem: the shell is overloaded and is constraining the editor’s strongest workflow.
- **Founder approval needed:** Yes. Approval is needed for the product direction, the mandatory hi-fi mockup gate in Slice 0, and the slice structure before implementation begins.
- **Next actions:** Design produces the Slice 0 hi-fi mockups and retained or demoted or removed inventory. QA drafts the acceptance pack from this plan. Level Design signs off the task model for layout and context. Developer prepares a DOM and state dependency inventory in [room-layout-editor.html](/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html) so implementation can start cleanly once Slice 0 is approved.
