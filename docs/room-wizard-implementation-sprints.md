# Room wizard — implementation sprints (actionable)

This document turns [`room-creation-wizard-plan.md`](room-creation-wizard-plan.md) into **demonstrable sprints**: each sprint ends with something you can **show in a demo** or **sign off in a checklist**. Sprint ids use **RW-1 … RW-n** (Room Wizard) to avoid confusion with [`room-editor-agent-task-spec.md`](room-editor-agent-task-spec.md) Sprints 1–4.

**Rules**

- **No skip wizard** for new rooms; **Add Room** enters the wizard.
- **Single file** `room-layout-editor.html` for UI unless a small shared module is extracted (same pattern as `room-layout-export-package.js`).
- After each sprint: update `tests/test_report.md`, run existing unit tests, add tests for new pure logic, commit, push (per repository Cursor rules).

---

## Sprint overview

| Sprint | Codename | Demo outcome (one sentence) |
|--------|----------|-------------------------------|
| **RW-1** | Vertical slice | Add Room → phase rail → Layout fields → Review → **Export JSON** works. |
| **RW-2** | Neighbors | Layout includes **adjoining room**, **align**, **hatch height**; data visible on global map. |
| **RW-3** | Terrain | **Terrain** phase edits **uneven** walkable surfaces on footprint; visible in Room view. |
| **RW-4** | Environment | **Environment** phase applies **tags / theme** to room; persisted in JSON. |
| **RW-5** | Objects & assets | **Objects** phase: place core entities + **local asset import** stub. |
| **RW-6** | Preview | **Per-tab preview** + **placeholder player** movement (separate from main canvas). |
| **RW-7** | Flight-deck parity | **Locked steps**, **blocking reasons**, **progress** string; sprite-style UX. |
| **RW-8** | Workbench & polish | **Asset Workbench sync** when API exists; else **docs + spec + hardening**. |

**Suggested order:** RW-1 → RW-2 → … linear. RW-8 can split: **RW-8a** polish always; **RW-8b** sync when unblocked.

---

## RW-1 — Vertical slice (shell + Layout + Review)

**Goal:** Prove the product loop: **Add Room** opens the wizard, user completes **Layout** and **Review & Export**, downloads layout without touching Advanced JSON.

### Deliverables

1. **Wizard shell** — Full-width or overlay panel inside `room-layout-editor.html`; `role="dialog"`, focus trap, Esc/close behavior defined.
2. **Phase rail** — Five labels: **Layout | Terrain | Environment | Objects | Review & Export**; **Layout** and **Review** active; middle three **locked** (disabled + tooltip “Coming in a later update” until RW-3+).
3. **Add Room** — Intercepts current `addRoom()` flow: **always** opens wizard for the new room (room row may be created first with defaults, then wizard edits that room).
4. **Layout phase (minimal)** — Fields: display name, room id (auto-suggest `nextRoomId()`), footprint preset (small/medium/large) **or** width×height; writes to **current room** in `state.data`.
5. **Review phase** — Plain-language summary; **`validateLayout`** results; buttons: **Export JSON**, **Export runtime**, **Open game** (reuse existing handlers); link to validation panel.
6. **Dirty state** — Wizard edits mark layout dirty; closing wizard returns to main editor with room selected.

### Tasks (checklist)

- [x] Introduce `state.roomWizard`: `{ active, phase, roomId, touched }` (+ `room-layout-wizard-footprint.js` for axis-aligned footprint).
- [x] Wire `#addRoom` → `openRoomWizard()` after `addRoom()` creates room.
- [x] Build phase rail component (HTML + CSS matching editor tokens).
- [x] Implement Layout panel markup + bind to wizard room.
- [x] Implement Review panel + `validateLayout`, `downloadJson`, `downloadExportPackage`, `openGameWithLayout`.
- [x] Lock Terrain / Environment / Objects with disabled + title tooltip.
- [x] Confirm on close when `roomWizard.touched` (after user edits in wizard).

### Demo script (5 min)

1. Open `room-layout-editor.html` (local server if needed).
2. Click **+ Add Room** → wizard appears with **Layout** selected.
3. Change room display name, pick footprint preset.
4. Click **Review & Export** → see validation summary.
5. Click **Export JSON** → file downloads; open file and show `rooms` contains new room.
6. Close wizard → main canvas shows new room in selector.

### Definition of done

- [ ] Demo script passes without console errors.
- [ ] No regression: existing rooms still load; **Add Room** without wizard is **not** available (wizard is mandatory for new room).
- [ ] `tests/test_report.md` updated; unit tests green.

### Out of scope

- Neighbor alignment, terrain, preview, asset import.

---

## RW-2 — Neighbors & alignment (Layout complete)

