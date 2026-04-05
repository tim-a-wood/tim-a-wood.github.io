# ENV-029 — Legacy v3 deprecation path

## Goal

Retire legacy v3-only fields gradually once the staged artifact path is trusted, without silently deleting data and without breaking existing room-editor flows during MVP calibration.

## Current coexistence model

The room environment still carries both:

- legacy/generated v3 fields on `room.environment`
  - `room_intent`
  - `component_contracts`
  - `assembly_plan`
  - `review_state`
  - `runtime.bespoke_asset_manifest`
- staged derived artifacts
  - `reference_pack`
  - `stylepack`
  - `room_semantics`
  - `environment_kit`
  - `environment_manifest`
  - `validation_report`
  - `staged_artifacts`
  - `editor_results_payload`

This coexistence is intentional during MVP calibration.

## Deprecation phases

### Phase 0 — additive only

Status: current MVP state

- Keep all legacy v3 fields readable and writable.
- Persist the staged artifacts to disk under `room_environment_assets/{room_id}/derived/v3/`.
- Hydrate staged artifacts on reopen when present.
- Treat staged artifacts as the preferred review surface, but not the only source of truth for legacy callers.

Exit criteria:

- staged save/load is stable
- reopen hydration is proven
- editor Results surface reads staged payload cleanly

### Phase 1 — staged artifacts become the preferred review contract

- Keep writing legacy fields and staged artifacts together.
- Treat the staged artifacts plus `editor_results_payload` as the canonical founder/QA review bundle.
- Legacy UI or server paths may still read `assembly_plan`, `review_state`, or `runtime.bespoke_asset_manifest`, but new logic should not introduce fresh one-off review fields outside the staged set.

Exit criteria:

- semantics, kit, composition, validation, and persistence all pass regression and QA gates
- no active editor surface depends on undocumented legacy-only review data

### Phase 2 — freeze legacy-field expansion

- Do not add new product meaning to:
  - `room_intent`
  - `component_contracts`
  - `assembly_plan`
  - `review_state`
- New staged MVP data must land in the derived artifacts or their payload bridge, not in ad hoc room-environment fields.
- Keep bridge compatibility reads in place.

Exit criteria:

- at least one founder-reviewed MVP room has been calibrated using the staged artifact path
- migration gaps are documented in `validation_report` or implementation notes

### Phase 3 — narrow legacy writes

- Stop writing replacement data redundantly into legacy structures where a staged artifact already owns that concern.
- Allowed exceptions:
  - fields still required by runtime or legacy preview/build code
  - compatibility summaries that are cheap and clearly derived
- Keep read support for legacy data so older saved rooms still open.

Candidate reductions:

- semantic review details should live only in `room_semantics`
- kit counts and taxonomy should live only in `environment_kit`
- manifest layer summaries should live only in `environment_manifest`
- validation severity details should live only in `validation_report`

Exit criteria:

- no reopen/regression failures from older rooms
- QA confirms staged artifacts remain sufficient without the redundant legacy mirrors

### Phase 4 — explicit retirement

- Mark legacy fields as compatibility-only in docs and code comments.
- If removal is desired later, do it in a dedicated migration pass with:
  - written founder approval
  - one-time migration notes
  - backward-compatibility fallback for older saved rooms

## Hard rules

- No silent deletion during MVP.
- No schema rename of the on-disk derived-artifact root during MVP unless founder-approved.
- No removal of `environment_pipeline_version` gating during MVP.
- If staged and legacy values disagree, prefer staged artifacts for review surfaces and log the mismatch as a validation/info concern instead of mutating data silently.

## Immediate next use

Use this path after `ENV-027` and `ENV-028`:

1. Keep the bridge dual-writing.
2. Stop adding new review semantics to legacy fields.
3. Use the founder calibration packet to decide when staged artifacts are trustworthy enough to begin Phase 2.
