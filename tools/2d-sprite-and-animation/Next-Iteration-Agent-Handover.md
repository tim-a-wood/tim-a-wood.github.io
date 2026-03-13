# Next Iteration Agent Handover

## Purpose

This document defines the next iteration of the 2D sprite workbench.

This iteration has two goals:

1. deliver a meaningful QoL pass
2. replace the current placeholder concept pipeline with a real concept workflow that produces much stronger initial concepts

This is an implementation handoff for an AI agent. Treat it as the authoritative iteration spec for this pass.

## Precedence

- This document is authoritative for this iteration.
- `tools/2d-sprite-and-animation/Solo-AI-Sprite-Workbench-Spec.md` is historical context and should not override this handoff.
- If those two documents conflict, follow this handoff.

## Current-State Assessment

Use these maturity levels:

- `High`: ready to use in production
- `Medium`: functionally usable but still missing important robustness or capability
- `Low`: placeholder, synthetic, or misleading relative to claimed behavior

### Maturity Matrix

| Component | Maturity | Assessment |
| --- | --- | --- |
| Local server and API scaffold | Medium | The Python server runs locally, persists projects to disk, serves static assets, and supports async jobs. Jobs are in-memory only and there is no restart recovery, but the core scaffold is usable. |
| Project persistence and file layout | Medium | File-backed storage is practical and lightweight. The current layout is easy to reason about. |
| Intake and prompt normalization | Low | Prompt parsing is shallow keyword mapping and loses most of the user's art direction intent. |
| Reference image support | Low | Reference fields are stored but not consumed anywhere downstream. |
| Concept generation | Low | Current concept generation is procedural placeholder art, not a real image generation backend. |
| Concept selection | Medium | Selection and concept lock work structurally, but the selected concepts are low quality because the upstream generator is fake. |
| Refinement | Low | Refinement mutates JSON only and does not generate new visual outputs. |
| Layer build | Low | Layers are generated from a synthetic part library rather than extracted from concept art. |
| Rig build | Low | Rigging is structurally coherent but only for synthetic layers. |
| Animation templates | Low | Idle and walk are fixed sine-wave templates, useful as a renderer demo but not a mature animation system. |
| Rendering pipeline | Medium | The deterministic renderer, cleanup pass, and spritesheet packing are structurally sound. |
| QA system | Low | Several checks are hard-coded or too weak to support production claims. |
| Export | Medium | Export outputs are usable and correctly structured, but they depend on synthetic upstream stages. |
| UI shell and navigation | Medium | The one-page UI works, but the concept review surface is underpowered and some copy overstates maturity. |
| Overall tool maturity | Low | The tool is a credible prototype of the intended workflow, not a production-ready sprite workbench. |

## Confirmed Placeholder and Synthetic Components

The following are known placeholders or synthetic stand-ins and must be treated as such:

1. `normalize_prompt()` in `scripts/sprite_workbench_server.py`
   - shallow token-to-canned-value mapping

2. `concept_variant()` and `draw_preview()` in `scripts/sprite_workbench_server.py`
   - placeholder concept pipeline using Pillow primitives

3. `/api/projects/<id>/refine`
   - JSON mutation only
   - no new concept generation

4. `PART_LIBRARY` and `make_part_image()`
   - synthetic procedural layer generation

5. `build_layered_character()`
   - always emits a pre-passed synthetic layer set

6. `build_animation_templates()`
   - fixed math-driven idle and walk loops

7. `run_qa()`
   - several checks are weak or hard-coded

8. reference inputs
   - saved in `brief.json`
   - not used in generation

9. review UI maturity
   - no ranking, compare mode, favorites, rejects, or lineage display

10. file hygiene
   - `tools/2d-sprite-and-animation/Untitled` is a stray placeholder file
   - `tools/2d-sprite-and-animation/Solo-AI-Sprite-Workbench-Spec.md` had a trailing space in its filename before this iteration

## Iteration Thesis

The next pass should not try to solve every production-quality gap.

It should do these things well:

1. replace fake concept generation with a real backend
2. make concept intake and references materially improve output quality
3. make refinement actually generate new visual candidates
4. make concept review faster and more informative
5. make the UI honest about which stages are real and which are still synthetic
6. strengthen the weakest downstream checks enough that the tool stops reporting fake confidence

## Required Outcomes

By the end of this iteration:

- initial concepts should no longer be placeholder geometry by default
- initial concept quality should improve from "usually unusable" to "at least 2 of 6 are worth refining" for a solid prompt
- refinement should generate new concept boards instead of just updating JSON
- references and style references should influence concept generation
- the review board should support compare, reject, favorite, and regenerate-similar workflows
- the UI should clearly label experimental and placeholder stages
- QA should stop reporting full confidence on checks that are still stubbed or weak

