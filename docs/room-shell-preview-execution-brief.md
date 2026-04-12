# Room Shell / Preview Corrective Pass — Execution Brief

**Date:** 2026-04-10  
**Status:** Ready for implementation  
**Primary source plan:** [room-shell-preview-corrective-action-plan.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-shell-preview-corrective-action-plan.md)  
**Supporting review:** [dev-qa-review-corrective-action-plan.md](/Users/timwood/Desktop/projects/PWA/MV/docs/dev-qa-review-corrective-action-plan.md)

## Purpose

This brief converts the corrective plan into an implementation-ready operating document for the agent who will execute the work.

It is optimized for:

- Developer-led implementation
- mandatory pre-implementation research
- explicit specialist involvement
- artifact-based QA
- visual-validation honesty
- anti-regression guardrails

## Scope

Target project and room:

- `Room AI Helpfulness QA`
- `R1`

Corrective scope:

1. shell reference contract
2. shell debug material reference
3. preview shape fidelity
4. ruins/theme drift

## Authoritative Constraints

These rules override any conflicting suggestion elsewhere.

1. Do not source shell debug material from `wall_piece`, `ceiling_piece`, or `primary_floor_piece`.
2. Do not reintroduce those obsolete component families as a fallback, a shortcut, or a temporary debug path.
3. Do not claim visual success without directly inspecting the exact saved artifacts being cited.
4. Do not loosen shell validation in this pass unless a failing test proves the validator itself is wrong.
5. Do not route around bad shell inputs by hiding them with runtime or postprocess tricks.

## Required Specialist Subagents

The implementing agent must use these specialist roles before and during implementation.

### 1. Developer Specialist

Owns:

- code-path tracing
- implementation sequencing
- shell debug-path changes
- prompt/reference-role alignment
- regression implementation

### 2. QA Specialist

Owns:

- automated regression design
- pass/fail gate definition
- provenance checks
- artifact checklists
- founder-facing acceptance packet support

### 3. Visual Validation Specialist

Owns:

- direct inspection of exact saved artifacts
- visible observation logging
- pairwise artifact comparison
- shell-thickness consistency review
- preview shape-fidelity review

### 4. Optional Supporting Specialists

Use only if needed by the implementing agent:

- `Runtime/Compositor` for preview/runtime artifact consumption and fidelity drift
- `Theme/Direction` or equivalent reviewer for `ruins` drift cleanup if the project/theme contract becomes ambiguous

## Mandatory Specialist Workflow

Each specialist must complete this sequence before implementation decisions are locked.

### Step 1. Scope Memo

Each specialist must produce:

- what they own
- what they do not own
- known failure modes
- anti-regression risks
- blocked decisions

### Step 2. Research Before Code

Each specialist must review only the sources that are directly relevant.

Minimum required research set:

- [research/library/INDEX.md](/Users/timwood/Desktop/projects/PWA/MV/research/library/INDEX.md)
- [research/dashboard.md](/Users/timwood/Desktop/projects/PWA/MV/research/dashboard.md)
- [2026-03-31-room-environment-quality-pass.md](/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md)
- [room-shell-preview-corrective-action-plan.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-shell-preview-corrective-action-plan.md)
- [dev-qa-review-corrective-action-plan.md](/Users/timwood/Desktop/projects/PWA/MV/docs/dev-qa-review-corrective-action-plan.md)
- the exact current saved artifacts in the target room
- the exact current code paths in [room_environment_system.py](/Users/timwood/Desktop/projects/PWA/MV/scripts/room_environment_system.py)

### Step 3. Research Evidence Bundle

Each specialist must record:

- sources read
- why they mattered
- what changed because of them
- what was rejected

### Step 4. Approach Recommendation

Each specialist must recommend:

- the narrowest correct fix
- what must not change
- what QA must block

### Step 5. Execution

Only after the steps above are complete may implementation begin.

## Prior Specialist Findings Already Available

These findings are already established and should not be rediscovered from scratch.

### Developer Findings Already Confirmed

- the active shell retry path currently uses `contract -> guide -> material`
- the inconsistent shell-thickness read is already present in the shell contract/guide artifacts
- the shell debug material ref is being poisoned by the keyed `foreground_frame` source
- stale shell debug artifacts from older regimes are mixed beside current shell refs
- obsolete structural sibling templates are not allowed back into this shell path

### QA Findings Already Confirmed

- shell validation catches some failures, but not malformed in-band thickness well enough
- preview approval lacks a real visual fidelity gate
- there is no adequate regression protecting against theme drift from generic `hall` language
- obsolete-template fallback must be treated as a hard QA failure

### Visual Validation Findings Already Confirmed

- the failed shell, shell contract, and shell guide all visibly share the same thickness inconsistency
- the shell debug material ref is visibly unusable
- the silhouette debug artifact is visually poor
- the preview outputs are still fundamentally full-frame compositions rather than shape-faithful room previews

