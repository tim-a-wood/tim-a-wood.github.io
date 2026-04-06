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

### 26. V3 activation in the editor must be explicit, and the results surface must expose planner coverage
- Status: Accepted
- Why: We explicitly rejected silent v2-to-v3 upgrades, and Design review required assembly-plan visibility as a first-class review surface.
- Consequence: The room editor now exposes a deliberate v3 calibration toggle in Environment setup, sends the selected pipeline version when building the room spec, and shows assembly-plan coverage plus validation-plan status in the Results surface for v3 rooms.

### 27. Manual review starts as a lightweight in-editor form attached to the v3 Results surface
- Status: Accepted
- Why: QA and Creative review needed to become a real part of the workflow quickly, but full screenshot annotation tooling would have delayed calibration.
- Consequence: The editor now supports submitting QA and Creative review rounds directly from the v3 Results surface with role, decision, finding codes, blockers, required changes, and runtime screenshot metadata. Richer annotation tooling remains a later enhancement.

### 28. Manual review evidence must track screenshot-stage coverage, not just round counts
- Status: Accepted
- Why: The validation plan requires review of multiple workflow surfaces. Counting rounds without stage evidence would allow false signoff even if reviewers only looked at runtime.
- Consequence: Review rounds now persist screenshot-stage coverage, review evidence summaries are exposed in the editor, and validation remains incomplete if QA or Creative rounds are missing required screenshot stages.

### 29. The editor should auto-assemble review evidence from room state for calibration rounds
- Status: Accepted
- Why: Requiring reviewers to manually type every stage increases process friction and creates avoidable evidence-quality mistakes during calibration.
- Consequence: The editor now auto-builds the baseline review evidence set from the current v3 room state, including runtime screenshots and referenced workflow stages, while still allowing manual stage additions. Missing required stages still block approval.

### 30. The v3 Results surface must show the review packet that QA and Creative are actually submitting
- Status: Accepted
- Why: Evidence enforcement is much less useful if reviewers cannot see which stages and artifacts the editor has assembled on their behalf before submitting a round.
- Consequence: The Results surface now exposes latest per-role stage coverage and the current review packet artifact list so QA and Creative can inspect the packet directly during calibration.

### 31. V3 should generate a review bundle with concrete stage artifacts for non-runtime review surfaces
- Status: Accepted
- Why: Relying on manually typed stage names or purely inferred evidence for room intent, biome selection, component contracts, and assembly-plan review still leaves too much ambiguity in the calibration workflow.
- Consequence: V3 now refreshes a persisted review bundle whenever environment state changes, producing concrete stage artifacts for planning and contract surfaces and exposing them in the editor as first-class review evidence.

### 32. QA and Creative implementation validation must remain an external delivery process, not a productized room-editor workflow
- Status: Accepted correction
- Why: Founder clarification established that QA and Creative were meant to validate implementation in phased review sessions, not through in-tool review forms, review bundles, or approval gating embedded in the product workflow.
- Consequence: The in-editor manual review UI, manual-review API route, review-bundle generation, and QA/Creative approval gating were removed. V3 product scope remains focused on environment planning, generation, and runtime validation; stakeholder validation happens outside the tool.

### 33. QA and Creative must be involved at early external checkpoints, not only near signoff
- Status: Accepted
- Why: Founder direction is to use QA and Creative as early course-correction partners so the team can catch planner, component-fit, and biome-identity mistakes before the pipeline is too far along.
- Consequence: External review checkpoints are now expected after the first planner-visible slice, after first slot-output calibration, and after runtime composition, with findings folded into the next implementation phase before continuing.

### 34. The first-slice biome is locked to ruined-gothic for the medieval dungeon / castle pass
- Status: Accepted
- Why: Founder selected a medieval dungeon / castle direction for the first external calibration pass, and `ruined-gothic` is the cleanest match in the current biome set.
- Consequence: The first slice uses `ruined-gothic` only, with the calibration room set `RG-R1` Gatehouse Threshold, `RG-R2` Broken Hall Passage, and `RG-R3` Keep Descent Shaft captured in `tests/fixtures/room_environment_v3/ruined_gothic_calibration_rooms.json`.

### 35. QA and Creative planner-checkpoint findings require door-anchor awareness and stronger wide-hall shell articulation before slot calibration
- Status: Accepted
- Why: Both agents independently flagged that the planner was still too generic for top-entry shaft doors and too backdrop-heavy for wide ruined halls.
- Consequence: The planner now infers door anchor classes, emits differentiated top/side/bottom threshold planning, and splits backwall coverage for wider ruined-gothic halls before the slot checkpoint proceeds.

### 36. Door slots must use deterministic template adaptation, and door biome templates must be normalized into real cutout alpha
- Status: Accepted
- Why: Live ruined-gothic slot calibration showed that Gemini can return doorway kit art with a fake checkerboard baked into the PNG, which breaks transition-slot transparency and makes door validation noisy.
- Consequence: `door_frame` now uses the direct template-adaptation path, and Gemini-generated `door_piece` biome templates are postprocessed into true alpha cutouts before slot generation reuses them.

### 37. First-slice biome kit refinement is a prerequisite for meaningful slot calibration when fallback seeds are too weak
- Status: Accepted
- Why: The initial ruined-gothic background template seed was too primitive to anchor slot generation, so slot review was diagnosing the fallback kit as much as the prompt contract.
- Consequence: The ruined-gothic biome template pack is now refreshed through Gemini with a stronger medieval-castle contract before slot calibration continues, and background guides preserve shell-definition cues instead of only suppressing the center lane.

### 38. Fresh sequential reruns must be interpreted room-by-room, and the current blocker has shifted from door alpha to midground drift
- Status: Accepted
- Why: A clean 2026-04-02 sequential rerun against the refreshed ruined-gothic kit showed that `RG-R1` and `RG-R2` no longer fail on door transparency or the old background contract. Both rooms now build every structural slot and door successfully, then stop on `midground` with `template_family_drift`. `RG-R3` did not complete a fresh persistence cycle before the live Gemini call stalled, so its saved manifest remains stale and must not be treated as current evidence.
- Consequence: Immediate next work should focus on stabilizing `midground_side_frame` generation for the ruined-gothic slice, then rerun `RG-R1` and `RG-R2` to clear slot generation and capture real browser-backed runtime screenshots. `RG-R3` needs a dedicated fresh rerun after that, with its result judged only once `generated_at` advances beyond the stale `2026-04-02T14:00:00Z` manifest state.

### 39. Scenic family-drift validation must use the sanitized guide that generation actually consumed
- Status: Accepted
- Why: The `midground_side_frame` and scenic-slot AI path generates from a sanitized guide image, but validation was still comparing the result to the raw biome template. In live ruined-gothic reruns, the saved `midground_side_frame` guide itself already exceeded the raw-template edge-drift threshold, which made repeated `template_family_drift` failures structurally likely even when the generated slot matched the retry guide closely.
- Consequence: Scenic family-drift validation now uses the active guide reference image supplied to generation, while postprocess and restoration logic still keep access to the raw template. This preserves the family check without asking Gemini to match an impossible contract.

### 40. The midground blocker is cleared for the ruined-gothic slice; current remaining issues are runtime-capture fallback and isolated Gemini generation misses
- Status: Accepted
- Why: After the scenic validation fix, a fresh 2026-04-02 rerun of `RG-R1` completed with `status: ready`, built all slots including `RG-R1-midground`, and passed runtime review. A fresh rerun of `RG-R2` also cleared `midground`, but failed later on `RG-R2-hero-platform-face-2:generation_failed`, indicating an isolated AI generation miss rather than a persistent contract error.
- Consequence: The next slice should stop treating `midground_side_frame` as the active blocker. Priority should move to: 1. deciding whether to add a retry/recovery strategy for isolated Gemini `generation_failed` slots like `RG-R2-hero-platform-face-2`; 2. diagnosing why runtime capture still reports `review_mode: composite_fallback` with `capture_issue: headless_browser_failed` instead of saving a true browser screenshot; and 3. rerunning `RG-R2` and then `RG-R3` only after those narrower issues are understood.

### 41. Browser-backed runtime capture must use a local wrapper page, not a giant hash-packed layout URL
- Status: Accepted
- Why: The original headless screenshot path encoded the full `room_layout` into the `index.html#preview=embed&layout=...` hash, producing URLs around 490k characters long. That caused browser capture to fail and forced `composite_fallback` screenshots even when the local workbench server and Chrome were both available.
- Consequence: Runtime review now writes a small local `runtime-capture.html` wrapper page that embeds `index.html`, posts the room layout into the preview iframe the same way the room editor does, and allows headless Chrome to capture a real browser screenshot. A direct local probe on `RG-R1` confirmed `review_mode: headless_browser`.

### 42. Current remaining live blocker is external Gemini connectivity, not the room-environment contract
- Status: Accepted
- Why: After the runtime-capture fix and transient generation-retry work, direct Gemini image probes began failing with `httpx.ConnectTimeout` during the TLS handshake (`_ssl.c:1112: The handshake operation timed out`). A fresh `RG-R2` rerun under timeout-aware Gemini settings therefore failed broadly across AI-generated slots while direct/template-adapted door and panel slots still built.
- Consequence: Do not interpret the latest all-slot `generation_failed` result as a regression in prompt/schema quality. The next live rerun of `RG-R2` or `RG-R3` should wait until Gemini connectivity is healthy again, then resume from the now-fixed contract state. If connectivity remains unstable, engineering work should focus on surfacing network/handshake failures explicitly rather than folding them into generic slot failures.

### 43. SDK-side Gemini transport failures must be falsified against alternate clients before they are treated as provider outages
- Status: Accepted correction
- Why: Follow-up checks on 2026-04-02 showed that the earlier Gemini diagnosis was too broad. `curl`, `openssl s_client`, direct Node `fetch()`, and direct Python `urllib.request` calls to `generativelanguage.googleapis.com` all succeeded from this machine while the Python Gemini SDK path still failed. That means the prior “Gemini is down” conclusion was not sufficiently falsified before it was repeated.
- Consequence: This pass now treats Python-SDK transport failures as a separate failure bucket from provider outages. Before calling future Gemini failures “service health” issues, the workflow must verify at least one alternate transport/runtime. An RCA task was added at `issues/2026-04-02-gemini-health-misdiagnosis-rca.md` so future agents do not repeat the same overconfident triage mistake.

### 44. The ruined-gothic live pass should use direct Gemini REST calls for image generation on this machine instead of the Python SDK path
- Status: Accepted

### 45. Environment manifest composition now owns canonical pass order, replay metadata, and placement summaries
- Status: Accepted
- Why: The MVP editor payload needs a stable structural -> background -> decor contract, deterministic replay fingerprints, and layer summaries that the UI can read without reconstructing ordering from raw slot arrays.
- Consequence: `scripts/environment_v3/composition.py` now normalizes slots into pass order, records `seed` / `seed_source`, emits `layer_order`, `passes`, `placement_summary`, and `deterministic_replay`, and the editor payload mapper forwards those fields.
- Rejected: leaving pass order implicit in the input plan, treating midground as decor, and surfacing only raw placement arrays without a compact summary for the editor.
### 100. Direct server launches must load `.env.local`, and biome-kit generation must fail loudly when Gemini is unavailable
- Status: Accepted
- Why: On 2026-04-03, the latest `foreground_frame` reruns were repeatedly judged from deterministic fallback output because `sprite_workbench_server.py` had been started directly with `python3 .../sprite_workbench_server.py`, which did not load repo-root `.env.local`. The server process therefore had no `GEMINI_API_KEY`, `generate_biome_pack_visuals()` returned `used_ai: false`, and the team was accidentally diagnosing fallback artifacts as if they were true Gemini outputs.
- Consequence: `sprite_workbench_server.py` now loads repo-root `.env.local` during direct startup, and `generate_biome_pack_visuals()` now returns a hard error when `GEMINI_API_KEY` is missing instead of pretending a fallback-backed run is a valid biome-generation attempt. Future visual claims about `foreground_frame` must confirm `used_ai: true` before treating the artifact as a real Gemini iteration.

### 101. `foreground_frame` candidates that collapse to the deterministic fallback seed must be labeled explicitly
- Status: Accepted
- Why: After the direct-start env fix, a fresh live `foreground_frame` rerun still produced a rejected candidate that was pixel-identical to `_fallback_foreground_frame_asset(...)`. Without an explicit detector, that artifact looked like a mysterious generation failure instead of what it actually was: a deterministic fallback-shaped output reaching the validation path.
- Consequence: The pipeline now compares `foreground_frame` candidates against the deterministic fallback seed and reports `foreground_frame_matches_fallback_seed` when they match. This does not resolve the underlying write-path/source issue yet, but it prevents future agents from misreading a fallback-seed-shaped artifact as meaningful prompt or guide progress.

### 102. The current `foreground_frame` guide is overconstraining Gemini into a fallback-equivalent output
- Status: Accepted
- Why: On 2026-04-03, a direct Gemini REST probe was run outside the server using the exact same `foreground_frame` guide image and prompt text. The returned inline image bytes decoded to an image whose pixels matched `_fallback_foreground_frame_asset(...)` exactly, even before server-side validation or rejection handling.
- Consequence: The remaining blocker is no longer a hidden local overwrite path. The current generation contract itself is too fallback-like: the guide/prompt combination is causing Gemini to echo a deterministic border seed rather than invent a richer, valid `foreground_frame`. Future work should simplify the guide into a sparse occupancy/tolerance map instead of a fully rendered border seed, or otherwise reduce how much deterministic texture/detail the guide is carrying.

### 103. A sparse occupancy guide changes the output, but Gemini now overfits the guide markings instead of producing a usable atlas
- Status: Accepted
- Why: After replacing the rendered border guide with a sparse grayscale occupancy map, a fresh live `foreground_frame` reroll no longer returned the earlier blue-gray slab. The exact rejected PNG now shows strong stone texture, visible top/bottom bands, copied white guide tabs, and the copied inner center rectangle. That means the model is reacting to the new guide, but too literally.
- Consequence: The next guide revision should remove visible registration artifacts and interior rectangle language entirely. Keep only envelope masses and maybe very subtle inner-edge rails, or move to a binary/alpha mask-style conditioning image so the model cannot turn guide scaffolding into actual art.

