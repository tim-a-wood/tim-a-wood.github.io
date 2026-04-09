# Ruined Gothic Runtime Artifact Note — 2026-04-05

## Scope

This note records direct visual inspection of exact saved runtime-review artifacts from:

- [tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402)
- Saved project summary: [ruined_gothic_calibration_summary.json](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/ruined_gothic_calibration_summary.json)

These are real saved runtime-review images, not synthetic UI-state captures.

## Saved Project Status

Two sources now exist and they do not fully agree:

- The older saved summary file still marks all three rooms as blocked/failed.
- A fresh 2026-04-05 rerun through `scripts/room_environment_system.py` now produces browser-backed `runtime-review.png` files for all three rooms with `review_mode: headless_browser`.

Current rerun results from the exact saved screenshots:

- `RG-R1`: failed, `room_shell_readability_low`, `threshold_visibility_low`
- `RG-R2`: failed, `room_shell_readability_low`, `top_occlusion_slab_present`, `threshold_visibility_low`
- `RG-R3`: failed, `top_occlusion_slab_present`, `platform_top_readability_low`, `threshold_visibility_low`

This means the old summary JSON is now stale as a capture-status source. The current blocker is no longer `browser_capture_required`; it is the visual/readability quality of the exact browser-backed artifacts saved on disk.

## Visual Inspection

### RG-R1

Inspected artifact: [RG-R1 runtime-review.png](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/room_environment_assets/RG-R1/review/runtime-review.png)

Visible observations:
- The room now saves as a real browser-backed runtime frame, with the main arch chamber centered and a single small platform suspended in the middle.
- The left door reads clearly, but the opposite threshold is pushed to the far right edge and does not read as a strong paired destination.
- A thick black band still sits across the entire top of the saved image, and the chamber interior remains a very dark brown haze with weak shell contrast.

Assessment: this is still not approval-quality. The image is now valid browser evidence, but the room remains too dim and the threshold read is still weak.

### RG-R2

Inspected artifact: [RG-R2 runtime-review.png](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/room_environment_assets/RG-R2/review/runtime-review.png)

Visible observations:
- Both side doors are visible, and the floor lane plus right-side step/pit structure makes the traversal path clearer than `RG-R1`.
- Two small floating platforms are visible in the upper half of the room, but they sit inside a very low-contrast brown chamber that feels flattened.
- A black band still occupies the full top portion of the screenshot, which makes the upper shell feel cropped rather than intentionally framed.

Assessment: this is browser-backed evidence now, but it still does not look signoff-ready because the shell is muted and the top occlusion slab remains visibly present.

### RG-R3

Inspected artifact: [RG-R3 runtime-review.png](/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/room_environment_assets/RG-R3/review/runtime-review.png)

Visible observations:
- The room reads as a tall shaft with three visible thresholds: one at the top, one mid-right, and one near the lower-left.
- A single horizontal platform crosses the shaft, but the platform top is very subdued against the surrounding brown field.
- The screenshot still carries a large black slab across the top, and the shaft itself looks under-defined and dim rather than strongly enclosed.

Assessment: this is valid browser-backed evidence of the current blocked state, but the platform/readability problem remains obvious in the exact saved artifact.

## Conclusion

Real saved browser-backed runtime screenshots now exist for the ruined-gothic calibration rooms, but they should not be treated as approved runtime evidence.

- The capture path is now fixed enough to save exact browser-backed runtime-review PNGs for all three rooms.
- Direct visual inspection shows that all three rooms still fail for real readability reasons in the saved artifacts.
- These files are now valid Milestone 4 blocked-state evidence, but they are not approval-quality runtime output.