## Slice Order

Execute in this order.

### Slice 1. Shell Reference Contract Stabilization

Goal:

- make shell geometry refs consistent, readable, and authoritative

Implementation focus:

- shell contract map
- shell guide
- shell reference-role metadata
- stale shell ref cleanup
- pre-punchout corner gate restoration

### Slice 2. Shell Debug Material Stabilization

Goal:

- replace the broken shell material swatch with a shell-safe debug material reference

Implementation focus:

- remove `foreground_frame` poisoning
- create shell-specific debug-material sourcing
- reject keyed/placeholder colors
- fail loudly if valid shell material debug input cannot be built

### Slice 3. Preview Shape Fidelity

Goal:

- make previews reflect the room shape rather than merely overlaying it

Implementation focus:

- post-generation shape masking/cropping
- preview validation prior to approval
- preview fidelity gates

### Slice 4. Ruins Drift Cleanup

Goal:

- stop generic wording and stale defaults from silently forcing `ruins`

Implementation focus:

- heuristic cleanup
- explicit theme precedence
- stale room/project spec correction
- generic prompt cleanup

## Implementation Instructions By Slice

## Slice 1 — Shell Reference Contract Stabilization

### Developer Execution Tasks

1. Audit the exact active shell ref set for the target failing room and confirm current order, timestamps, and saved attempt metadata.
2. Replace the current isotropic shell-band construction with a geometry-aware shell-band construction that preserves consistent visual thickness around straight runs, elbows, and concave turns.
3. Remove the unnecessary mixed shell color-language ambiguity from the active shell geometry references.
4. Ensure the shell retry path writes only the refs it actually uses.
5. Segregate or retire stale shell debug refs that belong to older shell-reference regimes.
6. Restore a real pre-punchout shell continuity/corner gate so malformed candidates can fail before deeper retry stages.
7. Update prompt/reference-role wording to match the actual live shell ref order and semantics.

### QA Gates

Slice 1 fails if any of these are true:

- shell first-generation refs are not exactly the intended current set and order
- shell guide and contract still teach visibly inconsistent wall thickness
- shell elbow / inner step is not visually clear in the saved refs
- stale shell debug refs remain mixed into the active `_refs` debugging surface without clear separation
- the pre-punchout continuity gate remains effectively disabled

### Required Automated Regressions

- assert exact active shell ref order
- assert shell contract/provenance metadata is persisted
- assert no obsolete shell refs are returned as active inputs
- assert shell-band thickness remains within tolerance on an L-shaped room
- assert pre-punchout shell continuity checks are functional

### Required Visual Validation

Inspect these artifacts directly:

- current shell contract
- current shell guide
- current shell silhouette if still written
- raw generated shell candidate

Record at least 3 concrete visible observations for:

- shell-band thickness consistency
- elbow / step legibility
- outer margin emptiness
- absence of nested-frame teaching

## Slice 2 — Shell Debug Material Stabilization

### Developer Execution Tasks

1. Remove `foreground_frame` as the shell debug material source.
2. Do not replace it with `wall_piece`, `ceiling_piece`, or `primary_floor_piece`.
3. Implement a shell-specific debug material source strategy only.
4. Acceptable directions:
   - sanitized approved-preview sampling that strips out geometry/composition signals
   - deterministic neutral shell debug texture created specifically for shell validation/debugging
5. Add explicit keyed-green and placeholder-color rejection to the patch-selection path.
6. Fail hard if a valid shell-specific material debug ref cannot be produced.

### QA Gates

Slice 2 fails if any of these are true:

- shell material debug ref contains keyed green or placeholder colors
- shell material debug ref still reads like a scene crop or framed room image
- shell material debug ref falls back to raw preview composition
- shell material path uses `wall_piece`, `ceiling_piece`, or `primary_floor_piece`

### Required Automated Regressions

- assert shell material ref rejects keyed-green input
- assert shell material ref does not use obsolete structural sibling templates
- assert shell material ref provenance is shell-specific and not raw-preview fallback

### Required Visual Validation

Inspect directly:

- active shell material debug artifact
- source material artifact used to build it
- regenerated raw shell candidate using that material input

Record at least 3 concrete visible observations for:

- material usefulness
- absence of placeholder/debug colors
- absence of framed room composition leakage

## Slice 3 — Preview Shape Fidelity

### Developer Execution Tasks

1. Add post-generation shape masking or cropping to level-3 previews.
2. Preserve only the portion of the scene that belongs to the intended room footprint.
3. Add a preview-validation step before approval.
4. Block preview approval when perspective/layout drift is obvious.

### QA Gates

Slice 3 fails if any of these are true:

- saved previews remain generic rectangular scenes while claiming room-shape fidelity
- wrong-layout or wrong-perspective previews can still be approved
- preview artifacts are not consistent with the room footprint contract

### Required Automated Regressions

