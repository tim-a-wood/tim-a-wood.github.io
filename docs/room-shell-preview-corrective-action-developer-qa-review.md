# Developer & QA joint review: room shell / preview corrective action plan

**Date:** 2026-04-10  
**Scope:** `docs/room-shell-preview-corrective-action-plan.md` vs current implementation (primarily `scripts/room_environment_system.py`; room wizard UI in `room-layout-editor.html` delegates generation/approval to the server).

**Tests:** Not executed for this review (documentation-only step). Coverage assessment is based on reading `tests/room_environment_system.test.py`.

**Visual evidence:** Artifact screenshots listed in the corrective-action plan were not re-opened in this session; findings below combine the written plan with traced code and existing tests.

---

## 1. Room editor / pipeline — what the code actually does

| Area | Implementation note |
|------|---------------------|
| **Shell band geometry** | `_room_shell_silhouette_band_mask` builds an outer ring by dilating the chamber polygon (`MaxFilter`) and subtracting the inner fill. Band width is derived from `~12%` of `min(w,h)` (clamped 24–220 px). That morphological recipe can produce **uneven apparent thickness** on concave or asymmetric footprints (corners vs straights), which matches the plan’s “inconsistent wall thickness” diagnosis at the algorithm level. |
| **Contract vs guide colors** | Constants: `ROOM_SHELL_CONTRACT_BAND_RGB` = warm gold `(232, 176, 84)`; `ROOM_SHELL_GUIDE_RGB` = cool grey `(104, 114, 124)`; clear opening `(8, 12, 16)`. Contract and guide **share the same `band_mask`** but **different band colors** — the plan’s “two color languages for the same shape” is accurate in code. |
| **Silhouette debug** | `_write_bespoke_room_silhouette_reference` paints the band in black on `ROOM_SHELL_SILHOUETTE_CLEAR_RGB` — very dark clear — so **low human legibility** is structurally expected unless contrast is improved. |
| **Material ref ordering** | `_bespoke_reference_images_for_component` for `room_shell_foreground` builds refs in order: **contract → guide → material** (when material build succeeds). Matches the plan and `test_room_shell_references_use_contract_map_guide_and_material_reference_in_order`. |
| **Material swatch source** | `_room_shell_material_reference` **prefers `template_path` when it exists** (the biome `foreground_frame` asset). `_patch_score` rewards high max luminance among other signals — **keyed green can win**, consistent with the plan. |
| **Level-3 previews** | `_generate_level3_image_with_gemini` saves the model image **as returned** (`image.save(path)`); **no** post-step mask/crop to the room polygon. Fallback `_render_level3_image` draws a full **768×432** frame with polygon overlay, not a shape-cropped interior — aligns with “rectangular scene + footprint overlay” risk. |
| **Preview approval** | `approve_room_environment_preview` checks `preview_id` exists and then sets approved state; **no** image-quality, perspective, or layout validation — matches QA gap in the plan. |
| **“Hall” → ruins** | `_keyword_theme` maps `("ruin", "cathedral", "crypt", "hall")` → `"ruins"`. Used from `_normalize_spec_response` when building theme from AI fields + description — so **generic “hall” in combined text can force `ruins`** when `themeId` is missing/weak, as the plan states. |

**Room editor HTML:** The Environment wizard surfaces generate/approve/build; it does not implement shell reference math — **fixes land in Python (and any server wiring)**, not in layout markup alone.

---

## 2. Assessment of the corrective-action plan

### Strengths

- **Root-cause ordering is sound:** Input refs (contract, guide, material) are generated **before** shell generation; fixing Slice 1–2 before prompt-only tuning matches the dependency graph in code.
- **Slices match real functions:** Named functions (`_room_shell_silhouette_band_mask`, `_write_room_shell_contract_map_reference`, `_room_shell_reference_guide`, `_room_shell_material_reference`, `_generate_level3_image_with_gemini`, `approve_room_environment_preview`, `_keyword_theme`) are the right levers.
- **Global QA gates** (saved artifacts, no visual claims without inspection) align with `AGENTS.md` and the room-environment decision log spirit.
- **Executing Slice 1 + 2 together** as a “shell-input stabilization pass” is coherent: material ref currently **depends on** `template_path` first, so fixing the band geometry **and** the material source addresses two failure modes that compound.

### Gaps / risks to tighten before execution

