# Room Shell And Preview Corrective Action Plan

**Date:** 2026-04-10
**Status:** Draft for execution
**Scope:** `Room AI Helpfulness QA` -> `R1`
**Primary objective:** Correct the shell reference contract, replace misleading shell debug references, make previews respect the room shape and intended theme, and add QA gates that prevent these regressions from returning.

## Plain-English Summary

The shell is not failing because it is merely "too dark." It is failing because the images that tell the model what the shell should look like are already wrong or misleading.

The biggest problems are:

1. The shell guide already shows inconsistent wall thickness.
2. The shell contract and shell guide use different colors for the same geometry, which adds confusion.
3. The shell debug material reference is pulling from a green-keyed template, so it is not a useful texture guide.
4. The saved silhouette debug image is too dark to be helpful.
5. The preview images are still full rectangular scene compositions with the room shape overlaid, not post-shaped to the room footprint.
6. "Ruins" is being reinforced by both saved project data and code heuristics, so it keeps leaking back in.

## Visual Evidence

These are the exact saved artifacts inspected during the audit.

### 1. Failed Shell Raw Output

Artifact:
[R1-room-shell-raw.png](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/R1-room-shell-raw.png)

![Failed shell raw](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/R1-room-shell-raw.png)

What is visibly wrong:

- The right vertical shell mass reads heavier than the left side.
- The top and bottom do not read like one consistent wall thickness.
- The shell feels pieced together instead of reading like one coherent perimeter.

### 2. Live Shell Contract

Artifact:
[room_shell_foreground-retry-contract.png](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/_refs/room_shell_foreground-retry-contract.png)

![Shell contract](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/_refs/room_shell_foreground-retry-contract.png)

What is visibly wrong:

- The top band is not visually even across the whole room shape.
- The right leg reads much deeper than the left and lower spans.
- The shell thickness already looks inconsistent before generation begins.

### 3. Live Shell Guide

Artifact:
[room_shell_foreground-retry-guide.png](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/_refs/room_shell_foreground-retry-guide.png)

![Shell guide](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/_refs/room_shell_foreground-retry-guide.png)

What is visibly wrong:

- It repeats the same uneven thickness problem as the contract image.
- The geometry is already teaching the generator an inconsistent shell.
- The visual mismatch is not something the model invented by itself.

### 4. Live Retry Material Reference

Artifact:
[room_shell_foreground-retry-material.png](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/_refs/room_shell_foreground-retry-material.png)

![Retry material](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/_refs/room_shell_foreground-retry-material.png)

What is visibly wrong:

- It is dominated by neon green.
- It does not read as stone or any useful shell texture.
- It is clearly not a useful debug material swatch.

### 5. Source Template Feeding The Bad Material Ref

Artifact:
[foreground_frame.png](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/art_direction_biomes/ruined-gothic-v1/foreground_frame.png)

![Foreground frame template](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/art_direction_biomes/ruined-gothic-v1/foreground_frame.png)

What is visibly wrong:

- The template contains a bright green keyed opening.
- This is not a safe material-source image for shell debug swatch extraction.
- Any patch picker can accidentally sample the green keyed area.

### 6. Legacy Silhouette Debug Reference

Artifact:
[room_shell_foreground-silhouette.png](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/_refs/room_shell_foreground-silhouette.png)

![Shell silhouette](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_assets/R1/bespoke/_refs/room_shell_foreground-silhouette.png)

What is visibly wrong:

- It is dark-on-dark and hard to read.
- It is not a good human debugging artifact.
- It is also stale for the current retry path and should not be treated as the active shell reference.

### 7. Preview Evidence

Preview 1:
[R1-lvl3-1.png](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_previews/R1/R1-lvl3-1.png)

![Preview 1](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_previews/R1/R1-lvl3-1.png)

Preview 3:
[R1-lvl3-3.png](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_previews/R1/R1-lvl3-3.png)

