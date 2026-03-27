# Room creation wizard — implementation plan

This document defines **what** the wizard is for, **how** it should behave, and **how** to implement it in phases. It aligns with `docs/room-editor-creative-decisions.md` (level tooling stays separate from the Sprite Workbench).

**Contents:** §1 Purpose · §2 Constraints · §3 Current behavior · §4 Flows · §5 v1 stages (per-stage tables + §5.2 order variants) · §5b Brainstorm · §5c Ideas matrix · §6–11 Technical design, phases, testing, open decisions, refs.

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

Linear flow for branch **C**; Back/Next navigates between steps. Skip links (e.g. “Use defaults”) reduce friction on meta/spawn steps if you add them in P1.x.

### 5.1 Stage detail — v1 core path

#### Stage 1 — `intent` (entry)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Separate “I want a guided empty project” from “I have JSON” without forcing either user through the other path. |
| **Primary actions** | **Start guided layout** → go to `world_meta`. **Import JSON** → jump to import subflow (paste or file). **Cancel** → close overlay; **no change** to `state.data`. |
| **Data written** | None. |
| **Validation** | None. |
| **Copy notes** | One sentence on what “guided” creates (one room, valid polygon, editable meta). Avoid implying the game will launch. |
| **Edge cases** | If opened from a menu while already dirty, show discard warning **before** this stage or on **Start guided** (product choice in §10). |

#### Stage 2 — `world_meta`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Set **global** layout parameters the game and export already read via `meta` / `engine_hints`. |
| **Fields** | **Layout title** — human label (→ `meta.title` if added to schema, else first line of `meta.notes`). **Grid snap** — default 32; must match editor snap options where possible. **World width / height** — integers; typical defaults 1600×1200 or 3200×1200 to match `index.html` zones; document min/max (e.g. 800–8000) to avoid absurd values. Optional: **notes** textarea for designer comments (append to `meta.notes`). |
| **Data written** | `meta.worldWidth`, `meta.worldHeight`, `meta.grid`, optional `meta.title` / `meta.notes`. |
| **Validation** | Numbers > 0; width/height divisible by grid **optional** (warn, not block). |
| **Defaults** | Pre-fill from last wizard session in `sessionStorage` **optional**; else project defaults from plan (e.g. Ashen Hollow–style bounds). |
| **Skip** | “Use defaults” → skip to `first_room` with baked constants. |

#### Stage 3 — `first_room`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Create the first **structurally valid** room: polygon ≥ 3 verts, `size` consistent with polygon bounds, unique `id`. |
| **Fields** | **Room ID** — e.g. `R1`; validate against `nextRoomId()` / pattern used in repo. **Display name** — free text. **Footprint** — preset **Small / Medium / Large** (width×height in px, snapped to grid) **or** custom width × height. **Margin** — inset from room edges for polygon (default one grid cell or 160px) so the rectangle isn’t flush with zero. |
| **Geometry** | Axis-aligned rectangle polygon: `(margin, margin)` → `(W-margin, margin)` → `(W-margin, H-margin)` → `(margin, H-margin)` in **room local** space; `room.size` = `{ width: W, height: H }`. |
| **Global placement** | `global: { x, y }` — default center of world canvas in global map (e.g. half world minus half room width) or fixed `(600, 360)` to match `addRoom()` today; document choice. |
| **Data written** | One object in `rooms[]`; empty `platforms`, `doors`, `keys`, `abilities`, `movingPlatforms`, `edgeLinks`, `removedEdges: []`. |
| **Validation** | Unique ID; W/H ≥ minimum room size; polygon vertex count ≥ 3 after `ensureRoomShape`. |

#### Stage 4 — `spawn_optional`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Reduce L1 **L1-006** (“no player start”) immediately for authors who want a clean validation run. |
| **Fields** | Checkbox **Place player start now**. If on: **preset** — floor center-bottom (recommended), room center, or custom x/y (advanced expando). |
| **Data written** | `playerStart: { x, y }` or `null`. |
| **Validation** | If custom, coordinates inside polygon (point-in-polygon) **optional** v1; v1 can clamp to bounding box. |

#### Stage 5 — `confirm`

| Aspect | Detail |
|--------|--------|
| **Purpose** | Review before commit; last chance to go Back. |
| **Content** | Read-only summary: title, world size, grid, room id/name, footprint, spawn on/off. |
| **Primary action** | **Create layout** → `buildLayoutFromWizardDraft(draft)` → `initializeData` → `setDirty(true)` → close wizard → `setStatus` success. |
| **Secondary** | **Back** → `spawn_optional`. |
| **Post-action** | Optionally run `validateLayout` and show toast with summary; open validation panel if errors (should be rare). |

### 5.2 Stage order variants (pick one product line)

