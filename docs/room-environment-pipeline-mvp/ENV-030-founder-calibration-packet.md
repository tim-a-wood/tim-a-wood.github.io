# ENV-030 — Founder calibration packet

## Purpose

This packet is the founder-facing review bundle for the first MVP room using the staged room-environment pipeline.

It is intentionally compact. The goal is to let the founder judge whether the new staged path is trustworthy enough to keep widening, without requiring them to inspect raw JSON files directly.

## Packet contents

### 1. Room identity

- `room_id`
- room name
- pipeline version
- stylepack lock status
- seed used for composition

### 2. Stylepack summary

Show:

- one-line style summary
- palette profile summary
- material / motif vocabulary highlights
- drift-forbidden traits
- whether the stylepack is still draft or explicitly locked

Source:

- `stylepack.json`
- `editor_results_payload.stylepack`

### 3. Semantics truth snapshot

Show:

- room role
- counts for tops, openings, anchors, cavities, decor-safe zones, exclusion zones
- overlay keys available for inspection
- truth checks

Source:

- `room_semantics.json`
- `editor_results_payload.semantics`

### 4. Kit summary

Show:

- structural / background / decor counts
- component count by type
- taxonomy summary
- kit validation errors, if any

Source:

- `environment_kit.json`
- `editor_results_payload.kit`

### 5. Manifest / composition summary

Show:

- pass order
- layer order
- total placement count
- deterministic replay key
- validation flags carried by the manifest

Source:

- `environment_manifest.json`
- `editor_results_payload.manifest`

### 6. Validation summary

Show:

- blocker / warning / info counts
- unresolved surfaces
- top blocker codes
- top warning codes
- whether visual validation is still pending or screenshot-backed

Source:

- `validation_report.json`
- `editor_results_payload.validation`

### 7. Open issues

Call out:

- any remaining blocker findings
- any warnings that could mislead founder review
- any known editor-only or browser-only gaps
- any coexistence or migration caveats

## Review standard

The founder should be able to answer:

1. Does the stylepack feel directionally right?
2. Do the semantics match the room truth?
3. Does the kit taxonomy feel believable and bounded?
4. Does composition look deterministic and inspectable?
5. Are the reported blockers/warnings clear enough to trust?
6. Is the staged pipeline good enough to keep widening?

## Current MVP status

Implemented and test-backed:

- staged semantics sidecar
- staged kit artifact
- deterministic composition manifest
- structured validation report
- disk-backed staged persistence and reopen hydration

Still required before calling the surface founder-ready:

- browser-backed visual inspection of the live editor Results surface
- final review of how overlays/highlights are shown in the editor

## Recommended first live packet

Use the first real irregular MVP room once:

- the stylepack is locked
- semantics overlay is visually checked in browser
- manifest and validation are generated from the persisted staged artifacts

At that point the founder packet should include:

- screenshots of the Results surface
- screenshot or artifact refs for semantics overlays
- the saved staged JSON artifact paths
- a short summary memo written from the exact saved artifacts