![Preview 3](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_environment_previews/R1/R1-lvl3-3.png)

What is visibly wrong:

- Preview 1 reads like a scenic hall composition more than a room-shape-faithful room concept.
- Preview 3 does not convincingly follow the room layout.
- Both previews are still full rectangular images with footprint overlays, not room-shape-cropped results.

## Confirmed Root Causes

### A. Shell Geometry Contract Root Cause

The active shell contract and guide are both derived from the same band-mask function in [scripts/room_environment_system.py](../scripts/room_environment_system.py), specifically:

- `_room_shell_silhouette_band_mask`
- `_write_room_shell_contract_map_reference`
- `_room_shell_reference_guide`

The problem is not that the guide and contract disagree on geometry. The problem is that they agree on geometry that is already visually bad for this use case.

Plain English:

- The system is generating a shell "outer ring" around the room shape.
- That ring is not being represented in a way that reads like a clean, consistent wall-thickness instruction.
- The generator is therefore being taught the wrong shell proportions from the beginning.

### B. Gold Versus Grey Shell Ref Root Cause

The shell contract and shell guide intentionally use different colors:

- contract band: warm gold
- guide band: cool grey

Plain English:

- Two images are telling the model the same shape in two different color languages.
- That does not help the model or the human reviewer.
- It is avoidable ambiguity.

### C. Shell Material Reference Root Cause

The shell material swatch is currently built from the `foreground_frame` template path before falling back to preview imagery.

Plain English:

- The material swatch is being sourced from the wrong image family.
- That source image still contains a green keyed opening.
- The patch picker can choose that green area because it is bright and high-contrast.
- So the debug material swatch becomes nonsense.

Authoritative constraint:

- Do not replace this by sourcing from `wall_piece`, `ceiling_piece`, or `primary_floor_piece`.
- Those template families are obsolete for this shell-debug path and must not be reintroduced as a fallback or "temporary" replacement.
- Any corrective implementation that routes shell debug material sourcing through those obsolete template families is considered a regression.

### D. Silhouette Debug Root Cause

The silhouette debug image is written as black shell occupancy over a near-black clear region.

Plain English:

- The file may be structurally valid for code, but it is visually poor for humans.
- It also belongs to an older shell-reference regime and is not the main live shell reference for the current retry path.

### E. Preview Fidelity Root Cause

The level-3 preview path conditions generation on room geometry, but it does not crop or mask the result to the room shape after generation.

Plain English:

- The system asks for a room-shaped result.
- It then accepts the full rectangular generated scene as-is.
- That allows wrong perspective and wrong layout reads to survive into approval.

### F. "Ruins" Drift Root Cause

The current project and room data are already biased toward `ruins`, and code heuristics reinforce that bias.

Plain English:

- This is not just one stray prompt word.
- The project art direction is locked to ruined-gothic.
- The saved room spec is already `ruins` / `hall`.
- The code also treats words like `hall` as a signal for `ruins`.
- So the system keeps drifting back into that biome even when that is not what we want.

## Previous Use Of Specialist Subagents

This corrective plan is based on specialist-assisted auditing, plus direct visual inspection of the saved artifacts.

### Developer Specialist Use

The Developer specialist traced:

- the live shell reference order
- the shell contract writer
- the shell guide writer
- the shell material-reference writer
- the raw shell-output persistence path
- the preview generation path

The Developer specialist confirmed:

- the active shell path currently uses `contract -> guide -> material`
- the inconsistent shell thickness is already present in the generated contract/guide refs
- the material swatch bug is caused by sampling from the keyed `foreground_frame` template
- the proposed fallback to `wall_piece`, `ceiling_piece`, or `primary_floor_piece` must be rejected because those component families are obsolete for this shell workflow

### QA Specialist Use

The QA specialist traced:

- current shell validation coverage
- current preview approval behavior
- current regression-test coverage
- current theme inference behavior

The QA specialist confirmed:

