# Room creation wizard — implementation plan

This document defines **what** the wizard is for, **how** it should behave, and **how** to implement it in phases. It aligns with `docs/room-editor-creative-decisions.md` (level tooling stays separate from the Sprite Workbench).

---

## 1. Purpose

**Problem:** New authors hit the editor with either a full embedded seed layout, a loaded canonical file, or empty states that say “import JSON or add a room” — without guidance on world bounds, naming, or a sensible first room.

**Goal:** A **short, optional guided flow** that:

- Chooses **how** a session starts (continue existing work vs new vs import).
- For **new** layouts, collects **metadata** and creates a **minimal valid** first room (or applies a **template**) so `validateLayout` and export have something coherent to work with.
- Stays **inside** `room-layout-editor.html` (see constraints below).

**Non-goals (v1):**

- Replacing Advanced → JSON import or file-based load.
- Embedding the game for playtest (future).
- Sprite / tileset pipelines (future).

---

## 2. Constraints (from `docs/room-editor-agent-task-spec.md`)

| Constraint | Implication |
|------------|-------------|
| Single HTML file per tool | Wizard UI = **modal or full-screen overlay** in `room-layout-editor.html`, not a new `.html`. |
| No external JS/CSS frameworks | Use existing design tokens, buttons, and patterns from the editor. |
| Preserve `state` and layout JSON shape | Wizard only **produces** `version`, `meta`, `rooms[]` consistent with `room-layout-data.json`. |
| No new HTTP endpoints | Wizard cannot depend on new server APIs (optional: reuse existing `/api/layout` if already used for load). |

---

## 3. Current behavior (baseline)

- **`loadData()`** — Tries API layout → `room-layout-data.json` → localStorage scratch → falls back to **embedded `seedData`** with a status message.
- **`addRoom()`** — Appends a room with fixed defaults: `ROOM_W`/`ROOM_H`, a default axis-aligned polygon, empty platforms, `global` at `(600, 360)`.
- **`meta`** — Present on real files (`worldWidth`, `worldHeight`, `grid`, optional `notes`); wizard should set or confirm these for **new** layouts.

These hooks are the integration points: wizard completion should call something equivalent to `initializeData(newLayout, message)` and optionally skip redundant seed load paths when we intentionally “start fresh.”

---

## 4. Proposed user flows

### 4.1 When to show the wizard

**Recommended (v1):**

1. **On first meaningful visit** — If there is no localStorage scratch for this editor key **and** the page would otherwise only show embedded seed (or user explicitly chose “new”), offer the wizard. *Alternatively*, keep startup as today and add **File / Start menu: “New layout…”** to avoid surprising users who expect seed data.

2. **Explicit entry** — Menu item: **“New layout (wizard)…”** always available; confirms discard if dirty.

**Defer:** Auto-opening wizard on every cold load — too disruptive for devs who rely on seed/canonical data.

### 4.2 Wizard branches

| Branch | Steps |
|--------|--------|
| **A — Open / continue** | No wizard; `loadData()` as today (or pick project). |
| **B — Import JSON** | File picker or paste (reuse Advanced panel logic or a dedicated step); validate → `initializeData`. |
| **C — New guided layout** | Steps in §5. |

---

## 5. Wizard steps (v1 — recommended)

Linear flow for branch **C**; Back/Next navigates between steps.

| Step | ID | Content |
|------|-----|--------|
| **1** | `intent` | Title + short copy. Choices: **Guided new layout** (continue) · **Import JSON** (jump to import subflow) · **Cancel** (exit wizard, keep current data). |
| **2** | `world_meta` | **Layout name** (stored in `meta.notes` or new optional `meta.title` if you add it — prefer `meta.notes` prefix `title: …` until schema is extended). **Grid** (default 32). **World width / height** — map to `meta.worldWidth` / `meta.worldHeight` (must stay consistent with `index.html` / export `engine_hints`). |
| **3** | `first_room` | **Room ID** (validate: unique, matches existing `nextRoomId()` rules). **Display name**. **Room size** — presets (e.g. Small / Medium / Large using multiples of grid) or numeric width × height; drives `room.size` and initial **polygon** bounds (axis-aligned rectangle from `(margin, margin)` to `(width-margin, height-margin)` in local space). |
| **4** | `spawn_optional` | Checkbox: **Place player start** — if checked, set `playerStart` to bottom-center or center of polygon; if unchecked, leave `null` (L1 validation will warn until placed). |
| **5** | `confirm` | Summary list + **Create layout** → apply state and close wizard. |

