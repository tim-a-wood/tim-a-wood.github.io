# Sprite Workbench Overhaul: Pixel Lab Integration

Version: 0.3
Date: 2026-03-18
Status: Phases 1–4 complete

## Decisions

- **Canvas size**: 64x64 (hero is 28x40 against 32px tiles; 64px gives ~38px sprite at 60% coverage — natural fit)
- **Existing projects**: Force re-creation. Legacy projects are not migrated.
- **Gemini concept validation**: Removed. The deterministic prompt scaffold handles constraints.
- **Template animation IDs**: Full list queried — see Appendix A. Use these directly in Phase 5 UI.

## Implementation Status (as of 2026-03-18)

### ✅ Complete
- **1.1** `PIXELLAB_API_KEY` env config + `pixellab_configured()` helper
- **1.2** `scripts/pixellab_client.py` — `PixelLabClient` class with HTTP plumbing + job polling
- **1.3** Concept generation methods: `create_image_pixflux`, `create_image_v2`, `image_to_pixelart`
- **1.4** Character creation methods: `create_character_4dir`, `create_character_8dir`, `get_character`, `list_characters`, `download_character_zip`
- **1.5** Skeleton + animation methods: `estimate_skeleton`, `animate_character`, `animate_with_text_v2`, `animate_with_skeleton`, `interpolation_v2`
- **1.6** Editing methods: `edit_animation_v2`, `inpaint_v3`, `transfer_outfit_v2`
- **1.7** `GET /api/pixellab/health` route + lazy singleton `get_pixellab_client()`
- **2.1** Brief schema extended: `outline_style`, `shading_style`, `detail_level`, `canvas_size`, `character_template`
- **2.2** `build_concept_prompt(brief)` — deterministic scaffold returning `display_prompt`, `pixellab_params`, `debug_constraints`
- **2.3** `build_iteration_prompt(brief, element, change_text, source_concept_path)` — inpaint-v3 based, per-element mask boxes
- **2.4** `POST /api/projects/<id>/concepts/build-prompt` and `build-iteration-prompt` endpoints
- **3.1** `POST /api/projects/<id>/concepts/generate-pixellab` — concept gen via Pixel Lab or debug_procedural
- **3.2** `POST /api/projects/<id>/concepts/iterate-pixellab` — iteration via inpaint-v3, stores `parent_concept_id` lineage
- **3.3** `POST /api/projects/<id>/concepts/import` extended with optional `convert_to_pixelart` boolean
- **4.1** `POST /api/projects/<id>/pixellab/create-character` — 4-dir or 8-dir, debug_procedural fallback, writes `pixellab_character.json` + `character/<dir>.png`
- **4.2** `POST /api/projects/<id>/pixellab/estimate-skeleton` — writes `pixellab_skeleton.json` with 18 keypoints
- **4.3** `POST /api/projects/<id>/pixellab/approve-character` — sets `approved: true` in `pixellab_character.json` and `pixellab_character_approved` on project
- **5.1** `POST /api/projects/<id>/pixellab/animate` — template animation, guard-gated, calls `animate_character()` with stored `character_id`, saves frames to `animations/<name>/<direction>/frame_NN.png`, appends to `pixellab_animations.json`
- **5.2** `POST /api/projects/<id>/pixellab/animate-custom` — text animation, guard-gated, east reference image, calls `animate_with_text_v2()`
- **5.3** `POST /api/projects/<id>/pixellab/animate-skeleton` — skeleton animation, guard-gated, requires `pixellab_skeleton.json`, calls `animate_with_skeleton()`
- **5.4** `POST /api/projects/<id>/pixellab/edit-animation` — animation edit, guard-gated, loads existing frames, calls `edit_animation_v2()`
- **5.5** `POST /api/projects/<id>/pixellab/build-clips` — guard-gated, reads `pixellab_animations.json`, writes canonical `animation_clips.json` with `fps`, `loop`, `frame_count`, `frames`, `frames_by_direction`
- **6.1** `run_pixellab_qa()` added; `run_qa()` routes to it when `pixellab_pipeline_ready_for_qa()` returns true. Checks: `pixellab_character.json` + `pixellab_animations.json` exist, approval guard, frame count/transparency/dimension checks kept, part_split/sprite_model checks removed.
- **6.2** Export pipeline adapted: reads frames from `animations/<clip>/<direction>/frame_NN.png` via `animation_clips.json`. Produces `spritesheet.png`, `atlas.json`, `animations.json`, `preview.gif`, `export_manifest.json`. Manifest includes `pixellab_character_id` and `pixellab_latest_job_ids`; no `sprite_model_hash`/`rig_hash`. Export mode flagged as `"export_mode": "pixellab"`.