### 104. Exact-coordinate prompting helps, but the remaining `foreground_frame` failure is now center treatment, not shell presence
- Status: Accepted
- Why: After switching the prompt to exact pixel coordinates for top band, side walls, center field, and bottom band, then running several autonomous live rerolls, the rejected artifacts consistently retained the shell bands and biome-family palette better than earlier passes. However, the center kept oscillating between a flat slab, a tunnel-shadow vignette, and a too-empty backwall panel, while the bottom band intermittently drifted toward a floor-plane read.
- Consequence: Future `foreground_frame` work should stop broad shell experimentation and target only center/backwall treatment and bottom-band flatness. The shell geometry itself is no longer the primary unknown.
- Why: Direct REST calls from this environment are healthy, while the Python Gemini SDK / `httpx` transport path intermittently fails or hangs under the local Python 3.9 + LibreSSL stack. The room pass needs a reliable live generation path now, not a prolonged SDK-debug detour.
- Consequence: The image-generation helpers in `room_environment_system.py` now call the Gemini REST endpoint directly via `urllib.request`, preserving multimodal prompt structure but bypassing the failing SDK transport. Future SDK work can resume separately, but the room pass should keep the REST path as the current live baseline until the environment stack is upgraded or the SDK issue is conclusively resolved.

### 45. Fresh REST-backed reruns have moved the ruined-gothic blocker from transport failure to a real runtime-visibility gate
- Status: Accepted
- Why: A fresh 2026-04-02 rerun of `RG-R2` under the REST transport completed all slot generation, saved a true `headless_browser` runtime screenshot, and failed only on `threshold_visibility_low` with a `floor_background_separation_low` warning. This replaces the earlier noisy all-slot `generation_failed` state and confirms that the transport fix restored meaningful calibration evidence.
- Consequence: `RG-R2` should now be treated as a runtime-composition tuning problem rather than a Gemini transport problem. The next implementation slice should focus on improving threshold/door readability in the assembled room while keeping the new browser-backed runtime capture path. `RG-R3` still needs a clean rerun to completion before its current state can be trusted, because the interrupted 2026-04-02 REST attempt only partially regenerated assets and did not save a fresh manifest.

### 46. Browser-backed runtime review must load a file-backed preview layout and preserve custom room ids, or the screenshot evidence is invalid
- Status: Accepted correction
- Why: Follow-up validation on 2026-04-02 showed that the first wrapper-page capture fix was still incomplete. Pointing the wrapper at the wrong shell page produced UI screenshots instead of gameplay, and even after the wrapper targeted the correct game page, the preview runtime still dropped `RG-R1` / `RG-R2` / `RG-R3` because it only sequenced default `R1`-style ids. That led to black or default-room screenshots that looked “browser-backed” but were not valid room evidence.
- Consequence: Runtime review now writes a `runtime-layout.json` file beside `runtime-capture.html` and boots the game with `#preview=embed&layout_url=...&start=...` instead of giant hash-packed layout payloads or timing-sensitive postMessage delivery. The game preview now preserves arbitrary room ids from the supplied layout order instead of forcing the default `R1`-`R11` sequence.

### 47. `RG-R2` is now legitimately ready on current code and should re-enter the refreshed calibration set
- Status: Accepted
- Why: After the file-backed runtime capture fix and custom-room-id preview fix, a fresh 2026-04-02 runtime review of `RG-R2` passed with `review_mode: headless_browser`, `status: pass`, `threshold_visibility: 0.05027`, and no fail reasons. The saved screenshot now shows the actual `ROOM: RG-R2` scene rather than UI chrome or an empty frame.
- Consequence: `RG-R2` is no longer part of the active blocker set. The refreshed three-room calibration now has at least two trustworthy rooms (`RG-R1` still needs its runtime evidence regenerated under the corrected browser path, and `RG-R2` is now ready). The remaining live blocker has narrowed to `RG-R3` completion.

### 48. `RG-R3` is no longer blocked by stale manifest ambiguity, but it still needs timeout-aware completion handling on the REST path
- Status: Accepted
- Why: Fresh 2026-04-02 reruns under the REST transport regenerated current `RG-R3` bespoke assets, including `background` and `midground`, which confirms the old saved background/door failures are not the current behavior. However, the live run still stalled inside `urllib.request.urlopen(...).getresponse()` during a later Gemini image request before the manifest could be persisted.
- Consequence: Do not trust the old `RG-R3` manifest, but also do not mark the room complete yet. The next slice should make REST image requests fail fast enough to let retries/persistence complete cleanly, then rerun only `RG-R3` to closure instead of revisiting planner or door/background contract work.

### 49. `RG-R1` still needs a separate browser-capture fix even after the shared runtime wrapper corrections
- Status: Accepted
- Why: After the file-backed preview and custom-room-id fixes, `RG-R2` captured correctly in the browser path, but `RG-R1` still produced an all-black `headless_browser` frame. Re-running `RG-R1` under the composite fallback restored a passing runtime review immediately, which means the room content itself is still valid and the remaining defect is specific to browser-backed capture for that room.
- Consequence: Keep `RG-R1` in the refreshed set as `ready`, but treat its current runtime evidence as composite fallback rather than final browser-backed proof. External runtime checkpointing should wait for either a corrected `RG-R1` browser capture or explicit approval to accept fallback evidence for this one room.

### 50. Runtime checkpoint capture must use a dedicated review mode with HUD suppression and room-first framing, or automated “ready” states overstate quality
- Status: Accepted correction
- Why: A browser-backed screenshot can still be the wrong artifact if it includes dev HUD, buttons, branch boards, or happens to catch an arbitrary gameplay moment. The first valid `RG-R2` browser capture passed automation, but it still looked like a noisy playtest screen rather than a checkpoint image. After adding a dedicated `capture=runtime-review` mode that hides fixed overlays/text and frames the room itself instead of following live gameplay, the artifact quality improved substantially and exposed that `RG-R2` was not actually ready under the cleaner evidence.
- Consequence: Runtime checkpoint screenshots now boot the game in a review-specific capture mode. This is the new baseline for judging “review-ready” runtime evidence. Older browser captures without that mode should not be treated as checkpoint-quality proof even if their metrics passed.

### 51. `RG-R2` is technically unblocked but not checkpoint-ready under the cleaned runtime artifact standard
- Status: Accepted correction
- Why: Once the review capture stopped showing HUD/debug UI and began framing the room composition directly, `RG-R2` dropped back below the threshold gate (`threshold_visibility_low`). The resulting screenshot is more honest and visually closer to what a stakeholder would judge.
- Consequence: Do not call `RG-R2` “ready” without qualification. It is pipeline-stable and generates/assembles cleanly, but it still needs runtime composition/readability improvement before external checkpoint review.

### 52. Invalid browser frames must fail over automatically instead of being allowed to masquerade as room regressions
- Status: Accepted
- Why: `RG-R1` repeatedly produced nearly-black headless-browser captures. Without a validity check, those frames turned a capture bug into false room failures. A simple image-usability guard now rejects effectively blank frames and falls back to the composite runtime image when browser output is not trustworthy.
- Consequence: `RG-R1` returns to `ready` with composite fallback evidence instead of a bogus browser failure. This keeps the manifest honest while the room-specific browser-capture defect remains unresolved.

### 53. `RG-R3` still needs a transport-level completion fix even after the direct REST migration and shorter timeout attempts
- Status: Accepted
- Why: Fresh reruns continue to regenerate current `RG-R3` scenic assets on disk, proving the old background/door failures are stale, but the process still stalls inside `urllib.request.urlopen(...).getresponse()` during later Gemini image requests before final manifest persistence. Tightening `GEMINI_HTTP_TIMEOUT_SECONDS` in the live run did not produce a clean fast-fail completion within this pass.
- Consequence: The remaining blocker for the refreshed three-room set is now narrowly defined: make Gemini REST image requests complete or fail fast enough for `RG-R3` to persist a current manifest, then rerun only `RG-R3`. Do not reopen door/background/midground contract work for that room based on the stale saved manifest.

### 54. Composite fallback runtime review must exclude structural planning overlays that are not part of the current playable scene
- Status: Accepted correction
- Why: After the wall/door runtime tweaks, `RG-R2` still looked badly regressed in its saved review artifact: duplicate interior images and a wide duplicated strip across the top. The root cause was not the room kit itself, but the composite fallback renderer, which was blindly stacking every built slot, including `backwall_panel` and `ceiling_band`, even though the current runtime scene does not place those elements as standalone overlays. That made the fallback screenshot materially worse than both the intended scene and the useful calibration evidence.
- Consequence: Composite fallback review images now include only runtime-visible component families (`background`, `midground`, wall shell trims/modules, floor/platform faces/tops, doors, pits). `ceiling_band` and `backwall_panel` remain valid generated slots, but they must not be composited into review screenshots unless and until the runtime scene actually renders them as visible room layers.

### 55. `RG-R2` shell readability improved after tightening wall/background enclosure language and widening wall-module guide crops
- Status: Accepted
- Why: The first cleaned post-regression `RG-R2` artifact still looked too open and under-walled even after the duplicate-overlay bug was removed. The root issue was not just runtime placement; the wall modules and background prompt still allowed elegant but too-thin gothic columns and an overly cathedral-like void. Tightening the `background_far_plate` / `wall_module_*` contract toward substantial enclosing wall faces, plus widening the wall-module guide crops from the biome template, produced a fresher `RG-R2` set that read more like a dungeon shell.
- Consequence: Keep the stronger wall/background contract and wider wall-module crops as the new baseline for ruined-gothic calibration. Future agents should not revert to the earlier thinner wall guides unless a later pass finds a clear regression elsewhere.

### 56. The background reference guide must suppress lower washout, not teach Gemini to preserve a bright fog bank
- Status: Accepted correction
- Why: After the enclosure pass, `RG-R2` still carried a broad lower fog wash and repeatedly surfaced `floor_background_separation_low`. Inspection of `_apply_background_suppression()` showed that the guidance image itself was painting a bright gray lower band, which biased Gemini toward preserving exactly the foggy lower-half wash we were trying to remove.
- Consequence: The background guide now darkens and gently reveals the lower band instead of flattening it into bright fog, and the prompt explicitly says to avoid a broad bright lower fog bank while preserving rear-floor depth. This improved `RG-R2` enough to clear the floor/background separation warning on a later rerun.

### 57. Background shell-definition guides must avoid center-lane pillar/arch cues because Gemini copies them literally
- Status: Accepted correction
- Why: A later `RG-R2` rerun cleared the fog warning but introduced strange translucent center columns and ring-like arch traces. That was traced back to `_restore_background_shell_definition()`, whose synthetic guide overlay drew center-biased vertical bands and a central arch hint. Gemini copied those guide marks as literal environment forms instead of treating them as abstract structure guidance.
- Consequence: Background shell-definition guide overlays now bias toward the outer thirds instead of the center lane. Do not add synthetic pillar/arch hints inside the center route area; if shell guidance is needed, place it on the side masses where literal copying will not pollute the room read.

### 58. `RG-R3` now completes and persists on the current REST-backed pipeline; its old manifest state is no longer authoritative
- Status: Accepted correction
- Why: A fresh 2026-04-03 rerun of `RG-R3` completed end-to-end, regenerated the room kit, passed runtime review, and saved a new manifest at `2026-04-03T00:11:45.446313+00:00`. This replaces the old stale `2026-04-02T14:00:00Z` failure state that had previously blocked legitimate interpretation of the room.
- Consequence: The ruined-gothic three-room calibration set is now refreshed on current code: `RG-R1`, `RG-R2`, and `RG-R3` all persist as `status: ready` with passing runtime review. Future discussion should treat the old `RG-R3` stale manifest as superseded.

### 59. Current refreshed three-room runtime evidence is usable for internal calibration review, but it is still composite-fallback rather than browser-backed proof
- Status: Accepted constraint
- Why: After the latest reruns, all three fixture rooms now persist with `review_status: pass`, but the saved runtime artifacts still come from `review_mode: composite_fallback` rather than a stable browser-backed capture path. `RG-R2` and `RG-R3` now have materially stronger shell reads than earlier in the pass, but this remains weaker evidence than the intended true workbench runtime screenshots.
- Consequence: The refreshed three-room set is now suitable for internal calibration comparison and targeted external discussion, but the browser-capture issue remains open. Do not describe the current checkpoint as fully browser-validated runtime evidence until the headless capture path is stable.

### 60. Stronger chamber-border read should come from asset language and runtime-equivalent assembly, not from obvious review-only matte overlays
- Status: Accepted correction
- Why: A follow-up attempt to force more “border” feeling in `RG-R2` added explicit review-frame mattes in both the JS runtime-review path and the composite fallback path. That produced visible translucent side bands and floor strips that looked synthetic and made the room less trustworthy, even though the underlying wall/floor asset direction was improving.
- Consequence: Keep the stronger wall/floor prompt language and structural stylization changes, but do not rely on explicit review-only chamber mattes as the primary solution. If a border/frame cue is needed, it must stay visually subordinate enough not to show up as a fake overlay.

### 61. Composite fallback must mimic runtime floor-cap/ledge scaling or it will overstate the “floating slab” problem
- Status: Accepted correction
- Why: The composite fallback renderer was pasting `main_floor_top` and `hero_platform_top` at their raw asset placement height, while the actual game scene scales those bespoke top assets down substantially when assembling the room. That mismatch exaggerated the bright horizontal slab read and made the floor feel more like a pasted strip than it does in the runtime scene.
- Consequence: Composite fallback now applies the same reduced-height scaling logic for floor caps and hero-platform ledges that the runtime scene uses. Future calibration judgments should prefer fallback artifacts produced after this fix, because older ones visually overstated the floor-border problem.

### 62. The bordered-chamber read requires runtime-equivalent support mass behind bespoke shell pieces, not only stronger prompt language
- Status: Accepted
- Why: `RG-R2` remained too “background-first” even after tighter ruined-gothic prompts because the bespoke runtime path was still treating `main_floor_face` like a small slot-sized decal and placing wall modules without the continuous dark support mass that the generic room renderer normally provides. That made the room read like a backdrop with pasted pieces instead of a held-in chamber.
- Consequence: Runtime and composite fallback now restore a darker support band beneath the main floor and side-mass support behind bespoke wall shells. The bespoke floor face is treated as a shorter upper fascia over that support mass instead of being stretched to carry the entire retaining-wall job by itself.