- shell validation catches some hard failures, but not malformed in-band thickness
- preview approval has no real visual validation gate
- no regression currently prevents generic `hall` language from silently reinforcing `ruins`
- the plan must explicitly forbid obsolete-template fallback in the shell material/debug path

### Visual Inspection Process Used In This Audit

For this audit, the saved images themselves were opened and inspected directly:

- failed shell raw output
- active shell contract
- active shell guide
- active material reference
- shell silhouette debug artifact
- source `foreground_frame` template
- latest level-3 previews

This plan is therefore grounded in the actual saved images, not only in code or tests.

## Relevant Research And Prior Context

This plan was prepared after checking prior repo context first.

### Internal Research / Context Reviewed

- [research/library/INDEX.md](../research/library/INDEX.md)
- [research/dashboard.md](../research/dashboard.md)
- [decisions/2026-03-31-room-environment-quality-pass.md](../decisions/2026-03-31-room-environment-quality-pass.md)

### Relevant Prior Findings From Existing Decision Context

- runtime review must be honest even when provisional
- shell readability matters more than scenic composition drift
- structural slots should not inherit scene-heavy or misleading references
- browser/runtime evidence is required to close visual claims honestly

### Additional Review Findings Incorporated

This plan also incorporates the useful findings from:

- [dev-qa-review-corrective-action-plan.md](./dev-qa-review-corrective-action-plan.md)
- [room-shell-preview-corrective-action-plan.md](./room-shell-preview-corrective-action-plan.md)

Important note:

- Where those findings suggested routing shell debug material through `wall_piece`, `ceiling_piece`, or `primary_floor_piece`, that guidance is explicitly overridden here.
- The authoritative rule for this plan is that those obsolete template families must not be used for the shell corrective pass.

### Code Evidence Used As Research

Primary code evidence for this corrective plan:

- [scripts/room_environment_system.py](../scripts/room_environment_system.py)
- [tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/project.json](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/project.json)
- [tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_layout.json](../tools/2d-sprite-and-animation/projects-data/room-ai-helpfulness-qa-67562113/room_layout.json)
- [tests/room_environment_system.test.py](../tests/room_environment_system.test.py)
- [index.html](../index.html)

## Corrective Action Slices

## Slice 1 - Fix The Shell Reference Contract

### Goal

Make the shell geometry references clean, consistent, human-readable, and model-usable before any new shell generation is attempted.

### Developer Tasks

1. Replace the current shell band-guide output with a deterministic geometry guide that expresses consistent wall thickness around the room perimeter.
2. Remove the unnecessary gold-versus-grey split for live shell geometry references, or reduce it to one neutral geometry language plus a clearly separate material swatch.
3. Stop mixing stale shell debug artifacts from older reference regimes into the same `_refs` folder used by the current retry path.
4. Make the saved shell silhouette artifact either clearly legible for debugging or remove it from the active shell-debug surface when it is not in use.
5. Replace the current isotropic `MaxFilter` shell-band construction with a geometry-aware band construction that preserves consistent visual thickness around straight edges, elbows, and concave turns.
6. Restore a real pre-punchout shell corner gate so obvious malformed shell candidates can fail before they move deeper into the shell retry path.

### QA Tasks

1. Add regression coverage that fails visibly malformed shell thickness even when the output remains broadly inside the allowed shell band.
2. Add regression coverage that checks concave elbows and inner steps remain clearly represented in the shell reference images.
3. Add regression coverage that the active shell retry path only emits the expected current shell-reference set.
4. Add a regression that proves the shell-band construction keeps thickness within a reasonable tolerance around an L-shaped room instead of thickening visibly at the concave elbow.
5. Add a regression that proves the pre-punchout corner/continuity gate is functional and not effectively disabled.

### Slice 1 QA Gates

Slice 1 is not complete until QA signs off all of these:

