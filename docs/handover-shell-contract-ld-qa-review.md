# Handover: Shell Contract Hardening — Level Design + QA Joint Review

**Date:** 2026-04-09
**Reviewers:** Level Design Agent + QA Agent (joint)
**Source documents:** Contract-First Fix Plan (inline), `docs/handover-room-shell-fidelity-fix.md`, `docs/handover-room-shell-fidelity-ld-qa-review.md`
**Artifacts inspected:** all four files under `artifacts/qa/room-shell-live-debug-2026-04-09/`
**Status:** Review complete — implementation approved to begin

---

## Visual Artifact Inspection (Visual Honesty Gate)

Artifacts inspected directly before any judgment.

**`updated-room-shell-band-preview.png`**
1. Shows three visible regions: narrow dark outer frame → grey-slate shell band → large dark inner rectangle
2. The outer dark frame is rendered as an opaque filled region, not transparent — it reads as "part of the composition"
3. The grey-slate shell band is the only region with material color; it floats between two dark zones

**`updated-room-shell-guide.png`**
1. Pixel-for-pixel identical to `band-preview.png`
2. Two references that are supposed to be distinct inputs are the same image — the model receives the compositional framing template twice

**`updated-room-shell-silhouette.png`**
1. Near-black throughout with a slightly lighter inner rectangle visible at very low contrast
2. The outer margin is dark/filled, not transparent or distinctly flagged — it does not communicate "forbidden zone"
3. Reads as a binary depth cue at best; a model parsing it sees a rectangular scene with an inset frame, same topology as the failure output

**`updated-room-shell-guide-single-tone-preview.png`**
1. Again identical to `band-preview.png` — same nested-frame composition, same grey-slate band
2. Three of the four reference images are effectively teaching the same nested-frame topology

**Visual judgment:** The failure is confirmed in the references themselves. The model is not hallucinating a second frame — it is accurately reproducing the reference topology. The outer dark margin is opaque in the references, so the model renders it with material. The fix must break the reference's outer-margin from being a filled dark region into something the model cannot paint over.

---

## Level Design Assessment

### Contract map semantics — approved with one note

The 3-region contract map (required shell band / required clear opening / forbidden outer margin) is the correct semantic encoding. It solves the root cause: the current references all present the outer margin as an opaque region with the same visual weight as the shell band, which teaches the model to treat the outer margin as part of the scene.

Required properties for the contract map to function:
- The three regions must be visually distinct enough that a diffusion/generation model cannot conflate them — not just slight tone differences; hue or high-contrast separation recommended
- The forbidden outer margin must read as "nothing here" — either fully transparent (preferred) or a strongly signaled exclusion color distinct from both shell band and opening
- The geometry must remain authoritative: same polygon footprint, same band width as today

### Room-shape fidelity — no objection for rectangular rooms

The test room (`test-40b4b333/R1`) appears to be a standard rectangular room. The contract map semantics are unambiguous for this geometry. No concavity concerns for this specific case.

### Level Design flag

The plan should explicitly require that the contract map be generated from the authoritative polygon, not from a rasterized version of the existing band preview. If the contract map is derived by color-shifting the current guide, the spatial proportions will be correct but the outer-margin encoding problem remains. Confirm the contract map writer reads from polygon geometry directly.

---

## QA Assessment

### The plan's QA gate is appropriate and complete

Cross-checking the plan's QA gate against the prior handover acceptance criteria:

| Plan gate item | Maps to AC | Status |
|---|---|---|
| Reference #1 clearly distinguishes 3 regions | New (contract-map specific) | No current test — required |
| Reference #3 is material-only, not full scene | Partial AC-2 analogue | No current test — required |
| Prompt/retry language is biome-neutral | New | No current test — required |
| Validator behavior is unchanged | AC-5 (regression) | Existing rectangular tests cover this |
| Regenerated shell no longer reads as nested frame | Visual honesty gate | Requires artifact inspection after regeneration |
| Visual validation confirms exact saved artifacts inspected | AGENTS.md honesty gate | Must be satisfied — not satisfiable by test pass alone |

### QA concern 1 — overreach regression

The plan's test #5 ("rectangular control room still passes current expectations") is necessary but not sufficient. The validator `shell_silhouette_overreach` gate must be confirmed to still fire correctly on the overreach case — not just that a valid rectangle passes. Recommend adding an explicit test that a shell with material in the outer margin zone still triggers `shell_silhouette_overreach` after the prompt/retry changes. This confirms the validator wasn't accidentally softened by the wording changes.

### QA concern 2 — material-only reference definition

The plan correctly identifies that if the material-only reference is still composition-heavy, the nested-frame behavior may persist. The QA gate needs a concrete pass/fail definition for "material-only."

**Suggested definition:** the reference must contain no enclosed rectangular or frame-shaped region with interior negative space. A material swatch, a tiling surface section, or a cropped wall texture all pass. A cropped room preview that shows an inset dark opening fails.

### QA concern 3 — retry language test specificity

The plan requires retry wording to call out outer/nested frame generically. The test should:
- Assert these specific phrases are absent: "masonry," "stone arch," and any masonry-specific nouns
- Assert these are present: "outer frame," "nested frame," "exactly one shell ring," "exactly one clear opening," "forbidden outer margin"

---

## Overall Verdict

**Level Design: Approved to proceed** — the 3-region contract map approach correctly encodes room-intent geometry. No objection to the scope of this slice. The single pre-condition is that the contract map must derive from polygon geometry, not from re-coloring the existing guide.

**QA: Approved to proceed with three additions:**
1. Add an explicit regression test that `shell_silhouette_overreach` still fires on outer-margin violation after prompt changes
2. Define a concrete pass/fail rule for "material-only reference" before the material reference is accepted — no enclosed frame/negative-space composition allowed
3. After regenerating `R1-room-shell`, artifacts must be inspected directly (not just test passes) before the slice is marked closed — the visual honesty gate in AGENTS.md applies

**No blocking objections. Implementation may begin.**

---

*End of review.*