### ⚠️ Known implementation notes (reviewed 2026-03-18)
- `animate_character` endpoint path is `/v2/characters/animations` — confirmed via validation error query
- `create_character_4dir`/`create_character_8dir` poll for async job completion (same `_extract_job_id` + `_poll_job` pattern as other async methods) — do NOT pass `async_mode=True` from server; polling is handled inside the client methods
- `_pixellab_character_approved_guard(project_dir)` is defined in server and must be called at the top of every Phase 5 handler — supports both `pixellab_character_approved` and legacy `approved` keys
- Frame filenames are zero-padded: `frame_%02d.png`
- `pixellab_animations.json` is written via `_upsert_pixellab_animation_frames()` / `_save_pixellab_animations_store()`
- 3 pre-existing test failures exist in the old Gemini validation path (`test_upload_import_creates_concept_attempt`, `test_local_path_import_creates_concept_attempt`, `test_generate_improved_prompt_includes_prior_prompt_and_feedback`) — these are unrelated to the new pipeline and will be removed in Phase 8

## Goal

Replace the ComfyUI-based sprite pipeline with Pixel Lab API, simplify the workflow
from 15+ steps to ~5 phases, and add deterministic prompt scaffolding for concept
generation via Gemini (manual) or Pixel Lab (API).

## New Pipeline

```
DESCRIBE → CONCEPTS → CHARACTER → ANIMATIONS → EXPORT
(brief)    (scaffold   (4-dir +    (template    (spritesheet
            + generate   skeleton)   anims +      + atlas)
            or import)              custom)
```

## Design Principles

1. **debug_procedural survives** — adapted for the new pipeline shape (returns synthetic
   character directions, skeleton, and animation frames) so the full test suite runs
   without burning Pixel Lab credits and UI development works offline.
2. **Interleaved frontend** — each new panel is built and its old equivalent hidden in the
   same task, keeping the app in a working state at every commit.
3. **Credits visible from day one** — Pixel Lab returns `usage.remaining_credits` on every
   response; surface it in the UI header starting in Phase 1.7.
4. **Legacy projects are dead** — no migration path, no read-only hydration. Old project
   directories are ignored by the new server. Users re-create projects in the new pipeline.

---

## Phase 1: Foundation — Pixel Lab Client + Config

### 1.0 Query Pixel Lab API for template animation IDs
- Use real API key to call character creation + animation endpoints
- Document the full list of available `template_animation_id` values
- Record which ones are most relevant for a 2D side-view Metroidvania (idle, walk, run, attack, jump, death, etc.)
- Save findings in this doc under a new "Pixel Lab Animation Templates" appendix

### 1.1 Add PIXELLAB_API_KEY to env config
- Add `PIXELLAB_API_KEY` to `.env.local.example`
- Read it in `sprite_workbench_server.py` via `os.environ.get("PIXELLAB_API_KEY")`
- Add a `pixellab_configured()` helper that returns True if key is set
- **Test**: unit test that `pixellab_configured()` returns False when env is unset

### 1.2 Create Pixel Lab API client module
- Add `scripts/pixellab_client.py` as a standalone module
- Implement `PixelLabClient` class with:
  - `__init__(self, api_key, base_url="https://api.pixellab.ai")`
  - `_request(self, method, path, payload=None)` — shared HTTP logic, auth header, error handling
  - `_poll_job(self, job_id, timeout=120, interval=3)` — polls `GET /v2/background-jobs/{job_id}`
  - `get_balance(self)` — `GET /v1/balance`
- No Pixel Lab-specific endpoints yet — just the HTTP plumbing
- **Test**: unit test with mocked HTTP responses for auth, error codes (401, 402, 429)

