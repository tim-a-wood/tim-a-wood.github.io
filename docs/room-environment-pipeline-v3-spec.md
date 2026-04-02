# Room Environment Pipeline V3 Spec

**Date:** 2026-04-01
**Status:** Proposed
**Owner:** Level Design with Development, QA, and Creative
**Scope:** Room environment pipeline from art direction lock through biome kit generation, room-specific environment planning, component generation, runtime review, and manual validation

---

## 1. Purpose

This spec defines a replacement architecture for the room environment pipeline.

The goals are:

- Keep the current high-level approach of using a schema and template system with Gemini
- Vastly improve environment quality by fixing the code and process around Gemini
- Ensure the generated art **fits the component types**
- Ensure biome setup is real production data, not just prompt flavor text
- Add repeated manual validation loops with QA and Creative using screenshots from the actual workflow

This spec also absorbs related planning issues identified during review:

- cross-room style drift within the same biome
- need for canonical biome style anchors
- requirement that biome and palette application remain proposal-first
- requirement that room planning account for progression context, not biome only

This spec replaces the current quality strategy of:

- large monolithic spec prompts
- one shared biome pack chosen implicitly
- underspecified room planning
- weak post-hoc rescue through validators and image suppression

---

## 2. Non-Goals

- Replacing Gemini with another model
- Replacing the room environment feature with hand-authored art only
- Solving final shipping art direction for every biome in one pass
- Fully automating quality approval without human review

---

## 3. Core Principles

### 3.1 Geometry first

The room layout is the authority. The environment plan must fit the actual room geometry, door locations, platform spans, pits, ceiling shape, and traversal routes.

### 3.2 Component-fit is a first-class contract

Every generated image must fit a known component type. “Looks cool” is insufficient if the image does not read as the specific component it is meant to be.

### 3.3 Biome data must be explicit

Biome selection, biome kit choice, and allowed visual language must be represented in structured data and used directly by planning and generation.

### 3.4 Scenic and structural work must be separated

Structural components are responsible for shell readability.
Scenic components are responsible for mood and depth.
A scenic layer must never be allowed to carry shell readability by itself.

### 3.5 Manual review is mandatory

QA and Creative must inspect the pipeline manually, with screenshots captured at each required stage.
The team must iterate several times through this manual validation loop before considering the new pipeline stable.

### 3.6 Proposal-first application

AI-generated biome, palette, and environment outputs must remain proposals until explicitly accepted by the user.

No environment style change, palette application, biome kit swap, or room-level environment application may happen silently.

### 3.7 Progression-aware planning

Biome is not enough context for a metroidvania room.
Room environment planning must also account for room role and progression context so hub rooms, threshold rooms, ambush rooms, reward rooms, and pre-boss rooms do not collapse into the same visual planning logic.

---

## 4. Quality Targets

The v3 pipeline must achieve all of the following:

- Walls read as enclosure architecture, not concept-art backdrop
- Floors and platforms read immediately as gameplay surfaces
- Door components read as thresholds with obvious opening contrast
- Midground stays out of the center traversal lane
- Background provides shell depth without flattening into fog slab or shrine tableau
- The room’s actual traversal structure is represented in the generated kit
- Different biomes produce materially distinct shell language, not just palette shifts
- Generated art stays inside the allowed visual language for the selected biome

---

## 5. Pipeline Overview

V3 is split into five stages:

1. Art direction lock
2. Biome kit definition
3. Room assembly planning
4. Slot generation
5. Runtime and external phase review

Each stage has an explicit contract and explicit fail conditions.

QA and Creative must be included as external reviewers at three early checkpoints:

1. Planner checkpoint
Review the room intent, biome choice, and assembly-plan coverage before broad slot generation work continues.

2. Slot checkpoint
Review the first calibrated slot outputs for component fit, shell language, and biome identity before scaling the slot set.

3. Runtime checkpoint
Review the composed runtime result before the slice is considered ready for wider rollout.

The locked first slice for this pass is:

- biome: `ruined-gothic`
- direction: medieval dungeon / castle
- calibration rooms: `RG-R1` Gatehouse Threshold, `RG-R2` Broken Hall Passage, `RG-R3` Keep Descent Shaft
- fixture file: [ruined_gothic_calibration_rooms.json](/Users/timwood/Desktop/projects/PWA/MV/tests/fixtures/room_environment_v3/ruined_gothic_calibration_rooms.json)

---

## 6. Data Model Changes

## 6.1 Art Direction

The existing locked art direction remains, but it becomes an upstream source only.

