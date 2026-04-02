# Room Environment Quality Pass

**Date:** 2026-03-31
**Feature:** Typed environment component schema overhaul and bespoke room environment quality pass
**Status:** Active
**Owner:** Environment art / runtime pipeline agents

---

## Purpose

This log records decisions for the room environment and bespoke asset quality pass so future agents do not repeat failed composition strategies, misleading build behaviors, or weak validation contracts.

## Working Rules

- Read this file before making another substantive change to the environment-art generation pipeline, runtime composition, or review gate.
- Update this file after meaningful decisions, reversals, or rejected directions.
- Record both accepted and rejected paths.

## Decisions

### 1. Typed component schemas are now the primary production contract
- Status: Accepted
- Why: The older coarse prompt map was not constraining walls, floors, platforms, background, and midground strongly enough.
- Consequence: Production logic should prefer `env.spec.component_schemas` over the legacy prompt bundle.

### 2. Build completion must require runtime review, not just image generation
- Status: Accepted
- Why: Prior versions could report success while still producing unreadable rooms or stale playtest output.
- Consequence: `Build Production Assets` is not complete until schema validation, required slot generation, and runtime screenshot review all pass.

### 3. Template-only “success” for v2 production slots is not acceptable
- Status: Rejected
- Why: It created false-positive builds where assets looked unchanged and no real AI generation occurred.
- Consequence: Structural and scenic v2 slots must use the AI generation path; template fallback may be used only as a guide/reference mechanism, not as the final silent output.

### 4. Reusing approved previews or scene-heavy frozen concept art for structural production slots is not acceptable
- Status: Rejected
- Why: It kept reintroducing scenic focal art into walls, floor language, and shell components.
- Consequence: Structural slots use slot-specific guide references derived from templates, not room preview imagery.

### 5. Scenic production slots must be guided by sanitized slot references, not by raw scene art
- Status: Accepted
- Why: Raw scenic references kept reintroducing center clutter, shrine/altar reads, and floor/background mismatch.
- Consequence: `background_far_plate` and `midground_side_frame` now use sanitized guide images with explicit center suppression / center clearance.

### 6. Runtime review must be honest even if playtest rendering is provisional
- Status: Accepted
- Why: Users need to inspect failed-but-built outputs, but the build state still needs to reflect actual quality failures.
- Consequence: Playtest may show provisional assets for inspection while the manifest remains blocked or failed.

### 7. The current “calm center” suppression can overshoot into a fog slab
- Status: Accepted problem statement
- Why: One passing runtime review still produced a visually weak room where the center became an over-suppressed gray block.
- Consequence: Future work must tighten the review gate to reject collage/composite reads and over-suppressed scenic emptiness, not just altar/clutter failures.

### 8. The room currently needs stronger shell readability inspired by Hollow Knight-like separation
- Status: Accepted direction
- Why: The desired target is clearer structural readability with dark wall masses, sharp platform/floor edges, and distinct foreground/background separation.
- Consequence: Future schema and slot work should emphasize heavy wall masses, crisp traversable edges, stronger value separation, and likely additional structural component types such as ceiling, backwall panel, or wall face.

### 9. Runtime must render the bespoke shell pieces, not just the scenic plate and top strips
- Status: Accepted
- Why: The latest pass still read like a collage because runtime mostly relied on the background/midground plus top lip assets, while bespoke wall modules, wall trims, and floor/platform faces were not carrying the room shell in play.
- Consequence: Runtime now preloads all bespoke slots and uses placed wall modules, wall trims, floor faces, and platform faces as environment decor so the play view more closely matches the authored shell kit.

### 10. Runtime review must fail over-suppressed “fog slab” rooms, not just cluttered ones
- Status: Accepted
- Why: The previous gate could pass rooms with a very calm center even when that calmness flattened into a giant unreadable slab and floor/background separation stayed weak.
- Consequence: Runtime review now records extra center-lane contrast metrics and fails rooms when low floor/background separation combines with an over-suppressed, structurally unreadable center lane.

### 11. Midground side frames must reject bright inner-edge doorway reads
- Status: Accepted
- Why: One recurring artifact in the latest pass was luminous vertical bands near the center lane that read like pasted doorway cutouts instead of side-only framing.
- Consequence: Midground validation and postprocessing now detect and suppress hot inner-edge bands so side framing stays dark and subordinate.

## Rejected Paths To Avoid Repeating

