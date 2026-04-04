# Foreground Frame Validation Handoff — 2026-04-03

## Scope

Project root:
- `/Users/timwood/Desktop/projects/PWA/MV`

Active project:
- `ruined-gothic-calibration-gemini-20260402`

Primary room under iteration:
- `RG-R2`

Prior handoff:
- `/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-04-03-room-environment-handoff.md`

## Read First

Required context before continuing:
- `/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-04-03-room-environment-handoff.md`
- `/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md`
- `/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-spec.md`
- `/Users/timwood/Desktop/projects/PWA/MV/AGENTS.md`

## Current Truth

- The targeted generation path is confirmed working (server respects `component_types`).
- The `foreground_frame` is the shared structural source for all shell slots: ceiling, walls, floor, platforms.
- The current `foreground_frame.png` was directly inspected and is visually wrong.
- Two code gaps were identified and fixed this session: a weak prompt and a missing source validation gate.
- Tests pass: 66 tests, all OK.

## What Was Fixed This Session

### 1. Tightened `foreground_frame` prompt

**File:** `scripts/room_environment_system.py` → `_build_biome_template_prompt()`

**Before:** The role text described the desired output family (ceiling cap, side wall masses, floor band) but gave no spatial layout contract. Gemini was free to place ledges, skip the ceiling, and leave one wall near-black.

**After:** The role text now includes:
- Explicit spatial zones: top band 18–22% of image height, side strips 18–22% of width each, bottom floor band 8–10%
- Center region contract: calm dark neutral, no props, not pitch-black void
- Hard prohibition list: no floating ledges, no gaps in top band, no asymmetric wall collapse, no torn edges spanning an entire band, no fog/arches/symbols/scenic composition

### 2. New `_validate_foreground_frame_source()` function

**File:** `scripts/room_environment_system.py` (~line 3031)

Four structural sanity checks run against the generated PNG before it can be accepted as a biome template:

| Error code | What it catches |
|---|---|
| `top_band_missing_or_too_dark` | Top 20% strip luminance < 15 — no ceiling cap |
| `left_wall_collapsed` | Left outer strip luminance < 12 — near-black left wall |
| `right_wall_collapsed` | Right outer strip luminance < 12 — near-black right wall |
| `wall_asymmetry_excessive` | Left/right luminance ratio > 4× — one side invisible |
| `floating_interior_ledges` | Center mid-height significantly brighter than wall strips — floating fragment signal |

### 3. Validation wired into `generate_biome_pack_visuals()`

**File:** `scripts/room_environment_system.py` (~line 3518)

If `foreground_frame` AI generation succeeds but fails structural validation:
- Returns `error: "foreground_frame_source_invalid"` with `validation_errors` list in results
- Does **not** update `biome_visual_generated_at` — old image is preserved, not replaced with a bad one
- Generation loop continues (skips to next component if any)

### 4. Tests added

**File:** `tests/room_environment_system.test.py` (5 new tests, total now 66, all passing)

- `test_validate_foreground_frame_source_passes_correct_perimeter_frame`
- `test_validate_foreground_frame_source_fails_missing_top_band`
- `test_validate_foreground_frame_source_fails_collapsed_right_wall`
- `test_validate_foreground_frame_source_fails_floating_interior_ledges`
- `test_generate_biome_pack_visuals_rejects_invalid_foreground_frame_source`

## Current Source State (Directly Inspected)

**File:** `tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/art_direction_biomes/ruined-gothic-v1/foreground_frame.png`

Concrete visible problems in the exact saved image:
- No top band — ceiling area is pure dark void, no masonry cap across the top
- Four floating stone shelves/platforms isolated in the center, completely detached from perimeter
- No floor band — bottom is black, same as top
- Right wall has real stone coursing; left wall is thinner and darker
- Center void is calm but the perimeter contract is incomplete

This image would **fail** `top_band_missing_or_too_dark` and `floating_interior_ledges` under the new validation gate. It must be replaced before `RG-R2` is rebuilt.

## Current Room State (Directly Inspected)

**File:** `tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/room_environment_assets/RG-R2/review/runtime-review.png`

What's working in the room:
- Walls read as actual masonry — stone block texture, piers on both sides
- Floor band present and readable at bottom
- Doors correct — dark opening, proper frame, no checkerboard bleed
- Stone material family consistent across walls, floor, platforms

Active problems in the room (sourced from the bad `foreground_frame`):
- Large glowing fog slab in center dominates the room — background doing too much scenic work
- No ceiling structural cap — top of chamber reads as open void
- Floor/background separation low — fog bleeds to floor
- Floating platform ledges in upper area appear detached with no wall context
- Center brighter than shell elements — value hierarchy inverted

## Test Status

```
python3 tests/room_environment_system.test.py
Ran 66 tests ... OK
```

Other tests also passing (unchanged):
- `node tests/game-logic.test.js`
- `node tests/room-wizard-terrain.test.js`

## Files Changed This Session

- `scripts/room_environment_system.py`
- `tests/room_environment_system.test.py`

## Recommended Next Steps

Do this in order:

1. Do **not** rebuild `RG-R2` from the current `foreground_frame.png` — it will fail validation and produce another non-qualifying pass.
2. Do one targeted `foreground_frame` reroll only via the fresh server:
   ```
   component_types: ["foreground_frame"]
   confirm_overwrite: true
   ```
3. Check the response — if it returns `error: "foreground_frame_source_invalid"` with `validation_errors`, do not proceed to room rebuild. Reroll again or adjust prompt.
4. If generation returns `ok: true`, open the exact `foreground_frame.png` and visually confirm:
   - Continuous masonry band across the full top
   - Continuous left and right wall strips, materially symmetric
   - No floating ledges or shelf fragments in the center
   - No near-black side collapse
   - Bottom retaining band present
5. Only if source passes visual inspection, rebuild `RG-R2`.
6. Open the exact saved `runtime-review.png` before making any claims. Only present it if:
   - At least one named aspect improved (fog slab, ceiling cap, floor separation)
   - No previously-reviewed aspect regressed (doors, walls, floor, platform family)

## Prompt Direction for Next Reroll

The new prompt is already tighter, but if the first reroll still drifts, the extra prompt field (`extra_prompt`) can add:

```
Complete perimeter structural frame only. One continuous masonry top band from left edge to right edge.
Continuous left and right wall strips running full height. Thin bottom retaining band.
No floating platforms, shelves, or isolated stone pieces in the center.
No fog. No atmospheric depth. No torn edges spanning a full band.
Center must be calm dark neutral — not scenic, not pitch black, not foggy.
```

## Risks

- The heuristic thresholds in `_validate_foreground_frame_source()` are conservative — a visually weak source that barely passes validation may still produce an inadequate room. Visual inspection of the source image remains mandatory before room rebuild.
- The validation gate catches structural collapse and floating fragments but cannot detect subtle scenic drift (e.g., a faint arch motif in the background of the wall strip). Prompt language remains the first line of defense against those.
- Gemini spending cap may still be exhausted. If generation returns `gemini_image_generation_failed`, falsify against the REST response before concluding it is a prompt failure.

## Confidence

High. The two root causes (weak prompt, no source gate) were directly identified from source inspection and code review. The fixes are narrow and targeted. Tests pass. The remaining work is one clean reroll and visual verification.