Required fields:

- `template_id`
- `style_family`
- `high_level_direction`
- `negative_direction`
- `palette`
- `shape_language`
- `lighting_rules`
- `material_rules`
- `frozen_concepts`

Art direction must no longer be used directly as the biome selection mechanism.

## 6.2 Biome Definition

Add a new structured `biome_definition` contract.

Each biome definition must include:

- `biome_id`
- `label`
- `derived_from_art_direction`
- `theme_ids_supported`
- `shell_family`
- `material_family`
- `shape_grammar`
- `traversal_surface_rules`
- `door_language`
- `hazard_language`
- `background_language`
- `midground_language`
- `forbidden_motifs`
- `allowed_accents`
- `repeat_metrics`
- `value_structure`
- `template_library`
- `validation_rules`
- `identity_checklist`
- `canonical_style_anchor`

### 6.2.1 Example shape grammar fields

- `wall_mass_profile`
- `arch_frequency`
- `column_spacing`
- `trim_weight`
- `ledge_endcap_style`
- `ceiling_junction_style`

### 6.2.2 Example traversal surface rules

- `top_lip_min_px`
- `top_lip_max_px`
- `face_height_range`
- `allowed_damage_density`
- `allowed_support_styles`
- `prohibit_scenic_overhangs`

### 6.2.3 Example value structure

- `wall_edge_darkening`
- `top_plane_vs_face_delta`
- `door_opening_vs_frame_delta`
- `background_center_quietness`
- `midground_side_density`

### 6.2.4 Biome identity checklist

Each biome definition must include a concise identity checklist used during generation and review.

Required checklist dimensions:

- shell silhouette identity
- trim language
- wear and damage language
- accent placement rules
- atmospheric density
- motif exclusions
- distinction from neighboring biome families

### 6.2.5 Canonical style anchors

Each biome may define a canonical style anchor image or image set.

Canonical style anchors:

- define family-level visual identity
- stabilize style across repeated generation
- must not force identical composition from room to room
- guide kit generation, not replace room-local planning

## 6.3 Room Environment Spec

The room environment spec must be split into:

- `room_intent`
- `component_contracts`
- `assembly_plan`
- `review_state`

### 6.3.1 `room_intent`

Contains:

- room description
- mood
- lighting
- fog
- landmarks
- hazards
- readability notes
- selected biome id
- room role
- progression context

### 6.3.1.1 `room_role`

Examples:

- corridor_transition
- hub
- shrine_chamber
- ambush_pocket
- reward_room
- traversal_shaft
- threshold
- pre_boss

### 6.3.1.2 `progression_context`

Contains:

- world region
- intended progression beat
- safety level
- return-visit expectation
- ability-gate context if relevant

### 6.3.2 `component_contracts`

Contains explicit contracts for:

- `walls`
- `floor`
- `platforms`
- `doors`
- `pits`
- `background`
- `midground`
- `ceiling`
- `backwall_panel`

`ceiling` and `backwall_panel` should be added as first-class types in v3.

### 6.3.3 `assembly_plan`

Contains a generated list of actual room slots.

Each slot must contain:

- `slot_id`
- `component_type`
- `schema_key`
- `biome_component_template_id`
- `source_region`
- `target_dimensions`
- `placement`
- `orientation`
- `tile_mode`
- `protected_zones`
- `fit_rules`
- `validation_rules`

## 6.4 Review State

Keep review state product-facing and minimal:

- `automated_validation`
- `runtime_review`
- `approval_status`

QA and Creative validation for implementation phases should happen outside the toolchain as an external delivery process, not as stored in-product review rounds.

## 6.5 Versioning and migration

V3 must not be introduced as an unversioned extension of the current environment payload.

Required controls:

- explicit `environment_pipeline_version`
- schema version for v3 environment metadata
- migration boundary between v2 and v3
- ability to keep v2 rooms readable during calibration

Recommended implementation path:

- support v2 and v3 side-by-side during calibration
- gate v3 behavior by room-level or environment-level pipeline version
- keep room layout export versioning separate from environment-pipeline versioning if runtime export lags behind authoring metadata

---

## 7. Stage 1: Art Direction Lock

## 7.1 Inputs

- locked art direction
- frozen concept anchors

## 7.2 Outputs

- approved art direction package
- one or more biome definitions derived from the locked direction

## 7.3 Rules

- art direction lock cannot directly create production room assets
- it only supplies world-level visual constraints
- every downstream biome must declare how it interprets the locked direction