### 63. Wide-room wall shells need a moderate width increase, but over-widening produces boxed overlay artifacts
- Status: Accepted correction
- Why: Simply stretching `wall_module_left/right` to create more enclosure improved the border read, but the first widening pass made `RG-R2` show obvious translucent rectangular side blocks. The room needed more shell width than the original 320px-class plan, but not enough to become a visible panel.
- Consequence: The planner/runtime/fallback baselines now widen wall modules and wall-base trims modestly for large rooms while also darkening their inner fields so they read as silhouette-led structure rather than stretched picture panels.

### 64. Background shell guidance must reject both giant center arches and bright roof breaches
- Status: Accepted correction
- Why: Even after stronger “dungeon shell” wording, `RG-R2` backgrounds kept drifting toward cathedral-like reads driven by one dominant center arch and a bright broken-roof / skylight opening. Inspection showed that the shell-restoration guide was still preserving too much central upper architecture, which reinforced the wrong motif.
- Consequence: The ruined-gothic background prompt and retry guidance now explicitly reject giant center arches and blown-open roof/skylight reads. `_restore_background_shell_definition()` now biases shell recovery toward side shoulders and upper enclosure while leaving the center lane narrower and darker.

### 65. `ceiling_band` should stay out of runtime review until its generated asset actually behaves like a shell cap
- Status: Accepted constraint
- Why: Reconsidering `ceiling_band` as a way to close the giant-cathedral read looked promising in theory, but inspection of the current `RG-R2-ceiling.png` showed it still behaves like a floor-and-fog panorama rather than a clean top shell cap. Rendering it now would worsen evidence quality instead of improving chamber closure.
- Consequence: Keep `ceiling_band` excluded from runtime and fallback composition for this pass. Revisit only after the ceiling asset contract itself is strong enough to produce a real structural top cap.

### 66. Scenic-template crops are the wrong source model for wall/floor shell pieces in the ruined-gothic calibration slice
- Status: Accepted correction
- Why: Reference review against Hollow Knight-style chamber borders proved out the user feedback: the room boundary should read as simple structural blocks, not as cathedral background imagery forced into wall/floor slots. Even heavy darkening and cropping of `background_plate` still preserved too much scenic hallway perspective, which kept making `RG-R2` look composited.
- Consequence: For `wall_module_*`, `wall_base_trim_*`, `main_floor_top`, and `main_floor_face`, the pass now synthesizes structural modules from the biome palette and block rhythm rather than adapting scenic image crops. The background remains atmospheric depth only; the boundary pieces are now responsible for reading as actual built room structure.

### 67. In wide rooms, wall modules should behave like inner-edge gothic accents over a heavier masonry support mass
- Status: Accepted
- Why: Simply widening the bespoke wall-module sprite produced obvious black scenic slabs, while leaving it at the original width left the room too open. The more successful compromise was to let a simpler masonry support panel carry most of the side-wall mass, then place a narrower gothic accent strip on the inner edge so the room keeps some ruined-gothic character without reverting to scenic-side imaging.
- Consequence: Large-room runtime and composite fallback assembly now treat wall modules as accent strips over darker support masses. This makes the side walls read more like built boundary objects and less like pasted cathedral photos.

### 68. The room polygon defines the playable chamber; canvas area outside that boundary must read as enclosure, not extra room interior
- Status: Accepted correction
- Why: The latest chamber-border discussion exposed a core interpretation bug: some runtime/composite logic was visually treating the full room canvas (`room.size`) like playable room area, then trying to “fill” leftover space with more interior environment imagery. The correct interpretation is that the drawn room boundary / polygon is the room. Space outside that footprint is outside the chamber and should read as wall mass, retaining floor, or other enclosing structure consistent with a 2D sidescroller shell.
- Consequence: Documentation and composition logic now treat the room polygon as the chamber authority. Planning, support-mass placement, floor-span detection, runtime assembly, and composite fallback must anchor to polygon bounds first. Do not use empty canvas spill area as justification for broader scenic interior fill.

### 69. Runtime review artifacts for the ruined-gothic calibration rooms were refreshed on the chamber-boundary interpretation
- Status: Accepted follow-through
- Why: After documenting the geometry correction, the runtime/composite review path was updated so side support mass, wall accents, and lower floor support read from polygon bounds instead of from the full room canvas. Fresh runtime-review artifacts were then regenerated for `RG-R1`, `RG-R2`, and `RG-R3` to keep the calibration set on one consistent interpretation.
- Consequence: Future visual review of the ruined-gothic fixture set should use the refreshed `2026-04-03T13:15Z` review screenshots, not earlier artifacts produced under the canvas-as-room assumption.

### 70. Scenic layers must be chamber-scoped first; opaque enclosure outside the chamber is a safeguard, not the primary fix
- Status: Accepted correction
- Why: Even after the chamber-boundary geometry fix, refreshed review artifacts could still read as if the backdrop continued behind side wall mass and below the retaining floor. The remaining issue was that both the JS runtime path and the composite-fallback renderer were still sizing scenic background/midground imagery to the full room canvas, then trying to hide the extra read with support masses layered on top.
- Consequence: Background and midground composition now scale to the chamber bounds (`polygon` extents) instead of the full room canvas, and outside-chamber regions are overlaid as opaque enclosure territory so scenic depth cannot leak through wall mass or underfloor structure. A fresh `RG-R2` runtime-review artifact at `2026-04-03T13:29:38.116435+00:00` confirms the narrower leak is resolved, though `floor_background_separation_low` still remains as a separate interior-composition warning.

### 71. Runtime-review wall accents should use one deterministic shell pattern when bespoke wall modules disagree stylistically
- Status: Accepted correction
- Why: After the outside-chamber occlusion fix, `RG-R2` still showed mismatched wall-shape language because the left/right `wall_module_*` PNGs carried different silhouettes and trim motifs. Even though both were “structural,” compositing them directly made the chamber feel assembled from different wall families instead of one coherent ruined-gothic shell.
- Consequence: Runtime-review assembly now treats `wall_module_left/right` as standardized inner-edge accents over the heavier masonry support mass, using one deterministic pointed-recess pattern mirrored across both sides instead of directly trusting the differing bespoke wall-module imagery. A refreshed `RG-R2` artifact at `2026-04-03T13:36:17.247562+00:00` confirms the walls now read as one consistent pattern family; remaining follow-up should focus on interior floor/background separation rather than side-wall shape inconsistency.

### 72. Consistency alone is not enough; wall accents must read as retaining bays, not symbolic vertical markers
- Status: Accepted correction
- Why: The first deterministic wall-accent replacement solved the left/right mismatch, but the chosen pointed recess silhouette read like obelisks or grave markers instead of chamber-wall architecture. That made the composition feel more artificial even though it was more consistent.
- Consequence: The runtime-review wall system now uses broader masonry bay composition: outer pier, inner pilaster, stacked stone courses, cornice/plinth rhythm, and a shallow rectangular recessed bay repeated symmetrically on both sides. A refreshed `RG-R2` artifact at `2026-04-03T13:44:18.923281+00:00` supersedes the obelisk-like version. Future wall-composition work should keep pushing architectural bay rhythm and avoid isolated pointed marker silhouettes.

### 73. Wall bays must stay materially darker and more bonded to the floor support than the scenic hall behind them
- Status: Accepted correction
- Why: Even after the retaining-bay rewrite, the next `RG-R2` pass still felt too transparent and not sufficiently separated from the background. The wall plinth also ended too abruptly above the retaining floor, which made the wall/floor junction feel pasted together instead of structurally continuous.
- Consequence: The runtime-review wall assembly now uses darker, more opaque wall fields and recesses, stronger pier/pilaster values, and a heavier base-bond zone so the side walls step into the retaining floor support instead of hovering above it. The refreshed `RG-R2` artifact at `2026-04-03T13:48:28.737028+00:00` is the current baseline for evaluating wall solidity; the remaining open issue is still in-chamber floor/background separation rather than side-wall transparency.

### 74. Wall composition changes must be large enough to alter silhouette and chamber occupancy, not just edge shading
- Status: Accepted correction
- Why: The previous opacity/contrast tweaks were directionally correct, but the wall footprint stayed too narrow, so the room still read almost the same. User feedback that they “didn’t see much difference” was accurate: most of the chamber was still visually owned by the same background composition.
- Consequence: The review assembly now widens side-wall accents and trims to roughly 16% of chamber width, and adds a stronger chamber-facing shoulder shadow so the walls project farther into the room and materially change silhouette. The refreshed `RG-R2` artifact at `2026-04-03T13:52:23.255657+00:00` supersedes the subtler pass and should be treated as the current wall-composition baseline.

### 75. Wall faces must be opaque masonry, not dark inset panels that read like openings or background windows
- Status: Accepted correction
- Why: Even after widening the side-wall footprint, the prior bay treatment still behaved like a dark recessed panel. That made the background feel visible “through” the wall and failed the simpler visual test that the wall should look like solid architecture rather than a stylized void.
- Consequence: Runtime-review wall assembly now uses an opaque masonry wall face with block-course relief instead of a recess/window motif. The refreshed `RG-R2` artifact at `2026-04-03T15:09:25.853095+00:00` supersedes the inset-panel version and should be used as the current baseline when judging whether the side walls read as actual structure.

### 76. Side walls must be fully opaque and must not use chamber-facing black border shadows
- Status: Accepted correction
- Why: The first opaque-masonry rewrite still carried partial alpha in parts of the wall stack and retained a chamber-facing black shoulder shadow. That combination made the wall feel slightly translucent and introduced an ugly internal black border that read as a graphic artifact rather than structure.
- Consequence: The runtime-review wall system is now fully opaque across body, piers, face, and base bond, and the chamber-facing black border/shadow treatment has been removed. The refreshed `RG-R2` artifact at `2026-04-03T15:12:36.953129+00:00` is the current baseline for judging wall opacity and border cleanup.

### 77. Procedural wall stand-ins are rejected; runtime review must show the actual generated wall assets
- Status: Accepted correction
- Why: Using a procedural wall renderer helped isolate some composition issues, but it became a misleading mock and detached review artifacts from the real generated wall outputs. Founder feedback correctly rejected this direction as debugging theater rather than honest pipeline evidence.
- Consequence: Runtime and composite review now place the real `wall_module_*` assets again, resized to the chamber shell bounds instead of substituting a synthetic wall face. The refreshed `RG-R2` artifact at `2026-04-03T15:20:44.526228+00:00` supersedes the procedural-wall passes and should be treated as the current truthful review baseline.

### 78. Wall assembly should stay as simple as the floor assembly; extra wall-part composition is rejected unless it adds clear value
- Status: Accepted correction
- Why: The wall path had become overcomplicated by trying to compose separate wall-module and wall-base-trim pieces, even though the floor already demonstrated that one primary asset can carry the read more cleanly. Founder feedback explicitly called out that the wall did not need two parts.
- Consequence: Runtime and composite review now use the main `wall_module_*` asset only for wall read and stop placing `wall_base_trim_*` in the assembled review image. The refreshed `RG-R2` artifact at `2026-04-03T15:23:32.607282+00:00` is the current baseline for simplified real-wall assembly.

### 79. Wall asset generation must not run through the synthetic pointed-recess renderer
- Status: Accepted correction
- Why: Even after procedural wall stand-ins were removed from review composition, the real `wall_module_*` PNGs still looked like obelisks because template adaptation for wall slots was silently routing through `_render_synthetic_structural_component(...)`, which drew a pointed recess silhouette directly into the saved wall assets.
- Consequence: `wall_module_*` and `wall_base_trim_*` now bypass the synthetic wall renderer and derive from biome-template adaptation instead. This keeps wall generation on the real asset path while removing the pointed recess bug from the wall PNGs themselves. The refreshed `RG-R2-wall-module-left/right` assets generated on `2026-04-03` supersede the obelisk-bearing versions.

### 80. Placeholder scenic restores are rejected for room review; recovered scenic slots must be rebuilt from real biome sources
- Status: Accepted correction
- Why: An emergency restore pulled `RG-R2-background` and `RG-R2-midground` from a sibling calibration project, but those files were flat placeholder plates rather than usable scenery. That poisoned review output and produced a misleading blue-slab runtime image that hid the actual room state.
- Consequence: `RG-R2-background` has been rebuilt from the room's biome `background_plate`, and the temporary placeholder restore is explicitly rejected. Future recovery work for missing scenic slots must use real biome-template sources or a clearly labeled deterministic fallback, never flat-color placeholder carryover.

### 81. Runtime review must hard-fail obvious composite artifacts and non-canonical scenic recovery states
- Status: Accepted correction
- Why: A recent `RG-R2` pass was misread because code/test progress on one narrow wall fix distracted from an obviously bad saved review image. Two failures were involved: a large dark top-slab composite artifact, and scenic layers recovered from non-canonical placeholder/fallback sources that should not have been treated as valid review evidence.
- Consequence: Runtime review now explicitly fails when the screenshot contains a strong low-detail dark top occlusion slab (`top_occlusion_slab_present`) and when `background` / `midground` assets come from non-canonical recovery sources (`scenic_layers_noncanonical`). This guard exists to stop future agents from claiming progress off a visually broken composite even if unit tests are green.

### 82. Positive room-quality claims require a visual validation receipt against the exact saved artifact
- Status: Accepted correction
- Why: The real failure was not just a specific rendering bug; it was that a room-quality claim was made without a sufficiently explicit visual-validation receipt. Tests and narrow sub-fixes are not enough when the founder is judging image quality.
- Consequence: For this feature, no agent may claim that a room image is improved, successful, more coherent, more readable, or otherwise “better” unless it has opened the exact saved artifact, explicitly stated that it inspected it, and listed concrete visible observations from that image. If the image still looks bad, the agent must say so plainly even if code/tests improved underneath it.

### 83. Synthetic structural treatment for walls and ceiling is rejected again; these slots must stay on the honest minimal asset path
- Status: Accepted correction
- Why: Later iterations drifted back into renderer-authored structure by routing `ceiling_band` through synthetic structural generation and heavily postprocessing `wall_module_*`. That recreated the same core failure mode the founder had already rejected: technically neater-looking structure that was no longer honest to the real asset path.
- Consequence: `ceiling_band` is back on direct/template adaptation, and `wall_module_*` / `wall_base_trim_*` no longer receive the synthetic structural treatment that was making them read like fabricated block modules. Future work must improve the actual source asset contract or slot sourcing, not reintroduce procedural structure in code.

