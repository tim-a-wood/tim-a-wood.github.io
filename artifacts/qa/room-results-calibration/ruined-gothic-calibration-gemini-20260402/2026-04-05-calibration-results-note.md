# Calibration Results Note — 2026-04-05

## Scope

This note records direct visual inspection of exact saved embedded `Results` tab screenshots for the ruined-gothic calibration project:

- [RG-R1.png](/Users/timwood/Desktop/projects/PWA/MV/artifacts/qa/room-results-calibration/ruined-gothic-calibration-gemini-20260402/RG-R1.png)
- [RG-R2.png](/Users/timwood/Desktop/projects/PWA/MV/artifacts/qa/room-results-calibration/ruined-gothic-calibration-gemini-20260402/RG-R2.png)
- [RG-R3.png](/Users/timwood/Desktop/projects/PWA/MV/artifacts/qa/room-results-calibration/ruined-gothic-calibration-gemini-20260402/RG-R3.png)
- Capture summary: [summary.json](/Users/timwood/Desktop/projects/PWA/MV/artifacts/qa/room-results-calibration/ruined-gothic-calibration-gemini-20260402/summary.json)

These are real project-backed editor screenshots, not synthetic state injections.

The latest capture pass on 2026-04-05 also includes a bounded-layout adjustment for the embedded `Results` tab. The real calibration screenshots now save at roughly `5670px`, `5742px`, and `5814px` tall instead of the earlier `7618px` to `8799px` range, because the dense review summary is now bounded beside the preview/gallery area on large screens.

## What The Capture Proves

- The editor can open the embedded Environment `Results` tab for all three ruined-gothic calibration rooms through the normal `?project_id=` flow.
- All three rooms keep the canonical staged order in browser output:
  1. Stylepack
  2. Semantics
  3. Kit
  4. Manifest
  5. Validation
  6. Overlay view
- Each room exposes a live rebuild action (`Retry Build Production Assets`) and a populated review surface rather than an empty placeholder state.

## Visual Inspection

### RG-R1

Visible observations:
- The panel includes a real generated preview image, not just text summaries, and the validation card shows mixed yellow/red findings.
- The generated preview plus thumbnail strip now sit to the left of a bounded review column, so the validation and staged cards are visible higher on the page than before.
- The review column still contains the full staged contract, including validation findings, but it no longer pushes the image gallery several screen-heights downward.

Assessment: this is not useless. It is a working review surface for a real room, and the current layout is more usable than the first long-stack version, though it is still denser than the approved mockup.

### RG-R2

Visible observations:
- The generated preview image and review summary are present, with the validation card again surfacing warnings and blockers in-line.
- The preview/gallery column and the bounded summary column now read as separate review lanes instead of one giant vertical stack.
- The room still feels less immediately informative than `RG-R1` because the overlay region remains visually sparse, but the page structure is easier to scan than before.

Assessment: the surface is functional, but some rooms make the overlay feel less informative than it should.

### RG-R3

Visible observations:
- The stage stack remains populated with a real preview image, validation findings, and the same canonical card order.
- The preview/gallery and the review summary now share the same horizontal band, which reduces the amount of vertical travel needed to compare image output against validation notes.
- The room is still the tallest of the three because its content is inherently dense, but it no longer feels like an endless single-column debug dump.

Assessment: this room makes the current layout weakness obvious. The tab still works, but repeated review would be slower than it should be.

## Conclusion

The current embedded `Results` tab is not a dead-end surface.

- It is connected to real project-backed staged data for the ruined-gothic calibration rooms.
- It exposes previews, validation findings, overlays, and asset galleries in browser output.
- The main weakness is still presentation efficiency, but the bounded summary layout proves that the panel can move toward the approved review model without throwing away the staged data.

This means the current work is worth continuing, but the next high-leverage improvement should be Results-surface composition and review ergonomics rather than runtime-art fine tuning.