## 7.4 Fail Conditions

- no frozen concept anchors
- no negative direction
- no explicit shape language
- no explicit material language

---

## 8. Stage 2: Biome Kit Definition

## 8.1 Goal

Turn the locked art direction into reusable biome kits that are specific enough for production generation.

Biome-kit outputs must remain proposal-first until explicitly approved for production use.

## 8.2 Required Biome Components

Each biome kit must define and generate:

- `background_far_plate`
- `midground_side_frame`
- `wall_module_left`
- `wall_module_right`
- `wall_base_trim_left`
- `wall_base_trim_right`
- `main_floor_top`
- `main_floor_face`
- `hero_platform_top`
- `hero_platform_face`
- `door_frame`
- `pit_rim`
- `pit_interior`
- `ceiling_band`
- `backwall_panel`

## 8.3 Biome Prompting Strategy

Gemini should not receive a single generic biome prompt.

Gemini must receive a slot-aware prompt scaffold containing:

- selected biome definition
- exact component type
- component-fit rules
- target dimensions
- tileability or stretch behavior
- forbidden motifs
- value structure constraints
- silhouette constraints
- source template reference
- frozen concept references

## 8.4 Biome Prompt Requirements

Every biome-generation prompt must explicitly state:

- what the component is
- what it is not
- how it should read in side-view
- what gameplay readability it must preserve
- what motifs must not appear
- whether the center lane must stay empty
- whether the asset must tile, stretch, or remain unique

## 8.5 Biome Validation

Each biome component must pass:

- size validation
- transparency validation
- tileability validation where relevant
- component-fit validation
- motif violation validation
- luminance/value-read validation
- template-family drift validation
- identity-checklist review

## 8.6 Component-Fit Rules

### Walls

Must read as enclosing shell mass.
Must not read as scenic backdrop, altar, or abstract texture slab.

### Floor

Must read as a walkable top plane plus front face.
Must not read as mural, ritual circle, or scenic floor painting.

### Platforms

Must read as narrow traversal surfaces in the same family as floor.
Must not read as props, altars, or hanging scenery.

### Doors

Must read as a threshold with a clear opening.
Must not read as a scenic window, shrine niche, or decorative panel.

### Pits

Must read as non-walkable danger.
Must not read as floor continuation.

### Background

Must read as far-depth shell architecture.
Must not read as center-stage tableau.

### Midground

Must read as side framing only.
Must not occupy the center traversal path.

### Ceiling

Must read as enclosing upper shell mass.
Must not create noisy silhouette clutter above gameplay lanes.

### Backwall Panel

Must read as a depth-bearing wall plane behind traversal.
Must not collapse into flat fog or scene illustration.

---

## 9. Stage 3: Room Assembly Planning

## 9.1 Goal

Convert the actual room geometry into a production assembly plan that covers the real room, not a simplified vignette.

## 9.2 Replace Current Simplifications

The new planner must not:

- collapse the room to one main floor plus three platforms
- ignore all but the first door
- ignore ceiling structure
- treat the background as one full-room scenic guess

## 9.3 Planner Inputs

- room polygon
- room size
- all doors
- all platforms
- all pits
- start point
- removed edges
- room intent
- room role
- progression context
- selected biome definition
- component contracts

## 9.4 Planner Outputs

The planner must generate slots for:

- every major wall span
- every ceiling band
- every major floor span
- every hero platform span
- every door threshold
- every pit opening
- background shell zones
- midground framing zones
- backwall panel zones

## 9.5 Slot Granularity Rules

- every door gets its own threshold slot
- every major platform visible in the route gets top and face slots
- long rooms may be segmented into multiple wall and background zones
- vertical rooms must receive distinct lower, mid, and upper shell planning

## 9.6 Protected Zones

Each slot must define protected zones for:

- traversal lanes
- jump apex space
- door mouth clearance
- pit read zones
- landmark read zones

These protected zones must be fed into both prompts and validators.

---

## 10. Stage 4: Slot Generation

## 10.1 Structural vs Scenic Generation

Structural slot strategy:

- prefer deterministic template transforms first
- allow Gemini refinement only when needed
- maintain strict family continuity

Scenic slot strategy:

- use Gemini with sanitized references
- generate under stronger composition constraints

## 10.2 Prompt Architecture

Each slot prompt must be assembled from:

1. System contract
2. Biome contract
3. Component-fit contract
4. Room-local assembly context
5. Protected zones
6. Retry clause if prior attempt failed

## 10.3 Prompt Content Rules