- Repeatedly prompt-tuning the same scenic background concept without changing the source-art contract.
- Treating a “passed” build as good enough without reviewing the runtime screenshot.
- Using one scenic plate to imply walls, ceiling, room shell, floor continuity, and depth simultaneously.
- Assuming a build is “close enough” if the runtime only shows the scenic plate plus traversal top strips while the bespoke shell pieces sit unused in the manifest.
- Interpreting fast build completion as success when the system may still be using silent template paths or stale outputs.

### 12. Solid black background is approved only as temporary QA, not a shipping biome
- Status: Accepted
- Why: Wall/floor/platform bespoke readability passes need a neutral ground; tinted theme backgrounds compete with shell evaluation.
- Consequence: Runtime and editor expose `themeId: contrast-qa` with camera clear color `#000000`. Label and copy state **temporary QA**; shipping rooms should use normal biomes (`cave`, `ruins`, etc.). Starfield tint is subdued (`0x333333`) so parallax does not dominate the pass.

### 13. Black void requires suppressing layers on top of the camera clear color
- Status: Accepted
- Why: Playtest showed a non-black frame because starfield, room background textures, midground, feather fades, and procedural `buildEnvironmentSetDressing` arches still drew above `setBackgroundColor`. Embedded layouts can also keep `themeId: ruins` while QA is intended.
- Consequence: `isContrastQaEnvironment(room)` true when `themeId === 'contrast-qa'` **or** URL has `?contrast-qa=1`. In that mode: starfield alpha 0; hide per-room bg/mid/feathers; skip procedural backdrop/shell overlay dressing; HUD appends `black-void(QA)` when URL forces. Procedural stone uses **ruins** warm palette, forces broken-masonry platform family, and raises floor/platform tile alpha so the shell reads without AI palette washing it cool blue.

## Troubleshooting

### Bespoke build 7/8 (or any partial) + `Runtime review: blocked · slot_generation_failed`
- **Meaning:** `_run_runtime_review` only runs when `built_slots` is non-empty **and** `failed_assets` is empty (`room_environment_system.generate_room_environment_asset_pack`). One slot did not produce a valid PNG URL.
- **Where to look:** Project room `environment.runtime.bespoke_asset_manifest.failed_assets` (slot ids), `validation_errors` (`slot_id:error_code`), and per-slot `assets[slot_id].validation.errors` / `assets[slot_id].attempts[-1].status`.
- **Typical causes:** `missing_template` / `missing_template_image`; Gemini `generation_failed` (API/key/network); post-build **validation** (e.g. `midground_center_clutter`, `center_lane_too_hot`, dimension mismatch). Scenic slots (background, midground) fail validation more often than structural strips.
- **UI:** Room wizard Environment output now surfaces `validation_errors` in the summary when the bespoke manifest status is `failed`.

### 14. Biome template kit may be refined with Gemini from the Environment page
- Status: Accepted
- Why: Default biome PNGs are curated copies or Pillow seeds; authors need a guided step to align the **shared** `art_direction_biomes/<id>/` library with locked direction without hand-painting.
- Consequence: `generate_biome_pack_visuals` POST targets the active `biome_packs[0].template_library` (same five layers as `V1_BESPOKE_COMPONENTS`). Requires `confirm_overwrite: true`. Successful layers set `biome_visual_generated_at` and `source_template_kind: gemini_biome`. `_refresh_biome_pack_templates` **skips** `_install_component_template_asset` when `biome_visual_generated_at` is set so `get_project_art_direction` no longer overwrites Gemini outputs with curated/fallback seeds. API: `POST /api/projects/{id}/art-direction/biome/generate-visuals`. UI: Room wizard Environment → Setup → “Biome template kit”; long jobs switch to Results tab for the shared waitbar.

### 15. Room environment suggestions now carry a durable helpfulness ledger
- Status: Accepted
- Why: Volume-only AI usage counts were not telling us whether room suggestions or preview images were actually useful, especially with a single inconsistent internal user.
- Consequence: Each preview generation now gets a stable `suggestion_id` and a compact `ai_helpfulness` record stored on the room environment. The ledger tracks request/view/decision/persistence funnel state, session/task/workflow context, time-to-decision and backtracking effort, lightweight reason codes, heuristic model self-rating, and reliability signals (latency/errors/cancellations/crashes). Room-layout saves now evaluate whether accepted suggestions persisted or were later replaced, instead of treating approval as final success.

### 16. Full room payload capture for helpfulness tracking remains explicitly rejected
- Status: Rejected
- Why: Storing full room snapshots to judge tweak magnitude would bloat project data and mix analytics with authoring payloads too tightly.
- Consequence: Tweak magnitude is tracked with lightweight count deltas and buckets derived from room structure (platforms, doors, movers, keys, edges, polygon points), not raw room content dumps.

