# Room Environment Handoff — 2026-04-03

## Scope

Project root:
- `/Users/timwood/Desktop/projects/PWA/MV`

Active project:
- `ruined-gothic-calibration-gemini-20260402`

Primary room under iteration:
- `RG-R2`

Primary feature log:
- `/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md`

## Read First

Required context before continuing:
- `/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md`
- `/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-spec.md`
- `/Users/timwood/Desktop/projects/PWA/MV/docs/room-environment-pipeline-v3-software-requirements.md`
- `/Users/timwood/Desktop/projects/PWA/MV/AGENTS.md`

## Current Truth

- The room polygon is the actual playable chamber.
- Anything outside the polygon is enclosure mass / wall thickness / retaining structure / void, not extra interior backdrop.
- The current shell consistency direction is a shared biome-level `foreground_frame` source for wall, ceiling, floor, and platform reads.
- The user rejected procedural/mock structural renderers. Review output must stay on the honest asset path.
- The user also required a stricter presentation rule:
  - no half-finished presentations
  - every shown pass must improve at least one named visual aspect
  - zero regressions are allowed in other already-reviewed aspects
  - if a regression appears, continue iterating or report blocked

## Important Rules Now in Force

From `AGENTS.md` and the decision log:
- Positive visual claims require inspecting the exact saved artifact and listing concrete visible observations.
- Broad biome-kit rerolls are not acceptable when the intent is a targeted structural iteration.
- If the live generation path ignores `component_types`, treat that as an efficiency blocker, not as permission to reroll the whole kit.
- If separate structural biome parts are generated, later parts must use earlier structural parts as visual anchors.

## What Was Fixed This Session

### 1. Targeted biome generation path

The stale workbench server was restarted on current code.

Before restart:
- the server ignored `component_types`
- a supposed `foreground_frame`-only reroll regenerated the entire ruined-gothic biome kit
- that caused unrelated regressions, including broken `door_piece`

After restart:
- endpoint now respects `component_types`
- confirmed response for targeted biome generation:
  - `component_types: ["foreground_frame"]`
  - `results: [{"component_type":"foreground_frame", ...}]`

Server currently running:
- `scripts/sprite_workbench_server.py --host 127.0.0.1 --port 8766`

## 2. Separate-asset consistency guard

Code was added so that if structural biome pieces are generated separately:
- `primary_floor_piece` is generated first
- later `wall_piece`, `ceiling_piece`, and `hero_platform_piece` generations receive structural sibling references
- prompt text tells Gemini to match material and proportion language

Files changed:
- `/Users/timwood/Desktop/projects/PWA/MV/scripts/room_environment_system.py`
- `/Users/timwood/Desktop/projects/PWA/MV/tests/room_environment_system.test.py`

## 3. Decision log updates

New relevant decisions added:
- 88: shared `foreground_frame` structural source
- 89: shared-frame crops must sample perimeter only, not atlas void
- 90: separate structural generations must anchor to earlier structural sources
- 91: broad biome rerolls rejected for targeted structural iteration

## Current Blocker

The targeted generation path is fixed, but the latest `foreground_frame` generations are still not good enough visually.

The current blocker is now source-template quality, not routing:
- the generated `foreground_frame` still behaves like a partial scene/atlas instead of a complete structural perimeter frame
- it keeps producing floating ledges / shelf fragments
- it does not reliably produce a continuous top band
- left/right wall treatment drifts
- shell readability can drop when the frame gets thinner

## Exact Current Source State

Latest targeted `foreground_frame`:
- `/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/art_direction_biomes/ruined-gothic-v1/foreground_frame.png`

I inspected that exact source image. Visible problems:
- no true continuous ceiling band
- floating ledge/shelf fragments inside the frame
- uneven left/right wall treatment
- right side can collapse into a near-black strip
- calm center, but not a coherent full perimeter frame

Because the source itself is visibly wrong, the next turn should not rebuild `RG-R2` from this newest source until the source contract is tightened first.

## Last Room Results Worth Knowing

### A. Last acceptable-ish `RG-R2` baseline before this latest source churn

Artifact:
- `/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/room_environment_assets/RG-R2/review/runtime-review.png`

That earlier pass was still not good enough, but it had:
- top slab removed
- more coherent shared structural family
- no new door regression