- the shell guide and shell contract visibly describe one consistent shell thickness
- the shell elbow / inner step is visually obvious in the saved references
- no stale shell-reference artifacts remain mixed into the active `_refs` set for the current retry path
- the saved shell debug artifacts are visually inspectable by a human without guessing

### Founder Approval Criteria

1. The saved shell guide now looks like a consistent wall-perimeter instruction.
2. The shell contract no longer sends confusing mixed visual signals.
3. The shell reference set is easier to understand and debug by eye.

## Slice 2 - Replace The Broken Debug Material Reference

### Goal

Replace the current misleading shell material swatch with a useful debug texture source that does not poison generation.

### Developer Tasks

1. Stop sourcing shell material debug refs from `foreground_frame.png`.
2. Do not replace `foreground_frame.png` with `wall_piece`, `ceiling_piece`, or `primary_floor_piece`.
3. Replace the material-debug path with a shell-specific debug source strategy that stays inside the current shell workflow only.
4. Preferred corrective direction:
   - derive the debug material from shell-specific approved-preview sampling after geometry-safe sanitation
   - or build a deterministic neutral shell debug texture specifically for shell validation/debugging
5. Explicitly reject keyed greens and other placeholder/debug colors from material patch selection.
6. Fail hard if a valid shell-specific material debug ref cannot be produced.

### Slice 2 Implementation Guardrail

The following are forbidden in this slice:

- using `wall_piece`
- using `ceiling_piece`
- using `primary_floor_piece`
- using any obsolete structural sibling template family as a shell-debug material fallback

This guardrail is authoritative. Any implementation that uses those obsolete component families for shell debug material sourcing fails the slice.

### QA Tasks

1. Add regression coverage that the shell material debug ref never includes keyed green or other placeholder colors.
2. Add regression coverage that `room_shell_foreground` reference #3 is a generated debug material artifact, not a raw preview fallback.
3. Add a visual QA check that the material ref reads as useful shell texture, not a scene crop or placeholder artifact.
4. Add a regression that fails if the shell material-debug source path reintroduces `wall_piece`, `ceiling_piece`, or `primary_floor_piece`.

### Slice 2 QA Gates

Slice 2 is not complete until QA signs off all of these:

- the material debug ref contains no keyed green
- the material debug ref visibly reads as shell texture or material guidance
- the shell pipeline no longer silently falls back to misleading reference images
- the shell material-debug path does not use any obsolete structural sibling template family

### Founder Approval Criteria

1. The debug material image now looks like a useful shell texture reference.
2. The shell pipeline is no longer being poisoned by placeholder or keyed imagery.
3. We did not regress by routing shell debug generation through obsolete template families.

## Slice 3 - Make Previews Respect The Room Shape

### Goal

Ensure level-3 previews are shape-faithful room previews rather than full rectangular scenic compositions with an overlaid footprint.

### Developer Tasks

1. Add post-generation room-shape masking or cropping for level-3 previews.
2. Preserve only the part of the generated scene that belongs inside the intended room footprint.
3. Add a preview validation step before approval that checks:
   - side-view perspective fidelity
   - room-layout fidelity
   - no substitute rectangular hall composition
4. Ensure approved previews cannot bypass this validation.

### QA Tasks

1. Add preview validation regressions for:
   - wrong-perspective preview output
   - wrong-layout preview output
   - preview not cropped/masked to room shape
2. Add saved-artifact review steps for all three preview variants before approval is possible.

### Slice 3 QA Gates

Slice 3 is not complete until QA signs off all of these:

- all saved previews are shape-aware after generation
- the room shape is not merely overlaid on a full rectangular scene
- previews with obvious layout drift cannot be approved

### Founder Approval Criteria

1. The preview images now look like the shape of the room, not just a scene with a footprint drawn on top.
2. Wrong-perspective or wrong-layout previews are blocked before approval.

## Slice 4 - Remove Unwanted Ruins Drift

### Goal

Stop generic language and stale project defaults from repeatedly pushing the room toward `ruins` when that is not intended.