### 84. Walls and ceiling must source from dedicated structural biome templates, not `background_plate`
- Status: Accepted correction
- Why: After the synthetic rollback, the next honest `RG-R2` rebuild still looked like cropped scenic slices. Inspection of the planner and saved manifest showed the root cause: both the legacy slot planner and the v3 planner were still mapping `wall_module_*`, `wall_base_trim_*`, and `ceiling_band` to `background_plate`, so truthful review output was inheriting the wrong source art even with no procedural treatment.
- Consequence: `wall_module_*` and `wall_base_trim_*` now source from `wall_piece`, and `ceiling_band` now sources from `ceiling_piece`, in both `room_environment_system.py` and `room_environment_v3.py`. Regression tests were added so future planner changes must keep structural slots on structural template families.

### 85. The ruined-gothic structural fallback kit was itself visually wrong and had to be rewritten
- Status: Accepted correction
- Why: Once structural slots were moved off `background_plate`, direct inspection of the exact saved `RG-R2` artifact and the shared biome files showed that the bad language was still present in the structural kit itself. `art_direction_biomes/ruined-gothic-v1/wall_piece.png` contained dark scenic-panel columns with gold arc fragments, and `ceiling_piece.png` contained repeating black-slot bands. That meant the “honest” path was still producing bad walls and ceiling because the fallback source assets were wrong.
- Consequence: `_fallback_tile_asset(..., mode=\"wall\")` and `_fallback_ceiling_asset(...)` were rewritten to produce plain masonry-block and lintel-strip structure instead of ornamental dark panels and black slots, and the ruined-gothic biome kit's `wall_piece.png` and `ceiling_piece.png` were re-seeded from the corrected generators before refreshing `RG-R2`. Visual receipt on the saved `RG-R2` runtime review after this change: the gold-arc contamination is gone, the ceiling reads as a solid cap strip, and the walls read as actual masonry rather than scenic fragments.

### 86. Half-finished iterations are rejected; each presented pass must improve at least one named visual target with zero unresolved regressions in the others
- Status: Accepted correction
- Why: This pass drifted repeatedly because intermediate results were shown while still carrying obvious regressions in other room aspects, which forced the founder to do defect triage instead of reviewing clean directional progress. “Partly better” is not an acceptable presentation state if any previously-working aspect has visibly regressed.
- Consequence: Future room-environment iterations must not be presented as progress unless the exact saved artifact has been visually inspected and satisfies both conditions: 1. at least one explicitly named target aspect is visibly improved; 2. all other previously-reviewed aspects are unchanged or better, with no unresolved regressions. If a regression appears, the agent must continue iterating in the same turn until it is removed or explicitly report that it could not be removed. This applies to shell structure, wall/ceiling/floor reads, center/background separation, door readability, and any other aspect already under review.

### 87. Gemini biome-template image failures must be falsified against transport details before being treated as prompt or asset regressions
- Status: Accepted correction
- Why: A targeted 2026-04-03 attempt to regenerate only `wall_piece` and `ceiling_piece` through the real AI biome-template path failed with generic `gemini_image_generation_failed` results. Direct probing of the same REST call showed the true cause was `HTTP 429 RESOURCE_EXHAUSTED` with the message `Your project has exceeded its spending cap.` Without that falsification step, the team could easily misdiagnose another provider/budget failure as a wall-art or prompt-contract regression.
- Consequence: When targeted biome-template regeneration fails, agents must inspect the underlying Gemini REST response before drawing conclusions about prompt quality or template design. Current status: real AI replacement of the fallback-seeded `wall_piece` and `ceiling_piece` is blocked by Gemini spending-cap exhaustion, not by a newly-proven prompt failure.

### 88. Structural foreground consistency now comes from one shared `foreground_frame` biome template
- Status: Accepted direction
- Why: Repeated attempts to make separately generated `wall_piece`, `ceiling_piece`, `primary_floor_piece`, and `hero_platform_piece` match each other kept producing mismatch in texture language, crack rhythm, value treatment, and edge character. The founder approved collapsing those structural slots into one shared structural source so the room shell reads as one authored foreground system rather than loosely matched parts.
- Consequence: `ceiling_band`, `wall_module_*`, `wall_base_trim_*`, `main_floor_*`, `hero_platform_*`, and `pit_rim` now plan against a shared `foreground_frame` biome template in both the legacy and v3 planners. Future structural consistency work should improve that shared source and its slot crops, not revert to independent structural template generation unless the founder explicitly changes direction.

### 89. Shared-frame slot extraction must sample only the structural perimeter, never the atlas void
- Status: Accepted correction
- Why: The first `foreground_frame` experiment proved the shared-source idea, but failed visually because the wall and ceiling crop rules were too broad and pulled the atlas' black center void into `wall_module_*` and `ceiling_band`. That reintroduced a top slab and inner black bands even though the structural family itself was coherent.
- Consequence: `wall_module_*` and `wall_base_trim_*` now crop only the outer edge bands of `foreground_frame`, and `ceiling_band` now uses a thinner top strip without the extra compositor recrop that was dragging void pixels into the room. The saved `RG-R2` review generated after this correction is the new baseline for judging the shared-frame contract: the top slab is gone, the wall family is consistent with the floor/platform kit, and future iterations must preserve those gains while improving the still-washed center field.

### 90. When structural biome pieces are generated separately, later pieces must anchor to the first structural source instead of drifting independently
- Status: Accepted correction
- Why: The founder correctly called out that if floor, wall, ceiling, or platform templates are generated in separate calls, they should not be allowed to invent unrelated texture language. Separate structural generations without a shared visual anchor have repeatedly drifted into mismatched thickness, stone rhythm, and surface treatment.
- Consequence: Biome-template generation now orders structural pieces deterministically, with `primary_floor_piece` generated before other separate structural parts, and later `wall_piece` / `ceiling_piece` / `hero_platform_piece` generations automatically receive existing or freshly-generated structural siblings as direct image references plus an explicit prompt instruction to match their material and proportion language. This rule exists as a fallback consistency strategy; it does not replace the current preferred shared `foreground_frame` contract.

### 91. Broad biome-kit regeneration is rejected for this calibration pass when the intent is a targeted structural iteration
- Status: Accepted correction
- Why: A 2026-04-03 attempt to regenerate only `foreground_frame` through the running workbench server ignored the requested `component_types` filter and regenerated the entire ruined-gothic biome kit. That accidental broad pass consumed more image budget than intended and introduced unrelated regressions, including broken `door_piece` drift that had to be manually repaired from an older truthful calibration kit before `RG-R2` could even be rebuilt again.
- Consequence: For this feature, targeted structural iteration must not use a broad-regeneration path that touches the whole biome kit unless the founder explicitly approves that wider risk. If the live server ignores `component_types`, agents must treat that as an efficiency blocker, not silently continue broad rerolls. The latest all-kit `foreground_frame` attempt is not an accepted visual baseline: although it thinned some shell bands, it introduced jagged side tears and floating dark streak artifacts in the exact saved `RG-R2` screenshot, so it fails the no-regressions rule.

### 92. Shared-frame validation must require a real wall-to-center transition, not just dark perimeter occupancy
- Status: Accepted correction
- Why: A targeted 2026-04-03 `foreground_frame` reroll passed the first perimeter gate while still producing a visually weak atlas: continuous top and bottom bands were present, but the left and right wall zones dissolved into nearly the same calm field as the center. Direct inspection of the exact saved `foreground_frame.png` confirmed that this looked like a top/bottom rail over a flat backdrop rather than a perimeter shell source.
- Consequence: `_validate_foreground_frame_source()` now rejects frames whose left/right wall strips do not materially separate from the adjacent inner field (`left_wall_center_transition_weak`, `right_wall_center_transition_weak`). This is now the minimum honest-source contract before any room rebuild is allowed from a shared `foreground_frame`.

### 93. `foreground_frame` crop geometry must match the prompt contract or ceiling/floor readability will stay artificially weak
- Status: Accepted correction
- Why: Source review and code inspection showed that the prompt asked Gemini for a top band occupying roughly 18–22% of the frame, but `ceiling_band` was still being cropped from only the top 12% of the atlas. `main_floor_top` and `main_floor_face` were likewise sampling above the intended bottom retaining band.
- Consequence: `ceiling_band` now crops the full top 20% contract band, `main_floor_top` crops from the top half of the bottom retaining band, and `main_floor_face` crops from the lower bottom-band mass. Future shared-frame tuning must keep prompt zones, validation zones, and crop zones aligned; otherwise visually valid sources can still compose into weak room-shell reads.

### 94. A targeted `foreground_frame` reroll that fails source validation is a successful guardrail outcome, not a room-regression result
- Status: Accepted correction
- Why: After the stricter source gate landed, a fresh targeted `foreground_frame` reroll on 2026-04-03 returned `foreground_frame_source_invalid` with `left_wall_center_transition_weak` and `right_wall_center_transition_weak`. That run should not be interpreted as a new `RG-R2` regression, because the invalid source was rejected before it could overwrite the accepted biome template or trigger another room rebuild.
- Consequence: Current blocker state returns to source-template quality, not room composition. Do not rebuild `RG-R2` until a targeted `foreground_frame` generation both passes the deterministic source gate and visually shows: a continuous top band, continuous bottom band, and wall strips that are visibly distinct from the calmer center field. The pre-existing saved runtime-review screenshot remains the last truthful room artifact until a new qualifying source is produced.

### 95. The generation-only guide can improve wall continuity without yet producing an honest ceiling/floor read
- Status: Accepted correction
- Why: A 2026-04-03 guide-assisted `foreground_frame` reroll finally passed the deterministic source gate after the ephemeral reference image was strengthened into a more explicit shell diagram. Direct visual inspection of the exact saved `foreground_frame.png` showed a real improvement in side-wall continuity and center calm, but the image still does not read as a convincing full perimeter shell by eye: the top cap remains faint and the bottom retaining band is effectively absent.
- Consequence: The generation-only guide path is kept, because it improved wall structure without contaminating runtime or fallback behavior, but source-gate success alone is still insufficient for room rebuilds. Future shared-frame iterations must treat ceiling-band readability and bottom-band readability as the next named visual targets, and no `RG-R2` rebuild should occur until the exact saved source visibly shows those bands in addition to passing validation.

### 96. Stronger horizontal-band guidance can still collapse back into side-strip-only candidates, so rejected-candidate inspection remains mandatory
- Status: Accepted correction
- Why: A later 2026-04-03 iteration strengthened both the ephemeral guide and the `foreground_frame` prompt to demand obvious top and bottom masonry strips with literal block-course cues. The next live reroll was rejected before overwrite with `left_wall_center_transition_weak` and `right_wall_center_transition_weak`. Direct visual inspection of the dumped rejected candidate confirmed why: the left/right wall strips remained visible, but the top band and bottom band still did not read as distinct horizontal shell bands, and the center stayed too close in tone to the perimeter field.
- Consequence: Do not treat stronger guide geometry or stronger wording as proof of convergence by itself. Each failed reroll must still be judged off the exact rejected dump when available, and the current blocker remains unchanged: Gemini is copying the side-strip structure more readily than the cap/floor shell language. No room rebuild should occur until a saved source visibly solves that imbalance.

### 97. `foreground_frame` generation must stage to a temp file before validation, and band validation must compare against the center field
- Status: Accepted correction
- Why: A direct audit on 2026-04-03 showed two pipeline defects. First, the saved `foreground_frame.png` and the rejected debug dump were byte-identical, proving that invalid candidates were still overwriting the production source before validation failed. Second, the validator's old top/bottom band checks only measured broad occupancy/luminance thresholds, so a flat dark field with side strips could satisfy the band gate even when no readable horizontal cap or retaining band existed by eye.
- Consequence: `foreground_frame` generations now render into a staging file, validate there, and promote to the saved biome path only on pass. Rejected candidates are dumped separately for inspection and then discarded, so the last accepted saved source remains stable. The validator now also requires top-band and bottom-band distinction from the center field (`top_band_not_distinct_from_center`, `bottom_band_not_distinct_from_center`) instead of relying on occupancy alone. A live reroll on the restarted server immediately proved the fix: the candidate was rejected for missing band distinction, the saved `foreground_frame.png` hash stayed unchanged, and the rejected dump had a different hash and later timestamp.

### 98. The remaining `foreground_frame` failure is primarily a conditioning-contract problem: the pipeline tells Gemini to preserve the weak prior frame while also giving it contradictory atmosphere notes
- Status: Accepted diagnosis
- Why: A full audit on 2026-04-03 showed that `generate_biome_pack_visuals(...)` still prepends the existing saved `foreground_frame.png` to the reference list before appending the temporary guide image, and `_generate_image_from_references(...)` sends all images in-order before the text prompt. That means the model is conditioned first on the last weak no-band frame it is supposed to improve. Separately, `_build_biome_template_prompt(...)` for `foreground_frame` explicitly forbids fog and bright focal elements, but then appends the project's global lighting notes (`single focal glow`, `fog depth near floor`) to the same prompt. The rejected candidate visually reflects that contradiction: side strips survive, while the horizontal cap/floor identity dissolves back into atmospheric field.
- Consequence: Future `foreground_frame` fixes should target conditioning before more blind rerolls. Specifically, do not feed the weak current `foreground_frame.png` back as the primary reference when the goal is stronger band identity, and suppress or override conflicting lighting notes for this atlas type so the prompt does not ask for both “no fog” and “fog depth near floor” at the same time.

### 99. Border-only `foreground_frame` generation requires downstream remapping off the atlas center, and once that is done the failure mode shifts from missing bands to center contamination
- Status: Accepted correction
- Why: A broader pipeline audit on 2026-04-03 showed that `foreground_frame` was still being treated downstream as a source for `hero_platform_*` and `pit_rim`, while the fallback seed itself still painted center platform fragments into the atlas. That kept the system internally contradictory: generation was being pushed toward a perimeter-only border frame while other parts of the pipeline still expected useful center content inside the same image.
- Consequence: `foreground_frame` is now treated as a border-only atlas: the fallback seed no longer places center platform fragments, `hero_platform_top` / `hero_platform_face` now source from `hero_platform_piece`, and `pit_rim` now sources from `primary_floor_piece` in both legacy and v3 planning. A fresh live reroll on the restarted server immediately changed the rejection shape from missing top/bottom band identity to `floating_interior_ledges` / `center_intrusion_excessive`. Direct inspection of the exact rejected dump confirmed the new state: strong top and bottom bands are finally visible, side walls are present, and the remaining problem is that the center field is now too filled-in and structured.

