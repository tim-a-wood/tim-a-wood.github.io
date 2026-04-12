# Room bespoke compositor — minimal stack (intense-dev plan)

**Status:** Slice 1 implemented (runtime opt-in). Default behavior unchanged.  
**Related decisions:** `decisions/2026-03-31-room-environment-quality-pass.md` §202b (premask), §203 (editor overlay).  
**Cross-stack fix (generation + QA + runtime):** `docs/plans/room-bespoke-pipeline-void-and-alignment.md` — use when **baked void / plate collage** in PNGs limits what this runtime track can fix.

---

## Phase 1 — Problem statement

**Goal:** Stop compounding runtime “fixes” on AI plates and unified shells. Prefer a **small, inspectable stack**: scenic background constrained to the walkable footprint, unified shell drawn **on top** with **minimal** extra processing.

**Non-goals (this track):** Replacing Gemini; rewriting the full v3 planner; changing physics tiles in slice 1.

**Class:** Visual / runtime composition.

---

## Phase 2 — Roster

| Role | Scope |
|------|--------|
| Developer | `index.html` compositor branches, flags, tests |
| QA | Contract tests; manual `?minimalBespokeCompositor=1` vs default; capture `runtime-review.png` |
| Visual validation | **Mandatory before default-on:** Human (or delegated reviewer) opens the **exact** saved `runtime-review.png` / playtest frame and records **≥3 concrete observations** per `AGENTS.md` honesty gate. No “looks better” without that receipt. |

---

## Phase 3 — Research (stop rule: enough to choose default)

| Source | Conclusion |
|--------|------------|
| `index.html` `createRoomEnvironmentBackgrounds` | Background already uses **footprint GeometryMask** (`applyRoomInteriorFootprintMask`); extra cost is **feather fades**, **midground** (often disabled), **shell Canvas premask** (`destination-out`). |
| §202b | Premask corrects **bad PNG alpha** vs polygon; it also **adds** processing and can fight founder expectations if assets improve. |

**Open question:** Should minimal mode become default only after **one** golden room’s visual sign-off?

---

## Phase 4 — Implementation spec

### Contract

- **`MINIMAL_BESPOKE_COMPOSITOR`:** `true` when URL contains `minimalBespokeCompositor=1` or `window.__MV_MINIMAL_BESPOKE_COMPOSITOR === true` before boot.
- Applies only when the room has **bespoke background** and/or **unified shell** (same rooms that triggered the heaviest stack).

### Behavior (minimal)

1. **Background:** Unchanged scaling + **polygon interior mask** only. **No feather sprites** (no fade-edge stack).
2. **Shell:** Use **raw** `env-bespoke-{slotId}` texture — **no** `getOrCreatePremaskedShellTexture`. Opening must come from **asset alpha** (generation responsibility).
3. **Midground:** Unchanged vs global `DISABLE_RUNTIME_MIDGROUND` (already off in current tree).

### Rollback

- Remove query flag; or set `window.__MV_MINIMAL_BESPOKE_COMPOSITOR = false`.

### Files

- `index.html` — flag, branches in `createRoomEnvironmentBackgrounds`, `addRoomBespokeUnifiedShellForegroundDecor`
- `tests/game-logic.test.js` — contract strings
- `tests/test_report.md` — note when exercised

---

## Phase 5 — Slices

| Slice | Done when |
|-------|-----------|
| **S1** (current) | Opt-in minimal path merged; tests pass; this doc committed. |
| **S2** | Founder visual gate on **one** project room (e.g. R1): minimal vs premask, saved artifact cited. |
| **S3** | If S2 passes: consider **default** minimal for new builds; keep premask behind `?shellPremask=1` or inverse flag. |
| **S4** | Pipeline: reduce server-side fit/crop on `background_plate` / `room_shell_foreground` only if runtime still wrong **after** S2. |

### Risk register

| Risk | Mitigation |
|------|------------|
| Raw shell opening wrong | S2 visual gate; fall back to premask URL flag (future) |
| Too-bright background without feathers | Tune alpha only in minimal branch after visual evidence |

---

## Phase 6 — Founder checkpoint (answer before S3)

1. Should **minimal** become the **default** if R1 passes visual gate? (Y/N)  
2. If PNG alpha is wrong, prefer **regenerate shell** or **restore premask** as default?  
3. Should midground ever re-enter for unified-shell rooms, or stay off?

---

## Evidence pack (per slice)

- Commands: `node tests/game-logic.test.js`  
- Visual: path to reviewed PNG + 3 bullets  
- Decision log line when default changes
