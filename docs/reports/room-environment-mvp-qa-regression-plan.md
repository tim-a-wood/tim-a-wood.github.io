# Room Environment MVP QA Regression Plan

**Date:** 2026-04-04
**Owner:** QA
**Scope:** Room Environment Pipeline MVP adaptation, milestones 1-7

## Assumption

No separate milestone document was present in the repo, so this plan maps the seven MVP milestones to the Phase A-F structure in [docs/room-environment-pipeline-v3-software-requirements.md](/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-software-requirements.md) plus the final rollout gate.

## Release-Gate Posture

- Blockers always stop the current milestone and block rollout.
- Warnings do not automatically block a milestone, but warnings in browser capture, export determinism, or visual evidence must be resolved before rollout or before the next broader milestone.
- Info items never block progress and are evidence only.

## Validation Report Severity Contract

`validation_report.json` should roll up like this:

- `blocker` means the report status is `fail`.
- `warning` means the report status is `warning` when there are no blockers.
- `info` is non-blocking metadata and should not change a passing report into a warning.

Recommended interpretation for the report:

| Severity | Meaning | Example |
|---|---|---|
| `blocker` | Hard stop for the current milestone and rollout | Missing assembly-plan screenshot, silent v2->v3 upgrade, invalid schema, browser capture fallback used as approval evidence |
| `warning` | Acceptable for local iteration, but must be tracked and closed before rollout | Weak biome identity, minor composition drift, cross-browser cosmetic mismatch, incomplete annotation metadata |
| `info` | Evidence only | Artifact hashes, timestamps, room ids, reviewer notes, pass counts, non-blocking coverage summaries |

## Milestone Regression Matrix

| Milestone | What to test | Blockers | Required evidence |
|---|---|---|---|
| 1. Schema and version boundary | Save/load v2 and v3 payloads; explicit `environment_pipeline_version`; no silent upgrade | Missing version field, v3 fields absent, v2 unreadable, silent migration | Schema/unit tests and a round-trip JSON fixture |
| 2. Planner coverage | Geometry-first assembly plan, slot map, overlay coverage, all doors and major traversal structures represented | Collapsed room summary, missing major slot, missing door threshold, missing overlay | Planner tests and the assembly-plan screenshot |
| 3. Prompt scaffolds and component fit | Slot-level prompts, structural vs scenic separation, negative constraints, fit validators | Raw scenic art used for structural slots, component-fit failure, broad prompt leakage | Prompt fixture tests, slot-gallery capture, validation report |
| 4. Runtime composition | Compose the room from generated slots, capture runtime and contrast-QA views, reject collage/composite reads | Composite fallback used for approval, browser capture missing, center-lane occlusion, unreadable shell | Browser runtime screenshot set and runtime validation result |
| 5. Review workflow | Fixed review-surface order, screenshot bundle persistence, findings recording, severity roll-up | Wrong surface order, missing screenshot bundle, missing blocker summary, bad severity roll-up | Review bundle manifest, `validation_report.json`, findings memo |
| 6. Calibration set | End-to-end reruns for the locked first slice rooms, compare against prior approved bundles, repeat QA and Creative loops | Any previously approved room regresses, any unresolved blocker remains, no written findings memo | Three room-level calibration reports and artifact hashes |
| 7. Rollout hardening | Real-browser rerun of a previously approved room, export determinism, cross-browser smoke, final go/no-go | Browser diff, nondeterministic export, flaky rerun, unresolved rollout warning | Playwright results, export hash comparison, release-gate memo |

## Required Browser-Backed E2E Flow

Use a real browser session for the approval path. Do not substitute jsdom, DOM-only tests, or composite fallback screenshots for this flow.

1. Open the local workbench or runtime wrapper in a browser.
2. Load the locked fixture room for the milestone under test.
3. Select the v3 environment pipeline and generate the proposal.
4. Inspect the assembly-plan overlay before generation continues.
5. Generate slots and open the slot gallery.
6. Open the combined kit, then the runtime view, then the contrast-QA view.
7. Save the artifact bundle and reload the saved room from disk.
8. Compare the saved `validation_report.json`, runtime screenshot, and export hash against the expected baseline.
9. Repeat the same smoke path in at least one second browser before rollout.

## Visual Validation Honesty Requirements

- Inspect the exact saved artifact that will be cited.
- State the file path of the artifact being judged.
- Include at least three concrete visible observations from that exact artifact.
- Do not claim that an image is good, better, clearer, or approved unless the exact saved file was visually inspected.
- Composite fallback, mockups, or generated previews can be useful for debugging, but they are not approval evidence.
- If the artifact is bad, say so plainly and keep the milestone blocked.
- Test results can support a visual claim, but they do not replace direct inspection of the saved image.

## QA Handoff For Engineering

- Treat milestone 1 as the contract gate: schema, versioning, and round-trip persistence must stay stable before anything else expands.
- Treat milestone 2 and 4 as the highest-risk visual/behavioral gates because they can fail even when unit tests pass.
- Treat milestone 5 as the place where `validation_report.json` should become the shared source of truth for blocker and warning triage.
- Treat milestone 6 as the last calibration loop before rollout, not as a cosmetic pass.
- Treat milestone 7 as the release candidate gate: one browser-backed rerun, cross-browser smoke, export determinism, and no unresolved blockers.