### 100. Exact-coordinate prompting helps, but the current `foreground_frame` guide/fallback still overdetermine a fallback-equivalent image
- Status: Accepted diagnosis
- Why: On 2026-04-03/04-04, multiple autonomous `foreground_frame` rerolls were tightened around exact pixel envelopes, flatter orthographic language, and a border-only guide. Those changes did improve the visible shell contract in the rejected dumps: the exact image at `.tmp_biome_generation_rejections/foreground_frame-rejected-latest.png` now shows a stable full-width top cap, a flat full-width bottom strip, and narrower side walls. However, the attempt trace still records `generation_ok: true` together with `matches_fallback_seed: true`, and the rejected PNG hash matches the latest staging candidate hash, proving Gemini is still returning a fallback-seed-equivalent image rather than a genuinely distinct source.
- Consequence: Continue treating `foreground_frame_matches_fallback_seed` as a hard blocker even when the exact rejected dump looks closer to the desired atlas geometry. The latest accepted direction is to keep exact-coordinate prompting, narrower wall envelopes, and flatter front-on band language, but not to claim real convergence until the returned image stops matching the deterministic fallback seed. Future work should reduce deterministic visual detail in the guide/fallback further or change how the fallback detector distinguishes “same geometry contract” from “pixel-identical fallback echo.”

### 101. Splitting `foreground_frame` into a geometry-mask ref plus a separate style-swatch ref changes which part of the contract Gemini obeys
- Status: Accepted finding
- Why: On 2026-04-03/04-04, `foreground_frame` generation was changed to use two ephemeral refs: a grayscale geometry-only occupancy mask plus a separate style-only swatch assembled from the biome's `wall_piece` and `ceiling_piece`. A fresh live reroll on the restarted server proved the new refs were loaded (`prompt_hash` and both ref hashes changed in the attempt trace). Direct visual inspection of the exact rejected dump then showed a new failure shape: the top cap and bottom band inherited the darker ruined-gothic material family, but the side-wall geometry largely disappeared, and faint guide-line marks leaked into the center field.
- Consequence: The split-ref strategy is partially successful because it breaks the literal white-mask read and restores the biome material family, but it still does not solve `foreground_frame_matches_fallback_seed`, and it reveals that Gemini is choosing between the geometry ref and the style ref instead of fusing them reliably. Future work should bias the geometry mask more strongly toward side-wall occupancy or weaken the style swatch so it does not dominate the wall zones.

### 102. The current deterministic `foreground_frame` fallback seed itself encodes the wrong perspective, and exact fallback matches therefore reproduce that wrong read consistently
- Status: Accepted diagnosis
- Why: A full pipeline audit on 2026-04-03/04-04 rechecked the latest rejected `foreground_frame` against the exact image produced by `_fallback_foreground_frame_asset(...)`. The images were pixel-identical (`ImageChops.difference(...).getbbox() is None`), confirming that the latest rejected artifact was not merely similar to the fallback seed but exactly equal to it. Code inspection then showed why the fallback keeps carrying the same bad read: `_fallback_foreground_frame_asset(...)` builds the bottom band by resizing `_fallback_tile_asset(..., mode='floor')`, which still encodes walk-surface / floor-plane language, and it builds the side masses from full-height wall tiles that read more like framed posts than flat border strips.
- Consequence: The repeated “wrong perspective” failure is partly a fallback-seed design bug, not just a Gemini prompt-compliance bug. Future `foreground_frame` work should stop treating the current fallback seed as a neutral baseline. The fallback seed itself must be redesigned into a true flat border-only atlas, or `foreground_frame_matches_fallback_seed` will keep collapsing diverse live failures into the same wrong-perspective artifact family whenever Gemini echoes that seed exactly.

### 103. `_fit_image_to_size(...)` is not the cause of the recurring `foreground_frame` wall-loss / perspective failure
- Status: Accepted negative finding
- Why: The same audit verified that the latest rejected `foreground_frame` already contained the wall/perspective failure before any downstream room crop, and `_fit_image_to_size(...)` is only doing aspect-ratio-preserving center crop + resize. The rejected artifact and the deterministic fallback seed compare equal at final 1600x1200 resolution, which means the defect is present before any later planner/runtime extraction.
- Consequence: Future debugging should focus on reference construction, fallback-seed design, and generation conditioning. Do not spend more cycles blaming downstream crop windows or final-size fitting for the recurring missing-wall / wrong-perspective failure unless new evidence appears.

### 104. Correcting the fallback seed fixes the deterministic hierarchy, but the live `foreground_frame` path is still returning that seed exactly instead of a distinct candidate
- Status: Accepted diagnosis
- Why: On 2026-04-04, `_fallback_foreground_frame_asset(...)` was rewritten so the seed now teaches a flatter border-only atlas: the bottom strip is a hand-drawn front-facing retaining band instead of a resized floor tile, the wall strips are darkened below the center field, and the center overlay is dimmed so the seed satisfies the border-only test contract again. Deterministic verification now passes (`top > center`, `bottom > center`, `left < center`). A fresh real `generate_biome_pack_visuals(..., component_types=['foreground_frame'])` run still returned `foreground_frame_source_invalid` with only `foreground_frame_matches_fallback_seed`, and direct comparison proved the newest rejected dump is still pixel-identical to the newly corrected fallback seed as well.
- Consequence: The fallback seed is no longer teaching the old floor-plane perspective bug, but the primary blocker has tightened further: the live generation path is still collapsing directly to the deterministic seed instead of producing a new candidate at all. Future work should focus on why the Gemini request is echoing the seed exactly, not on more validator or downstream crop changes.

### 105. The generic center-crop fitter was collapsing distinct raw `foreground_frame` returns into the same normalized chamber frame
- Status: Accepted correction
- Why: A direct experiment on 2026-04-04 sent four live Gemini request variants for `foreground_frame` (`prompt_only`, `prompt_then_guide`, `guide_then_prompt`, `prompt_style_guide`) and saved the raw returned images before fitting. Those raw images were different sizes (`1024x1024`, `1184x864`) and visibly different from one another, but after `_fit_image_to_size(...)` center-cropped them to `1600x1200`, every one of them became pixel-identical to the current fallback seed. This proved the repeated seed-like artifact was being amplified by pipeline normalization, not only by the model.
- Consequence: `foreground_frame` now uses a dedicated fit path that trims edge-connected padding/background and resizes the full returned border image instead of applying the generic center-crop fitter. The fallback-seed detector also now requires equal dimensions, so ad hoc diagnostics no longer report false positives on raw off-size images.

### 106. The `foreground_frame_matches_fallback_seed` gate must evaluate the raw pre-fit candidate, not the post-fit normalized image
- Status: Accepted correction
- Why: Even after the dedicated fitter landed, the live `foreground_frame` branch was still rejecting on `foreground_frame_matches_fallback_seed` because the detector was checking the post-fit staging file, not the raw Gemini return. That conflated genuine model echoing with the pipeline's own normalization step. After preserving the raw staging output and moving the detector to that raw file, the next fresh live reroll no longer matched the fallback seed and finally surfaced a real image failure (`center_intrusion_excessive`).
- Consequence: The pipeline now keeps a transient raw `foreground_frame` candidate alongside the staged fitted image and uses the raw file for fallback-seed detection and attempt tracing. This restores honest failure reporting: the next live reroll after the fix showed a boxed inner-opening / center-fill problem instead of a spurious fallback-seed failure.

### 107. Re-strengthening band cues via the guide/style swatch can regress into a brighter boxed inset opening, so band identity and center openness still have to be balanced together
- Status: Accepted finding
- Why: On 2026-04-04, a follow-up pass increased top/bottom-vs-center contrast in the geometry guide and reintroduced more explicit horizontal band teaching in the style swatch. The next live reroll did not fall back to the deterministic seed, but the exact rejected dump regressed visually into a bright rectangular inset field framed by dark inner posts. Direct visual inspection of `.tmp_biome_generation_rejections/foreground_frame-rejected-latest.png` showed: (1) the center became a nearly flat light gray panel, (2) the top and bottom strips still were not distinct enough from that panel by the validator, and (3) small inward ledge / lip shapes reappeared near the side-wall shoulders.
- Consequence: Future work should keep the raw-pre-fit detector and dedicated fitter, but not continue strengthening band cues by simply brightening the center contrast scaffolding. The next pass should target a darker, subtler center backwall treatment while preserving band readability, otherwise the model tends to flip back into a boxed inset opening.

### 108. Reverting the over-bright band scaffolding improves the boxed-inset regression, but the current blocker remains band-vs-center separation
- Status: Accepted finding
- Why: On 2026-04-04, the brighter guide/style adjustments from the prior pass were rolled back while keeping the dedicated fitter and raw-pre-fit fallback detector in place. The next live reroll produced a darker, less boxy rejected artifact. Direct visual inspection of `.tmp_biome_generation_rejections/foreground_frame-rejected-latest.png` showed: (1) the center returned to a darker, calmer backwall plane instead of a bright inset panel, (2) the side walls stayed flatter and less portal-like than the regressed version, and (3) the top and bottom bands still remained too close in value to the center field to pass distinction checks.
- Consequence: The current best-known direction is the darker-center rollback state, not the brighter band-emphasis state. Future work should keep this calmer center treatment and focus narrowly on strengthening top/bottom strip identity without reintroducing interior lips, a boxed inset opening, or a floor-plane read.

### 109. `used_ai` was under-reporting rejected `foreground_frame` attempts because it only flipped true after promotion, not after successful image generation
- Status: Accepted correction
- Why: On 2026-04-03/04-04, fresh `foreground_frame` reruns returned top-level payloads with `used_ai: false` even when the attempt trace proved Gemini had generated a real staging image and the exact rejected PNG could be visually inspected. Code inspection showed `generate_biome_pack_visuals(...)` only set `used_ai = True` after a candidate passed validation and was moved into the biome template path. That made honest AI-generated-but-rejected attempts look like fallback-only runs in the API response and history event.
- Consequence: `used_ai` now flips true as soon as `_generate_bespoke_component_from_references(...)` returns a real image, even if the candidate is later rejected by `foreground_frame` validation. Future debugging should trust the top-level `used_ai` flag again when distinguishing “Gemini generated a bad image” from “the system never got an AI image at all.”

### 110. A reserved chroma-key center works better than trying to coerce a “perfect calm backwall” for `foreground_frame`
- Status: Accepted pivot
- Why: On 2026-04-04, `foreground_frame` was changed from a “paint a calm center plane” contract to a deterministic chroma-key center contract. The generation guide center was changed to green, the prompt now requires the exact center rectangle to be filled as a green-screen holdout, the fallback seed was updated to reserve the same center, and validation was changed to detect green-screen dominance in the center interior instead of treating a dark center as success. The first live run after this pivot produced a visibly green center but still failed because the border read as a framed opening with tapered side supports and a perspective floor. After tightening the prompt against tapered bases, floor-lip perspective, and black corner voids, a later live reroll finally passed the deterministic source gate and promoted a new saved `foreground_frame.png`.
- Consequence: The keyed-center idea should be kept. It solved the recurring center contamination problem more effectively than repeated “calm center” prompt tweaks. Future work should preserve the chroma-key center contract and focus on the remaining border issues only.

### 111. The current saved keyed-center `foreground_frame` source is structurally closer, but the bottom band still reads like a perspective floor plane by eye
- Status: Accepted visual finding
- Why: After the keyed-center prompt refinements on 2026-04-04, a fresh live reroll passed validation and promoted `art_direction_biomes/ruined-gothic-v1/foreground_frame.png`. Direct visual inspection of that exact saved file showed: (1) the center is now a clean green holdout with no floating fragments, (2) the left and right wall strips are straight and fused to the border instead of freestanding pillar reads, and (3) the top band is continuous and materially coherent. However, the bottom strip still shows a visible top surface and floor-tile perspective, so it reads like a walkable floor plane rather than a pure front-facing retaining band.
- Consequence: This is the best `foreground_frame` source so far, but it is not yet rebuild-worthy under the no-regressions rule. The next pass should preserve the keyed center, straight side walls, and continuous top cap while specifically flattening the bottom band into a true front-facing strip.

### 112. A prompt-only bottom-band flattening pass did not improve the saved source and should not be treated as a successful fix
- Status: Rejected approach
- Why: On 2026-04-04, the `foreground_frame` prompt was tightened with additional bottom-band wording (`retaining wall face`, `no paving stones`, `no trapezoid slab tops`, `no receding tile seams`) while leaving the keyed center and the rest of the pipeline unchanged. Deterministic tests passed, but the next live reroll failed validation with `top_band_not_distinct_from_center` and `bottom_band_not_distinct_from_center`, and no rejected dump path was provided in the result payload. Re-checking the exact saved `art_direction_biomes/ruined-gothic-v1/foreground_frame.png` confirmed the promoted source had not changed visually from the prior keyed-center success case.
- Consequence: The existing saved keyed-center source remains the current best baseline. Future work should not assume that stronger bottom-band wording alone solves the remaining floor-plane read; the next change likely needs a different reference/guide adjustment rather than more prose-only emphasis.

### 113. Adding an explicit bottom-band material strip to the `foreground_frame` style swatch overcorrected and collapsed wall/top-band authority
- Status: Rejected approach
- Why: On 2026-04-04, the full `foreground_frame` pipeline was re-audited after the saved keyed-center source kept showing a perspective floor-plane read. The audit found a real contract mismatch: the geometry guide taught top, sides, bottom, and center, but the style swatch only taught ceiling and wall material, so Gemini had no bottom-band material anchor and kept inventing its own floor semantics. A follow-up implementation added a third front-facing bottom-band material strip to `_write_foreground_frame_style_swatch(...)`. Deterministic tests passed, but the next live reroll failed with `top_band_not_distinct_from_center`, `left_wall_center_transition_weak`, and `bottom_band_not_distinct_from_center`. Direct visual inspection of the exact rejected `.tmp_biome_generation_rejections/foreground_frame-rejected-latest.png` showed: (1) the green keyed center remained clean, (2) the right wall barely survived while the left wall mostly disappeared, and (3) the top band weakened into a thin partial strip. The bottom-plane problem did not improve in a usable way because the whole border shell regressed.
- Consequence: A separate bottom-band material row in the style swatch is not the right next lever. Future work should keep the current saved keyed-center source as the best baseline and avoid broadening the swatch further in a way that dilutes wall/top-band authority.