### 1.3 Add concept generation methods to client
- `create_image_pixflux(self, description, image_size, **kwargs)` — `POST /v1/generate-image-pixflux`
- `create_image_v2(self, description, image_size, **kwargs)` — `POST /v2/generate-image-v2` (async + poll)
- `image_to_pixelart(self, image_b64, input_size, output_size, **kwargs)` — `POST /v2/image-to-pixelart`
- Helper: `encode_image(path_or_pil) -> base64 string`
- Helper: `decode_image(b64_string) -> PIL.Image`
- **Test**: unit test with mocked responses, verify base64 encoding/decoding round-trips

### 1.4 Add character creation methods to client
- `create_character_4dir(self, description, image_size, **kwargs)` — `POST /v2/create-character-with-4-directions` (async)
- `create_character_8dir(self, description, image_size, **kwargs)` — `POST /v2/create-character-with-8-directions` (async)
- `get_character(self, character_id)` — `GET /v2/characters/{character_id}`
- `list_characters(self, limit=20, offset=0)` — `GET /v2/characters`
- `download_character_zip(self, character_id)` — `GET /v2/characters/{character_id}/zip`
- **Test**: unit test with mocked async job responses (202 → poll → complete)

### 1.5 Add skeleton + animation methods to client
- `estimate_skeleton(self, image_b64)` — `POST /v1/estimate-skeleton`
- `animate_character(self, character_id, template_animation_id, **kwargs)` — `POST /v2/characters/animations` (async)
- `animate_with_text_v2(self, reference_image, action, image_size, **kwargs)` — `POST /v2/animate-with-text-v2` (async)
- `animate_with_skeleton(self, reference_image, image_size, skeleton_keypoints, **kwargs)` — `POST /v1/animate-with-skeleton`
- `interpolation_v2(self, start_image, end_image, action, image_size, **kwargs)` — `POST /v2/interpolation-v2` (async)
- **Test**: unit test with mocked responses for skeleton estimation and animation jobs

### 1.6 Add editing methods to client
- `edit_animation_v2(self, description, frames, image_size, **kwargs)` — `POST /v2/edit-animation-v2` (async)
- `inpaint_v3(self, description, inpainting_image, mask_image, **kwargs)` — `POST /v2/inpaint-v3` (async)
- `transfer_outfit_v2(self, reference_image, frames, image_size, **kwargs)` — `POST /v2/transfer-outfit-v2` (async)
- **Test**: unit test with mocked responses

### 1.7 Wire client into server + credits display
- Import `PixelLabClient` in `sprite_workbench_server.py`
- Create a lazy singleton: `_pixellab_client = None; get_pixellab_client()` that initializes on first use
- Add `GET /api/pixellab/health` route — returns `{ configured: bool, balance: ... }` (calls `get_balance()`)
- Every Pixel Lab endpoint response should include `usage` from the API response (credits_used, remaining_credits, remaining_generations) — store last-known usage on the singleton and return it from health
- Frontend: add a small "PL: {credits} credits" indicator in the sidebar header, refreshed on health poll
- **Test**: integration test that health endpoint returns `configured: false` when key is unset

---

## Phase 2: Prompt Scaffold Engine

### 2.1 Define brief schema with Pixel Lab style fields
- Update `brief.json` schema to add new fields alongside existing ones:
  - `outline_style`: enum matching Pixel Lab (`"single color black outline"`, `"selective outline"`, `"lineless"`)
  - `shading_style`: enum (`"flat shading"`, `"basic shading"`, `"medium shading"`, etc.)
  - `detail_level`: enum (`"low detail"`, `"medium detail"`, `"highly detailed"`)
  - `canvas_size`: int (default 64; options: 32, 64, 128, 256 — must match Pixel Lab skeleton-supported sizes)
  - `character_template`: enum (`"mannequin"`, `"bear"`, `"cat"`, `"dog"`, `"horse"`, `"lion"`)
- Provide sensible defaults for all new fields
- Existing brief fields (`role_archetype`, `silhouette_intent`, `outfit_materials`, `prop`, `palette_mood`, `shape_language`, `mood_tone`) remain unchanged
- **Test**: load_project still works for existing projects (new fields get defaults)

### 2.2 Implement build_concept_prompt()
- Add `build_concept_prompt(brief)` function to server
- Returns dict with two keys:
  - `display_prompt`: full human-readable text with all brief fields + technical requirements block
  - `pixellab_params`: dict ready to send to `create_image_pixflux` (description, image_size, view, direction, outline, shading, detail, no_background)
- The `display_prompt` template is a deterministic f-string, no LLM involved
- **Test**: given a sample brief dict, verify display_prompt contains all fields and technical requirements; verify pixellab_params has correct types and enums