**Goal:** Layout phase matches product spec: **adjoining room**, **align**, **corridor/hatch height** on the connecting edge.

### Deliverables

1. **Adjoining room** — Dropdown of other rooms (exclude current); optional “none yet.”
2. **Align with neighbor** — Action applies **snap** of `global` (and optionally suggests edge link) so shared boundaries line up; uses existing global map math where possible.
3. **Match opening height** — Control to align **door Y** or **platform floor** at threshold with neighbor’s matching edge (exact behavior depends on edge index selection — minimum: pick **edge** on each room for the connection).
4. **Global map** — After wizard actions, switching to **Global Map** shows consistent positions/links (same `state.data`).

### Tasks

- [ ] UI: adjoining room, edge pickers (or simplified), align button, height match.
- [ ] Implement `alignRoomToNeighbor(roomId, neighborId, …)` pure helpers + tests.
- [ ] Persist `edgeLinks` / `global` updates; run `validateLayout` after apply.
- [ ] Document edge cases (no neighbor, single room in project) in UI copy.

### Demo script

1. Project with ≥2 rooms; add third via wizard.
2. In Layout, pick **adjoining room** = existing room; **Align** → global map shows rooms flush.
3. **Match hatch height** → door/platform Y consistent at threshold (show in Room view + inspector).

### Definition of done

- [ ] Demo script passes; L1 passes for linked rooms.
- [ ] New unit tests for alignment helpers.

### Out of scope

- Terrain phase content; preview.

---

## RW-3 — Terrain phase (uneven terrain)

**Goal:** **Terrain** tab unlocks; user builds **uneven** walkable surfaces on the **footprint** from Layout — not a single flat floor.

### Deliverables

1. Unlock **Terrain** when Layout is “complete” (footprint + name; rules in code).
2. **Terrain** UI: presets (flat / two-level / stepped), **add ledge** actions, or **embedded mini-editor** that mirrors **platform** placement for **this room only**.
3. All edits write **platforms** (and any new terrain fields) on **current room**; visible in existing **Room view** canvas.
4. Copy: **floors / ledges / uneven ground** — hide internal jargon in primary labels.

### Tasks

- [ ] Define `isLayoutCompleteForTerrain(room)` predicate.
- [ ] Terrain panel: presets apply platform arrays (or call existing placement logic).
- [ ] Optional: height histogram or “lowest floor” line for clarity.
- [ ] Tests: preset → expected platform count / y spread.

### Demo script

1. Complete Layout → **Terrain** unlocks.
2. Apply “two-level” preset → two distinct heights visible in Room view.
3. Run validation → L2 warnings acceptable; L1 passes.

### Definition of done

- [ ] Demo script passes; platforms visible and editable in main canvas after wizard.

### Out of scope

- True mesh / non-rect terrain (future engine).

---

## RW-4 — Environment phase

**Goal:** **Environment** tab sets **look & feel** tags / theme for the room; data persists for export.

### Deliverables

1. Unlock **Environment** after Terrain (or after Layout if Terrain empty — product decision: default **after Terrain**).
2. Fields: theme tags, optional swatches, optional `meta`-level vs **room-level** theme field (extend JSON schema in one place; document in `room-layout-export-package.js` if needed).
3. **Review** shows environment summary.

### Tasks

- [ ] Add `room.theme` or `room.environment` object (versioned) — align with game loader or stub for now.
- [ ] UI: tag chips, preset themes.
- [ ] Export: include in runtime room slice if applicable.

### Demo script

1. Set theme “cave” → export runtime → room file contains theme.
2. Reload editor → theme still visible in wizard Review.

### Definition of done

- [ ] Schema documented; demo passes.

---

## RW-5 — Objects & assets (import)

**Goal:** **Objects** phase for doors, keys, movers, etc., plus **local asset import** (paths or embedded refs); **stub** for future Asset Workbench **sync**.

### Deliverables

1. Unlock **Objects** after Environment (or configurable order).
2. Guided placement flows reusing **inspector** patterns (minimal fields first).
3. **Import asset** — file picker → store reference under room or project (structure documented); **no Workbench sync** yet unless API ready.
4. Placeholder UI: “Sync from Asset Workbench (coming soon)” disabled.

### Tasks

- [ ] Define `room.assetRefs[]` or similar; document in `docs/room-editor-creative-decisions.md`.
- [ ] Wire file picker + validation (type, size limits).
- [ ] Tests for ref serialization.

### Demo script

1. Add door + key in Objects phase.
2. Import small image → appears in list / binds to prop placeholder.
3. Export JSON contains refs.

### Definition of done

- [ ] Demo passes; Workbench sync remains stub.

---

## RW-6 — Per-tab preview

**Goal:** Each **phase tab** includes a **preview panel** (not the main canvas): embedded view, **placeholder player**, move with keyboard (and touch if feasible).