Remaining problems there:
- walls / floor / ceiling still too thick
- ceiling looked segmented
- shell still too synthetic / procedural

### B. Door regression and recovery

The accidental broad biome reroll broke `door_piece`:
- new `door_piece` had a baked light/checkerboard-like background and a filled opening
- this caused `RG-R2-door-1` and `RG-R2-door-2` to fail `template_family_drift`

Recovery applied:
- copied older truthful ruined-gothic door template from:
  - `/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-20260402/art_direction_biomes/ruined-gothic-v1/door_piece.png`
- restored into:
  - `/Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/art_direction_biomes/ruined-gothic-v1/door_piece.png`

Keep that restored door template unless a better targeted door regeneration is intentionally done later.

## Most Recent Non-Qualifying Room Pass

After one thinner targeted `foreground_frame` reroll, `RG-R2` rebuilt to a failing room screenshot:
- fail reason: `room_shell_readability_low`

Visible issues in that exact saved screenshot:
- thickness improved somewhat
- but shell became too weak
- cropped edge blocks appeared
- floating ledge artifacts remained

That pass did not qualify under the no-regressions rule and should not be used as a presented baseline.

## Files Changed This Session

- `/Users/timwood/Desktop/projects/PWA/MV/scripts/room_environment_system.py`
- `/Users/timwood/Desktop/projects/PWA/MV/tests/room_environment_system.test.py`
- `/Users/timwood/Desktop/projects/PWA/MV/decisions/2026-03-31-room-environment-quality-pass.md`

## Test Status

Current tests passing:
- `python3 /Users/timwood/Desktop/projects/PWA/MV/tests/room_environment_system.test.py`
  - `Ran 61 tests ... OK`
- `node /Users/timwood/Desktop/projects/PWA/MV/tests/game-logic.test.js`
  - passed
- `node /Users/timwood/Desktop/projects/PWA/MV/tests/room-wizard-terrain.test.js`
  - passed

## Recommended Next Steps

Do this next, in order:

1. Do not rebuild `RG-R2` again from the current newest `foreground_frame` yet.
2. Tighten the `foreground_frame` source contract further before another image spend.
3. Add or strengthen source-template validation for `foreground_frame` before room rebuild:
   - continuous top band required
   - continuous left/right side masses required
   - no floating ledges
   - no cropped-off shelf fragments
   - no dramatic tear silhouettes
   - no near-black side collapse
4. Then do one targeted `foreground_frame` reroll only via the fresh server.
5. Inspect the exact `foreground_frame.png` first.
6. Only if the source itself looks coherent, rebuild `RG-R2`.
7. Inspect the exact saved `runtime-review.png` and only present it if:
   - at least one named aspect improved
   - no previously-reviewed aspect regressed

## Practical Prompt Direction For The Next `foreground_frame` Reroll

The next source prompt likely needs to be even stricter:
- complete perimeter structural frame, not a partial composition
- one continuous masonry top band across the chamber width
- continuous left and right wall strips
- thin but load-bearing shell
- thin continuous bottom retaining band
- no floating platforms or shelves inside the frame source
- no torn edges, giant cracks, or dramatic missing chunks
- center must stay calm and non-scenic, but should not become a hard black void
- no fog, props, openings, windows, arches, symbols, or scenic composition

## Recommendation

Keep the fixed targeted-generation path and the shared `foreground_frame` contract, but do not spend more room rebuilds until the `foreground_frame` source itself passes a basic structural sanity check.

## Risks

- The current source generator still drifts toward partial scene framing instead of a full structural kit.
- If the next turn skips source inspection and goes straight to room rebuild, it will likely waste more credits and produce another non-qualifying screenshot.
- Broad biome rerolls may reappear if the wrong server/process is used again.

## Confidence

High. The targeted server behavior was directly verified, the current source image was directly inspected, and the remaining blocker is now clearly source-template quality rather than uncertainty about the pipeline path.

## Founder Approval Needed

No immediate approval needed to continue on the targeted `foreground_frame` path.

## Next Actions

1. Tighten `foreground_frame` source validation and prompt language.
2. Regenerate only `foreground_frame` through the fresh server.
3. Inspect the exact source image first.
4. Rebuild `RG-R2` only if the source is coherent enough.