### 2.3 Implement build_iteration_prompt()
- Add `build_iteration_prompt(brief, element, change_text, source_concept=None)` function
- `element`: one of `"outfit"`, `"weapon/prop"`, `"palette/colors"`, `"pose"`, `"silhouette"`, `"hair/head"`, `"accessories"`, `"expression"`, `"proportions"`
- Returns dict with:
  - `display_prompt`: full character description (from brief) + iteration block (element, change, constraints)
  - `pixellab_params`: same as concept prompt but with `init_image` field populated from source_concept path
- **Test**: verify iteration prompt contains change text, element label, and constraint block; verify pixellab_params includes init_image_strength

### 2.4 Add scaffold API endpoints
- `POST /api/projects/<id>/concepts/build-prompt` — calls `build_concept_prompt(brief)`, returns `{ display_prompt, pixellab_params }`
- `POST /api/projects/<id>/concepts/build-iteration-prompt` — body: `{ concept_id, element, change_text }`, calls `build_iteration_prompt()`, returns same shape
- Both endpoints are pure computation, no external API calls
- **Test**: HTTP-level test that endpoints return correct shape

---

## Phase 3: Concept Generation + Import

### 3.1 Add Pixel Lab concept generation endpoint
- `POST /api/projects/<id>/concepts/generate-pixellab` — body: `{ pixellab_params }` (from scaffold output)
- Calls `pixellab_client.create_image_pixflux()` with the params
- Saves result as `concepts/concept-NNNN.png` + `concepts/concept-NNNN.json` (metadata: source="pixellab", params, seed)
- Returns concept metadata + image path
- **Test**: unit test with mocked Pixel Lab response, verify files are written

### 3.2 Add Pixel Lab iteration generation endpoint
- `POST /api/projects/<id>/concepts/iterate-pixellab` — body: `{ concept_id, pixellab_params }`
- Loads source concept image, base64-encodes it as `init_image`
- Calls `create_image_pixflux()` with init_image + iteration params
- Saves as new concept with `parent_concept_id` in metadata JSON
- **Test**: unit test with mocked response, verify parent lineage is stored

### 3.3 Adapt existing concept import endpoint
- Keep `POST /api/projects/<id>/concepts/import` for file upload path (manual Gemini workflow)
- Add optional `convert_to_pixelart` boolean in body
- If true, call `pixellab_client.image_to_pixelart()` on the uploaded image before saving
- Save conversion metadata in concept JSON
- **Test**: unit test that import with conversion flag writes converted image

### 3.4 Add concept image describe endpoint (optional, for imported images) — DEFERRED
- Skipped in initial implementation. Not required for Phase 5.
- If added later: `POST /api/projects/<id>/concepts/<cid>/build-describe-prompt` — pure scaffold, no LLM call

---

## Phase 4: Character Creation

### 4.1 Add character creation endpoint
- `POST /api/projects/<id>/pixellab/create-character` — body: `{ directions: 4|8, description, image_size, color_image_concept_id?, ... }`
- If `color_image_concept_id` is provided, load that concept image and send it as Pixel Lab v2 `color_image` (`Base64Image`: `{ type: "base64", base64, format }`), not a raw string
- Calls `create_character_4dir()` or `create_character_8dir()`
- Polls async job until complete
- Saves direction images to `character/south.png`, `character/west.png`, `character/east.png`, `character/north.png`
- Writes `pixellab_character.json` with character_id, job params, image paths
- Returns character data
- **Test**: unit test with mocked async job, verify directory structure and JSON

### 4.2 Add skeleton estimation endpoint
- `POST /api/projects/<id>/pixellab/estimate-skeleton` — no body needed (uses east/side-view direction image)
- Loads `character/east.png`, calls `estimate_skeleton()`
- Writes `pixellab_skeleton.json` with keypoints array
- Returns skeleton data
- **Test**: unit test with mocked skeleton response, verify JSON written

### 4.3 Add character approval endpoint
- `POST /api/projects/<id>/pixellab/approve-character`
- Sets `pixellab_character.json` → `approved: true`
- Gates downstream animation endpoints (animation endpoints check this flag)
- **Test**: verify approval flag is persisted and that pre-approval animation calls are rejected

---

## Phase 5: Animation

