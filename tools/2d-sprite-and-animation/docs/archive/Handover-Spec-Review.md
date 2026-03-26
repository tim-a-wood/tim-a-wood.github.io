# Handover Spec Review
**Document reviewed:** `Next-Iteration-Agent-Handover.md`  
**Reviewer:** Claude (pre-implementation review)  
**Date:** 2026-03-13

---

## Overall Assessment

The spec is well-structured and honest about current state. The maturity matrix and placeholder inventory are genuinely useful anchors. The gaps are concentrated in the "how" layer — the implementing agent will need concrete backend targets, prompt templates, storage conventions, and interface contracts to avoid producing another round of well-structured scaffolding.

---

## Critical Gaps
*These will cause the agent to stall or diverge without resolution.*

### 1. WS1 — Concept backend is unspecified

"Call a configured local image generation backend" is not actionable. The agent needs:

- **Which backend to target.** Realistic options for a solo local tool: Automatic1111/SDXL (`/sdapi/v1/txt2img`) or ComfyUI (workflow API). These have different schemas, parameter names, and auth models.
- **How it is configured.** Env var (`CONCEPT_BACKEND_URL`)? A `config.json` beside `index.html`? A UI settings panel?
- **What happens when the backend is unavailable.** Auto-fallback to procedural with a warning, or hard-fail with a clear error?

**Fix:** Add a "Backend configuration" pre-task to WS1. Define:
- Abstract function signature: inputs (prompt, negative prompt, seed, dimensions, optional reference bytes) → outputs (PNG bytes + metadata)
- Primary target backend (name it)
- Config schema and storage location
- Fallback and error behavior

---

### 2. WS1 / WS5 — Multi-run storage is undefined

Concepts currently overwrite in place (`concepts/concept-01.png`–`concept-04.png`). WS1 adds regeneration and expands to 6; WS5 requires concept history. Regeneration must not clobber previous runs, but no naming convention is defined.

**Fix:** Specify run-namespaced storage (e.g., `concepts/<run_id>/concept-01.png`). Define how run IDs are generated (timestamp or UUID) and whether old runs are retained indefinitely, capped at N, or archived.

---

### 3. WS2 — No prompt assembly template

Eight structured brief fields are defined but there is no template showing how they combine into the final diffusion prompt. The agent will invent something arbitrary.

**Fix:** Provide the canonical prompt template. Example structure:
```
{role_archetype}, {silhouette_intent} silhouette, wearing {outfit_and_materials},
holding {prop}, {palette_mood} palette, {shape_language}, {mood_tone},
strict side view, single character, game sprite, no background
```
The exact content matters for generation quality; the agent should not design it independently.

---

### 4. WS3 — No upload endpoint; reference integration mechanism unspecified

The server has no file upload API. References are stored in `brief.json` as string arrays but nothing reads them. For a diffusion backend, integrating references requires a concrete decision: prompt description only, img2img, IP-Adapter, or ControlNet. These are not interchangeable.

**Fix:**
1. Add required work item to WS3: "Add `POST /api/projects/:id/references` endpoint that stores uploaded files in `references/` under the project dir."
2. Specify the integration mechanism explicitly — even if the answer is "encode reference description as supplemental prompt text for now; defer img2img/IP-Adapter."

---

### 5. WS4 — "Refinement strength" is undefined

The spec requires a "refinement strength" control but never defines what it maps to. For diffusion it is typically `denoising_strength` (0.0–1.0 for img2img). If refinement is prompt-only, strength has a different or no meaning.

**Fix:** Define the data type, range, label (e.g., "How much to change: 0.1–1.0"), and the backend parameter it maps to.

---

## Significant Gaps
*The agent will make poor choices without guidance here.*

### 6. WS6 — Filtering implementation approach unspecified

Five scoring criteria are listed (side-view compliance, single-character, silhouette readability, prop separation, background cleanliness). For AI-generated images these require either a secondary vision model (conflicts with the "no new deps" spirit) or calibrated PIL heuristics.

**Fix:** State explicitly that filtering uses PIL-based heuristics only. Sketch what each check means at the pixel level. For example: *"background cleanliness = >90% of non-alpha pixels in the outer 20% of the image are transparent or near-uniform."*

---

### 7. WS7 — No post-iteration maturity table

