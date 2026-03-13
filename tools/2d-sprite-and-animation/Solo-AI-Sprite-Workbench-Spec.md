# Specification: Solo AI Sprite Workbench v1
# Production-Ready Output Required

## 1. Objective

Build a local-first tool for one user that outputs a fully game-ready 2D sprite package for one character, including final animation frames and engine-usable metadata.

Game-ready means the exported frames are the final deliverable, not draft art.

## 2. Production Contract

The system shall not export an asset package unless all of these are true:

- every frame has transparent background
- every frame is exactly 256x256 pixels
- every frame shares the same bottom-center pivot
- no frame has broken anatomy, missing limbs, or duplicated props
- no frame is clipped at the canvas edge
- idle loop is seamless
- walk loop is seamless
- frame ordering is stable and deterministic
- atlas and animation metadata match the exported sheet exactly

If any check fails, export is blocked.

## 3. Hard Scope

V1 supports only this target:

- one humanoid biped character
- side view only
- one facing direction only
- one handheld prop maximum
- stylized raster sprite output
- idle animation: 6 frames at 8 FPS
- walk animation: 8 frames at 10 FPS
- final frame size: 256x256

## 4. Unsupported Inputs

The tool must reject these at intake:

- quadrupeds
- multi-character scenes
- wings
- large flowing capes
- long physics-driven appendages
- multiple weapons
- top-down designs
- isometric designs
- highly asymmetric multi-view requirements

Rejected prompts must return a clear reason.

## 5. Core Technical Rule

AI is allowed for:

- concept generation
- concept refinement
- style exploration
- reference-image conditioning
- layered asset extraction assistance
- inpainting hidden parts during part extraction

AI is not allowed as the final source of animation frames.

Final animation frames must be rendered from a canonical layered character model and a fixed rig.

## 6. Production Architecture

The implementation must have these stages:

1. Intake
2. Concept generation
3. Concept refinement
4. Concept lock
5. Canonical layered character build
6. Rig fitting
7. Deterministic animation rendering
8. QA validation
9. Export

## 7. Canonical Character Model

After concept lock, the system must build one authoritative character asset made of transparent layers.

Required parts:

- head
- hair_front
- hair_back
- torso
- pelvis
- upper_arm_left
- lower_arm_left
- hand_left
- upper_arm_right
- lower_arm_right
- hand_right
- upper_leg_left
- lower_leg_left
- foot_left
- upper_leg_right
- lower_leg_right
- foot_right
- prop
- accessory_front
- accessory_back

Each part must store:

- source image path
- local bounding box
- pivot point
- draw order
- parent joint
- mask integrity status

Production is blocked until all required parts exist and pass layer QA.

## 8. Rig Definition

The rig must define these joints:

- root
- pelvis
- torso
- neck
- head
- shoulder_left
- elbow_left
- wrist_left
- shoulder_right
- elbow_right
- wrist_right
- hip_left
- knee_left
- ankle_left
- hip_right
- knee_right
- ankle_right

The rig must also store:

- default neutral pose
- per-joint rotation limits
- draw-order rules for overlap
- foot anchor reference
- prop attachment joint

## 9. Animation Source of Truth

Animations must be rendered from fixed templates, not generated freeform.

Required templates:

- idle
- walk

Each template must define:

- exact frame count
- exact playback FPS
- exact joint transforms per frame
- root motion policy
- loop frame continuity

The tool may use AI to propose a template, but final rendering must use the saved template values.

## 10. Intake Rules

The UI must collect:

- project name
- prompt text
- optional reference images
- optional style references

The server must normalize the prompt into:

- subject
- silhouette
- outfit
- palette direction
- prop
- material notes
- side-view readability notes

If the prompt cannot be normalized into the supported input envelope, the project cannot proceed.

## 11. Concept Generation Rules

- exactly 4 concept variants per run
- all concepts must preserve the same core identity
- concepts may vary silhouette, outfit detail, and palette
- each concept must store prompt, negative prompt, seed, and preview image
- one concept only may be approved

## 12. Refinement Rules

Refinement must operate on the approved concept only.

Supported locks:

- silhouette
- face_head_shape
- outfit
- palette
- prop

A refinement request may change only one major attribute group at a time.

If the request attempts multiple major changes, it must be rejected.

## 13. Concept Lock

When the user approves a concept, the system must write `character_spec.json` containing:

- approved concept ID
- canonical prompt
- negative prompt
- locked attributes
- seed history
- palette definition
- prop definition
- side-view rules
- production target
- model identifiers used during concept generation

No production step may begin without this file.

## 14. Layer Build Stage

After concept lock, the system must generate and validate a layered master character.

This stage must:

- isolate each required body part to transparent PNG
- inpaint hidden limb segments if needed
- preserve palette consistency
- preserve outline style consistency
- assign pivots and parent joints
- assign front/back draw order