### 5.1 Add template animation endpoint
- `POST /api/projects/<id>/pixellab/animate` — body: `{ template_animation_id, directions?, animation_name? }`
- Calls `animate_character()` with the stored `character_id`
- Polls async job
- Saves frames to `animations/<animation_name>/<direction>/frame_NN.png`
- Appends to `pixellab_animations.json`
- **Test**: unit test with mocked animation job, verify frame files written

### 5.2 Add custom text animation endpoint
- `POST /api/projects/<id>/pixellab/animate-custom` — body: `{ action, image_size }`
- Uses east-facing character image as reference
- Calls `animate_with_text_v2()`
- Polls async job, saves frames
- **Test**: unit test with mocked response

### 5.3 Add skeleton-based animation endpoint
- `POST /api/projects/<id>/pixellab/animate-skeleton` — body: `{ keypoint_frames: [[Point, ...], ...] }`
- Uses east-facing character image as reference, stored skeleton as base
- Calls `animate_with_skeleton()` (synchronous, 4 frames per call)
- Saves frames
- **Test**: unit test with mocked response

### 5.4 Add animation editing endpoint
- `POST /api/projects/<id>/pixellab/edit-animation` — body: `{ animation_name, description }`
- Loads existing animation frames, calls `edit_animation_v2()`
- Overwrites frames or saves as variant
- **Test**: unit test with mocked response

### 5.5 Build animation_clips.json from Pixel Lab frames
- `POST /api/projects/<id>/pixellab/build-clips`
- Reads `pixellab_animations.json`, assembles `animation_clips.json` in the existing canonical format
- Maps each animation to fps, loop, frame_count, frame paths
- This bridges Pixel Lab output to the existing export pipeline
- **Test**: verify animation_clips.json matches expected schema

---

## Phase 6: QA + Export (Adapt Existing)

### 6.1 Adapt QA validation for Pixel Lab pipeline
- Update `run_qa()` to check for `pixellab_character.json` and `pixellab_animations.json` instead of sprite_model + rig
- Keep frame count, transparency, and dimension checks
- Remove checks specific to part extraction (part_split, sprite_model build_report)
- **Test**: QA passes on a project with Pixel Lab data, fails on incomplete project

### 6.2 Adapt export pipeline for Pixel Lab frames
- Update export to pack frames from `animations/<clip>/<direction>/frame_NN.png`
- Keep: spritesheet packing, atlas.json generation, animations.json, preview.gif, export_manifest.json
- Add Pixel Lab character_id and animation job IDs to export_manifest lineage
- Remove: sprite_model/rig references in export manifest
- **Test**: export produces valid spritesheet from Pixel Lab animation frames

---

## Phase 7: Simplified Frontend (Interleaved Build/Replace)

Each task builds the new panel AND hides/removes the old equivalent in the same commit,
keeping the app functional at every step.

### 7.1 Add Pixel Lab style controls to Setup panel + hide old backend toggle
- Add dropdowns for: outline_style, shading_style, detail_level, canvas_size, character_template
- Wire to brief.json save via existing `POST /api/projects/<id>/brief` endpoint
- Keep all existing brief fields (description, role, outfit, etc.)
- Remove: backend_mode selector (comfyui vs debug_procedural), checkpoint input, ComfyUI-specific advanced settings
- Add: Pixel Lab credits indicator in sidebar (wired to `GET /api/pixellab/health`)
- **Implementation note (2026-03-18):** Do **not** remove server `debug_procedural` branching in Phase 7. UI must not offer backend_mode; on `POST .../brief`, re-send stored `backend_mode` / `comfyui_checkpoint` so they are not wiped. New projects omit them so `create_project` keeps defaulting to `debug_procedural` when no valid mode is posted.

### 7.2 Build new Concepts panel + remove old concepts/character-lock/key-pose panels
- [x] Replace existing `concepts` + `ai-character-lock` + `ai-key-pose-board` sections with single `concepts` panel
- [x] Layout: [Build Prompt] → `persist-scaffold-prompt` → read-only textarea; mode toggle (Pixel Lab / Manual); `WORKBENCH_SECTION_IDS` / `WIZARD_SECTION_MAP` updated (no character-lock / key-pose nav)
- [x] Concept grid with thumbnails, selection, **Mark valid** / **Approve as character source** (Gemini revalidate/improve removed from cards)
- [x] [Generate via Pixel Lab] → `generate-pixellab`; Manual **Import Image** uses `lastConceptScaffold.anchor_concept_id`
- [x] Large preview + iteration compare hooks
- [x] Remove old panel HTML; stub `renderAiCharacterLockBoard` / `renderAiKeyPoseBoard`; server: AI wizard gates treat approved concept as character-lock/key-pose for progression; motion can use `_ai_synthetic_key_pose_run_from_selected_concept` when no approved pose board