**Optional v1.1:** Step **0** “Template” — Empty room vs “Single room hub” vs “Two-room stub” (pre-creates rooms + edge links). Adds complexity; ship after bare v1 works.

---

## 6. Technical design

### 6.1 State machine

- **`wizard` object** on `state` or module-local: `{ open: boolean, step: string, draft: { meta, firstRoom } }`.
- Pure functions: `buildLayoutFromWizardDraft(draft) → { version, meta, rooms: [one room] }`.
- **`openWizard()`** / **`closeWizard()`** — toggle overlay visibility, reset draft when closing without apply.

### 6.2 Integration with load

**Option A (minimal):** Wizard only runs when user clicks “New layout…”; builds JSON in memory and calls `initializeData`, `setDirty(true)`. Does not change `loadData()` order.

**Option B:** Add query param `?wizard=1` or localStorage flag `roomEditor.showWizardOnce` to auto-open on first visit — implement only after Option A is stable.

### 6.3 UI

- **Overlay:** full-viewport `div` with `role="dialog"`, `aria-modal="true"`, focus trap for accessibility.
- Reuse **btn-primary**, **btn-secondary**, typography from sidebar/header.
- Mobile: stack steps vertically; same content as desktop.

### 6.4 Validation

- Before **Create layout**: client-side checks (numeric bounds, room id pattern `R\d+` or project’s `nextRoomId()`).
- After apply: optionally call **`validateLayout(state.data)`** and show toast if L1 fails (should not happen if polygon ≥ 3 vertices and ids unique).

---

## 7. Implementation phases

| Phase | Scope | Done when |
|-------|--------|-----------|
| **P0** | Spec + this plan | You are reading it. |
| **P1** | “New layout (wizard)” menu + overlay Steps 1–5 + `buildLayoutFromWizardDraft` + `initializeData` | User can create a fresh single-room layout without touching JSON. |
| **P2** | Import branch inside wizard (file + validate) | Branch B works without opening Advanced. |
| **P3** | Template step + multi-room stubs | Optional presets for common starts. |
| **P4** | First-run auto-offer + `?wizard=1` | Onboarding polish. |

---

## 8. Testing

- **Unit:** `buildLayoutFromWizardDraft` in a small `room-layout-wizard.js` (mirroring `room-layout-export-package.js`) with Node tests, or inline pure function in HTML + `window` export for tests.
- **Manual:** New layout → export JSON → confirm `meta` and first room → open in game or reload editor.

---

## 9. Documentation updates after implementation

- Append **Sprint 5** (or “Wizard”) section to `docs/room-editor-agent-task-spec.md` with verification checklist.
- Update `docs/room-editor-creative-decisions.md` — replace “wizard TBD” with link to this plan and note shipped phase.

---

## 10. Open decisions

1. **Discard guard** — Block “New layout” if `state.isDirty` unless Confirm dialog (recommended: yes).
2. **`meta.title`** — Add optional field to schema vs stuffing title into `meta.notes` (prefer explicit `meta.title` in v1 if you are willing to extend the JSON contract everywhere it is read).
3. **Seed vs wizard** — Whether default open still loads embedded seed; likely **yes**, wizard only on explicit “New layout.”

---

## 11. References

- `room-layout-editor.html` — `loadData`, `addRoom`, `initializeData`, `ensureRoomShape`
- `room-layout-export-package.js` — `engine_hints` / `meta` alignment
- `docs/room-editor-creative-decisions.md`
- `docs/room-editor-agent-task-spec.md` — Global Constraints
