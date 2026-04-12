# Handover: Room Shell Fidelity — Level Design + QA Joint Review

**Date:** 2026-04-09
**Reviewers:** Level Design Agent + QA Agent (joint)
**Source documents:** Fix Plan (inline), Handover (`docs/handover-room-shell-fidelity-fix.md`), live code review
**Status:** Review complete — Slice 1 implementation cleared to begin

---

## 1. Code Review Findings

### 1.1 Shared fit path — root cause confirmed

**File:** `scripts/room_environment_system.py` lines 7425–7434

```python
# Both component types share the same postprocess call
if component_type in {"foreground_frame", "room_shell_foreground"}:
    ...
    _fit_foreground_frame_image_to_size(output_path, size)
```

`_fit_foreground_frame_image_to_size` (lines 4326–4333) does three things that are wrong for a concave shell:

1. Composites the image onto a fully opaque black backing — collapses transparency
2. Calls `_trim_edge_connected_background` — flood-fills from all four corners and masks any pixel matching corner-seed colors within tolerance 22
3. Crops via `getbbox()` on the resulting mask — **this is the geometry killer**: for an L-shaped room, the corner fill eats into the missing quadrant and the bbox crop normalises the result to the smallest enclosing rectangle

The infrastructure for polygon-following processing already exists (`_room_shell_silhouette_band_mask`, lines 3656–3679, which calls `_geometry_footprint_polygon_output_pixels` and erodes an inward ring). It is used only in post-punchout validation, not in fit/postprocess. The fix is to wire a shell-specific path that keeps canvas size, skips the bbox crop, and leverages this existing mask.

**Level Design verdict:** The fit path will silently rectangularise any concave shell. A valid L-shaped Gemini output can enter this function and leave as a cropped rectangle. This is the single most important code fix in Slice 1.

---

### 1.2 Dead validators — confirmed, with exact locations

**File:** `scripts/room_environment_system.py`

| Location | Dead check | Why dead |
|---|---|---|
| Line 3580 | `if top_edge_fill < 0.0` | `alpha_occupied_fraction` returns `[0.0, 1.0]`; condition is always false |
| Line 3651 | `if min(corner_fill_vals) < 0.0` | Same — `occupied_fraction` is also `[0.0, 1.0]`; always false |

Both append error codes (`shell_top_edge_gap_post`, `shell_corner_gap_pre`) that can never be appended. These look like guardrails but provide zero protection.

**Operative thresholds (working):**

| Line | Check | Threshold |
|---|---|---|
| 3588 | `min(corner_fill_vals) < 0.02` → `shell_corner_gap_post` | ✓ operative |
| 3611 | `outside_ratio > 0.16` → `shell_silhouette_overreach` | ✓ operative |
| 3508 | `opaque_fraction < 0.038` → `shell_rim_mass_low` | ✓ operative |

---

### 1.3 `inside_ratio` — computed, never enforced

Lines 3594–3611 compute both `inside_ratio` (shell mass within the polygon-derived band) and `outside_ratio` (mass outside it). Only `outside_ratio > 0.16` → `shell_silhouette_overreach` is hard-failed. `inside_ratio` is computed and then silently dropped.

**QA consequence:** A perfectly rectangular shell on an L-shaped room can pass every validator today as long as it does not *overflow* the silhouette band. A box that fits inside the bounding rectangle but fills the missing quadrant will have low `outside_ratio` (because the fill stays inside the overall bbox polygon) and produce no error. There is no underfill gate.

---

### 1.4 v3 kit — `room_shell_foreground` absent from metadata

**File:** `scripts/environment_v3/kit.py`

`METADATA_BY_COMPONENT_TYPE` (lines 87–193) has entries for 14+ component types. `room_shell_foreground` is not among them.

`_component_metadata` (lines 211–240) fallback logic for an unknown type:

| Field | Fallback value | Why wrong |
|---|---|---|
| `component_class` | `"decor"` | Not in STRUCTURAL or BACKGROUND sets |
| `allowed_zones` | `["decor_safe_zones"]` | Should be `["shell_surfaces", ...]` |
| `allowed_surfaces` | `["room_shell_foreground"]` | Non-standard surface key; should be `["walls"]` |
| `readability_impact` | `"low"` | Decor default; should be `"high"` for structural |

In v3, the unified shell is treated as a low-readability decor item sitting in the decor safe zone. Any structural shell validation that checks for wall/shell surface presence will not count the unified shell, and any decor safe-zone blocker that the shell physically overlaps will fire incorrectly.

---

### 1.5 Existing test coverage

**File:** `tests/room_environment_system.test.py` (3,575 lines)

