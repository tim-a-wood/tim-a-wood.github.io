# Room Environment Pipeline V3 — QA Review

**Date:** 2026-04-01
**Reviewer:** QA
**Package reviewed:**
- [docs/room-environment-pipeline-v3-spec.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-spec.md)
- [docs/reports/room-environment-v3-stakeholder-review-kickoff-2026-04-01.md](/Users/timwood/Desktop/projects/PWA/MV/docs/reports/room-environment-v3-stakeholder-review-kickoff-2026-04-01.md)
- [decisions/2026-03-31-room-environment-quality-pass.md](/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md)

## Position

Accept with changes.

The spec correctly recognizes that automated validation is not sufficient and that screenshot-driven review through the actual workflow is necessary. QA supports the direction, but the validation loop needs sharper blocker definitions and more operational detail.

## Top Findings

### 1. The screenshot checkpoints are good, but the assembly-plan overlay is mandatory

The current required screenshot set is strong, especially because it includes:

- environment setup
- component contracts
- assembly plan
- slot gallery
- assembled kit view
- runtime screenshot
- contrast-QA screenshot

This is enough to catch many current failures, but only if the assembly-plan screenshot is not optional. Without it, QA cannot tell whether a missing visual result is caused by planning or generation.

Recommendation: treat missing assembly-plan capture as a blocked review run.

### 2. Review rounds need blocker severity definitions

The spec calls for multiple rounds but does not fully define what fails a round.

Recommended blockers for any round:

- missing required slot for any major room structure
- any door in-room without corresponding threshold slot
- floor or hero platform top unreadable at gameplay scale
- midground crossing the center traversal lane
- background acting as the sole shell read
- component-fit failure on walls, floors, platforms, or doors
- runtime screenshot showing collage/composite read

### 3. Fixture room coverage should be locked before implementation review starts

The proposed room types are directionally correct. QA recommends a fixed review matrix with named fixtures and stable IDs.

Recommended minimum calibration matrix:

- `fixture_corridor_transition`
- `fixture_vertical_shaft`
- `fixture_shrine_chamber`
- `fixture_multi_door_hub`
- `fixture_pit_traversal`
- `fixture_large_arena`

The first slice may only implement three of these, but the full matrix should be defined now so the team does not keep changing what “good” means.

### 4. Manual review records need structured defect categories

If QA and Creative are both reviewing screenshots repeatedly, findings must be bucketed consistently.

Recommended categories:

- `component_fit`
- `planner_coverage`
- `biome_identity`
- `shell_readability`
- `traversal_readability`
- `motif_violation`
- `runtime_composition`
- `workflow_usability`

### 5. Real runtime capture should remain preferred

The current runtime review logic in [scripts/room_environment_system.py](/Users/timwood/Desktop/projects/PWA/MV/scripts/room_environment_system.py#L4441) often falls back to a composite image. That is useful for debugging, but QA does not want composite fallback to become the de facto review artifact for v3.

Recommendation: for formal review rounds, both runtime and composite screenshots should be stored when available, but runtime should be the approval artifact.

## Additional QA Requirements

### Naming Convention

Each screenshot should include:

- room id
- biome id
- round
- reviewer role
- stage
- timestamp

### Required Per-Round Outputs

- screenshot bundle
- findings log
- blocker summary
- pass/fail status

### Required Regression Check

Whenever planner or prompt logic changes, rerun at least one previously approved room and compare against prior screenshots.

## Recommended Blocker Criteria

### P1 For Review Rounds

- incorrect component type read
- missing planned major slot
- center-lane occlusion
- unreadable threshold
- unreadable top plane
- shell coherence failure in runtime

### P2 For Review Rounds

- weak biome distinctness
- non-blocking motif drift
- minor composition mismatch
- review workflow friction without correctness impact

## Verdict

Pass with flags.

QA supports proceeding if the team adds explicit blocker definitions, fixed fixture naming, and a stronger requirement for assembly-plan screenshots and runtime-first review evidence.

