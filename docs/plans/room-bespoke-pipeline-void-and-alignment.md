# Room bespoke pipeline — void bands, shell alignment, cross-stack fix (intense-dev)

**Mode:** Intense (multi-layer: generation, validation, runtime, tooling).  
**Canonical workflow:** `docs/skills/intense-dev-orchestration.md`.  
**Related:** `docs/plans/room-bespoke-compositor-minimal.md` (engineering opt-in only; **founder: do not use** for QA — see `decisions/2026-03-31-room-environment-quality-pass.md` §206), `decisions/2026-03-31-room-environment-quality-pass.md`.

**Founder update (2026-04-12):** Use **default** runtime compositor only (§202b). **Defer** strict new auto-reject validators; favor prompts + regen + manual review on QA R1 until calibration matures.

---

## Phase 1 — Problem statement

**Observed:** Playtest and review screenshots show **large solid black regions**, **fragmented “islands”** of scenic art, and **shell / background misalignment**. A/B between default runtime and `?minimalBespokeCompositor=1` can look **identical** because both paths ultimately sample the **same on-disk PNGs**.

**Root cause (evidence):** Inspection of project bespoke outputs (e.g. `tools/2d-sprite-and-animation/projects-data/.../R1/bespoke/R1-background.png` and `R1-room-shell.png`) shows **baked-in black voids and banding** and **discontinuous composition** in the raster itself — not only mask or premask behavior in `index.html`.

**Goal:** Establish an **end-to-end contract** so scenic plates and unified shells are **continuous under the walkable footprint**, **free of prompt-induced black wedges**, and **runtime composition** only applies **masking / ordering** that assumes coherent alpha and interior fill. **Strict automated rejection** is a later phase (§206: avoid over-tight validation now; use prompts + regen + manual review first).

**Non-goals (initial slices):** Replacing Gemini with another model; full v3 planner rewrite; changing game physics or room graph schema.

**Constraints:** No silent mutation in the editor (founder-approved apply-before-save); respect `AGENTS.md` **visual validation honesty gate** for any “fixed” claim (open exact PNG, ≥3 concrete observations).

---

## Phase 2 — Roster and pre-scope

| Role | Owns | Out of scope |
|------|------|----------------|
| **Orchestrator** | Slice ordering, conflict resolution, founder checkpoints | Implementing every line of code alone |
| **Developer** | Python pipeline + runtime JS + tests | Art direction beyond prompt text supplied by Creative |
| **QA** | Unit/integration coverage, acceptance mapping, regression matrix | Final pixel approval without cited artifacts |
| **Research** | Index/decisions sync, spike stop-rules | Open-ended unbounded exploration |
| **Visual / Creative (as needed)** | Palette/motif language, reference packs, human signoff on golden room | Validator threshold tuning without examples |

**Must read:** `AGENTS.md` (research protocol, visual gate), `decisions/2026-03-31-room-environment-quality-pass.md`, `research/library/INDEX.md`, `prompts/project_plan.md`, `docs/plans/room-bespoke-compositor-minimal.md`.

---

## Phase 3 — Research (concise)

| Source | Conclusion |
|--------|------------|
| Bespoke PNGs on disk (`.../bespoke/R1-*.png`) | **Black bands and L-shaped voids are present in source art**; runtime cannot fully “heal” them. |
| `docs/plans/room-bespoke-compositor-minimal.md` | Minimal compositor correctly **reduces** feather/premask variables; it does **not** replace bad plates. |
| `scripts/room_environment_system.py` (grep: void, wedge, holdout) | Prompts already **discourage** black wedges; model still violates — need **stronger constraints and/or post-validate + regen**. |
| `index.html` (`applyRoomInteriorFootprintMask`, `getOrCreatePremaskedShellTexture`) | Footprint mask **reveals** interior pixels; holes in mask or **opaque black in texture** read as **void**. |
| `tests/test_report.md` history | Many prior slices fixed **ceiling**, **shell punchout**, **capture letterbox** — current failure mode is **scenic plate collage + void**. |

**Open questions**

1. Should `background_far_plate` / unified scenic slot be **single-pass full-bleed** only (no multi-rectangle collage language anywhere)?
2. Acceptable **maximum** near-black pixel ratio inside chamber bbox before auto-reject? (Calibrate on one golden + one bad example.)
3. Is a **theme-color underfill** in runtime an acceptable **safety net** when alpha is correct but art is dark — or forbidden as masking the problem?

**Recommended next step:** **Prompt / regen** and manual gates on QA R1; **Slice A** (automated void/collage reject) only when thresholds are **conservative** and founder agrees — see §206 (avoid over-tight validation now).

---

## Phase 4 — Architecture sketch (data flow)

```text
  room-layout-editor (RW-4b)
           |
           v
  sprite_workbench_server.py ----configure----> room_environment_system.py
           |                    ^                  |
           |                    |                  v
           |         room_environment_v3.py   (Gemini + validators,
           |         (planner slots)           prompts, punchout, post)
           |                    |                  |
           +--------------------+------------------+
                                v
                 projects-data/.../bespoke/*.png
                                |
                                v
  index.html (Phaser) <--- load textures <--- manifest + asset paths
           |
           +-- footprint GeometryMask, shell depth, optional minimal/premask branches
```

**Contracts (target)**

- **C1 — Plate continuity:** For each scenic `background_*` / primary plate slot, **≥ (1 − ε)** of the chamber interior bbox must be **non–near-black** OR explicitly tagged as intentional pit/hazard (separate slot), where ε is test-calibrated.
- **C2 — No collage void:** Generated plate must not contain **large rectangular black regions** separating horizontal bands (validator: connected-components on near-black mask, or run-length bands).
- **C3 — Shell rim:** Unified shell must pass existing punchout validators **and** new **pre-punchout void-band** checks on the **raw** model output (before tone normalize), so black bars are not “fixed” only by postprocess.
- **C4 — Runtime:** Background = masked plate only; shell = on top; **optional** underfill layer documented and feature-flagged.