### 114. Replacing the swatch's live `ceiling_piece` row and then tightening the anti-rim prompt removed the placeholder-like top strip and narrowed the current failure to center intrusion
- Status: Accepted checkpoint
- Why: On 2026-04-04, the top row of `foreground_frame-style.png` was switched away from the live `ceiling_piece.png` and onto a deterministic fallback ceiling sample after direct visual inspection showed the placeholder-like top cap and detached block language were being inherited from the live ceiling asset. A follow-up prompt-only pass then tightened the keyed opening contract: the stone touching the green field must never be lighter than the wall mass, the center must not be framed by a second lighter rectangle, and the bottom boundary may not show a separate top-edge line or coping strip. Deterministic tests passed, and the next live reroll on the same refs no longer failed on top/bottom distinction. Direct visual inspection of the exact rejected `.tmp_biome_generation_rejections/foreground_frame-rejected-latest.png` showed: (1) the top strip is now a fuller continuous masonry band rather than the old placeholder-like cap, (2) the bright inner jamb/rim read is substantially reduced, and (3) the green keyed center stays clean while the side walls remain materially present.
- Consequence: Keep the clean deterministic ceiling row in the style swatch and keep the stronger anti-rim / anti-inner-frame prompt language. The current live blocker is now `center_intrusion_excessive`, so future work should continue from this checkpoint instead of revisiting the old placeholder-top-strip path or broad band-separation tuning.

### 115. Over-specifying the green holdout boundary pixels regresses `foreground_frame` back into a portal-frame / pillar read
- Status: Rejected approach
- Why: On 2026-04-04, the prompt was tightened again to name exact center-boundary pixels like `(224,240)` and `(1375,1079)` and to insist those pixels remain green. Deterministic tests passed, but the next live reroll regressed visually even though the validator only reported `top_band_not_distinct_from_center`. Direct visual inspection of the exact rejected `.tmp_biome_generation_rejections/foreground_frame-rejected-latest.png` showed: (1) the side walls had become full-height column-like posts with base and capital reads, (2) the top band turned into a recessed portal header over the keyed opening, and (3) the whole border read like a framed doorway/window rather than flat outer strips fused to the image border.
- Consequence: Do not continue tightening the prompt with literal coordinate examples for the keyed opening boundary. That wording pushes Gemini toward architectural frame semantics instead of a flat border shell. Keep the earlier anti-rim checkpoint (Decision 114) as the better prompt baseline and treat this latest coordinate-example wording as a regression.

### 116. Structural biome generation must not inherit cross-room room outputs or scenic frozen-concept refs
- Status: Accepted correction
- Why: A full pipeline audit on 2026-04-04 found two upstream authority leaks. First, biome template bootstrap could still scan prior `room_environment_assets/*` room outputs for candidate PNGs, which let structural biome templates inherit stale downstream room artifacts or even mismatched component classes. Second, `generate_biome_pack_visuals(...)` appended `direction.frozen_concepts` to every biome component request, which meant structural templates like `foreground_frame`, `wall_piece`, and `ceiling_piece` could still inherit scene-scale concept composition and depth cues before any validator ran.
- Consequence: Structural biome template bootstrap now skips curated cross-room sources entirely and falls back to deterministic seeds instead of old room outputs. `generate_biome_pack_visuals(...)` now resolves frozen concept refs per component: structural biome components receive none, while scenic biome components use the biome pack's `locked_concept_ids` (falling back to direction-level frozen ids only when the pack has none). This establishes a cleaner authority chain before further slot-ownership or validator work.

### 117. Production shell slots now use component-specific structural sources, and `foreground_frame` is diagnostic-only
- Status: Accepted correction
- Why: The core architectural defect was that `foreground_frame` acted as the production source for ceiling, walls, trims, and floor shell slots in both v2 and v3 planners. That overloaded one shared atlas and made small semantic mistakes propagate everywhere as posts, portal headers, and floor-plane reads.
- Consequence: Shell-slot ownership is now explicit and component-specific across the environment pipeline: `ceiling_band -> ceiling_piece`, `wall_module_*` and `wall_base_trim_* -> wall_piece`, `main_floor_top`, `main_floor_face`, and `pit_rim -> primary_floor_piece`, and hero-platform slots remain on `hero_platform_piece`. `foreground_frame` remains in the biome pack for diagnostic/review use only and is no longer a production shell slicing source. Structural biome sibling-reference priority was also updated so production structural pieces no longer use `foreground_frame` as an anchor.

### 118. Structural review now starts from source assets and derived shell crops, and runtime acceptance requires browser-backed capture
- Status: Accepted correction
- Why: Prior review could skip directly to runtime screenshots, and composite fallback output could still be treated as usable acceptance evidence. That made it too easy to miss source-stage structural drift and too hard to diagnose whether failures were in source generation or runtime composition.
- Consequence: `generate_room_environment_asset_pack(...)` now emits a `structural_review_bundle` containing exact source PNGs (`wall_piece`, `ceiling_piece`, `primary_floor_piece`, `hero_platform_piece`, plus diagnostic `foreground_frame`) and a deterministic contact sheet of representative derived shell assets. Runtime review now fails with `browser_capture_required` whenever capture falls back to non-browser modes, so composite fallback remains debug-only and cannot satisfy pass/fail acceptance.

### 119. Structural validation is now component-specific and checks cross-part family coherence instead of overloading `foreground_frame` as the shell proxy
- Status: Accepted correction
- Why: The old quality gate relied too heavily on `foreground_frame` and did not test the actual recurring failure classes on the individual structural pieces. That let placeholder headers, floor-plane reads, or opening/recess wall language slip through until runtime review.
- Consequence: `wall_piece`, `ceiling_piece`, and `primary_floor_piece` now have dedicated validators and retry prompts, and the biome pass also checks a cross-component structural-family contract for palette/value drift across wall, ceiling, and floor sources. `foreground_frame` validation remains in place for its diagnostic keyed-atlas role, but it is no longer the proxy validator for the whole shell kit.

### 120. Structural shell rendering now uses a normalized material basis before deriving room-fit wall/ceiling/floor pieces
- Status: Accepted calibration step
- Why: After the slot-ownership remap landed, the runtime shell still looked overtly procedural and was also inheriting bad semantics from the current ruined-gothic structural source art (`wall_piece` still read like an opening, `ceiling_piece` still carried header/floating-block language, and `primary_floor_piece` still implied a perspective lip). The derived shell pieces needed a cleaner intermediate material basis without reverting to `foreground_frame`.
- Consequence: Synthetic shell rendering now normalizes `wall_piece`, `ceiling_piece`, and `primary_floor_piece` into deterministic structural material sources based on the source palette before generating `wall_module_*`, `ceiling_band`, `main_floor_*`, and `pit_rim`. A low-opacity texture wash from that normalized basis is then blended into the final shell piece so the runtime output stays aligned to the structural family while avoiding direct reuse of the broken source semantics.

### 121. Phase 1 of the border-first reset is schema-only and must not create authoritative shell assets yet
- Status: Accepted checkpoint
- Why: On 2026-04-04, the new border-first contract was introduced in parallel with the old environment path instead of replacing it in place. The biome pack now carries a `border_first_contract` with canonical shell template `border_piece`, new biome component types (`border_piece`, `background_far_piece`, `background_mid_piece`, `platform_piece`, `door_piece`), and planned room asset types (`room_border_shell`, `room_background`, `room_platforms`, `room_doors`). However, this Phase 1 slice intentionally leaves the old runtime assembly untouched and marks the new contract as non-authoritative while the new biome templates are still pending generation.
- Consequence: Treat the new border-first schema and manifest fields as migration scaffolding only until the new biome templates are visually valid. QA passed this slice only because it was additive, test-backed, and did not force placeholder files or a runtime swap.

### 122. Phase 2 plumbing for border-first biome generation is real, but the first ruined-gothic outputs are not valid biome templates
- Status: Accepted failure checkpoint
- Why: On 2026-04-04, the new biome-generation path for `border_piece`, `background_far_piece`, `background_mid_piece`, and `platform_piece` was implemented and all targeted tests passed (`103` Python tests plus both JS suites). A real ruined-gothic generation run then produced exact saved artifacts for those four component types. Direct visual inspection of the exact files showed the path is not founder-review-ready yet: (1) `art_direction_biomes/ruined-gothic-v1/border_piece.png` is a finished pointed-arch chamber illustration with a built-in floor slab, rubble, fog, and visible matte padding rather than a generic reusable border template, (2) `.tmp_biome_generation_rejections/border_piece-rejected-latest.png` is actually closer to the intended border contract than the accepted saved border, which means the validator/promoter is selecting the wrong artifact class, (3) `background_far_piece.png` is a composed graveyard/bridge vista with statues, stairs, and white letterbox bars, (4) `background_mid_piece.png` is a full scene slice with stairs, platforms, arches, and a candle focal point, and (5) only `platform_piece.png` is roughly on-contract, though still weak and somewhat placeholder-like.
- Consequence: Phase 2 is an engineering checkpoint only. Do not advance to border-first room generation from these saved biome templates. The next corrective slice must remove legacy split-shell asset contamination from the new reference path, delete the duplicate `border_piece` guide attachment, and add semantic validators for `border_piece`, `background_far_piece`, and `background_mid_piece` that reject scenic room illustrations, matte padding, portal-frame borders, and layout-specific compositions.

### 123. Narrowing Phase 2 to `border_piece`, `background_far_piece`, and `platform_piece` improved artifact class, but promotion still prefers the wrong `border_piece`
- Status: Accepted correction checkpoint
- Why: After founder validation on 2026-04-04 marked `border_piece` as over-detailed, `background_far_piece` as potentially usable only if faded, `background_mid_piece` as unnecessary for now, and `platform_piece` as bad, the active border-first contract was narrowed to `border_piece`, `background_far_piece`, `platform_piece`, and `door_piece`. The corrective pass then: (1) removed `background_mid_piece` from the active contract constants, pending-template set, and manifest exposure, (2) removed legacy split-shell references from the new `border_piece`, `background_far_piece`, and `platform_piece` generation paths, (3) deleted the duplicate `border_piece` guide definition / duplicate guide attachment, (4) tightened the prompts around border geometry, far-background genericity, and simple platform behavior, (5) added semantic validators for `background_far_piece` and `platform_piece`, and (6) added trim-based matte cleanup for the new border-first biome templates before promotion. The exact regenerated artifacts showed mixed results: `.tmp_biome_generation_rejections/border_piece-rejected-latest.png` became a flatter rectangular shell with calmer center and simpler side masses, `background_far_piece.png` lost its white letterbox bars and cooled down materially, and `platform_piece.png` became simpler with less warm trim. However, the accepted saved `border_piece.png` still remained an ornate pointed-arch frame with built-in floor slab, rubble, foreground steps, and matte padding, while the rejected candidate was visibly closer to the intended generic border contract.
- Consequence: Keep the narrowed scope and the new prompt/reference/validator changes, but do not treat Phase 2 as visually complete. The next Phase 2 fix must target border-piece selection/promotion itself, because the pipeline is still choosing the wrong border artifact class even after the geometry contract improved. `background_far_piece` also still needs stricter anti-composition gating against centered bridges, bilateral stairs, and hero-vista composition. QA reviewed this checkpoint and again marked it engineering-only rather than founder-ready.

### 124. Tightening `border_piece` side-wall straightness reduced wall flare, but pushing that constraint too hard turns the center into a torn breach
- Status: Rejected approach
- Why: On 2026-04-04, the `border_piece` prompt was tightened again to require constant wall-strip thickness, square top/bottom wall corners, and no corbel or pedestal flare. The border validator was also strengthened with a geometry-based side-wall boundary check in addition to the earlier luminance-based flare guard. Deterministic tests passed (`105` Python tests plus both JS suites), and a fresh real `border_piece` reroll was generated. Direct visual inspection of the exact rejected `.tmp_biome_generation_rejections/border_piece-rejected-latest.png` showed that the top/bottom wall flare did improve, but Gemini overcorrected by turning the center into one large jagged torn-plaster / broken-hole shape. QA independently reviewed that same exact rejected PNG and agreed: the side walls are straighter, but the image now reads like a breached wall opening instead of a reusable border template.
- Consequence: Keep the stronger straight-wall contract and the new flare validator, but do not continue tightening straightness alone. The next `border_piece` pass must explicitly suppress torn-hole / shattered-opening semantics in the center while preserving the improved vertical wall silhouette.

### 127. Room semantics extraction should be a derived sidecar contract, not a second room-authority model
- Status: Accepted
- Why: The room JSON remains the source of truth for geometry, traversal, and room identity, while the new semantics layer is only meant to classify and expose what the room already contains. Treating semantics as another authority would create drift between `room-layout-data.json`, v3 overlays, and QA review surfaces.
- Consequence: `room_semantics.json` should be generated from the room payload and used as a derived review artifact. It must preserve the source room polygon, doors, platforms, moving-platform paths, edge links, and removed edges verbatim, while adding tops, undersides, vertical faces, shell surfaces, openings, corners, cavities, decor-safe zones, gameplay exclusion zones, anchors, and overlay geometry for QA and planner truth checks. Future agents should not invent alternate room geometry from this sidecar.

### 125. MVP adaptation QA gate uses blocker/warning/info severity and requires browser-backed evidence for saved-artifact approval
- Status: Accepted gate posture
- Why: The MVP adaptation plan needs a release-ready QA contract that lines up with the v3 requirements without letting composite fallback, DOM-only checks, or unlabeled screenshots pass as approval evidence. The existing room-validation pattern already rolls up to `pass / warning / fail`, so the MVP gate should keep the same spirit while naming the triage levels more explicitly for the new regression plan.
- Consequence: For the MVP adaptation, `validation_report.json` should roll up `blocker -> fail`, `warning -> warning`, and `info -> pass metadata only`. Browser-backed E2E is required for approval evidence, and any positive visual claim must cite the exact saved artifact with at least three concrete visible observations. Composite fallback remains debug-only and cannot satisfy rollout signoff.

### 126. Staged v3 environment MVP — docs + `scripts/environment_v3/` package scaffold
- Status: Accepted (2026-04-04)
- Why: The founder plan locks a **references → stylepack → semantics → kit → compose → validate** pipeline while keeping the room editor and `environment_pipeline_version = "v3"` gate. Milestone 1 maps the current `/environment/*` HTTP flow to that model, defines on-disk derived artifacts under `room_environment_derived/{room_id}/`, and specifies the results-panel payload extensions without a new workspace.
- Consequence: Implementation proceeds incrementally; `scripts/room_environment_v3.py` stays the compatibility bridge until modules move into `scripts/environment_v3/`. Legacy v3 fields and `generate-assets` remain until ENV-028/ENV-029 deprecations are explicit. Authoring docs: `docs/room-environment-pipeline-mvp/`.