### 17. Helpfulness reporting must be verified through the real server payload, not only unit helpers
- Status: Accepted
- Why: The first QA pass caught two integration-only failures that unit coverage alone did not surface: `suggestion_id` hashing used a non-string input in the live server, and dashboard aggregation initially scanned the wrong persisted room-layout filename.
- Consequence: When this ledger changes, QA should include one real `/api/projects/.../environment/*` → `/api/dashboard-data` smoke run in addition to unit tests.

## Open Questions

- Should `ceiling`, `backwall_panel`, or `wall_face` become first-class component schema types?
- Should runtime review add explicit collage/composite heuristics and stronger floor/wall/platform edge separation checks?
- Should scenic slots remain AI-generated, or should some shell/background families move to more deterministic construction?

### 18. The current prompt/spec/biome block should be replaced with a staged v3 pipeline
- Status: Accepted direction
- Why: Review of the end-to-end code showed the current architecture is underfitting the room, overloading a monolithic prompt/spec step, and treating biomes mostly as a single shared style pack rather than explicit production data.
- Consequence: Future work should shift to a staged pipeline with separate contracts for biome definition, room assembly planning, slot generation, runtime review, and manual QA/Creative review. The implementation spec lives in `docs/room-environment-pipeline-v3-spec.md`.

### 19. Component-fit is now a top-level quality gate, not an implicit aesthetic preference
- Status: Accepted
- Why: A major failure mode in the current pipeline is that outputs can look visually interesting while still failing their actual job as walls, floors, platforms, doors, pits, or side framing.
- Consequence: Future prompts, validators, screenshot reviews, and acceptance criteria must all explicitly test whether art fits its assigned component type.

### 20. QA and Creative screenshot review loops are mandatory before pipeline signoff
- Status: Accepted
- Why: Automated validators and runtime heuristics are not sufficient to judge shell readability, coherence, or motif drift; the workflow itself must be inspected manually.
- Consequence: The replacement pipeline must include repeated manual validation rounds with QA and Creative, with screenshots captured from the workflow and runtime views at defined checkpoints before approval.

### 21. V3 implementation must use explicit module boundaries and a versioned payload
- Status: Accepted
- Why: Engineering review concluded that the current planner and environment architecture have reached an architectural ceiling, and that continuing to grow the monolith would preserve incorrect assumptions and create migration risk.
- Consequence: V3 must ship behind `environment_pipeline_version`, coexist with v2 during calibration, and split core logic into dedicated biome-definition, planner, prompt-scaffold, validator, review, runtime-adapter, and persistence modules.

### 22. Review surfaces and design diagrams are part of the implementation contract
- Status: Accepted
- Why: Design review concluded that assembly-plan visibility, fixed review order, and proposal-first workflow behavior are necessary for reviewers to correctly diagnose failures and trust the system.
- Consequence: V3 requirements and implementation planning must preserve the fixed review-surface order (`room intent` -> `biome selection` -> `component contracts` -> `assembly-plan overlay` -> `slot gallery` -> `combined kit` -> `runtime view` -> `contrast-QA view`) and use semi-formal architecture/behavior diagrams as part of the build contract.

### 23. V3 starts as a versioned contract layered onto the current environment flow before planner replacement
- Status: Accepted
- Why: The safest implementation path is to introduce the v3 payload contract, review-state persistence, and validation-plan enforcement first, without breaking the working v2 generation path during calibration.
- Consequence: The first implementation slice adds `environment_pipeline_version`, v3 contract scaffolding (`room_intent`, `component_contracts`, `assembly_plan`, `review_state`), and manual-review persistence now; the planner rewrite remains a follow-up phase rather than being coupled to the schema rollout.

### 24. Manual review gate enforcement must include required round counts, not only presence/absence
- Status: Accepted
- Why: The validation plan requires repeated QA and Creative rounds before signoff. Treating a single review round as sufficient would weaken the gate and create false approvals.
- Consequence: V3 review-state validation now tracks required round counts for QA and Creative and keeps approval in `manual_review_pending` until the configured minimum review rounds are recorded without blockers.

### 25. V3 asset generation now uses a replacement planner path that covers all doors and major traversal platforms
- Status: Accepted
- Why: The old planner collapsed rooms down to one main floor, a few hero platforms, and one active door. That was the core architectural quality cap identified in review.
- Consequence: V3 rooms now generate their bespoke slot plan from a separate geometry-first planner path that includes all door thresholds, all major traversal platforms, ceiling, backwall panel, side walls, and overlay geometry for review. The old planner remains only for v2 rooms during calibration.