### 7.3 Add iteration sub-panel to Concepts
- [x] Element dropdown + change text + [Build Iteration Prompt] → `build-iteration-prompt`
- [x] Iteration prompt textarea (read-only)
- [x] [Generate via Pixel Lab] → `iterate-pixellab`; [Import Edited Image] → `concepts/import` with `source_prompt_id` = selected concept
- [x] Side-by-side before/after preview (`lastIteratedConceptId`)
- [x] Removed heavy Gemini validation UI from concept cards (revalidate / improve / override invalid paths not shown)

### 7.4 Build new Character panel + remove old motion/extraction/cleanup panels
- [x] Shows chosen concept at top (`#character` / `pixellab-character-board`)
- [x] [Create Character (4 dir)] / [Create Character (8 dir)] → `POST .../pixellab/create-character`
- [x] Direction image grid (all dirs from `pixellab_character.json`; 4 or 8)
- [x] [Estimate skeleton (east)] → `POST .../pixellab/estimate-skeleton`; skeleton overlay toggle on east (canvas keypoints)
- [x] [Approve Character] → `POST .../pixellab/approve-character`
- [x] Removed HTML: `ai-motion-workflow`, `ai-cleanup-qa`; removed `renderAiMotionWorkflowBoard` / `renderAiCleanupQaBoard` and Comfy-only motion handlers
- [x] Wizard: `clips` → `#character`; `qa` → main `#qa` Checks panel; `load_project` hydrates `pixellab_character` + `pixellab_skeleton`; `compute_wizard_context` uses character approval when `brief.backend_mode === pixellab`

### 7.5 Build new Animations panel + remove old rig/part/production panels
- [x] Template pickers (idle vs walk lists from Appendix A IDs, server-matched inference)
- [x] **Generate via template** per clip → `POST .../pixellab/animate` (4/8 dirs from character)
- [x] Custom action + **Generate custom** → `animate-custom`; **Edit animation** → `edit-animation`
- [x] Per-clip preview direction, frame strip, Play/Stop (FPS from store)
- [x] Store summary table + **Build canonical clips** → `build-clips`
- [x] Removed HTML panels: `rig-layout` … `production`; `renderAll` no longer calls legacy rig/part/clip renderers (functions remain as no-ops when DOM absent)
- [x] `load_project` hydrates `pixellab_animations`; wizard step `animations` after `clips` for `backend_mode=pixellab` (`wizard_steps_active`, `pixellab_animations_step_complete`)

### 7.6 Adapt Review/QA + Export panel
- Merge existing `qa` + `export` panels into single panel
- Animation playback preview
- QA status indicators
- [Run QA] button
- [Export] button with spritesheet preview

### 7.7 Update wizard flow and navigation
- Update `WIZARD_SECTION_MAP` to map new 5-phase flow: describe → concepts → character → animations → export
- Update sidebar navigation links (5 items instead of 13+)
- Remove wizard steps that referenced old panels
- Remove old nav entries

---

## Phase 8: Cleanup

### 8.1 Remove ComfyUI integration code from server
- Remove all ComfyUI workflow template loading, parameter patching, job submission, and polling code
- Remove PhotoMaker, ToonCrafter, IPAdapter, AnimeSeg references
- Remove `backend_mode` toggle logic (no more `comfyui` vs `debug_procedural` selector)
- Remove Gemini concept validation code (`run_gemini_concept_validation` and related)

### 8.2 Adapt debug_procedural for new pipeline shape
- Update debug_procedural to return synthetic data matching the new pipeline:
  - Concept generation: return a PIL-generated placeholder image (colored rectangle with text label)
  - Character creation: return 4 synthetic direction images + fake character_id
  - Skeleton estimation: return a hardcoded 18-point humanoid skeleton for 64x64
  - Animation: return N synthetic frames per clip (colored rectangles with frame number)
