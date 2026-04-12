# Developer + QA Joint Review: Room Shell Preview Corrective Action Plan

**Date:** 2026-04-10
**Reviewers:** Developer agent, QA agent
**Document under review:** [room-shell-preview-corrective-action-plan.md](room-shell-preview-corrective-action-plan.md)
**Verdict:** Plan is grounded and execution-ready, with amendments noted below.

---

## 1. Code Verification of Root Causes

### A. Shell Geometry — CONFIRMED

The plan correctly identifies `_room_shell_silhouette_band_mask` ([room_environment_system.py:3660](../scripts/room_environment_system.py#L3660)) as the shared geometry source for all three shell references (silhouette, contract, guide). The band width calculation at line 3674 uses a fixed 12% of `min(w, h)` clamped to 24–220px:

```python
band_px = int(round(min(out_w, out_h) * 0.12))
band_px = max(24, min(220, band_px))
```

This produces a uniform dilation via `MaxFilter`, which cannot represent variable wall thickness at concave elbows or L-shaped corners. The plan's claim that "the ring is not being represented in a way that reads like a clean, consistent wall-thickness instruction" is accurate — `MaxFilter` dilation is isotropic, so concave inner corners get a thicker band than straight edges and convex turns get a thinner band. For non-rectangular rooms, this is geometrically guaranteed to produce uneven thickness.

### B. Gold vs Grey Color Split — CONFIRMED

Constants at [line 2478–2479](../scripts/room_environment_system.py#L2478):
- `ROOM_SHELL_CONTRACT_BAND_RGB = (232, 176, 84)` — warm gold
- `ROOM_SHELL_GUIDE_RGB = (104, 114, 124)` — cool grey

The contract map ([line 3707](../scripts/room_environment_system.py#L3707)) and guide ([line 3738](../scripts/room_environment_system.py#L3738)) use the same `_room_shell_silhouette_band_mask` geometry but render in different colors. The Gemini prompt at [line 6488](../scripts/room_environment_system.py#L6488) explicitly tells the model to interpret the gold band as "required occupied shell surface." The guide serves as a structural envelope reference. Having two color languages for the same shape is confirmed as unnecessary ambiguity — especially since the guide is appended as a separate reference image alongside the contract.

### C. Material Reference Poisoning — CONFIRMED

`_room_shell_material_reference` ([line 3758](../scripts/room_environment_system.py#L3758)) takes `template_path` as its first argument. The caller at [line 7460](../scripts/room_environment_system.py#L7460) passes the biome template path, which resolves to `foreground_frame.png` for the `room_shell_foreground` component type (mapped at [line 2457](../scripts/room_environment_system.py#L2457): `"template_component_type": "foreground_frame"`).

The patch picker (`_best_material_patches`, line 3813) selects patches by `_patch_score` which rewards high edge energy, high stddev, and high max luminance. The green-keyed opening in the foreground frame template is bright and high-contrast — it will naturally score highest. There is **no green-rejection filter** anywhere in the material extraction pipeline. The plan's root cause is correct.

### D. Silhouette Debug — CONFIRMED

`_write_bespoke_room_silhouette_reference` ([line 3686](../scripts/room_environment_system.py#L3686)) renders black shell occupancy over `ROOM_SHELL_SILHOUETTE_CLEAR_RGB = (8, 12, 16)` — near-black. Black-on-near-black is structurally valid but useless for human review.

The `_refs` directory currently contains **both** the original silhouette and the retry silhouette (`room_shell_foreground-silhouette.png` + `room_shell_foreground-retry-silhouette.png`), confirming the plan's finding that stale artifacts coexist with retry-path artifacts.

### E. Preview Shape — CONFIRMED

`_generate_level3_image_with_gemini` ([line 4204](../scripts/room_environment_system.py#L4204)) saves the Gemini response image directly at line 4260 with no post-generation cropping or masking. The room geometry polygon is sent as a conditioning image, but the output is accepted as a full rectangle. There is no `_room_shell_silhouette_band_mask`-style post-processing on previews.

### F. Ruins Drift — CONFIRMED

`_keyword_theme` ([line 1492](../scripts/room_environment_system.py#L1492)) maps `"hall"` → `"ruins"` at line 1502. The word "hall" is a generic architectural term that should not force a biome. The project's `style_family` is also hardcoded to `"dark fantasy ruins"` at line 104. Both paths converge to reinforce ruins.

---

## 2. Test Coverage Gaps

### Current coverage (from [room_environment_system.test.py](../tests/room_environment_system.test.py))

| Area | Existing Tests | Gap |
|------|---------------|-----|
| Shell band mask | `test_room_shell_silhouette_band_mask_creates_border_zone` (line 1463) | Only checks band exists and has nonzero pixels. Does **not** test thickness consistency at concave elbows. |
| Shell contract map | `test_room_shell_contract_map_has_three_semantic_regions` (line 2166) | Checks three color regions exist. Does **not** check visual consistency of band thickness. |
| Contract vs guide | `test_room_shell_contract_map_is_not_identical_to_structural_guide` (line 2182) | Confirms they differ. Does **not** question whether they *should* differ. |
| Shell guide | `test_room_shell_structural_guide_uses_single_shell_band_tone` (line 2197) | Checks single tone. No thickness validation. |
| Material reference | `test_room_shell_material_reference_has_no_frame_or_enclosed_negative_space` (line 2210), `test_room_shell_material_reference_prefers_high_information_patch` (line 2235) | Checks for no enclosed negative space and high-info patches. Does **not** reject green-keyed patches or placeholder colors. |
| Pre-punchout validation | `test_validate_room_shell_before_punchout_tolerates_dark_top_band` (line 1432) | Corner fill thresholds are set to 0.0 (line 3655), meaning the pre-punchout gate currently **cannot fail on corner gaps**. |
| Preview shape | None | **No tests** for post-generation room-shape masking or cropping. |
| Theme drift | None | **No tests** for `_keyword_theme` behavior or ruins drift from generic terms. |

### Critical finding: Pre-punchout gate is a no-op

At line 3655:
```python
if min(corner_fill_vals) < 0.0:
    errors.append("shell_corner_gap_pre")
```

A fill fraction can never be negative — this gate will never fire. This was likely relaxed to stop false positives on dark shells (per the comment at line 3646), but it means there is currently **no functional pre-punchout corner validation**. The plan should address this.

---

## 3. Plan Assessment by Slice

### Slice 1 — Shell Reference Contract: APPROVE WITH AMENDMENTS

**Strengths:**
- Correctly prioritizes fixing inputs before re-running generation.
- Developer tasks are specific and actionable.
- QA gates are concrete.

**Amendments needed:**
1. **Task 1 should specify the fix**: Replace `MaxFilter` dilation with a geometry-aware band that walks each edge segment and extrudes a fixed pixel width perpendicular to the local edge normal. This produces uniform visual thickness regardless of concave/convex geometry.
2. **Task 2 — merge, don't choose**: Unify to one reference image with the contract's semantic regions (band vs opening vs margin) rendered in the guide's neutral grey palette. The gold color leaks into the model's output palette when used as a reference image. Use a single neutral palette with clearly distinct luminance values.
3. **Add task**: Fix the pre-punchout gate at line 3655 — change `< 0.0` to a real threshold (e.g., `< 0.02` to match the post-punchout gate at line 3591).
4. **QA gap**: Add a test that exercises `_room_shell_silhouette_band_mask` on an L-shaped room polygon and asserts that the band width measured perpendicular to each edge segment falls within a tolerance (e.g., ±15% of target).

### Slice 2 — Debug Material Reference: APPROVE WITH AMENDMENTS

**Strengths:**
- Correctly identifies `foreground_frame.png` as the poison source.
- "Fail hard" requirement is good.

**Authoritative override:**
- Any suggestion in this review to route shell debug material sourcing through `wall_piece`, `ceiling_piece`, or `primary_floor_piece` is superseded.
- Those template families are obsolete for the current shell corrective path and must not be used.

**Amendments needed:**
1. **Developer task 3 needs specifics**: Add a green-channel dominance check in `_patch_score` or as a filter step. Reject any patch where green channel mean exceeds both red and blue channel means by more than a threshold (e.g., 30 units). This catches chroma-keyed green without rejecting natural mossy stone.
2. **Developer task 2 — preferred source order**: Do not use obsolete structural sibling templates (`wall_piece`, `ceiling_piece`, `primary_floor_piece`). Replace `foreground_frame` with a shell-specific source strategy only, such as sanitized shell-specific approved-preview sampling or a deterministic neutral shell debug texture purpose-built for validation.
3. **QA addition**: Add a regression test that creates a fake template image with a bright green region and asserts `_room_shell_material_reference` either rejects the green patch or does not include it in the output.

### Slice 3 — Preview Shape Enforcement: APPROVE WITH CAVEAT

**Strengths:**
- Correctly diagnoses the missing post-generation mask step.
- QA gates are well-defined.

**Caveat — founder decision needed before implementation:**
- Room-shape cropping creates a non-rectangular PNG with transparent margins. This changes the visual contract in the room editor preview panel. The plan correctly flags this for founder approval but should note: if the preview panel currently assumes opaque rectangular images, a background fill or compositing change may be needed in the frontend.
- "Side-view perspective fidelity" validation (task 3) is hard to automate. Recommend making this a human QA checkpoint rather than an automated gate for Slice 3, with automated perspective detection deferred to a later pass.

### Slice 4 — Ruins Drift: APPROVE AS-IS

**Strengths:**
- `_keyword_theme` is a clean surgical fix — remove `"hall"` from the ruins keyword list.
- Project-level `style_family` cleanup is correctly scoped as a separate data change.
- QA tasks are testable.

**No amendments needed.** This is the simplest slice and the fix is unambiguous.

---

## 4. Execution Order Assessment

The plan's recommended order (1 → 2 → 3 → 4) is correct. Slices 1+2 together as one stabilization pass is also correct — the material reference fix is cheap and removing it from the poison path before any regeneration prevents wasted cycles.

**One dependency the plan should note:** Slice 3's preview masking code will likely want to reuse the same `_geometry_footprint_polygon_output_pixels` function that Slice 1's band mask uses. If Slice 1 changes the geometry representation, Slice 3 should be built on top of it, not in parallel.

---

## 5. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| `MaxFilter` replacement changes band shape for all rooms, not just R1 | Medium | Run existing tests + new L-shaped test on multiple polygon fixtures before merging |
| Gold-to-neutral color change breaks Gemini prompt that references specific RGB values | High | The prompt at line 6488 explicitly mentions `ROOM_SHELL_CONTRACT_BAND_RGB` values — **must update the prompt text when changing the constant** |
| Preview cropping reveals that Gemini output doesn't actually follow room shape | Medium | This is a feature, not a risk — it exposes the real quality state |
| Removing `"hall"` from ruins keywords changes theme for existing projects | Low | Only affects future generations; existing saved assets are not regenerated automatically |

---

## 6. Summary Verdict

The corrective-action plan is **well-grounded, correctly diagnosed, and execution-ready**. The root causes are all confirmed in code. The four slices are correctly ordered and scoped.

**Required amendments before execution:**
1. Specify geometry-aware band extrusion to replace `MaxFilter` dilation (Slice 1)
2. Fix the no-op pre-punchout gate at line 3655 (Slice 1)
3. Add green-channel rejection filter for material patches (Slice 2)
4. Source material from structural siblings instead of `foreground_frame` (Slice 2)
5. Update the Gemini prompt RGB references if contract band color changes (Slice 1)

**Founder decisions still needed:**
1. Level-3 previews: room-shape-cropped (transparent margins) or room-shape-composited (dark fill margins)?
2. Should `"hall"` stop implying `"ruins"`? (Plan says yes, we agree.)
3. Is the pre-punchout corner gate intentionally disabled, or should it be restored?