- assert non-rectangular rooms do not silently drift to generic rectangular hall previews
- assert shape masking/cropping is applied when this feature is enabled
- assert preview approval is blocked if preview validation fails

### Required Visual Validation

Inspect directly:

- all three saved preview variants
- the approved preview candidate if any
- any saved composite/editor artifact shown in approval UI

Record at least 3 concrete visible observations per key preview for:

- room-shape fidelity
- perspective fidelity
- whether the result is still a rectangular scene with a footprint overlay

## Slice 4 — Ruins Drift Cleanup

### Developer Execution Tasks

1. Remove or narrow generic keyword mappings that force `ruins`.
2. Ensure explicit theme choice wins over heuristic inference.
3. Clean stale room/project theme state when required by the approved fix path.
4. Remove generic prompt wording that unnecessarily hardcodes ruined-gothic direction into non-ruins flows.

### QA Gates

Slice 4 fails if any of these are true:

- generic architectural language still forces `ruins`
- explicit non-ruins theme choices still drift back to ruined-gothic in outputs
- preview or shell artifacts visibly contradict selected non-ruins direction

### Required Automated Regressions

- assert `hall` no longer silently implies `ruins` unless explicitly intended
- assert explicit non-ruins theme survives preview generation
- assert explicit non-ruins theme survives shell generation

### Required Visual Validation

Inspect directly:

- regenerated preview artifacts
- regenerated shell/material refs

Record at least 3 concrete visible observations for:

- biome/theme correctness
- absence of stale ruined-gothic drift
- consistency with the approved room/theme direction

## Global QA Gates

These apply across all slices.

1. No slice is complete without exact saved-artifact inspection.
2. No slice is complete without automated regressions for the new behavior.
3. No slice is complete if any positive visual claim is based only on tests or code intent.
4. No slice is complete if artifact provenance is unclear or stale.
5. No slice is complete if the obsolete-template rule is violated anywhere in the shell debug-material path.

## Visual Validation Protocol

The Visual Validation specialist must inspect and compare:

- shell silhouette
- shell guide
- shell contract
- shell material ref
- raw shell output
- final shell output
- runtime/review artifact
- preview artifacts

For each key artifact, the reviewer must record:

- exact artifact path
- timestamp
- whether it was visually inspected directly
- at least 3 concrete visible observations
- pass/fail verdict

Automatic visual fail conditions:

- boxed shell where concave shell is expected
- inconsistent wall thickness that changes the shell read
- nested-frame or duplicated-frame teaching
- forbidden outer margin visibly filled
- debug-material leakage into final shell
- preview remains a generic rectangular composition instead of respecting room shape

## Research Bundle Requirement

Before code is merged, the implementing agent must include a compact research bundle in the handoff.

Per specialist, record:

- specialist name
- scoped task
- sources consulted
- why those sources were relevant
- what changed because of that research
- what was rejected

Minimum included sources:

- internal research index
- internal research dashboard
- room-environment decision log
- corrective plan
- Developer+QA review doc
- exact saved target artifacts
- exact code modules touched

## Founder Review Points

Founder review is required for:

1. whether previews should become room-shape-scoped by default
2. whether generic `hall` language should stop implying `ruins`

Suggested founder interview at the end of implementation:

1. Do you agree the saved shell references now teach one clear perimeter shape and thickness?
2. Do you agree the shell debug material input is now useful and not polluted by placeholder imagery?
3. Do you agree the saved previews now match the room shape closely enough to trust them?
4. Do you agree the room no longer drifts into `ruins` unless that is explicitly intended?
5. Do you approve closing this corrective pass or want a follow-up runtime polish slice?

## Definition Of Done

This corrective pass is only done when:

- slices are executed in order
- required specialists complete scope + research + recommendation before code
- automated regressions pass
- exact saved artifacts are visually inspected
- QA signs off all active gates
- obsolete-template rule remains unbroken
- founder review points are answered where required

## Recommendation

Use this brief as the implementation source of truth, with Slice 1 and Slice 2 executed first as the shell-input stabilization pass before preview and theme cleanup.

## Risks

- The highest risk is regression through an “easy fallback” that quietly reintroduces obsolete template families into the shell debug path.
- The second-highest risk is declaring preview success before shape-scoped preview artifacts actually exist.
- The third-highest risk is fixing the shell inputs while leaving ruins drift uncorrected, causing the wrong direction to keep resurfacing.

## Confidence

High. This brief is based on direct artifact inspection, traced code paths, Developer and QA specialist findings, and explicit anti-regression constraints.

## Founder Approval Needed

Yes — for preview shape-scoping policy and for the `hall` -> `ruins` inference change.

## Next Actions

1. Approve this execution brief.
2. Run Slice 1 and Slice 2 with Developer, QA, and Visual Validation specialists engaged from the start.
3. Present the regenerated shell artifact packet for founder review.
4. Only then move to Slice 3 and Slice 4.