- This is the test/offline backend — no Pixel Lab key needed
- **Test**: full pipeline test using debug_procedural produces valid export

### 8.3 Remove legacy rig/part pipeline code from server
- Remove rig layout LLM handoff endpoints and functions
- Remove part manifest generation endpoints and functions
- Remove part shape computation endpoints and functions
- Remove part split/extraction endpoints and functions
- Remove sprite model build endpoints and functions
- Remove occlusion recovery endpoints and functions
- Remove legacy load_project hydration (no more `layered_character.json`, `animation_templates.json`, `palette.json` support)
- Remove old `CANONICAL_DOWNSTREAM_FILES` entries for retired files

### 8.4 Remove legacy frontend code
- Delete any remaining old panel HTML/JS not already removed in Phase 7
- Remove CSS rules targeting deleted elements
- Remove JS functions that handled old panel rendering, events, and state

### 8.5 Update stage-maturity.json
- Remove old stages (`intake`, `concepts`, `refine`, `master_pose`, `sprite_model`, `layer_review`, `rig_review`, `production`, `qa`, `export`)
- Add new stages: `describe`, `concepts`, `character`, `animations`, `export`
- Set maturity levels (all start as `experimental`, promote as they stabilize)

### 8.6 Update CANONICAL-DOWNSTREAM-CONTRACT.md
- Document new canonical files: `pixellab_character.json`, `pixellab_skeleton.json`, `pixellab_animations.json`
- Document removed files: `sprite_model.json`, `sprite_model_history.json`, `rig.json`, `ai_workflow.json`, `external_authoring.json`
- Update export manifest schema
- Remove references to ComfyUI, SkelForm, and legacy part extraction

---

## Phase 9: Tests + Docs

### 9.1 Add Pixel Lab client unit tests
- Test all client methods with mocked HTTP (use unittest.mock.patch on urllib/requests)
- Test async polling (job pending → completed, job pending → failed, timeout)
- Test error handling (401, 402, 429, 422)
- Test base64 encode/decode helpers

### 9.2 Add scaffold engine unit tests
- Test build_concept_prompt with various brief configurations
- Test build_iteration_prompt with each element type
- Test edge cases: missing fields, empty strings, unusual canvas sizes

### 9.3 Add integration tests for new pipeline
- Create `build_pixellab_debug_pipeline()` helper (like existing `build_ai_debug_workflow()`)
- Mock all Pixel Lab API calls, exercise full flow: create project → build prompt → generate concept → create character → estimate skeleton → generate animation → build clips → QA → export
- Verify all canonical files are written correctly

### 9.4 Update workflow documentation
- Rewrite How-To-Use-AI-Workflow.md for new pipeline
- Update README.md sprite workbench section
- Archive old Comfy-Integration-Setup.md
- Archive old SkelForm-Integration-Notes.md

### 9.5 Update .env.local.example
- Add `PIXELLAB_API_KEY="paste_key_here"`
- Remove `GEMINI_API_KEY` (no longer used — concept validation removed)
- Remove `SPRITE_WORKBENCH_COMFYUI_URL`, `SPRITE_WORKBENCH_COMFYUI_CHECKPOINT`, `SPRITE_WORKBENCH_COMFYUI_JOB_TIMEOUT_SECONDS`

---

## Implementation Order

Recommended sequence (each task is independently committable):

```
Recon:                 1.0  ✅
Phase 1 (foundation):  1.1 ✅ → 1.2 ✅ → 1.3 ✅ → 1.4 ✅ → 1.5 ✅ → 1.6 ✅ → 1.7 ✅
Phase 2 (scaffold):    2.1 ✅ → 2.2 ✅ → 2.3 ✅ → 2.4 ✅
Phase 3 (concepts):    3.1 ✅ → 3.2 ✅ → 3.3 ✅ → 3.4 (deferred)
Phase 4 (character):   4.1 ✅ → 4.2 ✅ → 4.3 ✅
Phase 5 (animation):   5.1 ✅ → 5.2 ✅ → 5.3 ✅ → 5.4 ✅ → 5.5 ✅
Phase 6 (QA/export):   6.1 ✅ → 6.2 ✅
Phase 7 (frontend):    7.1 ✅ → 7.2 ✅ → 7.3 ✅ → 7.4 ✅ → 7.5 ✅ → 7.6 → 7.7  ← NEXT
Phase 8 (cleanup):     8.1 → 8.2 → 8.3 → 8.4 → 8.5 → 8.6
Phase 9 (tests/docs):  9.1 → 9.2 → 9.3 → 9.4 → 9.5
```