1. **Slice 1 — “consistent wall thickness”:** The current algorithm is a **single global band width** + morphological dilation. A visually even perimeter may require a **different geometric strategy** (e.g. offset curve / distance field, or per-edge thickness with explicit rules), not only parameter tuning. The plan should allow **algorithmic options** if visual QA still fails after one pass.
2. **Slice 2 — “fail hard”:** Today `_room_shell_material_reference` returns `False` on failure and the caller **falls back** to `approved_preview_path` or `template_path` as raw refs. “Fail hard” implies **no silent fallback** to misleading images — **explicitly** change `_bespoke_reference_images_for_component` behavior when material ref is required.
3. **Slice 3 — scope and cost:** Post-generation **mask/crop** needs a defined **alpha mask** from the same footprint as the shell (and handling of Gemini aspect ratio vs 1600×1200 shell). Worth a short **spec note** on resolution and letterboxing before implementation.
4. **Slice 4 — precedence:** `_normalize_spec_response` already prefers `raw.get("themeId")` when present; the fix is partly **ensuring Copilot/UI always emits `themeId` when user picks a theme**, and **narrowing `_keyword_theme`** so “hall” alone does not override explicit non-ruins intent. The plan should mention **explicit `themeId` wins** in code as well as heuristics.
5. **Tests:** Existing tests assert **order** of refs, **non-identity** of contract vs guide, and **band mask existence** — not **uniform band thickness**, **green rejection**, or **preview crop**. The plan’s new QA tasks are **necessary**; expect non-trivial test fixtures (synthetic PNGs or geometry cases).

---

## 3. Alignment with execution recommendation

| Statement | Verdict |
|-----------|--------|
| Execute Slice 1 + 2 first as shell-input stabilization | **Agree** — aligns with code and dependencies. |
| Skipping ref fixes and tuning prompts only → bad inputs | **Agree** — material ref and band mask are upstream inputs. |
| Founder decisions on L3 shape-crop default and `hall` vs `ruins` | **Agree** — code supports both as product/policy choices (`approve_room_environment_preview` / `_keyword_theme`). |

---

## 4. Unit tests (coverage check)

- **Checked:** `tests/room_environment_system.test.py` covers shell ref order, contract map semantics, material ref with synthetic templates, silhouette band mask, and validators after punchout — **not** the new behaviors the plan adds (thickness uniformity, green guard, L3 crop, theme regression).
- **Not run:** For this documentation-only review; when executing slices, run the project’s usual test command for `tests/room_environment_system.test.py` after changes.
- **Acceptance / test report:** Per repo rules, update `tests/test_report.md` when code changes land; no automatic update in this documentation-only step.

---

## Summary table (Developer + QA)

| Slice | Plan accuracy vs code | Ready to execute? |
|-------|------------------------|-------------------|
| **1** Shell reference | High — same mask, gold vs grey, dark silhouette | Yes, with possible algorithm follow-up |
| **2** Material ref | High — template-first + scoring favors bright green | Yes, with explicit “no bad fallback” |
| **3** Preview shape | High — no post-crop in Gemini path | Yes, after founder call on default crop |
| **4** Ruins drift | High — `hall` in `_keyword_theme` | Yes, combine with explicit `themeId` behavior |

---

## Standard output (Agent OS)

**Recommendation:** Treat the plan as **execution-ready** for Slice 1–2 after adding **explicit fallback behavior** for material ref (Slice 2) and **accepting** that Slice 1 may need **more than one** geometry approach if the band-mask approach hits a ceiling.

**Risks:** (1) Morphological band may not reach “even thickness” without a new representation. (2) Slice 3 may interact with Gemini output size/aspect. (3) Slice 4 changes without UI/contract guarantees could still leave `themeId` empty.

**Confidence:** **High** for code-path alignment with the plan; **Medium** for how much Slice 1 improves perceived thickness without a second design pass.

**Founder approval needed:** **Yes** — same as the corrective-action plan: default L3 shape-cropping; whether `hall` should imply `ruins`.

**Next actions:** Approve the plan as written or adjust Slice 1–2 acceptance criteria; then implement Slice 1–2, regenerate R1 refs, **visually inspect** saved artifacts per the honesty gate in `AGENTS.md`, then extend tests and run the suite.

---

## Note on status files

No edits were made to `engineering-status.json`, `qa-status.json`, or `os-dashboard.html` for this review-only deliverable.
