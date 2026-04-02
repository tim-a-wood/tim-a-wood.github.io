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