**Dependency notes:**
- 1.0 (recon) informs Phase 5 animation picker UI — do first
- Phases 1-6 are backend-only, each produces testable endpoints
- Phase 7 frontend tasks each build a new panel AND remove the old equivalent in the same commit
- Phase 8.2 (debug_procedural adaptation) should happen before Phase 9.3 (integration tests)
- Phase 9 tests run in parallel throughout — write tests alongside each phase

## Resolved Questions

1. **Canvas size**: 64x64 (matches 32px tile scale, best Pixel Lab support for skeleton/animation)
2. **Existing projects**: Force re-creation. No migration, no legacy read-only mode.
3. **Gemini concept validation**: Removed. Scaffold handles technical constraints deterministically.
4. **Template animation IDs**: Full list queried — see Appendix A.
5. **Pixel Lab pricing**: Credit-based. Surface remaining credits in UI from day one (task 1.7).

---

## Appendix A: Pixel Lab Template Animation IDs

Full list queried from `POST /v2/characters/animations` validation (2026-03-18).
48 templates total. Grouped by relevance to a 2D side-view Metroidvania.

### Tier 1 — Core (use first)

| Template ID | Category | Notes |
|---|---|---|
| `breathing-idle` | Idle | Primary idle animation |
| `walk` | Movement | Basic walk cycle |
| `walking` | Movement | Alt walk (test both, pick best) |
| `walking-4-frames` | Movement | 4-frame walk — good for pixel art |
| `walking-6-frames` | Movement | 6-frame walk |
| `walking-8-frames` | Movement | 8-frame walk — smoothest |
| `running-4-frames` | Movement | 4-frame run |
| `running-6-frames` | Movement | 6-frame run |
| `running-8-frames` | Movement | 8-frame run — smoothest |
| `jumping-1` | Movement | Jump variant 1 |
| `jumping-2` | Movement | Jump variant 2 |
| `two-footed-jump` | Movement | Standing jump |
| `crouching` | Movement | Crouch pose |
| `crouched-walking` | Movement | Crouch walk (stealth/crawl) |
| `falling-back-death` | Death | Death animation |
| `fight-stance-idle-8-frames` | Combat | Combat idle |
| `lead-jab` | Combat | Quick attack |
| `cross-punch` | Combat | Heavy attack |

### Tier 2 — Expansion (combat + traversal)

| Template ID | Category | Notes |
|---|---|---|
| `high-kick` | Combat | High attack |
| `roundhouse-kick` | Combat | Sweeping attack |
| `hurricane-kick` | Combat | Spinning attack |
| `surprise-uppercut` | Combat | Launcher/anti-air |
| `leg-sweep` | Combat | Low attack |
| `flying-kick` | Combat | Air attack |
| `fireball` | Combat | Ranged/projectile |
| `taking-punch` | Combat | Hit reaction |
| `getting-up` | Combat | Recover from knockdown |
| `backflip` | Traversal | Evasion/acrobatic |
| `front-flip` | Traversal | Acrobatic |
| `running-jump` | Traversal | Moving jump |
| `running-slide` | Traversal | Slide move |

### Tier 3 — Flavor (polish + world-building)

| Template ID | Category | Notes |
|---|---|---|
| `drinking` | Interaction | Recovery/potion animation |
| `picking-up` | Interaction | Item pickup |
| `throw-object` | Interaction | Throw item |
| `pushing` | Interaction | Push object puzzle |
| `pull-heavy-object` | Interaction | Pull object puzzle |
| `sad-walk` | Flavor | Low-health or story walk |
| `scary-walk` | Flavor | Cautious/fear walk |
| `walk-1` | Movement | Walk variant |
| `walk-2` | Movement | Walk variant |
| `walking-2` | Movement | Walk variant |
| `walking-3` | Movement | Walk variant |
| `walking-4` | Movement | Walk variant |
| `walking-5` | Movement | Walk variant |
| `walking-6` | Movement | Walk variant |
| `walking-7` | Movement | Walk variant |
| `walking-8` | Movement | Walk variant |
| `walking-9` | Movement | Walk variant |
| `walking-10` | Movement | Walk variant |
