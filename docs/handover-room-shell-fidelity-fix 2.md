# Handover: Room Shell Fidelity Fix (Level Design + QA Review)

**Purpose:** Single source for reviewers and implementers: verified code findings, alignment with the Room Shell Fidelity Audit Fix Plan, acceptance criteria, and scope/approval boundaries.

**Status:** Review complete — implementation not started in this handover.

**Owners:** Level Design (footprint / concavity intent), QA (validators + regressions + evidence), Engineering (implementation per delivery sequence).

---

## 1. Executive summary

Concave (e.g. L-shaped) **unified shell** (`room_shell_foreground`) can degrade to a **rectangle-normalized** result because:

1. **Shared post-Gemini fit path** — `room_shell_foreground` uses `_fit_foreground_frame_image_to_size`, which trims edge-connected background and **crops to bounding box** before resize, breaking fixed canvas and silhouette fidelity.
2. **Validation gap** — `inside_ratio` (silhouette band underfill) is computed but **not enforced**; only `shell_silhouette_overreach` is hard-failed today.
3. **Dead guardrails** — Some thresholds compare occupancy/luminance fractions to **&lt; 0.0**, which cannot trigger for normal [0, 1] fractions.
4. **v3 kit classification** — `room_shell_foreground` has **no** `METADATA_BY_COMPONENT_TYPE` entry in `scripts/environment_v3/kit.py`, so it defaults to **decor**-like semantics instead of structural shell.

The audit fix plan (two slices) remains valid: **Slice 1** stops geometry corruption and tightens validation; **Slice 2** makes polygon shell geometry authoritative across planning, runtime, and contracts (requires explicit founder approval for broad payload changes).

---

## 2. Problem statement (user-visible)

For polygon rooms, the unified shell should **follow the chamber silhouette** (including concave cutouts). Today, pipeline and classification issues can produce **boxed fills**, **wrong crops**, or **decor-layer false positives** in v3, undermining trust in the room editor / environment pipeline.

---

## 3. Verified code findings

### 3.1 Shared fit path (root cause candidate)

| Location | Finding |
|----------|---------|
| `scripts/room_environment_system.py` — `_generate_bespoke_component_from_references` | Both `foreground_frame` and `room_shell_foreground` call `_fit_foreground_frame_image_to_size` after generation. |
| `_fit_foreground_frame_image_to_size` | Uses `_trim_edge_connected_background` then **crops** via `getbbox()` before `resize` to target size. |

**Implication:** Shell output is not guaranteed to keep **fixed canvas size** or **exact silhouette alignment** through this step.

### 3.2 Post-punchout validation

| Finding | Code reality |
|---------|----------------|
| Underfill not hard-failed | `inside_ratio` computed; comment states underfill is advisory; only `outside_ratio > 0.16` → `shell_silhouette_overreach`. |
| Boxed rectangular shell on L room | May avoid overreach while still violating L fidelity — needs explicit underfill / concavity-preservation errors per plan. |

### 3.3 Dead or ineffective thresholds

| Check | Issue |
|-------|--------|
| `top_edge_fill < 0.0` | `alpha_occupied_fraction` ∈ [0, 1] — condition never true. |
| Pre-punchout `min(corner_fill_vals) < 0.0` | Same class of issue for luminance `occupied_fraction`. |

Replace with meaningful floors or remove; avoid leaving misleading “guardrails” in code.

### 3.4 v3 kit (`scripts/environment_v3/kit.py`)

| Finding | Detail |
|---------|--------|
| No `room_shell_foreground` in `METADATA_BY_COMPONENT_TYPE` | `_component_metadata` falls through to **decor** default for unknown types not in structural/background sets. |
| Default `allowed_zones` | Can collapse toward slot group (e.g. foreground), not **walls** / **shell_surfaces** — reinforces wrong v3 validation behavior. |

### 3.5 Room editor UI (`room-layout-editor.html`)

| Finding | Detail |
|---------|--------|
| `roomWizardBespokeComponentUsesGemini('room_shell_foreground')` | Returns **true** — UI knows shell is special. |
| `foreground_frame` in “stretch” set | Does **not** implement Python fit/postprocess; server owns behavior. |

### 3.6 Reference ordering (partial)

| Finding | Detail |
|---------|--------|
| `_prefix_iteration_reference_refs` | For `room_shell_foreground`, keeps silhouette-first intent and inserts iteration preview at index ≤ 2. |
| Gap | **Initial** non-iteration ref list order should be audited where refs are first assembled (plan item: silhouette → structural template → palette preview). |

### 3.7 Unused computation

`inside_ratio` is computed in post-punchout validation but **never** drives an error code — either wire to `shell_silhouette_underfill` (or equivalent) or remove to reduce confusion.

---

## 4. Alignment with Room Shell Fidelity Audit Fix Plan