| Variant | Order | Best for |
|---------|------|----------|
| **A — Meta first** | intent → world_meta → first_room → spawn → confirm | Authors who think in “world” then “rooms.” Matches §5.1. |
| **B — Room first** | intent → first_room → world_meta → spawn → confirm | Authors who think “I need one room” first; meta defaults until step 3. |
| **C — Template first** | intent → **template** → (branch: template fills meta+rooms) → confirm | When P3 templates exist; shrinks steps for presets. |
| **D — Import-only** | intent → import JSON → (success) close | Thin wizard for migration; no meta stages. |

**Recommendation:** Ship **A** for P1; **C** replaces the middle when templates land.

---

## 5b. Brainstorm — candidate stages (beyond v1)

These are **not** commitments. Use for backlog triage; each row can be a future phase or a subsection inside an existing stage.

### Identity & session

| Idea | Description | Notes |
|------|-------------|--------|
| **Project label** | Separate “file name suggestion” vs internal layout title. | Helps export/download naming without changing room IDs. |
| **Workbench link** | Optional `project_id` reminder if URL already has query param. | Read-only; no new API. |
| **Fork vs replace** | “This replaces current layout” vs “Save current as…” before wizard. | Pairs with dirty guard. |

### Topology & scale

| Idea | Description | Notes |
|------|-------------|--------|
| **Room count hint** | “Roughly how many rooms?” (1 / few / many) | Doesn’t create rooms yet; sets expectations or picks template in P3. |
| **Single room vs hub** | Toggle: one room only vs “I will add branches later.” | UX only; could add second placeholder room in P3. |
| **Global map seed** | Initial `global` positions for N rooms in a row or grid. | Reduces manual dragging on global canvas. |

### Templates (P3)

| Idea | Description | Notes |
|------|-------------|--------|
| **Empty rectangle** | Current v1 behavior. | Baseline. |
| **Hub + corridor** | Two rooms, one edge link, one door placeholder. | Teaches edge links early. |
| **Match game MVP** | Pre-fill `meta` + room IDs from `docs/map-mvp-constraints.md` | Good for team content; needs maintenance when docs change. |
| **Duplicate from** | Start from a **copy** of current layout or from pasted JSON. | Overlaps import; different mental model (“template from my file”). |

### Quality & gates

| Idea | Description | Notes |
|------|-------------|--------|
| **Validation preview** | Run L1 (and L2 warnings) on draft **before** commit. | May be noisy before platforms exist; optional confirm stage. |
| **Export readiness** | “Mark as ready for runtime export” checklist (player start, min rooms). | Soft gate, not blocking. |
| **Accessibility** | “Minimum contrast / grid visibility” toggles for editor chrome only. | Editor-only; not layout JSON. |

### Playtest & embed (future)

| Idea | Description | Notes |
|------|-------------|--------|
| **Open game with layout** | Reuse **Open Game** hash flow after wizard completes. | Single button on confirm; requires hash encode of new layout. |
| **Embedded iframe** | Load `index.html` in sandboxed iframe. | Heavy; violates “simple” P1; may conflict with Phaser full-screen. |

### Import / export

| Idea | Description | Notes |
|------|-------------|--------|
| **Validate-then-import** | Show L1/L2 summary before applying JSON in wizard. | P2 import branch. |
| **Export at end** | Offer “Download JSON” immediately after create. | Nice for first-time users; optional checkbox on confirm. |

### Progressive disclosure

| Idea | Description | Notes |
|------|-------------|--------|
| **Simple vs Advanced** | Simple path: 3 screens (intent, room+meta combined, confirm). Advanced: full §5.1. | Reduces perceived length. |
| **“Expert mode” exit** | Checkbox: “Don’t show wizard again” → `localStorage`. | P4. |

---

## 5c. Ideas matrix (impact × effort — rough)

| | Low effort | Higher effort |
|---|------------|----------------|
| **High impact** | Defaults + skip buttons; confirm summary; dirty guard | Template step with real multi-room JSON |
| **Lower impact** | Project label; workbench read-only hint | Iframe playtest; full validation-before-commit |

Use this to prioritize after P1 ships.

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
4. **Stage order** — Default to **variant A** (meta → room) unless playtesting shows authors prefer **variant B** (room → meta); see §5.2.
5. **First room `global` placement** — Fixed `(600, 360)` (match `addRoom`) vs centered in world from `meta.worldWidth` / room width — affects global map first impression.

---

## 11. References

- `room-layout-editor.html` — `loadData`, `addRoom`, `initializeData`, `ensureRoomShape`
- `room-layout-export-package.js` — `engine_hints` / `meta` alignment
- `docs/room-editor-creative-decisions.md`
- `docs/room-editor-agent-task-spec.md` — Global Constraints