### 127. The MVP results surface should keep authoring controls visible beside the staged output, not bury them inside the summaries
- Status: Accepted
- Why: The room editor needs the user-facing inputs that affect the environment review loop - reference upload, theme name, notes, seed, and stylepack lock - visible while the generated summaries update. A single collapsed "environment summary" card would force authors to hunt for inputs and would blur the line between author intent and generated evidence.
- Consequence: The results surface now uses a persistent authoring column for those controls, while the staged summaries remain read-only review cards.

### 128. Results-stage ordering is fixed, and debug/layer toggles stay secondary and UI-only
- Status: Accepted
- Why: The review loop should stay aligned with the pipeline order and with QA expectations. The stable sequence is stylepack, semantics, kit, manifest, validation. Overlay toggles are useful diagnostics, but they are not part of the authored room payload and should never outrank the review cards.
- Consequence: The Results surface must keep that order and treat debug/layer switches as local view state rather than exported room data.

### 129. `room.environment.spec` is the canonical home for the MVP authoring fields
- Status: Accepted
- Why: Theme name, notes, seed, lock stylepack, and reference uploads are authoring metadata that should survive export with the rest of the room environment spec. Putting them into preview/runtime slices would leak them into generated state and make the contract harder to reason about.
- Consequence: The MVP contract stores those fields in `room.environment.spec`, while `preview`, `runtime`, `assembly_plan`, and `review_state` stay reserved for generated or review-derived data.

### 130. Room semantics v1 now exposes moving-platform tops, edge-link openings, and overlay truth metadata as a derived sidecar
- Status: Accepted
- Why: The MVP semantics slice needed to stay geometry-first while still giving the editor and QA more than a flat count summary. Moving platforms are part of the room-local traversal surface, and edge-link / removed-edge openings must stay visible on the polygon boundary rather than collapsing into generic room shape.
- Consequence: `derive_room_semantics(...)` now emits richer per-room semantics with structured tops, undersides, openings, corners, cavities, decor-safe zones, gameplay exclusion zones, anchors, overlay geometry, and truth checks. `build_results_payload(...)` now forwards the semantics overlay and truth metadata so the Results surface can inspect the same sidecar truth instead of reconstructing it ad hoc.

### 131. Environment kit v1 now carries explicit MVP taxonomy metadata and deterministic structural counts
- Status: Accepted
- Why: The next MVP slice needed the kit artifact to do more than mirror planner slots. QA required stable taxonomy boundaries and deterministic counts across structural, background, and decor classes before this stage could be treated as trustworthy.
- Consequence: `build_environment_kit(...)` now emits explicit component taxonomy metadata (`component_class`, `allowed_surfaces`, `allowed_zones`, `readability_impact`, provenance, and `component_count_by_type`) plus validation errors for malformed entries. The editor payload now forwards those kit counts/errors, and regression tests assert taxonomy boundaries, deterministic output, and alignment between kit summary counts and manifest layer counts.

### 132. Environment composition v1 uses explicit pass precedence and deterministic manifest replay metadata
- Status: Accepted
- Why: The initial MVP composition bridge was too thin: it trusted incoming planner order, treated only literal `background` slots as background, and provided too little manifest evidence for QA to verify pass precedence or deterministic replay. That left `midground` vulnerable to being misclassified as decor and made same-input replay harder to prove.
- Consequence: `build_environment_manifest(...)` now normalizes placements by explicit pass precedence (`structural -> background -> decor`), classifies `midground` with the background pass, records pass summaries and layer order in the manifest, and emits deterministic replay metadata (`plan_fingerprint`, `replay_key`, ordering rule). The editor payload now surfaces those manifest pass/replay details, and regression coverage includes pass-order, deterministic replay, payload exposure, and persistence round-trip checks.

### 133. Validation v1 must be a structured severity report and keep visual review honest
- Status: Accepted
- Why: The MVP validation slice needs to distinguish hard geometry failures from softer readability concerns, and the editor payload contract already expects structured findings rather than flat strings. At the same time, the visual-honesty gate means code-only validation cannot pretend to have judged final visual quality without screenshot-backed review evidence.
- Consequence: `build_validation_report(...)` now emits structured findings with `severity`, `code`, `message`, and optional refs; summary counts; unresolved-surface reporting; and `validation_highlights` for geometry refs. Geometry blockers now cover unresolved planner coverage, out-of-bounds placements, wrong-surface decor, opening obstruction, and gameplay-zone intrusion; readability/system findings stay separate; and visual validation remains an info-level reminder unless a runtime screenshot is actually present.

### 134. Results toggles must drive an in-panel overlay view, not just rewrite summary chips
- Status: Accepted
- Why: The Results panel already exposed structural/background/decor and debug toggles, but they only changed summary text. That made the workbench feel inert and blocked meaningful browser validation even when the staged payload was correct.
- Consequence: The Results surface now includes a dedicated overlay card that renders the room shell, manifest placements, semantics geometry, safe/exclusion zones, and validation/unresolved highlights from the persisted v3 artifacts. The existing toggles remain UI-local state, but they now control visible overlay layers and should be extended through this panel rather than adding more no-op chips.

### 135. Overlay controls belong inside the Overlay View card, and decor must degrade honestly when no decor placements exist
- Status: Accepted
- Why: The first overlay slice left the toggle controls in the Results workbench strip, which made them feel disconnected from the visualization they controlled. Live browser feedback also showed that the `Decor` toggle could appear broken when the current v3 manifest emitted no `layers.decor` placements even though room-level set-dressing intent existed in the spec.
- Consequence: The Results overlay now owns the layer/debug toggle controls directly, so the UI reads as one diagnostic surface. The overlay renderer also falls back to showing planned decor markers from `room.environment.spec.scene_schema.set_dressing` when the manifest decor layer is empty, while still keeping real decor placements authoritative when they exist. Future work should treat this as a stopgap until the v3 planner emits true decor placements where needed.

### 136. Milestone 1 evidence must run through repo `pytest`, with tests scoped to `tests/` and `*.test.py` imported via `importlib`
- Status: Accepted
- Why: On 2026-04-05 the environment MVP evidence existed, but the standard Python runner was not trustworthy. `pytest` could not collect `tests/environment_v3_package.test.py` or `tests/room_environment_system.test.py` under the default import mode because the dotted filenames were interpreted as module names, and a bare repo run also wandered into vendored `tools/ComfyUI` tests that require unavailable third-party dependencies.
- Consequence: The repo now carries a top-level `pytest.ini` that scopes collection to `tests/`, includes both `test_*.py` and `*.test.py`, and enables `--import-mode=importlib`. Milestone 1 evidence should be cited from `python3 -m pytest tests/environment_v3_package.test.py tests/room_environment_system.test.py -q` and repo health from `python3 -m pytest tests -q`, not from ad hoc direct-file invocations or third-party vendored test trees.

### 137. Embedded Results-tab browser state coverage now uses a local QA hook plus a Chrome capture harness
- Status: Accepted
- Why: By 2026-04-05, the Results surface contract and state vocabulary existed in code, but browser-backed QA of `empty`, `draft`, `locked`, `generating`, `partial`, `ready`, and `blocked` was still manual and easy to drift. External DevTools evaluation could not drive the room editor directly because its `state` and wizard helpers live inside the page script scope rather than on `window`.
- Consequence: `room-layout-editor.html` now exposes a narrow `window.__ROOM_WIZARD_QA__` hook for test-only state injection of the embedded Results tab, and `scripts/capture_room_results_states.js` drives headless Chrome to save a seven-state screenshot bundle under `artifacts/qa/room-results-states/`. These captures are valid for Milestone 5 UI-state coverage, but they are synthetic Results-state evidence only and must not be confused with real runtime-approval artifacts.

### 138. The saved ruined-gothic calibration runtime screenshots remain blocked evidence, not approval evidence
- Status: Accepted correction
- Why: On 2026-04-05, direct visual inspection of the exact saved runtime-review artifacts for `RG-R1`, `RG-R2`, and `RG-R3` in `ruined-gothic-calibration-gemini-20260402` showed that real runtime screenshots do exist on disk, but the center-fog / weak shell-definition problem remains visibly unresolved. The paired saved summary file still marks all three rooms as `failed` with `runtime_review: blocked`.
- Consequence: Future agents should treat those saved screenshots as Milestone 4 blocked-state evidence, not as approval or founder-packet artifacts. The rooms still need real runtime composition improvement before any positive signoff claim, even though a browser-backed screenshot file is present.

### 139. Runtime browser capture now defaults on when a headless browser is available; composite fallback is explicit opt-out only
- Status: Accepted correction
- Why: On 2026-04-05, inspection of the current ruined-gothic calibration project showed that the saved room JSON state had already moved past old door-transparency failures and now primarily carried `browser_capture_required`. The remaining blocker was not a missing wrapper-page implementation; it was that `_capture_runtime_review_screenshot(...)` still defaulted to composite fallback unless `ROOM_ENVIRONMENT_REVIEW_USE_BROWSER` was explicitly enabled, even on a machine with Chrome installed.
- Consequence: Runtime review now attempts real headless-browser capture by default whenever a compatible browser is available. Composite fallback remains available when browser capture is explicitly disabled (`ROOM_ENVIRONMENT_REVIEW_USE_BROWSER=false`) or when no browser is available. Future calibration reruns on this machine should therefore produce real browser-backed runtime screenshots unless they fail for a narrower capture reason.

### 140. Runtime review capture now uses a CDP helper that waits for the embedded preview to reach `| live` before saving the PNG
- Status: Accepted correction
- Why: After the browser-default change, direct inspection showed that the repo-root game preview could still save an almost-black or missing frame when Chrome's raw `--screenshot` path ran from Python. A narrower probe proved the preview iframe itself was healthy and reached `window.__ASHEN_HOLLOW_BOOT_STATE = "... | live"`, so the unstable part was the screenshot mechanism, not the room boot sequence.
- Consequence: Runtime review now prefers `scripts/capture_runtime_review.js`, which launches headless Chrome over CDP, waits for the wrapper iframe preview to report `| live` with no boot error, and only then captures the screenshot. The old raw Chrome `--screenshot` command remains as fallback when `node` or the helper is unavailable. Future agents should treat this helper as the authoritative browser-capture path for Milestone 4 evidence.

### 141. The current ruined-gothic runtime screenshots are now valid browser-backed evidence, and the remaining failures are visual/readability failures rather than capture failures
- Status: Accepted correction
- Why: On 2026-04-05, a fresh rerun of `RG-R1`, `RG-R2`, and `RG-R3` through `_run_runtime_review(...)` produced `review_mode: headless_browser` for all three rooms. Direct inspection of the exact saved `runtime-review.png` files showed that the artifacts are no longer composite placeholders, but they still visibly fail for shell readability, top-occlusion, platform-top, and threshold-read reasons depending on the room.
- Consequence: Milestone 4 is no longer blocked on `browser_capture_required` for this calibration set. The remaining blocker is improving the actual runtime composition and framing in the exact saved browser screenshots. Founder-facing or approval claims must now discuss the specific visual/readability failures visible in those PNGs, not generic capture plumbing.

### 142. Real calibration-room Results-tab captures prove the surface is contract-bearing and reviewable, but too tall for efficient repeated review
- Status: Accepted correction
- Why: On 2026-04-05, direct browser capture of the ruined-gothic calibration project through `room-layout-editor.html?project_id=...` produced real `Results` screenshots for `RG-R1`, `RG-R2`, and `RG-R3`, not just synthetic state fixtures. Visual inspection showed real preview images, validation findings, overlay content, and asset galleries on all three rooms. The same captures also showed the panel remains several screen-heights tall, especially for rooms with tall overlay geometry.
- Consequence: Future agents should not dismiss the embedded `Results` surface as fake or useless. Milestones 2, 3, and 5 already have meaningful implementation behind this panel. The next leverage point is compressing the Results composition toward the approved bounded-panel mockup, not re-litigating whether the surface should exist.

### 143. Bounding the Results summary beside the preview/gallery is a valid direction for Milestone 5 because it improves review efficiency without discarding staged evidence
- Status: Accepted
- Why: After the first real calibration-room `Results` captures proved the surface was functional but overly long, a narrow composition pass on 2026-04-05 kept the same stage data and card order while placing the dense review summary in a bounded pane beside the preview/gallery area on large screens. The next capture pass reduced ruined-gothic calibration page heights from roughly `7.6k–8.8k` pixels down to `5.6k–5.8k` pixels and made the preview plus validation comparison materially easier to scan in the exact saved artifacts.
- Consequence: Future Milestone 5 work should continue optimizing Results-tab composition through bounded layout and information hierarchy rather than removing stage content. The approved direction is “same contract, tighter presentation,” not “replace the Results tab with a new dashboard” and not “flatten everything into one long debug scroll.”

### 144. Client-uploaded debug reference images for room preview are removed
- Status: Accepted (2026-04-06)
- Why: Interim “upload reference art for preview” was a bridge until project frozen concepts and per-biome `locked_concept_ids` drove previews; keeping it splits the art-direction contract and invites ad-hoc payloads.
- Consequence: `generate_room_environment_previews` no longer accepts `debug_preview_reference_images`; Gemini level-3 preview uses layout conditioning plus resolved frozen concept files only. `preview.scene_plan` no longer includes `debug_preview_reference_count`. Room wizard Describe UI drops the debug file control.

### 145. Playtest must not skip bespoke wall shell when the room polygon fills the footprint (zero polygon wall rects)
- Status: Accepted (2026-04-05)
- Why: `applyRuntimeLayoutData` rebuilds `DUNGEON_WALL_RECTS` for every room with a polygon. A rectangle that covers the full room has no “outside polygon” cells, so `buildWallRectsFromPolygon` returns an empty `rects` array. The old gate treated “listed in `DUNGEON_WALL_RECTS`” as “use procedural rects only,” which skipped `addRoomBespokeWallShellDecor` and placed no procedural tiles either — invisible walls in editor-driven playtest.
- Consequence: `buildWorldGeometry` gates bespoke wall shell on `roomHasPolygonWallTileRects(roomId)` (non-empty rects) rather than mere membership. `addRoomBespokeWallShellDecor` returns false when wall slots exist but neither bespoke sprites nor flanking AI mass actually placed, so the outer `addRoomWallMassDecor` fallback can run.

