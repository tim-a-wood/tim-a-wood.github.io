# Results State Browser Note — 2026-04-05

## Scope

This note covers the embedded Environment `Results` tab state-capture harness, not real room runtime approval.

- Harness: [scripts/capture_room_results_states.js](/Users/timwood/Desktop/projects/PWA/MV/scripts/capture_room_results_states.js)
- Captures: [artifacts/qa/room-results-states](/Users/timwood/Desktop/projects/PWA/MV/artifacts/qa/room-results-states)
- Summary JSON: [artifacts/qa/room-results-states/summary.json](/Users/timwood/Desktop/projects/PWA/MV/artifacts/qa/room-results-states/summary.json)

These screenshots are synthetic state injections through the editor QA hook. They are valid for Milestone 5 embedded Results-surface state coverage, but they are **not** Milestone 4 runtime approval evidence and they are **not** founder calibration artifacts.

## Captured States

- `empty`
- `draft`
- `locked`
- `generating`
- `partial`
- `ready`
- `blocked`

All seven captures were produced in Chrome from the embedded room-editor Results tab and have distinct file hashes.

## Visual Inspection

### Empty

Inspected artifact: [empty.png](/Users/timwood/Desktop/projects/PWA/MV/artifacts/qa/room-results-states/empty.png)

Visible observations:
- The Environment `Results` tab is open and the staged card stack is visible in the expected order, including `1. Stylepack` through `6. Overlay view`.
- The build button reads `Build Production Assets` and appears disabled.
- The preview area is sparse compared with later states, and the lower overlay region shows the room map without runtime-review thumbnails or generated asset cards.

### Ready

Inspected artifact: [ready.png](/Users/timwood/Desktop/projects/PWA/MV/artifacts/qa/room-results-states/ready.png)

Visible observations:
- The build button reads `Rebuild Production Assets` and appears enabled.
- The stage cards show a more complete, success-oriented surface than `empty`, including green status accents and populated stage summaries.
- The overlay section contains a cyan-framed preview box with a purple center marker, and the asset area includes additional rendered cards/thumbnails that are absent in the `empty` state.

### Blocked

Inspected artifact: [blocked.png](/Users/timwood/Desktop/projects/PWA/MV/artifacts/qa/room-results-states/blocked.png)

Visible observations:
- The Results tab remains open, but the validation area contains red/error accents that are not present in `ready`.
- The stage stack is taller than `ready`, indicating additional blocker text and surfaced findings.
- The lower visual review area shows a darker runtime/review region with a more failure-oriented presentation than the greener `ready` capture.

## What This Proves

- The embedded Results surface can now be opened and captured in-browser across the requested QA state set.
- The captured states are visually distinct and preserve the staged card order in browser output.
- Button copy changes across state are visible in-browser: `Build Production Assets`, `Retry Build Production Assets`, and `Rebuild Production Assets`.

## What This Does Not Prove

- These captures do not prove real planner truth on calibration rooms.
- These captures do not prove real runtime composition or contrast-QA approval.
- These captures do not replace exact saved runtime-review artifacts from the actual room-environment pipeline.