| Test | Status |
|---|---|
| `test_validate_room_shell_after_punchout_rejects_hairline_mass` | ✓ exists |
| `test_validate_room_shell_after_punchout_rejects_near_black_shell_tone` | ✓ exists |
| `test_validate_room_shell_before_punchout_tolerates_dark_top_band` | ✓ exists (explicitly confirms dead pre-punchout check) |
| `test_validate_room_shell_after_punchout_rejects_corner_gap` | ✓ exists |
| `test_room_shell_silhouette_band_mask_creates_border_zone` | ✓ exists |
| `test_validate_room_shell_after_punchout_rejects_silhouette_overreach` | ✓ exists |
| L-shaped shell regression | **MISSING** |
| Boxed-shell underfill/concavity failure | **MISSING** |
| Shell fit/postprocess preserves canvas size | **MISSING** |
| v3 classification structural regression | **MISSING** |
| Runtime/composite polygon fidelity | **MISSING** |
| Border-piece silent fallback with polygon active | **MISSING** |

The existing suite tests post-punchout validation well but does not exercise the fit/postprocess path at all, does not test polygon-specific geometry outcomes, and has no v3 classification tests.

---

## 2. Plan Alignment — Item by Item

| Plan item | Code verdict | Priority |
|---|---|---|
| **1 — Split `room_shell_foreground` fit path** | Confirmed required. Lines 7425–7434 show direct shared call. `_fit_foreground_frame_image_to_size` will rectangularise any concave output. Polygon-aware infrastructure (`_room_shell_silhouette_band_mask`) is already available to anchor a shell-specific path. | **Slice 1 blocker** |
| **2 — Reference order (silhouette → structural → preview)** | Iteration path is partially ordered (`_prefix_iteration_reference_refs`). Initial first-generation ref chain order not directly visible in reviewed sections. Needs targeted audit of all call sites that assemble the initial `refs` list for `room_shell_foreground`. | **Verify before Slice 1 ships** |
| **3 — Harden validators (underfill, L-step, dead thresholds)** | Confirmed required. Two dead thresholds (3580, 3651), one unused metric (`inside_ratio`). Fix: replace `< 0.0` with meaningful floors; wire `inside_ratio` to a new `shell_silhouette_underfill` error at a tuned threshold; add a polygon-concavity check that verifies the missing quadrant stays transparent post-punchout. | **Slice 1 blocker** |
| **4 — Polygon-authoritative shell metadata** | Not present anywhere in reviewed code. Bbox only. Correct to defer to Slice 2. The `_use_unified_room_shell()` flag (line 1525) is the right gate — Slice 2 metadata should key off this. | **Slice 2** |
| **5 — v3 reclassify as structural** | Confirmed required. Missing from `METADATA_BY_COMPONENT_TYPE`. Fix is a single dict entry: `component_class: "structural"`, `allowed_surfaces: ["walls"]`, `allowed_zones: ["shell_surfaces", ...]`. Low regression risk. | **Slice 1 (low risk)** |
| **6 — Runtime polygon-aware composition** | Cannot fully verify without reading `index.html` compositor path. Plan's minimum bar (preserve concave punched-out opening visually, no rect-assumption in review compositing) is achievable without full engine rewrite. Compositor call site must be traced before Slice 1 is marked done. | **Slice 1 minimum / Slice 2 full** |
| **7 — No silent border_piece fallback** | `_use_unified_room_shell()` (line 1525) gates the path. Whether the generator falls back to `border_piece` on failure is unconfirmed — the fallback branch after a failed `room_shell_foreground` generation needs explicit tracing. Untested today. | **Trace required before Slice 1 ships** |

---

## 3. Level Design Assessment

### Geometry fidelity intent vs code reality

The design intent is unambiguous: the unified shell must follow the chamber polygon, including concave cutouts. The code has the right geometric primitives — `_room_shell_silhouette_band_mask` produces a correct inward ring from the polygon, and `_geometry_footprint_polygon_output_pixels` maps room geometry to output pixels correctly.

The failure is in the **postprocess step**, not in generation or the mask logic. The Gemini model may produce a correctly shaped shell. The fit path then destroys it. This means even a perfectly tuned prompt cannot reliably produce correct L-shaped output through the current pipeline.

### L-shape test fixtures required

For Level Design sign-off, the following polygon fixtures are needed as synthetic test inputs:

| Fixture | Description | Key assertion |
|---|---|---|
| Standard L | Missing bottom-right quadrant (~25% of bounding box area) | Pixel mass in missing quadrant < 2% of quadrant area after punchout |
| Wide L | Missing narrow top-right strip (tests shallow concavity) | Same |
| Rectangular control | Full bounding box | Regression baseline — must still pass with new path |

The 2% quadrant threshold is more specific than current `inside_ratio`/`outside_ratio` which measure band membership, not per-quadrant concavity preservation.

### Reference ordering risk

If the approved preview image (palette/material) is positioned earlier in the reference list than the silhouette, Gemini's attention may weight scene composition over geometry discipline. The iteration path's partial ordering is the correct pattern and must be applied to the initial generation path with the silhouette explicitly first.