## Non-Goals For This Iteration

- do not replace the deterministic renderer
- do not build fully automatic concept-to-layer extraction unless it falls out naturally from concept backend work
- do not add new animation types
- do not add multi-direction support
- do not add cloud infrastructure or a database
- do not add team, sharing, or auth features
- do not implement heavy semantic scoring systems such as CLIP/VLM filtering in this pass

## Backend Decision

The concept backend for this iteration is:

- `ComfyUI`
- local only
- default base URL: `http://127.0.0.1:8188`

This is the default and only real concept backend the next agent should target in this iteration.

The existing procedural concept generator may remain only as an explicitly labeled debug fallback.

Do not silently fall back to procedural concepts if ComfyUI is unavailable. The user must see a clear backend error unless they deliberately opt into debug mode.

## ComfyUI Integration Contract

Use HTTP plus polling. Do not add a websocket dependency for this iteration.

Required interaction shape:

1. upload reference images to ComfyUI if needed
2. submit a workflow prompt job
3. poll job status
4. fetch output images
5. store images and metadata in the project folder

The backend integration should be coded against these expected ComfyUI routes:

- `POST /upload/image`
- `POST /prompt`
- `GET /history/<prompt_id>`
- `GET /view`

## Backend Abstraction Contract

Create a concept backend abstraction in Python so the server can call one interface regardless of generation mode.

Use a contract equivalent to this:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

@dataclass
class ReferenceInput:
    role: str
    local_path: Path
    weight: float

@dataclass
class ConceptRequest:
    project_id: str
    positive_prompt: str
    negative_prompt: str
    width: int
    height: int
    seed: int
    count: int
    references: list[ReferenceInput]
    mode: str
    refine_from_image: Path | None = None
    refine_strength: float | None = None
    variation_axes: dict[str, Any] | None = None

@dataclass
class GeneratedConcept:
    seed: int
    image_path: Path
    backend_name: str
    backend_run_id: str
    positive_prompt: str
    negative_prompt: str
    variation_axes: dict[str, Any]
    references_used: list[dict[str, Any]]

class ConceptBackend(Protocol):
    def healthcheck(self) -> dict[str, Any]:
        ...

    def generate(self, request: ConceptRequest) -> list[GeneratedConcept]:
        ...