Honesty badges are required (real / experimental / placeholder) but the spec does not say which badge each stage carries after this iteration. Given the non-goals (no renderer replacement, no layer extraction), the layer, rig, and animation stages will remain placeholder.

**Fix:** Add a table alongside the existing maturity matrix showing the expected badge for each stage after this iteration. Prevents the agent from accidentally labeling synthetic stages "real."

---

### 8. WS9 — Job persistence and archive schemas are undefined

- "Persist job history to disk" leaves open: schema, location, retention policy.
- "Safe project archive" leaves open: folder rename, flag in `project.json`, or move to `_archived/`.

**Fix:**
- Jobs: append to `logs/jobs.json` per project, cap at last 50, include `job_id`, `job_type`, `status`, timestamps, error.
- Archive: set `"archived": true` in `project.json` and hide from the default project list (non-destructive, reversible).

---

### 9. WS10 — No storage location defined for metrics

**Fix:** State that metrics are appended to `<project_dir>/metrics.json` and define the schema for each event type (concept run, approval, rejection, refinement, time-to-approved).

---

## Work Breakdown Recommendations

### Recommendation 1 — Add a WS1 pre-task: "Backend configuration"

This is a blocker for all of WS1 and everything downstream. It should be the first item in WS1's required work. Scope: define the config schema, write it to `tools/2d-sprite-and-animation/config.json`, add a startup health check, and surface backend status in the UI on page load.

---

### Recommendation 2 — Move WS7 (honesty labels) earlier

The highest-risk moment for misleading labeling is immediately after WS1, when the concept stage goes real but everything downstream is still synthetic. The badge infrastructure and concept-stage label flip should be applied as part of WS1, not deferred to position 7. All other stage labels can be filled in later.

**Revised priority order:**

| Priority | Workstream |
|----------|------------|
| 1 | WS1: Real concept generation (includes backend config pre-task + honesty label for concept stage) |
| 2 | WS2: Structured brief |
| 3 | WS3: Reference support |
| 4 | WS4: Real refinement |
| 5 | WS5: Concept review UX |
| 6 | WS6: Pre-display filtering |
| 7 | WS7: Honesty pass for remaining stages |
| 8 | WS8: QA honesty improvements |
| 9 | WS9: Job and session QoL |
| 10 | WS10: Metrics |
| 11 | WS11: Repository hygiene (do this first, takes 2 minutes) |

---

### Recommendation 3 — Add explicit dependency annotations

The priority list reads as a total ordering, but several workstreams have hard dependencies that should be marked:

| Workstream | Blocked by |
|------------|-----------|
| WS4 (real refinement) | WS1 — refining procedural art is pointless |
| WS5 (concept history) | WS1 multi-run storage convention must be in place |
| WS6 (filtering) | WS1 — heuristics against procedural shapes are trivially moot |
| WS3 and WS2 | Independent of each other; can run in parallel if needed |

---

### Recommendation 4 — Expand file targets section

"May add supporting files" is too vague. Based on the scope of the workstreams, the agent should expect to create:

- `tools/2d-sprite-and-animation/config.json` — backend config
- `concepts/<run_id>/` — namespaced concept storage
- `<project_dir>/logs/jobs.json` — persisted job history (WS9)
- `<project_dir>/metrics.json` — per-project metrics (WS10)

---

### Recommendation 5 — Resolve the existing `ashen-sentinel` project data

`projects-data/ashen-sentinel-9ea9be55/` already exists in the repo. WS11 should include an explicit decision: keep it as a labeled curated fixture, or delete it. Leaving it unresolved means the agent will either ignore or arbitrarily handle it.

---

## Minor Issues

| # | Issue | Fix |
|---|-------|-----|
| 1 | Concept count `4` is hardcoded in a closure in `do_POST`, not a constant | Extract to a named constant (e.g., `CONCEPTS_PER_RUN`) before WS1 touches it |
| 2 | Intake form uses raw JSON textareas for references — WS2 adds structured fields but spec does not say whether the prompt textarea stays, becomes optional, or is replaced | State explicitly |
| 3 | WS11 stray-file cleanup is listed last but takes 2 minutes and should be the first commit | Move WS11 to "do first" in the priority notes |

---

## Definition of Done — No Changes Needed

The existing DoD is clear and verifiable. No additions recommended.