The user must be able to inspect the layered result before rigging begins.

## 15. Layer QA Gates

A layer build fails if any of these are true:

- missing required part
- visible background contamination
- broken mask edges
- inconsistent palette relative to approved concept
- unresolved occlusion causing impossible rigging
- prop not separable from hand when prop lock is enabled

A failed layer build blocks production.

## 16. Rig Fitting Stage

The system must fit the rig to the layered master asset.

The output must include:

- neutral pose render
- rig joint map
- pivot map
- occlusion order map

If the neutral pose render does not match the approved concept within visual tolerance, rig fitting fails.

## 17. Animation Rendering

Idle and walk frames must be rendered by applying the saved animation templates to the rigged layered asset.

This stage must not call text-to-image generation per frame.

Allowed operations:

- transform layers
- deform approved layers within bounded limits
- apply deterministic shading or outline harmonization
- rasterize to final frame

Disallowed operations:

- unconstrained frame hallucination
- full-frame diffusion redraw
- freeform image-to-image frame generation

## 18. Frame Cleanup

For every rendered frame, run this exact order:

1. composite transparent layers
2. rasterize to working canvas
3. crop to character bounds
4. pad to 256x256
5. align bottom-center pivot
6. normalize alpha edges
7. save frame
8. validate frame

This pipeline must be deterministic.

## 19. QA Validation

Each frame must pass:

- transparent background present
- exact size 256x256
- bottom-center pivot equal to project pivot within 1 pixel
- no clipped pixels on outer border
- no missing limb or duplicate limb
- no duplicate prop
- no frame-to-frame jitter greater than 1 pixel at foot anchor
- no outline thickness jump greater than allowed threshold
- no palette drift outside approved palette variance

Each animation must pass:

- required frame count exactly met
- exact frame names present
- loop seam visually continuous
- adjacent frames distinct enough to read as motion
- metadata order matches sheet order

## 20. Export Package

The tool must export:

- `spritesheet.png`
- `frames/idle_00.png` through `frames/idle_05.png`
- `frames/walk_00.png` through `frames/walk_07.png`
- `atlas.json`
- `animations.json`
- `preview.gif`
- `qa_report.json`
- `export_manifest.json`

Export is blocked if any QA rule fails.

## 21. Required JSON Outputs

`animations.json` must define exact FPS, loop flags, and ordered frame names.

`atlas.json` must define exact x, y, w, h coordinates for each frame in `spritesheet.png`.

`qa_report.json` must contain per-frame checks, per-animation checks, and pass/fail status.

`export_manifest.json` must contain project ID, approved concept ID, export timestamp, tool version, and source asset hashes.

## 22. UI Sections

The single-page UI must contain:

- Project List
- Intake
- Concepts
- Refine
- Layer Review
- Rig Review
- Production
- QA
- Export

Production cannot be entered until Layer Review and Rig Review are approved.

## 23. API Endpoints

Required endpoints:

- `GET /api/health`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/<project_id>`
- `POST /api/projects/<project_id>/concepts/generate`
- `POST /api/projects/<project_id>/concepts/<concept_id>/select`
- `POST /api/projects/<project_id>/refine`
- `POST /api/projects/<project_id>/layers/build`
- `POST /api/projects/<project_id>/rig/build`
- `POST /api/projects/<project_id>/animations/idle/render`
- `POST /api/projects/<project_id>/animations/walk/render`
- `POST /api/projects/<project_id>/qa/run`
- `POST /api/projects/<project_id>/export`
- `GET /api/projects/<project_id>/jobs/<job_id>`

All long-running operations must be async jobs.

## 24. Filesystem Layout

Each project must contain:

- `project.json`
- `brief.json`
- `character_spec.json`
- `layered_character.json`
- `rig.json`
- `animation_templates.json`
- `qa_report.json`
- `concepts/`
- `layers/`
- `rig/`
- `animations/idle/`
- `animations/walk/`
- `exports/`
- `logs/`

No database is allowed.

## 25. Acceptance Criteria

The implementation is complete only when all of these are true:

- a supported prompt can be turned into 4 concept variants
- one concept can be locked into a canonical spec
- the tool can build a complete layered character asset from the approved concept
- the tool can fit a valid rig to that layered asset
- the tool can render idle and walk without calling generative image synthesis per frame
- all exported frames pass the QA contract
- export is blocked on any failed QA rule
- the final package can be loaded by a simple runtime using only `spritesheet.png`, `atlas.json`, and `animations.json`

## 26. Definition of Done

Done does not mean “looks promising.”

Done means:

- concept approved
- layered master asset complete
- rig fitted
- animations rendered deterministically
- QA passed
- exports generated
- output is directly usable in-game without further art correction