### Developer Tasks

1. Remove or narrow the heuristic that maps generic terms like `hall` to `ruins`.
2. Ensure explicit room/theme intent wins over fallback keyword heuristics.
3. Clean the saved project or room spec if it is carrying stale ruined-gothic defaults that are no longer desired.
4. Remove ruined-gothic-specific wording from generic preview/template paths where it is not supposed to be global.

### QA Tasks

1. Add regression coverage that generic architectural terms do not silently force `ruins`.
2. Add regression coverage that explicit non-ruins theme choices survive preview generation and shell generation.
3. Add artifact review checks that the preview tone and shell/debug refs align to the selected theme.

### Slice 4 QA Gates

Slice 4 is not complete until QA signs off all of these:

- generic words like `hall` no longer force `ruins`
- explicit theme selection survives through preview generation
- shell and preview outputs reflect the intended biome/theme, not stale ruined-gothic defaults

### Founder Approval Criteria

1. The room no longer becomes a ruins room just because of generic architectural wording.
2. The selected theme now stays stable through preview and shell generation.

## Global QA Gates

No corrective slice is complete until these cross-cutting QA checks have all passed.

1. Saved-artifact review must be performed on the exact generated images for the slice.
2. Positive claims about visual quality must be tied to those saved artifacts.
3. Any shell fix must be checked both in saved shell refs and in the saved raw shell output.
4. Any preview fix must be checked on all three saved preview variants, not just one chosen example.
5. Any theme-drift fix must be checked in both saved data and resulting images.

## Execution Order

Recommended order:

1. Slice 1 - shell reference contract
2. Slice 2 - debug material replacement
3. Slice 3 - preview shape enforcement
4. Slice 4 - ruins/theme drift cleanup

Reason:

- Slice 1 and Slice 2 correct the source inputs that are currently poisoning shell generation.
- Slice 3 fixes the preview contract so approval evidence is trustworthy.
- Slice 4 prevents the system from reintroducing the wrong biome direction after the visual contract is fixed.

## Founder Approval Interview

When the corrective work is ready for review, use this short founder interview:

1. Do you agree that the shell reference images now describe a consistent wall perimeter clearly enough to guide generation?
2. Do you agree that the shell debug material reference is now useful and no longer contaminated by placeholder imagery?
3. Do you agree that the room previews now follow the room shape rather than remaining generic rectangular scene concepts?
4. Do you agree that the room no longer drifts into a ruins treatment unless that is explicitly intended?
5. Do you approve closing this corrective action pass, or do you want another slice focused on runtime polish after the references and previews are stable?

## Deliverables

This corrective action pass should deliver:

- corrected shell contract and guide artifacts
- corrected shell material debug artifact
- cleaned shell debug reference set
- shape-aware preview outputs
- updated regression coverage
- QA evidence tied to exact saved artifacts

## Recommendation

Fix the shell reference contract and debug material path first, then lock preview shape enforcement, then remove theme drift. The current failures are not random art failures; they are contract failures and acceptance-gap failures.

## Risks

- Prompt-only changes will not solve this because the generator is currently being given bad or misleading reference images.
- If preview approval remains ungated, wrong-perspective and wrong-layout concepts can still be locked in even after shell fixes.
- If `ruins` inference is not corrected, visual drift will continue to reappear.

## Confidence

High. This plan is based on direct visual inspection of the exact saved artifacts, direct code-path tracing, and specialist-assisted Developer and QA audits.

## Founder Approval Needed

Yes. Specifically:

- whether all level-3 previews should become room-shape-cropped or masked by default
- whether generic terms like `hall` should stop implying `ruins`

## Next Actions

1. Approve this corrective-action plan.
2. Execute Slice 1 and Slice 2 together as the shell-input stabilization pass.
3. Pause for founder review of saved shell-reference artifacts.
4. Execute Slice 3 and Slice 4 once the shell-input pass is accepted.