---

## 4. QA Assessment

### Acceptance criteria cross-check

| AC | Criterion | Current coverage | Gap |
|---|---|---|---|
| AC-1 | Fixed canvas after shell generation | None | Assert output dimensions == room target size after fit path |
| AC-2 | L-room missing quadrant stays transparent | None | L-shape synthetic fixture + pixel-count assertion on missing quadrant post-punchout |
| AC-3 | Boxed shell rejected with underfill/concavity error | None | Rectangular fill on L-room must fail with underfill/concavity error, not only overreach |
| AC-4 | v3 structural classification | None | Kit metadata lookup for `room_shell_foreground` returns structural class + walls surface |
| AC-5 | Rectangle regression | Implicit (existing tests use rect geometry) | Verify explicitly after fit path split |
| AC-6 | No silent border_piece fallback | None | With `MV_ROOM_SHELL_FOREGROUND=1` + valid polygon, assert no border_piece path executed |

All six AC gaps map directly to the five test items in the plan. Each has a clear pass/fail signal.

### Threshold calibration notes for `inside_ratio`

Before wiring `inside_ratio` to a hard failure, calibrate against:

- Valid rectangular shells — `inside_ratio` close to 1.0 by construction
- Valid L-shells — expected ~0.65–0.80 depending on L geometry and band width
- Boxed-fill on L-rooms — inflated `inside_ratio` because rectangular fill hits band pixels in the missing quadrant

**Suggested starting underfill threshold:** `inside_ratio < 0.55` → `shell_silhouette_underfill`

Must be verified against at least 3–5 real or synthetic shell outputs before Slice 1 ships. Use the existing `test_room_shell_silhouette_band_mask_creates_border_zone` test as a fixture basis.

### Pre-commit hook note (observed during review)

The `hardcore-goldstine` worktree has a failing pre-commit hook:
```
[Errno 2] No such file or directory: 'scripts/check_escalation_conditions.py'
```
This is a stale worktree path issue unrelated to shell fidelity. Resolve by cleaning the worktree or updating the hook path before any Slice 1 commits land there.

---

## 5. Open Questions (unresolved after code review)

| # | Question | Owner | Blocking? |
|---|---|---|---|
| 1 | What is the exact initial ref list order for first-generation `room_shell_foreground`? Which function assembles `refs` before `_generate_image_from_references` is called? | Engineering | Yes — must confirm silhouette is first |
| 2 | What does the generator do when `room_shell_foreground` returns `False, err`? Does it fall back to `border_piece` silently? Needs trace of the caller of `_generate_bespoke_component_from_references` for this type. | Engineering | Yes — AC-6 depends on it |
| 3 | What `inside_ratio` range do current real shell outputs land in for valid rectangular rooms? Needed to set the underfill floor without breaking the happy path. | QA + Engineering | Yes — needed before wiring the threshold |
| 4 | Does the review/composite path in `index.html` read `room_shell_foreground` output with a fixed rect assumption? | Engineering | Partial — needed before Slice 1 runtime claim |

---

## 6. Overall Verdict

**The plan is correct and the code confirms every finding in the handover.**

Slice 1 is well-scoped and achievable without contract changes. The three highest-leverage items — in order — are:

1. **Split the fit path** (`scripts/room_environment_system.py` lines 7425–7434): one targeted code change; direct geometry corruption fix
2. **Wire `inside_ratio` to a hard error** and kill the two dead thresholds (lines 3580, 3651): straightforward validator surgery
3. **Add `room_shell_foreground` to `METADATA_BY_COMPONENT_TYPE`** in `scripts/environment_v3/kit.py`: one dict entry, low regression risk

The L-shape failing test must be written **before** the fit path split so the fix can be verified to make it pass. AC-3 (boxed-shell rejection) requires `inside_ratio` enforcement to exist before it can be written as a positive failure test.

Slice 2 (polygon-authoritative metadata, runtime compositor, delivery sequence items 4–6) requires founder approval and must not begin until Slice 1 regressions are green.

**No blocking objections to beginning Slice 1 implementation.**

---

## 7. Next Actions

| Owner | Action |
|---|---|
| Engineering | Answer open questions 1 and 2 (ref order + fallback trace) before writing any code |
| QA | Create L-shape and rectangular synthetic fixtures; establish `inside_ratio` baseline range (open question 3) |
| Engineering | Write failing L-shape and boxed-shell tests; split fit path; tighten validators; add v3 metadata entry |
| Engineering | Trace `index.html` compositor for rect assumption (open question 4) |
| QA | Run full shell + v3 validation suite against L-shape and rectangular fixtures once Slice 1 lands |
| Founder | Review and approve Slice 2 scope when Slice 1 regressions are green |

---

*End of handover.*