| Plan item | Review verdict |
|-----------|----------------|
| 1 — Separate `room_shell_foreground` fit/postprocess from foreground-frame helper | **Required** — matches shared `_fit_foreground_frame_image_to_size` usage. |
| 2 — Reference order (silhouette → structure → preview) | **Verify** full initial ref chain; iteration path already partially ordered. |
| 3 — Harden validators (underfill, L-step, fix dead thresholds) | **Required** — matches unused inside_ratio and dead checks. |
| 4 — Polygon-authoritative shell metadata | **Slice 2** — contract work; keep bbox for compatibility. |
| 5 — v3: structural shell, walls / shell_surfaces | **Required** — matches missing `METADATA_BY_COMPONENT_TYPE`. |
| 6 — Runtime/review polygon-aware composition | **Phased** — minimum: same mask/envelope as generation; document approximate collision if deferred. |
| 7 — No silent border_piece fallback when polygon unified shell is active | **Must trace** `MV_ROOM_SHELL_FOREGROUND` + manifest paths in runtime/generator; add explicit test. |

---

## 5. Delivery sequence (recommended)

1. **Failing tests first** — L-shape synthetic shell, boxed-shell validator failure, rectangle compatibility.
2. **Split** `room_shell_foreground` off `_fit_foreground_frame_image_to_size` (preserve canvas; no bbox crop to “clear” interior for shell; shell-specific processing only before punchout).
3. **Tighten validators** until new regressions pass; fix dead thresholds.
4. **v3** — Add `room_shell_foreground` metadata: structural class, `allowed_surfaces` including `walls`, `allowed_zones` including `shell_surfaces`; adjust validation rules that currently false-block shell.
5. **Slice 2** — Metadata in plan/runtime, compositor consumption, collision/support follow-up.

---

## 6. QA acceptance criteria (evidence)

| ID | Criterion | Pass signal |
|----|-----------|-------------|
| AC-1 | Fixed canvas after shell generation | Output dimensions equal room target size; no unintended crop from trim/bbox. |
| AC-2 | L-room missing quadrant | After punchout, removed quadrant stays **transparent**; shell mass stays in polygon-derived band. |
| AC-3 | Boxed shell rejection | Full rectangular fill on L-shaped room **fails** with underfill/concavity error, not only generic overreach. |
| AC-4 | v3 kit | `room_shell_foreground` entries are **structural**, count toward shell structure, no default decor safe-zone blockers for shell alone. |
| AC-5 | Rectangle regression | Standard rectangular rooms still generate, validate, and render with new shell path. |
| AC-6 | Fallback | With `MV_ROOM_SHELL_FOREGROUND=1` and valid polygon, **no silent** authoritative fallback to `border_piece` for room shell (trace + test). |

**Visual honesty:** Any claim of compositor correctness requires inspecting the **saved artifact** (PNG/composite), not only passing Python tests.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Stricter validators increase generation retries | Tune thresholds using synthetic fixtures; retry prompts already exist for some components. |
| Slice 2 contract drift across projects | Founder approval before persisting new required fields; version manifests / feature flags if needed. |
| Runtime still rect-assumptive until Slice 6 | Document non-authoritative paths; single mask source of truth for generation vs review. |

---

## 8. Approvals

| Change class | Founder approval |
|----------------|------------------|
| Tests, validator tightening, shell-specific fit split, v3 metadata correction for `room_shell_foreground` | Not required per plan (confirm if org policy differs). |
| Broader planner/runtime payload contract and persisted geometry across projects | **Required** before implementation. |

---

## 9. Key file references

| File | Relevance |
|------|-----------|
| `scripts/room_environment_system.py` | `_generate_bespoke_component_from_references`, `_fit_foreground_frame_image_to_size`, `_trim_edge_connected_background`, shell validation, silhouette band mask. |
| `scripts/environment_v3/kit.py` | `METADATA_BY_COMPONENT_TYPE`, `_component_metadata`, defaults for unknown types. |
| `room-layout-editor.html` | `roomWizardBespokeComponentUsesGemini` — Gemini vs stretch (UI only). |
| `index.html` | Bespoke manifest, `room_shell_foreground` runtime loading (compositor review for Slice 2). |
| `tests/room_environment_system.test.py` | Existing shell/silhouette tests — extend for L-shape and boxed-shell. |

---

## 10. Open questions for implementer

1. Exact **initial** reference order for first-generation `room_shell_foreground` (all code paths into `_generate_image_from_references`).
2. Whether **`inside_ratio`** thresholds should be polygon-aware (different L vs rectangle) from day one or stepwise.
3. **Collision / support** data: confirm what stays approximate in Slice 1 and schedule Slice 2 polygon-following data if needed.

---

## 11. Next actions

| Owner | Action |
|-------|--------|
| Engineering | Implement delivery sequence §5; link PR to this doc. |
| QA | Define golden fixtures + AC checklist (§6); run targeted shell + v3 suites. |
| Level Design | Confirm L-room footprint test cases match production room wizard polygons. |
| Founder | Approve Slice 2 scope when ready to change persisted plan/runtime contracts. |

---

*End of handover.*