---

## Phase 4b — Files and modules expected to change

Grouped by layer (any slice may touch only a subset).

| Layer | Path | Why impacted |
|-------|------|----------------|
| **Planner / schema** | `scripts/room_environment_v3.py` | Slot definitions, optional merge of fragmented scenic components, `background_plate` sizing. |
| **Generation + validation** | `scripts/room_environment_system.py` | Prompts for `background_far_plate`, `room_shell_foreground`, structural slots; **new** `_validate_*` for void/collage/black-ratio; retry text; optional deterministic fill/clamp **only if** founder approves. |
| **Server API** | `scripts/sprite_workbench_server.py` | `_sync_room_environment_system_config`, error surfacing, optional QA metrics in ping/build summary. |
| **Runtime** | `index.html` | `createRoomEnvironmentBackgrounds`, `applyRoomInteriorFootprintMask`, unified shell path, optional **underfill** sprite; `MINIMAL_BESPOKE_COMPOSITOR` interaction. |
| **Editor** | `room-layout-editor.html` (+ inline JS) | Surface validator failures, regen UX, link to which slot failed new codes. |
| **Styles** | `room-wizard-workbench-shell.css` | Only if editor exposes new QA chips / banners (trivial token compliance). |
| **Tests** | `tests/room_environment_system.test.py`, `tests/game-logic.test.js` | New validator tests; compositor flag contracts; golden PNG fixtures if allowed. |
| **Acceptance / report** | `tests/acceptance_tests.md`, `tests/test_report.md` | Manual rows for “no void bands in bespoke export”; update when behavior changes. |
| **Config** | `.env.local.example` | New thresholds or feature flags (`MV_BESPOKE_VOID_*`, underfill flag). |
| **Decision log** | `decisions/2026-03-31-room-environment-quality-pass.md` | Log chosen thresholds, underfill policy, and any “postprocess heal” rejection. |
| **Outputs** | `tools/2d-sprite-and-animation/projects-data/*/room_environment_assets/` | Regenerated artifacts after pipeline fix — not hand-edited. |
| **Research** | `research/library/INDEX.md` | Research Agent: index this plan + finding “baked void dominant vs runtime”. |

---

## Phase 5 — Slices (atomic, with done definitions)

| Slice | Inputs | Outputs | Done when | Out of scope |
|-------|--------|---------|-----------|--------------|
| **A — Asset QA gates (deferred strictness)** | Current validators; §206 | Optional **light** checks or metrics only until calibration matures; **no** broad auto-reject tightening without founder signoff | Any new code is conservative (warn / log / narrow fixtures), not “fail closed” on borderline art | Strict ratio / collage hard-fail in this phase |
| **B — Prompt contract** | Slice A error codes | Tightened prompts: **single coherent interior**, **no black separator bands**, explicit **full-bleed** language for plate | Prompt unit tests updated; one manual Gemini regen documents new attempt metadata | Changing model ID |
| **C — Runtime safety net** | §205.3 | **Off** — no underfill per founder | N/A | Any underfill before clean PNGs |
| **D — Editor surfacing** | Slice A codes | Build summary / slot row shows **void/collage** failures clearly | Manual: user can see why regen fired | Full redesign of Results UI |
| **E — Close the loop** | Slices A–D | Regenerate calibration room pack; update decision log § | `runtime-review.png` + bespoke PNGs pass honesty gate; decision log entry | Expanding to all biomes |

**Per-slice V&V:** Run `python3 tests/room_environment_system.test.py` and `node --test tests/game-logic.test.js` (or project-standard equivalents). Update `tests/test_report.md` when behavior changes.

---

## Risk register (top)

| Risk | Mitigation |
|------|------------|
| Validators false-positive on legit dark pits | Separate **hazard** slots from **plate**; calibrate thresholds on two labeled PNGs; retry prompts before tightening globally |
| Postprocess “heals” hide bad generation | Founder policy: prefer **reject + regen** over aggressive inpaint; log any heal in decisions |
| Runtime underfill masks pipeline debt | Flag off by default; treat as **emergency** only per Slice C |
| Scope creep across `index.html` | Freeze runtime after A–B unless visual gate still fails **with** clean PNGs |

---

## Phase 6 — Founder checkpoint (answer before Slice C/E default)

1. **Reject vs heal:** If the plate fails void-band checks, should the pipeline **always** retry Gemini only, or allow a **deterministic** fill (e.g. expand non-black regions)?
2. **Pits:** Should intentional floor holes be **only** in dedicated hazard slots so the plate validator can be strict?
3. **Runtime underfill:** Allow **optional** flagged underfill, or **forbidden** until assets are clean?
4. **Golden room:** Which project/room id is the **contract** room for signoff (e.g. `room-ai-helpfulness-qa-67562113` R1 vs `RG-R1`)?
5. **Default compositor:** **Resolved in §206** — **do not use** minimal for QA/product path; keep §202b default stack.

Capture answers in `decisions/2026-03-31-room-environment-quality-pass.md` (new subsection) so slices do not re-litigate.

---

## Evidence pack (close-out checklist)

- [ ] This spec + slice table committed
- [ ] Validator tests + commands recorded in `tests/test_report.md`
- [ ] Exact paths to **inspected** before/after PNGs (honesty gate)
- [ ] Decision log updated with thresholds and founder answers
- [ ] Research index points to this plan or a distilled finding doc

---

*Created: 2026-04-12 — orchestration intake for bespoke void/alignment; supersedes single-file thinking.*