### Deliverables

1. Fixed **preview** region in wizard shell; updates per phase (Layout: footprint only; Terrain: platforms; …).
2. Implementation: **iframe** `index.html#layout=…` **or** minimal embedded scene (decide in sprint; **RW-1 §10** open decision).
3. **Placeholder player** (capsule or sprite) with **move** inside room bounds.
4. Performance: throttle updates if layout JSON large.

### Tasks

- [ ] Preview component: mount, teardown, message passing if iframe.
- [ ] Hash or postMessage current room JSON to preview.
- [ ] Movement keys documented on screen.
- [ ] If agent spec blocks iframe, document **exception** in `room-editor-agent-task-spec.md` (appendix).

### Demo script

1. Open each phase tab → preview updates.
2. Move placeholder player in preview → no crash.
3. Main canvas still authoritative for editing.

### Definition of done

- [ ] Demo passes on desktop; optional mobile note in test report.

---

## RW-7 — Flight-deck parity (locking & progress)

**Goal:** Match **Sprite Workbench** feel: **step_statuses**, **blocking_reasons**, **locked** tabs, **“N/M complete”** string.

### Deliverables

1. **Prerequisite graph** — e.g. Terrain locked until Layout valid; etc.
2. **Blocking tooltips** — why a tab is locked (reuse sprite pattern).
3. **Progress** — `wizardProgressSummary(project)` analogue for room wizard.
4. **Optional persistence** — `sessionStorage` or room-scoped `wizard_state` in layout JSON (versioned).

### Tasks

- [ ] Map phases to `step_statuses` enum.
- [ ] Centralize `canEnterPhase(phase)` checks.
- [ ] UI: progress text + rail styling for complete/active/locked.

### Demo script

1. Fresh room → only Layout open.
2. Complete Layout → Terrain unlocks; others still locked until prior complete.
3. Progress reads “3/5 complete” when on Environment.

### Definition of done

- [ ] Demo script passes; UX review against sprite workbench.

---

## RW-8 — Workbench sync & hardening

**Goal:** **Asset Workbench sync** when API exists; otherwise **release hardening**: accessibility, error boundaries, docs, [`room-editor-agent-task-spec.md`](room-editor-agent-task-spec.md) **Sprint RW** verification checklist.

### Deliverables

1. **If API available:** sync asset ids from workbench project; document contract.
2. **Always:** E2E manual checklist; fix P0 bugs; update `README` / `docs/room-creation-wizard-plan.md` “shipped” table.
3. Append **Room Wizard** verification section to agent task spec (or keep in this file).

### Tasks

- [ ] Integrate sync endpoint (TBD).
- [ ] Fallback: import-only path unchanged.
- [ ] Full demo: novice path from Add Room → export runtime → open game.

### Definition of done

- [ ] Sign-off checklist complete; stakeholder demo approved.

---

## Cross-sprint dependencies

```mermaid
flowchart LR
  RW1[RW-1 Shell] --> RW2[RW-2 Neighbors]
  RW2 --> RW3[RW-3 Terrain]
  RW3 --> RW4[RW-4 Environment]
  RW4 --> RW5[RW-5 Objects]
  RW5 --> RW6[RW-6 Preview]
  RW6 --> RW7[RW-7 Parity]
  RW7 --> RW8[RW-8 Ship]
```

**Parallelism:** RW-6 (preview) could start after RW-2 if preview is **Layout-only** first — optional risk reduction (spike preview in parallel with RW-4).

---

## Testing strategy (all sprints)

| Layer | What |
|-------|------|
| **Unit** | Pure helpers: alignment, `buildLayoutFromWizardDraft`, phase predicates — in `tests/room-wizard-*.test.js` or `room-layout-wizard.js`. |
| **Manual** | Demo script per sprint; record for stakeholders. |
| **Regression** | Existing `game-logic.test.js`, `room-editor-export.test.js` stay green. |

---

## Documentation updates (rolling)

| When | Update |
|------|--------|
| Each sprint | `tests/test_report.md` — note manual wizard demo for sprint RW-n. |
| RW-1 done | `docs/room-creation-wizard-plan.md` §7 — replace phase table with “see room-wizard-implementation-sprints.md”. |
| RW-8 done | `docs/room-editor-agent-task-spec.md` — add **Room Wizard (RW)** verification checklist; `docs/room-editor-creative-decisions.md` — shipped phase. |

---

## References

- [`room-creation-wizard-plan.md`](room-creation-wizard-plan.md) — product vision, five phases, preview, assets.
- [`room-editor-export-package.js`](../room-layout-export-package.js) — runtime export shape.
- `tools/2d-sprite-and-animation/app/core-helpers.js` — `FLIGHTDECK_PHASES`, UX reference.
