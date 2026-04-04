# Room Environment Stylepack / Reference Pack Contract

**Date:** 2026-04-04  
**Owner:** Creative  
**Scope:** Room Environment Pipeline MVP adaptation, uploads-first reference selection, Gemini-as-default candidate generation, and the review contract for style drift and readability safety.

## Purpose

This contract defines how the room environment pipeline should treat `reference_pack.json` and `stylepack.json` as Creative-owned art-direction data.

The goal is not to make the packs pretty. The goal is to keep room generation visually honest:

- uploads and approved references remain the source of truth
- Gemini remains the default generator for candidate imagery
- structural pieces stay structurally truthful
- scenic pieces may be expressive, but must never take over shell readability
- QA must know exactly which saved artifacts to inspect before signoff

This contract is written against the room-environment v3 direction, the Ashen Hollow art bible, and the pixel-art quality gate.

## Contract Summary

| File | Owns | Creative rule |
|---|---|---|
| `reference_pack.json` | Provenance, canonical source selection, candidate lineage, and rejection history | This is the trust record. If provenance is weak, the pack is provisional. |
| `stylepack.json` | Derived visual direction, locked motif vocabulary, prompt hints, and mixed-kit rules | This is the prompt-facing direction record. If the stylepack drifts from the reference pack, it is wrong. |

## `reference_pack.json`

`reference_pack.json` is the source register. It answers four questions:

1. Where did this image come from?
2. Why is it trusted?
3. What role does it play?
4. What drift is forbidden?

### Required Creative meaning

- `provenance` must record whether the source came from a founder upload, approved human reference, internal derived asset, or Gemini candidate.
- `canonical_reference_id` must point to the single chosen anchor for the pack.
- `canonical_reference_reason` must explain why that image won over the other candidates.
- `candidate_references` may include Gemini outputs, but only as candidates unless they are explicitly human-approved.
- `rejection_history` must preserve why near-misses were rejected, so future reruns do not repeat the same failure mode.

### Provenance rules

- Uploads-first means human-provided or human-approved uploads come first in the selection hierarchy.
- Gemini may propose candidates, but Gemini output is never canonical by default.
- A Gemini candidate can only become canonical after human review and explicit approval.
- A pack with no strong upload-backed anchor remains provisional, even if the generator output looks attractive.

### Canonical reference selection

Choose the canonical reference for truthfulness, not prettiness.

The canonical choice should be the image that best preserves:

- structural legibility
- value hierarchy
- clean silhouette read
- shell enclosure truth
- the intended biome family

Prefer the reference that is hardest to misunderstand at thumbnail size. A cinematic image that hides the shell is not a good canonical anchor.

If the pack has separate structural and scenic tracks, it may have:

- one structural canonical reference
- one scenic canonical reference

The structural canonical must dominate the room shell read. The scenic canonical must support mood without replacing shell readability.

## `stylepack.json`

`stylepack.json` is the direction register. It converts the trusted reference pack into a prompt-ready Creative contract.

### Required Creative meaning

- `visual_thesis` must state the room family in plain language.
- `material_vocabulary` must list the approved material family in the pack.
- `shape_language` must describe the shell geometry and contour behavior.
- `motif_vocabulary` must list the recurring symbols and architectural motifs that are allowed.
- `forbidden_drift_traits` must list what would make the output look like a different world.
- `prompt_pack_hints` must tell Gemini what to emphasize and what to suppress.
- `mixed_kit_rules` must separate deterministic structure work from AI scenic work.
- `review_checklist` must make the rejection criteria explicit.

### Stylepack contract

- The stylepack is derived from the reference pack and cannot contradict it.
- The stylepack may narrow or clarify the reference, but it should not widen the visual world.
- If a stylepack requires a new motif family, that is a new approval decision, not a silent prompt tweak.
- If a stylepack cannot describe the room in one coherent visual paragraph, it is too vague.

## Mixed-Kit Rules

The room kit is mixed on purpose, but the split must be explicit.

### Deterministic structural / template adaptation

Use deterministic adaptation for pieces that define the shell and traversal truth:

- floors
- ceiling bands
- wall masses
- door frames
- platform tops
- platform faces
- wall trims
- backwall panels
- pit rims and enclosure edges

These pieces may be cropped, aligned, alpha-normalized, or split from approved structural templates, but they must not invent new composition language.

Structural pieces must preserve:

- the load-bearing read
- the opening / threshold read
- the floor-to-wall boundary
- the platform top edge
- the left/right enclosure balance

### AI-generated scenic / decor candidates

Use Gemini for scenic or decor material that supports mood without carrying the shell:

- background depth
- midground framing
- distant damage
- props and relics
- fog, haze, and atmospheric lift
- secondary ornamentation
- small set dressing that does not change traversal readability

Scenic candidates may vary more than structural pieces, but they must still stay inside the pack vocabulary.

### Hard rule

If a piece changes where the player thinks they can stand, pass, enter, or fall, it is structural.

If a piece only changes mood, distance, or visual texture, it may be scenic.

## Forbidden Drift Traits

Reject the pack if it drifts into any of these behaviors:

