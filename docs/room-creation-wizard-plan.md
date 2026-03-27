# Room creation wizard — product & implementation plan

This document defines **who** the wizard is for, **how** it feels in the product, and **how** to implement it. It aligns with `docs/room-editor-creative-decisions.md` (level tooling stays separate from the Sprite Workbench).

**Contents:** **[Product](#product-vision--audience)** (vision, global map vs wizard, five phases, neighbors & alignment, brainstorm) · **[Technical appendix](#1-purpose)** (constraints, baseline behavior, earlier layout-from-scratch stages, implementation phases, testing).

---

## Product vision & audience

### Who it’s for

- **Novice and solo game developers** who want to shape a level without thinking like a programmer.
- People who are comfortable with **visual tools** (drag, click, simple choices) and want **plain-language** labels, short explanations, and **optional** “advanced” detail tucked away—not raw JSON as the default path.

### What we promise

- **You stay in one room layout tool** for building spaces; the **global map** is the single place where the **whole world** is maintained (add, remove, move, and link rooms)—behavior that **already exists** in the editor.
- **Creating a new room** is a **guided experience** (the wizard), not a blank polygon dropped with jargon.
- Over time: **less manual math** when two rooms should meet cleanly (alignment, door/hatch height).

### Tone & UX principles

| Principle | Example |
|-----------|--------|
| **Friendly defaults** | Pre-filled sizes, sensible grid, “Recommended” badges. |
| **Explain in place** | One-line help under scary fields; “What’s this?” for edge links, validation. |
| **Progress, not homework** | Five clear phases (below); skip / “decide later” where safe. |
| **Review before share** | Last step is confidence: export or open game without surprises. |

---

## Two surfaces: global map vs room wizard

These are **separate jobs** in the product—not one mega-wizard that does everything.

| Surface | Job | Notes |
|---------|-----|--------|
| **Global map** (existing **Global Map** view) | **Maintain the world:** add/remove rooms, position them, connect edges, see the big picture. | Treat as the **single home** for “where does this room live relative to others?” Keep improving this view rather than duplicating it inside the wizard. |
| **Room wizard** (new / expanded flow) | **Shape one new room** from a friendly flow: footprint, connections to neighbors, gameplay ingredients, polish, then review. | **Launch when the user adds a new room** (see below). Not a replacement for global map editing. |

**Implication:** The wizard focuses on **one room at a time**. World-level operations stay on the **global map**; the wizard may **read** neighbor context (which room is next door) and **write** things that the global map already shows (position, links), but the **primary canvas for panning the whole map** remains global view.

---

## When the wizard opens (product rule)

| Trigger | Behavior |
|---------|----------|
| **User adds a new room** (`+ Add Room` or equivalent) | **Start the room wizard** for that new room—this is the default happy path for novices. |
| **First room in an empty project** | Same flow: wizard is the friendly way to define that first room. |
| **Power users** | Optional: “Skip wizard” or “Edit raw” links to land in the current fast path (direct canvas + inventory). |

Earlier ideas in this doc about a separate **“new empty layout”** entry from a menu can remain **secondary** (e.g. Advanced or rare case), since the product story centers on **global map + per-room wizard**.

---

## Room wizard: five high-level phases (brainstorm)

These are **product buckets**—not all need full UI in v1. They give marketing and UX a shared language: **Layout → Terrain → Environment → Objects → Review**.

### 1) Layout

**Intent:** Room shape, size, and how it **connects** to the rest of the world.

- Footprint: rectangle vs simple polygon; room name and id in **human terms** (“Spawn hall”) with automatic safe ids behind the scenes if needed.
- **Adjoining room:** pick which existing room this one **touches** (dropdown or map thumbnail).
- **Alignment helper:** snap the new room’s global position so shared edges line up with the neighbor; optional “same width along shared edge.”
- **Opening height:** match **corridor** or **hatch** height on the **connecting wall** so doorways feel continuous (maps to consistent y / edge parameters—implementation ties to polygon edges + door/mover placement).
- Spawn point (optional in this phase or later): “Put spawn here” on the floor.

*Brainstorm:* Step-by-step illustrations; “show me the neighbor” side-by-side mini view.

### 2) Terrain

**Intent:** Walkable structure inside the room—what the player stands on and moves across.

- Platforms, ledges, gaps (the editor already has **platforms**).
- For novices, language like **“floors and ledges”** rather than “platform entities.”
- Optional presets: “flat arena”, “two-level”, “small jumps only.”

*Brainstorm:* Later: slope or hazard language if the game supports it; for now 2D rects are enough.

### 3) Environment

**Intent:** Look and feel—**textures**, materials, lighting mood (where the engine supports it).

- May start as **labels / tags** (“cave”, “ruins”, “metal”) that map to game themes later.
- Placeholder swatches or color chips before real texture pipeline exists.

*Brainstorm:* Tie to export `engine_hints` or a future `theme` field; avoid promising full material editor until scope is clear.

### 4) Objects / details

**Intent:** Gameplay things and props: doors, keys, movers, pickups, ability gates, decorations.

- Guided placement: “Add a door”, “Add a moving platform” with **simple** forms (the inspector already exists—surface the essentials first).
- Duplicate less: one object at a time with clear icons.

*Brainstorm:* “Details” as optional sub-step so speedrunners can skip to Review.

### 5) Review & export

**Intent:** Confidence and shipping.

- Plain-language **checklist**: spawn set?, doors reachable?, validation (errors vs warnings).
- Actions: **Export JSON**, **Export runtime**, **Open game** (existing actions), short explanations of each for non-technical users.

*Brainstorm:* “Share” or “copy link” later; screenshot of minimap for docs.

---

## Neighbors & alignment (deepening the product story)

This is the **differentiator** for solo devs who don’t want to manually align coordinates.

| Concept | User-facing idea | Implementation direction (sketch) |
|---------|------------------|-----------------------------------|
| **Adjoining room** | “This room connects to: [Room B ▼]” | Store selection in wizard state; drive `global` placement and/or **edge link** creation between the two rooms. |
| **Align** | “Line up with neighbor” button | Snap `global` x/y (and optionally rotation if ever added) so shared boundary matches; may use same logic as global map snap. |
| **Corridor / hatch height** | “Match opening height with neighbor” | Align **door** or **cut** y-position on the shared edge, or match **platform** floor height at the threshold; may require picking **which edge** connects (edge index UI). |

*Open product questions:* One neighbor only in v1 vs multiple; what if rooms don’t share an edge yet (wizard creates link vs prompts user to draw on global map).

---

## Continuing brainstorm (backlog prompts)

- **Onboarding:** 60-second tour the first time someone opens the editor: global map vs room view, then disable nag.
- **Language pack:** Replace internal terms (`edgeLinks`, `polygon`) in UI with **doors/walls/openings** where accurate.
- **Templates per phase:** “Boss arena”, “key room”, “corridor” could jump-start Terrain + Objects.
- **Solo dev workflow:** Save often, scratch persistence, “revert room to last save” for one room only.
- **Marketing line:** *“Lay out your map. Build each room step by step. Export when it feels right.”*

---

## Relationship to technical sections below

The rest of this document retains **constraints**, **current editor behavior**, and an **earlier “layout-from-scratch” step breakdown** (§5 onward) useful for implementation. **Product direction:** prioritize **per-room wizard** triggered by **Add Room**, **five phases** above, and **neighbor alignment** features; reconcile or replace older “intent → world_meta → first_room” linear spec as engineering proceeds.

---

## 1. Purpose

**Problem (original framing):** New authors hit the editor with either a full embedded seed layout, a loaded canonical file, or empty states that say “import JSON or add a room” — without guidance on world bounds, naming, or a sensible first room.

**Goal (technical):** A flow that can still support **optional** “new project” or **import** paths:

- Chooses **how** a session starts when not using Add Room (continue existing work vs new vs import).
- For **new** layouts, collects **metadata** and creates a **minimal valid** first room (or applies a **template**) so `validateLayout` and export have something coherent to work with.
- Stays **inside** `room-layout-editor.html` (see constraints below).

**Non-goals (v1):**

- Replacing Advanced → JSON import or file-based load.
- Embedding the game for playtest (future)—except **Open game** as today.
- Full sprite / tileset pipelines inside the wizard until Environment phase scope is defined.

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