### 146. Wall mass/body decor must fall back to procedural surface textures when `wall_body_strip` is absent
- Status: Accepted (2026-04-05)
- Why: `resolveRoomWallBodyTexture` returned null unless a 512×512 AI `wall_body_strip` loaded. `addRoomWallMassDecor` / `addRoomWallBodyDecor` then skipped, so rooms without a ready asset pack had no flanking mass and (combined with empty polygon rects) could show no walls at all. Procedural `env-surface-wall-*` tiles are always generated in `preload`.
- Consequence: After the AI strip check fails, use `roomSurfaceTextureKey(roomId, 'wall', 0)` when the texture exists. TileSprite scaling uses the texture frame size (32 vs 512) via `applyWallStripTileScaleFromTexture`. Layout rooms with a footprint polygon also set `emphasizeWalls` so procedural wall *tiles* are not stuck at ~12% alpha before bespoke completes.

### 147. Bespoke wall shell width must fill half the chamber on wide footprints (camera-centered playtest)
- Status: Superseded (2026-04-05) — see **#149**
- Why: Runtime review placed wall modules using `min(max(placement, 16% chamber), 50% chamber)` but typical `placement.display_width` (~320px) capped the strip to a few hundred pixels. On chambers much wider than the viewport (~800px), those strips stay at the polygon left/right edges while the camera follows the player mid-room — textures load and depth is correct, but **nothing wall-like appears in frame** (confirmed in founder playtest screenshot: floor + mid-distance fog, no side shells).
- Consequence (original): When `chamberWidth >= max(520, 0.85 * CONFIG.W)`, set bespoke shell `display_width` to **50% of chamber width** so left and right modules abut at the horizontal center.

### 149. Do not use 50/50 chamber split for bespoke wall shells (wallpaper artifact)
- Status: Accepted (2026-04-05)
- Why: Two half-chamber `Image` strips meeting at center **cover the entire footprint** with stretched wall art; the texture reads as a repeating masonry grid and a hard vertical seam at mid-room (“everywhere is wall”). That was a readability overcorrection to decision **#147**.
- Consequence: Rejected the 50/50 meet-at-center approach. Interim `wideStripCap` widening was tried next; **horizontal width policy is now #150** (authored scale + clamp), not viewport fractions.

### 150. Bespoke wall shell width must track authored asset/plan scale (not widened to “fill view”)
- Status: Accepted (2026-04-05)
- Why: Follow-on playtest showed wall modules stretched to hundreds of pixels wide (`wideStripCap` / chamber fractions), so each brick read enormous versus floor/ceiling strips. The pipeline already authors `placement.display_width`, `final_dimensions`, and `generation_plan.target_dimensions` for wall modules — runtime should respect that horizontal scale.
- Consequence: `addRoomBespokeWallShellDecor` sets `accentWidth` from `placement` → `final_dimensions` → plan `target_dimensions`, with fallback `max(200, planW || 14% chamber)`, clamped to `[96, min(50% chamber, 26% chamber)]`. Removed `wideChamber` / `wideStripCap` widening.

### 151. Bespoke wall shell height must not default to full chamber (vertical brick megascale)
- Status: Accepted (2026-04-05)
- Why: Runtime used `max(placement.display_height, chamber height)`, forcing every wall image to stretch to the full polygon vertical span. That made each masonry course enormous in frame (“pillar of giant blocks”) even when horizontal width matched authoring.
- Consequence: `display_height` follows `placement` / `final_dimensions` / plan `target_dimensions`, fallback `max(320, planH || 72% chamber)`, clamped to `[200, chamberH]`. Shell is **bottom-aligned** (`origin_y: 1`, `y: chamberBottom`) so it sits on the floor plane like floor strips.

### 152. Bespoke wall shell: cap display size to loaded texture pixels; skip in-shell flanking mass when wall modules exist
- Status: Accepted (2026-04-05)
- Why: Manifest `final_dimensions` / placement often still match **full chamber** height (~1100px), so clamping to `chamberH` alone does not reduce vertical stretch versus the actual raster (e.g. 320×640 source). Separately, **`addRoomWallMassDecor` flanking strips** beside the footprint polygon can span **hundreds to thousands of pixels** of repeating TileSprite masonry while bespoke `wall_module_*` images also place — the flanking layer often **dominates** the playtest read (“pillar” / full-screen wall) even when bespoke scale logic is correct.
- Consequence: After computing `accentWidth` / `accentHeight`, further cap both to `ceil(nativeFrame × 1.25)` via `getEnvBespokeTextureFrameSize` (read from the loaded `env-bespoke-${slot_id}` texture), then re-clamp to `capW` / `chamberH`. When `getRoomEnvironmentBespokeWallShellAssets` returns any wall assets, **do not** place left/right flanking mass inside `addRoomBespokeWallShellDecor`; `buildWorldGeometry` still runs procedural mass fallback if bespoke placement fails entirely.

### 153. Bespoke wall shell display width must stay narrow (absolute + chamber cap, no horizontal upscale)
- Status: Accepted (2026-04-05)
- Why: Follow-on playtest still read wall modules as **very wide**: `capW` allowed up to **26% of chamber width** (hundreds of world pixels on wide footprints), and `1.25×` native **width** still upscaled wide source frames. The no-`roomBounds` fallback path also used raw manifest `display_width`.
- Consequence: `capW = min(50% chamber, 14% chamber, 272px)`; texture cap uses **`WALL_ART_MAX_SCALE_W = 1`** (no horizontal upscale past native frame width) while height keeps `1.25×`. Fallback branch clamps `display_width`/`display_height` the same way (272 / native w, height ≤ `1.25×` native, max 800).

### 154. Side wall shell anchors must be boundary-flush (left shell right-edge on left boundary)
- Status: Accepted (2026-04-06)
- Why: Visual inspection of the exact playtest screenshot showed the left shell intruding into the room because it was anchored with `origin_x: 0` at `chamberBounds.left`. That makes its **left** edge flush, not its **right** edge.
- Consequence: In `addRoomBespokeWallShellDecor`, left shells now use `origin_x: 1` and `x = chamberBounds.left`; right shells use `origin_x: 0` and `x = chamberBounds.right`. This keeps side shells flush with room boundaries instead of drifting inward.

### 155. Primary floor decor must span chamber bounds and sit on the boundary seam
- Status: Accepted (2026-04-06)
- Why: Follow-on playtest showed floor/wall seams misaligned: primary floor cap used authored platform `x/len`, so it could stop short of side walls, and its top seam could drift off the polygon boundary line.
- Consequence: In `buildWorldGeometry` primary-floor path, floor decor now uses `primaryFloorLocalLeft = chamberLeft`, `primaryFloorWidth = chamberRight - chamberLeft`, `primaryFloorY = chamberBottom`, and `addRoomFloorCapDecor(... primaryFloorX, primaryFloorY, primaryFloorWidth ...)`. This makes floor meet both side walls and keeps floor top flush with room boundary.

### 156. Primary floor collision must align with the same chamber seam as floor decor
- Status: Accepted (2026-04-06)
- Why: Visual pass after #155 showed the player still standing on a higher/lower invisible strip because physics tiles for the primary floor were still emitted from authored platform `x/y/len` in the `ROOM_PLATFORM_LAYOUTS` loop.
- Consequence: For `isPrimaryFloor`, collision tiles now use chamber bounds (`collisionLeft = roomBounds.start + chamberLeft`, width `chamberRight - chamberLeft`) and `y = chamberBottom`. This keeps player feet flush with the visible floor seam.

### 157. Primary-floor collision gate must not depend on legacy authored `y`
- Status: Accepted (2026-04-06)
- Why: After #156, mismatch persisted because `isPrimaryFloor` still required `primaryFloorPlatform.y === ledge.y`; once seam moved to `chamberBottom`, that strict equality can fail and the chamber-bottom collision branch is skipped.
- Consequence: `isPrimaryFloor` now keys on room-local start `x` and `len` only (no `y` equality), ensuring the chamber-bottom collision row is applied for the primary floor strip.

### 158. Walk plane must follow the primary floor platform row (polygon bottom can differ)
- Status: Accepted (2026-04-06)
- Why: In footprint polygons, `bottom` can sit **below** the authored primary floor platform row (e.g. polygon bottom 1040 vs platform `y` 992). Using `polygonBounds.bottom` alone for floor cap, collision, and wall foot (#155–#157) desynced visuals from physics and left large gaps between wall, floor art, and walk surface.
- Consequence: `getPrimaryFloorTileCenterY` / `getRoomWalkPlaneTopY` define the seam; primary floor cap and collision use `primaryFloorTileCenterY`; bespoke wall shell foot uses `walkPlaneTopY` on `support`; outer mass height uses `primaryFloorTileCenterY` when a primary floor exists.

### 159. Bespoke side shell width must cover polygon inset when flanking is off
- Status: Accepted (2026-04-06)
- Why: With `wall_module_*` assets, flanking TileSprites are skipped to avoid giant margin pillars. `accentW` was capped at **272px** while polygon **chamber left** inset can be larger — the shell’s right edge stays at the chamber but its left edge stops short of the room edge, leaving a visible **black strip** at the viewport edge.
- Consequence: After `capW`, left shell width is `max(accentW, marginLeft)` and right shell `max(accentW, marginRight)`, each clamped to `maxHalf` (half chamber width).

### 160. Floor row and floor cap must follow layout polygon bottom (supersedes #158 floor line)
- Status: Accepted (2026-04-06)
- Why: The footprint polygon’s **`bottom`** is the layout contract for the **bottom edge of the floor tile row**. Driving the seam from **authored platform `y`** alone (or mixed cap origins) left the **floor component** visually off the room’s floor line; the player should match automatically once **physics** and **cap top** share the same **walk surface** (`polygon bottom − 32` for top of 32px tiles, `bottom − 16` for tile center).
- Consequence: `getLayoutFloorTileCenterY` uses `polygonBounds.bottom - 16` when a polygon exists; primary-floor physics, wall foot, and cap use that row. `addRoomFloorCapDecor` anchors at **`walkTop = y − 16`** with **`origin (0.5, 0)`** so the cap’s **top** is flush with the **top of the floor tiles**. Replaces #158’s “primary platform row vs polygon bottom” approach for the floor line.

### 161. Gemini key loading and diagnostics for bespoke generation failures
- Status: Accepted (2026-04-06)
- Why: `load_repo_env_local()` only applied `.env.local` when a key was **missing** from `os.environ`, so a **shell-exported empty `GEMINI_API_KEY`** blocked loading the real key from the file. Image generation also only read `GEMINI_API_KEY`, not `GOOGLE_API_KEY` (AI Studio default). `_gemini_generate_content_rest` swallowed HTTP/API errors, making `generation_failed` look mysterious in the UI.
- Consequence: `.env.local` overlays **empty** env values; `_gemini_api_key()` falls back to `GOOGLE_API_KEY`; failed Gemini calls log **HTTP status + JSON error body** (no key material) at WARNING.

### 162. Surface Gemini image failures and clarify “runtime blocked” when slots did not generate
- Status: Accepted (2026-04-06)
- Why: `/api/ping` only exposed key presence; bespoke failures stored `gemini_error` on attempts but the editor did not show it; `runtime_review.status: blocked` with `slot_generation_failed` was easy to read as screenshot QA failure.
- Consequence: `_gemini_generate_content_rest` records a user-safe last error for ping; `GET /api/ping` includes `lastGeminiImageError`, `geminiImageModel`, `geminiTextModel`, and optional `?probe=1` runs `gemini_image_probe()`; build summary shows `gemini_error` and clearer copy for slot-generation blocks.

### 163. Playtest camera bounds: one surface tile bleed past the footprint polygon
- Status: Accepted (2026-04-06)
- Why: Clamping `cameras.main.setBounds` exactly to the polygon AABB (with only an 8px pad) cropped wall/floor/ceiling shell art that legitimately extends one grid tile past the layout line; founder playtest showed harsh black bars at the scroll limits.
- Consequence: `getRoomCameraChamberBoundsWorld` expands polygon bounds by `CONFIG.CAMERA_CHAMBER_SURFACE_BLEED_PX` (**32px**, matching the uniform floor/wall tile grid) on each edge, still clamped to the room slot and world height. Runtime review capture uses the same rect.

### 164. Primary floor cap and collision extend by the same surface bleed as the camera
- Status: Accepted (2026-04-06)
- Why: Camera bleed revealed floor cap and physics ending exactly at polygon left/right while bespoke walls span the margin inset; an L-shaped black void appeared at the wall–floor corner.
- Consequence: In `buildWorldGeometry`, primary floor `primaryFloorLocalLeft` / `primaryFloorLocalRight` (cap, face band, support width) and primary-floor `collisionLocalLeft` / `collisionLocalRight` use the same `CONFIG.CAMERA_CHAMBER_SURFACE_BLEED_PX` expansion, clamped to the room slot width.

### 161b. `.env.local` must override non-empty wrong shell keys (follow-up 2026-04-06)
- Status: Accepted (2026-04-06)
- Why: Even after #161, **`room_layout_copilot`** loaded `.env.local` at import time with **“only if key not in os.environ”**, so a **wrong but non-empty** `GEMINI_API_KEY` in the shell still **blocked** the valid key in `.env.local`. The workbench server also froze `PIXELLAB_API_KEY` **before** `load_repo_env_local()` ran.
- Consequence: Both loaders apply **non-empty** `key=value` lines from `.env.local` **over** `os.environ`. `room_layout_copilot` uses `_copilot_gemini_api_key()` (`GEMINI` or `GOOGLE`). `load_repo_env_local()` runs once at module init (after the function is defined); `PIXELLAB_API_KEY` is read **after** that load.

### 148. Bespoke wall shell must run even when polygon wall rects are non-empty
- Status: Accepted (2026-04-05)
- Why: After decision 145, `buildWorldGeometry` only called `addRoomBespokeWallShellDecor` when `!roomHasPolygonWallTileRects`. Complex footprints (e.g. canonical R1) produce many outside-polygon cells, so `rects.length > 0` always — **bespoke wall_module composition never ran** while thin procedural tiles stayed at grid boundaries (often off-camera). Founder playtest still showed floor + void + no shell despite generated assets.
- Consequence: Always call `addRoomBespokeWallShellDecor` per room. Retain `roomHasPolygonWallTileRects` only to gate **AI wall mass fallback** when bespoke returns false (avoid double stack where rects already paint boundary mass).