- shrine tableau drift, where the room becomes a scene instead of a shell
- altar focality, where the center of the frame becomes the visual subject
- fog slab drift, where suppression destroys enclosure readability
- thin-shell drift, where walls become decorative borders instead of mass
- floor mural drift, where the floor reads like decoration instead of a playable surface
- doorway cutout drift, where transitions look pasted on top of the room
- collage seam drift, where the kit looks assembled from unrelated sources
- mirrored symmetry drift, where the room looks procedural and stiff
- palette expansion drift, where the pack introduces unapproved colors or accent families
- material contamination drift, where one material family starts borrowing another family’s language
- painterly softness drift, where the output stops reading as a crisp game asset

## Material Vocabulary

The stylepack should speak in a narrow, reusable material language.

Approved room-language materials should sound like:

- ash stone
- soot-dark masonry
- broken limestone
- oxidized iron
- verdigris metal
- tarnished brass
- dead timber
- bone or plaster fragments
- grime bands
- ash dust
- cold fog
- ember pinpoints

Material vocabulary must be stable across the pack. If a new material dominates the image, the stylepack has changed.

## Shape Language

The pack should describe how the room is built in silhouette terms.

Approved shape behavior should lean toward:

- thick enclosure masses
- load-bearing horizontals
- tapered but heavy verticals
- broken arches
- stepped damage
- clipped ledges
- framed thresholds
- side-weighted asymmetry
- clear top/bottom separation

Avoid shape language that suggests:

- floating fragments
- ornamental lace where a wall should be a wall
- soft scenic blobs where a boundary should be sharp
- repeated identical cuts on both sides of the frame

## Motif Vocabulary

The motif vocabulary should be small and repeatable.

For the ruined-gothic MVP slice, preferred motifs are:

- buttress breaks
- nave-like shell rhythm
- pressure-door frames
- iron bands
- cracked stone ribs
- dark bays
- torch niches
- worn thresholds
- relic recesses
- asymmetrical wall damage

If the biome changes later, the motif vocabulary may change too, but only through an explicit Creative update.

## Prompt-Pack Hints

Gemini prompts should be narrow and directional, not decorative essays.

The prompt pack should encourage:

- one clear shell family
- restrained palette behavior
- strong edge hierarchy
- low-clutter center lane
- side-weighted framing
- readable thresholds
- material consistency across components

The prompt pack should suppress:

- scenic overload
- altar or shrine behavior
- center clutter
- new architectural eras
- high-saturation focal objects
- decorative windows or arches that do not belong in the pack

## QA Visual Rejection Criteria

QA should reject the pack if any one of these is true:

- the biome reads as a different visual family at thumbnail size
- the structural pieces look scenic instead of load-bearing
- the scenic pieces start doing structural work
- the doorway no longer reads as a threshold
- the floor edge is not obvious without zooming
- the wall mass is too thin or too fragmented
- the center lane becomes visually busier than the sides
- the lighting direction changes from piece to piece without a documented reason
- the palette expands beyond the locked pack vocabulary
- the image contains checkerboard-like transparency artifacts or other generation leftovers

### Readability safety checklist

At minimum, inspect the image at 1x and 0.5x.

Pass only if all of these stay true:

- the player can identify the main floor surface quickly
- the player can identify the door or threshold quickly
- the player can identify the enclosing shell quickly
- the midground does not compete with the traversal lane
- the room still reads after contrast suppression

If any of those reads become ambiguous, the image is not safe.

## Exact Saved Artifacts To Inspect

Do not sign off from prompt text or a transient preview. Inspect the exact saved files.

At the pack level, QA should inspect:

- `reference_pack.json`
- `stylepack.json`
- the canonical reference image or images named inside those JSON files

At the biome asset level, QA should inspect the saved component files:

- `background_plate.png`
- `midground_frame.png`
- `primary_floor_piece.png`
- `hero_platform_piece.png`
- `door_piece.png`
- `foreground_frame.png` when that family exists

At the room-composition level, QA should inspect:

- `runtime-review.png`
- any saved component sheet or structural sheet that was used for the review round

For the current ruined-gothic MVP slice, that means inspecting the exact saved room review artifacts under:

- `tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/room_environment_assets/RG-R2/review/runtime-review.png`
- `tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/room_environment_assets/RG-R2/review/rg-r2-component-sheet.png`
- `tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/art_direction_biomes/ruined-gothic-v1/background_plate.png`
- `tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/art_direction_biomes/ruined-gothic-v1/midground_frame.png`
- `tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/art_direction_biomes/ruined-gothic-v1/primary_floor_piece.png`
- `tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/art_direction_biomes/ruined-gothic-v1/hero_platform_piece.png`
- `tools/2d-sprite-and-animation/projects-data/ruined-gothic-calibration-gemini-20260402/art_direction_biomes/ruined-gothic-v1/door_piece.png`

If `foreground_frame.png` is present for the current pass, it must be inspected too.

## Review Checklist

Creative review should answer these questions in order:

1. Does the canonical reference have the right provenance and the right amount of trust?
2. Does the stylepack stay inside that reference pack instead of drifting away from it?
3. Are structural pieces deterministic and shell-truthful?
4. Are scenic pieces expressive without stealing shell readability?
5. Does the composed room still read at 1x and 0.5x?
6. Do the saved artifacts match the pack contract, or do they show a new visual direction that needs explicit approval?

## Verdict

Approve this contract as the Creative baseline for the room-environment MVP adaptation.

Gemini remains the default image generator, but only inside the pack boundaries defined above. Anything outside those boundaries is a candidate for review, not a candidate for production.
