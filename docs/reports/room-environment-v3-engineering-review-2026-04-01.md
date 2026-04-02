# Room Environment Pipeline V3 — Engineering Review

**Date:** 2026-04-01
**Reviewer:** Development
**Package reviewed:**
- [docs/room-environment-pipeline-v3-spec.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-spec.md)
- [docs/reports/room-environment-v3-stakeholder-review-kickoff-2026-04-01.md](/Users/timwood/Desktop/projects/PWA/MV/docs/reports/room-environment-v3-stakeholder-review-kickoff-2026-04-01.md)
- [decisions/2026-03-31-room-environment-quality-pass.md](/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md)

## Position

Accept with changes.

The v3 direction is technically correct and materially stronger than the current architecture. The current code has hit an architectural ceiling. The proposed rewrite is justified.

The spec is strongest on:

- separating biome definition from room planning
- making component-fit explicit
- requiring room assembly planning from actual geometry
- introducing manual review as a formal gate

The spec needs tighter implementation framing in a few areas before coding starts.

## Top Findings

### 1. The current planner should be replaced, not incrementally expanded

The existing room-component planner in [scripts/room_environment_system.py](/Users/timwood/Desktop/projects/PWA/MV/scripts/room_environment_system.py#L3443) under-represents the room by collapsing it to one main floor, a few hero platforms, and one active door. That is not a safe base for extension. A piecemeal modification risks preserving incorrect assumptions.

Recommendation: implement a new planner module or clearly separated planner path rather than mutating the current one in place.

### 2. Schema versioning must be explicit before implementation

The proposed v3 data model introduces new first-class concepts:

- `biome_definition`
- `room_intent`
- `component_contracts`
- `assembly_plan`
- `review_state`
- new component types including `ceiling` and `backwall_panel`

Those changes are architecture-level changes and should not be introduced informally into the current structure.

Recommendation: define a room environment schema version bump before Phase 1 starts. Keep room layout export schema separate if runtime export does not yet consume all v3 environment metadata.

### 3. Review tooling should not be built first

The spec lists review tooling as a major phase, which is correct, but it should not come before the schema and planner slice. Screenshot tooling is only valuable once the assembly-plan view and slot generation outputs exist in stable form.

Recommendation: build order should be:

1. schema/data model
2. planner rewrite
3. prompt scaffold rewrite
4. biome kit rewrite
5. review tooling
6. calibration rounds

### 4. `ceiling` and `backwall_panel` are good additions, but they should be introduced behind a narrow first slice

These types are likely necessary to fix shell readability, but adding too many new types at once creates migration risk and validation complexity.

Recommendation: support them in the schema from the start, but only require them for the first calibration biome and first fixture rooms once the planner can actually place them correctly.

### 5. The current code contains reusable pieces, but not reusable architecture

Likely reusable:

- palette extraction
- image fit/crop helpers
- some bespoke validation helpers
- runtime review metrics as a starting point
- helpfulness ledger if still desired

Not safely reusable as architecture:

- monolithic spec prompt flow
- single-pack biome selection
- current planner
- current slot/reference-image assumptions
- current implicit fallback-heavy spec normalization strategy

## Required Changes Before Coding

### 1. Split implementation into explicit modules

Do not continue growing [scripts/room_environment_system.py](/Users/timwood/Desktop/projects/PWA/MV/scripts/room_environment_system.py) as one giant file for v3.

At minimum separate:

- biome definitions
- planner
- prompt scaffolds
- validators
- review tooling

### 2. Define a migration boundary

The system needs a clear decision on whether v3:

- coexists beside v2 behind a feature flag
- replaces v2 immediately for selected rooms
- or uses a room-level pipeline version flag

Recommendation: use a room-level or environment-level pipeline version flag and keep v2 readable during the calibration phase.

### 3. Lock the first slice more tightly

The first slice should be:

- one biome
- three rooms
- required component types limited to:
  - walls
  - floor
  - platforms
  - doors
  - background
  - midground
  - ceiling
  - backwall_panel

Do not solve all hazard families or all biome variants in the first slice.

## Recommended Implementation Sequence

### Phase A

- define v3 schema contracts
- add pipeline versioning
- define biome-definition storage

### Phase B

- implement new assembly planner
- add assembly-plan overlay output

### Phase C

- implement slot-level prompt scaffolds
- define component-fit validators

### Phase D

- generate first biome kit
- run first three-room calibration set

### Phase E

- add screenshot capture and formal review persistence
- start QA and Creative rounds

## Technical Risks

- Planner complexity may grow quickly for irregular rooms if slot segmentation rules are underspecified.
- Runtime composition may still expose hidden shell gaps even if individual slots validate.
- Mixing v2 and v3 data in the same room payload could create migration bugs if version boundaries are unclear.

## Verdict

Pass with flags.

The technical direction is sound, but coding should not start until schema/versioning boundaries and module boundaries are written down explicitly.