Prompt must include:

- component type
- biome id and shell family
- exact output dimensions
- target runtime display dimensions
- local room role
- progression context
- fit rules
- validation rules
- list of forbidden motifs
- allowed variation scope

Prompt must not include:

- vague “make it look cool” framing
- unused descriptive fields
- broad scenic references when generating structural components

## 10.4 Retry Strategy

Retries should be driven by structured failure reasons:

- `component_fit_failed`
- `center_lane_occluded`
- `door_threshold_unclear`
- `top_plane_unreadable`
- `template_family_drift`
- `tileability_failed`
- `shell_definition_low`

Each failure code must add a focused retry clause, not a broad rewritten prompt.

---

## 11. Stage 5: Runtime and Manual Review

## 11.1 Automated Review

Automated review remains required, but it is not sufficient for approval.

Required automated checks:

- schema validity
- slot completeness
- component-fit heuristics
- center-lane occlusion
- shell-definition score
- floor/background separation
- top-plane readability
- threshold visibility
- tileability where applicable

## 11.2 Runtime Screenshot Review

The pipeline must support screenshot capture from:

- room wizard preview
- assembled bespoke kit review view
- runtime play view
- contrast-QA view
- structural-only assembled view
- scenic-only assembled view

The browser-based runtime capture should be the preferred path, not disabled by default once the v3 review flow is in place.

Where available, both runtime and composite fallback captures may be stored, but runtime capture is the approval artifact.

## 11.3 Manual Review Requirement

No room environment pipeline change is complete until it has gone through manual review with QA and Creative.

Manual review is required for:

- new biome kit
- changed prompt scaffold
- changed planner logic
- changed slot generation logic
- changed runtime composition logic
- changed validators

---

## 12. QA Manual Validation Workflow

QA must execute the following workflow and capture screenshots at each step.

## 12.1 Required Screenshot Set

For each reviewed room:

1. Environment setup screen showing room intent and selected biome
2. Component contract screen showing component-fit data
3. Assembly plan view showing slot overlays on room geometry
4. Generated slot gallery showing each produced asset
5. Assembled bespoke kit review view
6. Structural-only assembled view
7. Scenic-only assembled view
8. Runtime screenshot in standard biome mode
9. Runtime screenshot in contrast-QA mode
10. Failure-state screenshot if any validator or review gate blocks the build

The assembly-plan screenshot is mandatory.
If it is missing, the review run is blocked.

## 12.2 QA Checklist

QA must verify:

- every generated slot matches its component type
- every major room structure received a slot
- no missing doors in the assembly plan
- floor/platform art reads clearly at gameplay scale
- wall shell reads on both sides of the room
- midground does not interfere with traversal
- background supports the shell instead of overpowering it
- the final room looks like one coherent kit, not a collage

## 12.3 QA Recording Format

QA findings must be recorded as:

- `finding_id`
- `room_id`
- `biome_id`
- `pipeline_version`
- `stage`
- `severity`
- `screenshot_refs`
- `observed_issue`
- `expected_behavior`
- `suspected_root_cause`
- `category`

Recommended categories:

- `component_fit`
- `planner_coverage`
- `biome_identity`
- `shell_readability`
- `traversal_readability`
- `motif_violation`
- `runtime_composition`
- `workflow_usability`

## 12.4 QA blocker criteria

The following are round blockers:

- missing required slot for a major room structure
- any in-room door without corresponding threshold slot
- wall, floor, platform, or door component-fit failure
- unreadable top plane at gameplay scale
- unreadable threshold opening
- center-lane occlusion from background or midground
- runtime collage/composite read
- background acting as the sole shell read

---

## 13. Creative Manual Validation Workflow

Creative must review the same room set after QA completes an initial pass.

## 13.1 Creative Review Questions

Creative must answer:

- does the environment feel coherent with the locked art direction
- does each biome feel materially distinct
- do the structural surfaces belong to the same visual family
- does any component look like it belongs to the wrong slot type
- does the room read as authored space rather than generated collage
- are any forbidden motifs reappearing
- is the room memorable without sacrificing traversal readability

## 13.2 Creative Deliverables

For each review round, Creative must provide:

- annotated screenshots
- accept/revise/reject per room
- notes per component family
- notes per biome family
- motif violations list

## 13.3 Creative rejection codes

Recommended rejection codes:

- `shell_not_coherent`
- `component_role_unclear`
- `biome_identity_weak`
- `motif_violation`
- `focal_scene_drift`
- `value_hierarchy_broken`