```

The agent may add more fields, but not fewer. This is the minimum contract.

## Workflow Template Contract

Store ComfyUI workflow templates under:

- `tools/2d-sprite-and-animation/workflows/`

Required templates:

- `concept_txt2img.json`
- `concept_refine_img2img.json`

These templates must be parameterized by the server rather than hard-coded inline as giant Python dicts.

## Reference Feeding Rules

Reference handling must be explicit and backend-specific.

Reference categories:

- `identity`
- `costume`
- `style`
- `prop`

Storage rules:

- uploaded or local reference files must be copied into the project under `references/`
- each reference must have typed metadata in `brief.json`

ComfyUI handling rules:

- reference images must be uploaded through `POST /upload/image`
- uploaded filenames must be inserted into the workflow template nodes used for image conditioning
- style references and identity references may use different workflow nodes or weights

If the installed ComfyUI workflow or node set does not support a reference type, surface a clear error instead of silently ignoring that reference.

## Refinement Strength Definition

Refinement strength is required for refinement runs.

It maps to img2img-style denoise strength for the ComfyUI refinement workflow.

Allowed UI values:

- `subtle`
- `medium`
- `strong`

Required backend mapping:

- `subtle` -> `0.25`
- `medium` -> `0.45`
- `strong` -> `0.65`

The server may store both the named value and the numeric denoise value.

## Timeout, Retry, and Failure Policy

The current tool is local-only and mostly deterministic. External backend integration changes that.

Required behavior:

- connection timeout: 3 seconds
- per poll interval: 1 second
- concept job timeout: 180 seconds
- refinement job timeout: 180 seconds
- no automatic rerun of failed generation jobs
- one immediate retry is allowed for a transient HTTP request failure before the job is marked failed
- backend validation errors must be surfaced to the UI
- missing workflow templates, missing nodes, and invalid backend responses must fail loudly

Do not silently switch to the procedural backend on failure.

## Compatibility and Migration Rules

Schema changes in this iteration must be backward-compatible.

Rules:

- existing projects must continue to load
- missing fields must be filled with sensible in-memory defaults
- old projects do not need an eager migration pass
- new fields may be written when an old project is next saved
- old concept boards with 4 concepts remain valid historical runs
- new concept runs must generate 6 concepts
- old projects must not crash because they lack lineage, metrics, typed references, or the new brief schema

## New and Updated Data Files

Use these project-level files:

- `project.json`
- `brief.json`
- `character_spec.json`
- `history.json`
- `layered_character.json`
- `rig.json`
- `animation_templates.json`
- `qa_report.json`

Do not add a separate `metrics.json`.

Metrics must be derived from `history.json`.

### `history.json`

`history.json` is the source of truth for:

- concept generation runs
- refinement runs
- user review actions
- job summaries

Keep only metadata and file paths. Do not store large image payloads in history.

Required retention:

- retain the last 50 jobs per project
- retain all concept and refinement run summaries unless the project is archived

## Concept Count Rules

Make the counts explicit and consistent:

- initial concept generation produces exactly 6 concepts
- refinement produces exactly 4 concepts
- the UI labels must reflect those counts
- old projects with 4-concept historical runs remain valid

Prop variation is new behavior in this iteration. If varied, it must remain within the same prop family. Example:

- short sword -> saber or falchion is allowed
- sword -> staff is not allowed unless the user explicitly refines the prop

## Workstreams

### Workstream 1: Replace the Fake Concept Generator

Implement a real concept pipeline using ComfyUI.

Required work:

- add a ComfyUI-backed `ConceptBackend` implementation
- keep the current procedural concept path only as debug fallback
- store workflow templates in `tools/2d-sprite-and-animation/workflows/`
- generate 6 initial concepts per run
- preserve a shared identity core across all concepts
- vary controlled axes:
  - silhouette
  - outfit complexity
  - palette direction
  - optional within-family prop silhouette variation
- store prompt, negative prompt, seed, backend identifier, backend run ID, variation axes, and references used

Acceptance criteria:

- the default concept path is no longer Pillow placeholder art
- concept outputs come from ComfyUI-generated images
- each concept card records why it differs from the base brief

### Workstream 2: Build a Better Structured Brief

Replace shallow prompt normalization with a richer brief builder.

Required work:

- expand the normalized brief to include:
  - role or archetype
  - silhouette intent
  - outfit and materials
  - prop
  - palette mood
  - shape language
  - mood or tone
  - side-view readability constraints
- preserve the original raw prompt
- add explicit intake fields in `tools/2d-sprite-and-animation/index.html`
- keep prompt-only entry supported, but enrich it with defaults
- support backward-compatible loading of old briefs

Acceptance criteria:

- the user can steer concepts with structured fields instead of prompt-only trial and error
- `brief.json` contains meaningful art-direction data

### Workstream 3: Make References Real

Reference inputs must affect concept generation.

Required work:

- distinguish between identity, costume, style, and prop references
- copy references into the project `references/` directory
- store typed reference metadata in `brief.json`
- feed references into ComfyUI workflows via uploaded image inputs
- record which references were actually used in each generation run

Acceptance criteria:

- concepts visibly respond to provided references
- the backend metadata shows which references influenced the run

### Workstream 4: Turn Refinement Into Real Iteration

Refinement must produce new visual outputs.

Required work:

- replace the current `/refine` mutation-only behavior with a refinement generation flow
- refinement must branch from the selected concept
- the user must choose:
  - one attribute group to change
  - a new target value
  - a refinement strength
- generate exactly 4 refined variants per refinement run
- preserve locked attributes
- record lineage from selected concept to refinement run

Acceptance criteria:

- refining `palette` changes palette while preserving silhouette and outfit when those are locked
- a refinement run creates visible new concept outputs

### Workstream 5: Review UX, History, and Metrics

Concept review, history, and derived metrics should share one source of truth.

Required work:

- add concept review actions:
  - approve
  - favorite
  - reject
- add a side-by-side compare panel
- define compare UX concretely:
  - selected concept fixed on the left
  - clicked comparison concept on the right
  - optional quick toggle between the two
- add zoomed concept preview
- add "regenerate similar" on any concept
- add concept run summaries visible in the UI
- store concept and refinement lineage in `history.json`
- derive and display:
  - concept runs per project
  - approvals per run
  - rejects per run
  - refinements per selected concept
  - time to approved concept

Acceptance criteria:

- the user can compare concepts without reading raw JSON
- the review workflow supports compare-and-converge
- metrics are visible and derived from recorded history

### Workstream 6: Lightweight Heuristic Triage

Do not build a heavy semantic scoring system in this iteration.

Required work:

- add cheap pre-display heuristic checks only for:
  - duplicate or near-duplicate outputs
  - background cleanliness
  - bounding-box occupancy
  - connected-component count as a rough clutter proxy
- mark flagged concepts as `warning` or `system-demoted`
- do not claim semantic certainty for side-view correctness or single-character compliance

Out of scope for this iteration:

- CLIP scoring
- VLM or LLM vision judging
- custom classifier training

Acceptance criteria:

- obvious duplicate or visually broken outputs are demoted
- the system does not pretend to solve hard semantic CV problems it is not actually solving

### Workstream 7: Production-Honesty UX

The UI must become more honest about current system maturity.

Required work:

- add stage maturity badges:
  - `real`
  - `experimental`
  - `placeholder`
- use a config file as the source of truth:
  - `tools/2d-sprite-and-animation/stage-maturity.json`
- update stage descriptions and helper copy to reflect actual implementation status
- add a warning before downstream production steps if upstream stages are still synthetic or experimental

Specific strings that must be reviewed in `index.html`:

- hero title and subtitle
- concept section helper text
- refine section helper text
- layer review copy
- rig review copy
- QA and export gate labels
- any remaining "production-ready" phrasing that is not currently true

Acceptance criteria:

- the UI no longer overstates current capability
- stage maturity labels come from one config source rather than scattered literals

### Workstream 8: Strengthen Downstream QA Honesty

The next pass does not need full production-grade validation, but it must remove fake certainty.

Required work:

- remove hard-coded `True` checks in `run_qa()`
- add real image-based checks where practical:
  - alpha presence
  - border clipping
  - bbox jitter
  - duplicate-frame detection
  - spritesheet ordering validation
- if a check is not implemented, it must appear as `not_implemented`, not `pass`
- make layer review and rig review summaries explicitly state whether assets are synthetic or extracted

Acceptance criteria:

- QA status is based on actual implemented checks
- incomplete checks no longer silently count as pass

### Workstream 9: Session, Project, and Job QoL

The tool should be easier to resume and branch.

Required work:

- persist job summaries to `history.json`
- preserve active project selection in local storage
- add project duplication
- define duplication semantics:
  - copy `project.json`, `brief.json`, `character_spec.json`, `history.json`, `concepts/`, and `references/`
  - do not copy `exports/`, `logs/`, or completed animation renders by default
  - generate a new `project_id`
- add archive instead of delete
- define archive semantics:
  - set `archived_at` in `project.json`
  - hide archived projects by default in the UI
  - do not move folders on disk in this iteration
- show last successful concept and refinement run summaries in the UI

Acceptance criteria:

- page reloads do not feel like lost context
- branching a project does not require manual folder work

### Workstream 10: Dependencies, Tests, and Repository Hygiene

Clean up the tool and make new dependencies explicit.

Required work:

- add a tool-local dependency file:
  - `tools/2d-sprite-and-animation/requirements.txt`
- include all required Python dependencies with version pins
- include `Pillow` explicitly since it is currently implicit
- keep dependency additions minimal
- add lightweight automated tests for:
  - backward-compatible project loading defaults
  - concept backend request shaping
  - refinement strength mapping
  - `history.json` metrics derivation
  - QA check state handling for `pass`, `fail`, and `not_implemented`
- prefer Python `unittest` or similarly lightweight tooling
- remove `tools/2d-sprite-and-animation/Untitled`
- normalize the trailing-space spec filename
- keep handover and review docs, but move them under a `docs/` subfolder if the tool directory is being cleaned
- update `README.md` if filenames, setup steps, or backend requirements change

Acceptance criteria:

- Python dependencies are explicit
- the tool has basic regression coverage for the new logic
- obvious stray placeholder files are removed or relocated

## File Targets

The agent should expect to modify at least:

- `scripts/sprite_workbench_server.py`
- `tools/2d-sprite-and-animation/index.html`
- `README.md`

The agent should expect to add:

- `tools/2d-sprite-and-animation/workflows/`
- `tools/2d-sprite-and-animation/stage-maturity.json`
- `tools/2d-sprite-and-animation/requirements.txt`
- tests for the sprite workbench

## Priority Order

Implement in this order:

1. Workstream 1: real concept backend
2. Workstream 2: structured brief
3. Workstream 3: reference support
4. Workstream 4: real refinement
5. Workstream 5: review UX, history, and metrics
6. Workstream 6: heuristic triage
7. Workstream 7: production-honesty UX
8. Workstream 8: QA honesty improvements
9. Workstream 9: session, project, and job QoL
10. Workstream 10: dependencies, tests, and hygiene

## Definition of Done For This Iteration

This iteration is done when all of these are true:

- the default concept board is generated by ComfyUI, not placeholder geometry
- initial generation produces 6 concepts and refinement produces 4
- references influence concept generation through the real backend path
- refinement produces new visual outputs and records lineage
- the review workflow supports compare, reject, favorite, and regenerate-similar
- history and derived metrics are recorded in `history.json`
- the UI clearly labels real, experimental, and placeholder stages
- QA no longer reports success for stubbed checks
- backward compatibility is preserved for old projects
- dependencies and basic regression tests are added