---

## 14. Iteration Loop with QA and Creative

The new pipeline must be iterated through manual review several times before signoff.

## 14.1 Required Rounds

Minimum required rounds:

1. Round A: internal baseline review on 3 representative rooms
2. Round B: after first fixes, rerun same rooms plus 2 new rooms
3. Round C: biome stress pass across at least 4 biome families
4. Round D: final signoff pass on candidate shipping workflow

The recommended review order inside each round is fixed:

1. room intent
2. biome selection
3. component contracts
4. assembly-plan overlay
5. slot gallery
6. combined kit
7. runtime standard view
8. contrast-QA view

## 14.2 Representative Room Set

The review set must include:

- corridor transition
- vertical shaft
- shrine chamber
- multi-door hub
- pit-heavy traversal room
- large confrontation room

## 14.3 Round Exit Criteria

Each round only passes when:

- QA critical issues are zero
- Creative rejects are zero
- no component-fit failures remain in reviewed rooms
- no repeated forbidden motif reappears
- runtime screenshots show coherent shell readability
- required assembly-plan screenshots are present
- proposal-first application behavior is preserved

---

## 15. Implementation Plan

## 15.1 Phase 1: Schema and Data Model

- add biome definition schema
- add new component types `ceiling` and `backwall_panel`
- split room environment spec into intent, contracts, and assembly plan
- add manual review record storage
- define `environment_pipeline_version`
- define migration boundary between v2 and v3

## 15.2 Phase 2: Planner Rewrite

- replace current `_room_component_plan`
- cover all doors and major traversal structures
- add wall, ceiling, and backwall segmentation
- add per-slot protected zones
- treat planner rewrite as a replacement path, not an incremental extension of the current planner

## 15.3 Phase 3: Prompt Scaffold Rewrite

- replace monolithic spec prompt with staged prompts
- add biome contract prompt scaffold
- add slot-generation prompt scaffold
- add structured retry prompts per failure code

## 15.4 Phase 4: Biome Kit Rewrite

- replace single implicit default pack logic
- support multiple explicit biome definitions
- tie room biome selection to actual biome packs
- add per-biome kit validation

## 15.5 Phase 5: Review Tooling

- add assembly-plan overlay view in the workflow
- add screenshot capture support for review stages
- add QA review form and Creative review form
- add round tracking and approval status
- support annotation-ready screenshot bundles and stable naming

## 15.6 Module boundaries

V3 should not continue as one large monolithic environment-system file.

At minimum, implementation should separate:

- biome definitions
- planner
- prompt scaffolds
- validators
- review tooling
- migration/versioning helpers

## 15.7 Phase 6: Calibration

- run four manual validation rounds
- collect findings
- update prompts, planner, and biome data
- repeat until all exit criteria pass

---

## 16. Testing Strategy

## 16.1 Automated Tests

Add tests for:

- biome selection by room data
- planner coverage of all doors/platform bands
- component-fit validation rules
- slot generation prompt assembly
- retry behavior per failure code
- runtime review metrics

## 16.2 Golden Review Fixtures

Create a fixed fixture set of representative rooms.

For each fixture, store:

- room layout
- selected biome
- room role
- progression context
- expected assembly slots
- expected screenshot checkpoints
- known failure examples

## 16.3 Manual Test Runs

Every major change to:

- planner
- prompt scaffold
- biome definition
- validator
- runtime composition

must trigger one real manual QA + Creative review cycle on the fixture set.

---

## 17. Success Metrics

The v3 pipeline is successful when:

- QA reports zero P1 and zero repeated P2 component-fit failures across the validation set
- Creative accepts the biome distinctness and shell coherence of the reviewed rooms
- reviewed rooms no longer read as collage or scenic-over-geometry composites
- prompt changes produce predictable slot-level behavior instead of broad instability
- biome differences are visible in shell language, not just palette

---

## 18. Open Decisions

- whether all structural slots should remain Gemini-refined or some should become fully deterministic
- whether room-level assembly planning should support hierarchical zones for very large rooms
- whether Creative should approve biome kits before any room-specific generation begins
- whether contrast-QA should become a required screenshot in every validation round or only structural debugging rounds

---

## 19. Recommended First Build Slice

Build the first v3 slice on one biome family and three rooms:

- biome: ruined gothic
- rooms: corridor transition, shrine chamber, vertical shaft

Do not start with all biomes.
Use the first slice to prove:

- component-fit contracts
- planner correctness
- screenshot review workflow
- QA and Creative iteration loop
