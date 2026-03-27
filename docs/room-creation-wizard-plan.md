# Room creation wizard — product & implementation plan

This document defines **who** the wizard is for, **how** it feels in the product, and **how** to implement it. It aligns with `docs/room-editor-creative-decisions.md` (level tooling stays separate from the Sprite Workbench).

**Contents:** **[Product](#product-vision--audience)** · **[Sprite wizard alignment](#alignment-with-sprite-workbench-wizard)** · **[Five phases](#room-wizard-five-phases-layout--terrain--environment--objects--review)** · **[Per-tab preview](#per-tab-preview-panel)** · **[Assets & workbench](#assets-imports--future-asset-workbench)** · **[Neighbors & alignment](#neighbors--alignment)** · **[Technical appendix](#1-purpose)** (constraints, implementation phases, testing).

---

## Product vision & audience

### Who it’s for

- **Novice and solo game developers** who want to shape a level without thinking like a programmer.
- People who are comfortable with **visual tools** (drag, click, simple choices) and want **plain-language** labels and short explanations—not raw JSON as the default path. Advanced JSON remains in **Advanced**, not as a “bypass” of the wizard.

### What we promise

- **You stay in one room layout tool** for building spaces; the **global map** is the single place where the **whole world** is maintained (add, remove, move, and link rooms)—behavior that **already exists** in the editor.
- **Creating a new room** is a **guided experience** (the wizard), not a blank polygon dropped with jargon.
- Over time: **less manual math** when two rooms should meet cleanly (alignment, door/hatch height).

### Tone & UX principles

| Principle | Example |
|-----------|--------|
| **Friendly defaults** | Pre-filled sizes, sensible grid, “Recommended” badges. |
| **Explain in place** | One-line help under fields; “What’s this?” for edge links, validation. |
| **Guided path only** | **No “skip wizard”** for new rooms—the flow is the product. Users can still use **Advanced** JSON and the main canvas when not in a new-room flow. |
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
| **User adds a new room** (`+ Add Room` or equivalent) | **Always start the room wizard** for that new room. There is **no** optional “skip wizard”—the guided path is the intended experience. |
| **First room in an empty project** | Same flow. |

Editing **existing** rooms uses the main **Room view** / **Global map** as today; the wizard is for **creating** the new room’s content through the five phases.

---

## Alignment with Sprite Workbench wizard

The room wizard should **feel like the same family** as the Sprite / 2D animation workbench (`tools/2d-sprite-and-animation/`), not a one-off modal.

| Sprite pattern (reference) | Room wizard analogue |
|----------------------------|----------------------|
| **Phase rail** (`FLIGHTDECK_PHASES` in `core-helpers.js`: Describe → Concepts → Animations → Review & Export) | **Five phases**: Layout → Terrain → Environment → Objects → Review & Export — same “flight deck” mental model: left-to-right progress, current phase highlighted. |
| **Wizard state** (`wizard_state.current_step`, `step_statuses`, `blocking_reasons` in `workflow-shell.js`) | Persist per-room wizard progress (step, status) so returning users resume where they left off when reasonable. |
| **Locked / active / complete** steps | Later steps stay **locked** until prerequisites are met (e.g. Layout footprint committed before Terrain). |
| **Progress copy** (`wizardProgressSummary`: “N/M steps complete”) | Same progress language for the room flow. |
| **Review & Export** as final phase | Bundle validation + export + confidence — same naming as sprite **Review & Export** phase. |

**Philosophy:** One obvious path, clear labels, no parallel “fast path” that undermines the wizard for new-room creation. Raw JSON stays in **Advanced** for maintenance, not as a first-class alternative to the wizard for novices.

---

## Room wizard: five phases (Layout → Terrain → Environment → Objects → Review)

These are the **product spine**. Implementation may ship incrementally, but **UX and marketing** should use these names consistently.

### 1) Layout

**Intent:** Room **footprint** and how this room **connects** to neighbors on the **global map**.

- Shape and size (polygon / bounds); human-friendly names; stable ids.
- **Adjoining room** picker, **alignment** with neighbor, **corridor / hatch height** on the shared edge (see [Neighbors & alignment](#neighbors--alignment)).
- Global map remains the **single** place for world-scale positioning; **Layout** in the wizard coordinates with that (same data the global map already edits).

### 2) Terrain

**Intent:** **Uneven terrain** on top of the footprint from Layout — not only a flat floor.

- **Walkable surfaces** at **varying heights** within the footprint: ledges, platforms, stepped floors, gaps (maps to **platforms** and collision geometry in the editor today; **extend** toward richer “terrain” as the engine allows).
- User-facing language: **floors, ledges, ramps**, **uneven ground** — avoid “entity list” jargon in primary copy.
- Presets can still help (“flat”, “two-level”, “stepped”) but the **default promise** is **height variation** inside the room bounds defined in Layout.

### 3) Environment

**Intent:** Look and feel — **textures**, materials, mood, lighting (as engine/export supports).

- Tags, swatches, or theme slots; later tie to real texture sets and `engine_hints` / theme fields.

### 4) Objects

**Intent:** Gameplay + **props** + **assets**.

- **Built-in object types:** doors, keys, movers, abilities, pickups, etc. (guided forms).
- **Assets:** **Import** files (images, sprites, props) and **sync from a future Asset Workbench** that lives **inside this suite** (same product as the room editor and sprite tools — shared library, versioned references in layout JSON). Exact schema TBD; plan for **asset id + source** (local import vs workbench project).

### 5) Review & export

**Intent:** Validation in plain language, then **Export JSON**, **Export runtime**, **Open game** — with short explanations for non-technical users.

---

## Per-tab preview panel

**Requirement:** In **each** wizard phase tab, include a **preview** area that is **separate from the main editing canvas** (not the same canvas resized).

| Aspect | Detail |
|--------|--------|
| **Purpose** | See the **current room** as you work **without** losing the main editor context; **try movement** early. |
| **Behavior** | **Embedded** view (e.g. iframe or dedicated canvas) showing **only this room** (or this room in isolation). **Placeholder player** with **move around** controls (keyboard + optional touch) so authors feel scale and spacing. |
| **Scope** | **Not** a full game build — placeholder art, physics aligned with game where possible; may lag main game features until parity. |
| **Updates** | Preview **rebuilds** when the room data for the phase changes (Layout → footprint; Terrain → platforms; etc.). |
| **Technical note** | Conflicts with strict “no external libs” in the agent spec may require **minimal** embedded runtime (e.g. shared Phaser snippet or lightweight stub) **inside** the single HTML file or a small bundled script — **document in Sprint 5** when implementing. Iframe to `index.html` with room hash is one option; dedicated mini-scene is another. |

**Relationship to main canvas:** Main **Room view** canvas remains the authoritative editor; preview is **feedback**, not a second editor.

---

## Assets: imports & future Asset Workbench

| Source | Role |
|--------|------|
| **Import** | User brings files into the project (images, props); wizard assigns them to placements or object slots. |
| **Asset Workbench (future)** | Same ecosystem: **sync** assets from a workbench tool that is **part of this tool** (alongside sprite/animation workbench). References in layout JSON point at stable asset ids / URLs. |

Document **asset contract** when the workbench API exists; until then, stub **import + local refs** in the Objects phase.

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

The rest of this document retains **constraints**, **current editor behavior**, and an **earlier “layout-from-scratch” step breakdown** (§5 onward) useful for implementation. **Product direction:** **per-room wizard** on **Add Room** (no skip), **sprite-style phase rail**, **five phases**, **neighbors & alignment**, **uneven terrain**, **objects + assets**, **per-tab preview**, and **Asset Workbench** integration when available; reconcile older linear spec with this.

---

## 1. Purpose

**Problem (original framing):** New authors hit the editor with either a full embedded seed layout, a loaded canonical file, or empty states that say “import JSON or add a room” — without guidance on world bounds, naming, or a sensible first room.

**Goal (technical):** A flow that can still support **optional** “new project” or **import** paths:

- Chooses **how** a session starts when not using Add Room (continue existing work vs new vs import).
- For **new** layouts, collects **metadata** and creates a **minimal valid** first room (or applies a **template**) so `validateLayout` and export have something coherent to work with.
- Stays **inside** `room-layout-editor.html` (see constraints below).

**Non-goals (v1 product scope):**

- Replacing Advanced → JSON import or file-based load for **maintenance** workflows.
- Full parity with the shipping game inside preview (preview may use placeholder art first).

**In scope (product):** **Per-tab embedded preview** with placeholder player (see [Per-tab preview panel](#per-tab-preview-panel)); **asset import** and **future Asset Workbench sync** in Objects phase; **uneven terrain** in Terrain phase.

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

- **Add Room** → always start the **five-phase** room wizard (see product sections above).
- **Cold load / open project** → unchanged: `loadData()` as today; wizard is **not** for “whole new project” unless that is added later as a separate entry.

### 4.2 Other flows (appendix)

| Branch | Notes |
|--------|--------|
| **Import JSON** | Advanced panel or optional future import step; **not** a substitute for the new-room wizard. |
| **Earlier layout-from-scratch** | Technical step list in §5.1 below — reconcile with **Layout** phase + phase rail. |

---

## 5. Wizard steps (v1 — recommended)

Linear flow; Back/Next between steps. **No skip wizard**; optional **“Use defaults”** on individual fields only (reduces typing, not phase bypass).

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
| **Field shortcuts** | “Use defaults” for world/meta **only** fills values — still advances through the wizard normally. |

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

### Playtest & preview

| Idea | Description | Notes |
|------|-------------|--------|
| **Per-tab preview** | Embedded preview + placeholder player on **each** phase — **product requirement** in main plan. | See [Per-tab preview panel](#per-tab-preview-panel). |
| **Open full game** | Reuse **Open Game** hash flow from Review. | Full game, not a substitute for per-tab preview. |

### Import / export

| Idea | Description | Notes |
|------|-------------|--------|
| **Validate-then-import** | Show L1/L2 summary before applying JSON in wizard. | P2 import branch. |
| **Export at end** | Offer “Download JSON” immediately after create. | Nice for first-time users; optional checkbox on confirm. |

### Progressive disclosure

| Idea | Description | Notes |
|------|-------------|--------|
| **Simple vs Advanced** | Fewer fields per screen vs. **same** five phases — does not remove the wizard for new rooms. | |
| **First-run tips** | Dismissible hints on phase rail — **not** “skip wizard forever.” | |

---

## 5c. Ideas matrix (impact × effort — rough)

| | Low effort | Higher effort |
|---|------------|----------------|
| **High impact** | Phase rail + dirty guard; field defaults; confirm summary | **Per-tab preview** + placeholder player; **uneven terrain** UX; **Asset Workbench** sync |
| **Lower impact** | Project label; workbench read-only hint | Full game parity inside preview |

Use this to prioritize after P1 ships.

---

## 6. Technical design

### 6.1 State machine

- **`wizard` object** on `state` or module-local: `{ open: boolean, step: string, draft: { meta, firstRoom } }`, plus **`step_statuses`** / **blocking** aligned with sprite workbench patterns where useful.
- Pure functions: `buildLayoutFromWizardDraft(draft) → { version, meta, rooms: [one room] }`.
- **`openWizard()`** / **`closeWizard()`** — tied to **Add Room**; reset draft when closing without apply.

### 6.2 Integration with load

- **`loadData()`** unchanged for cold load.
- **Add Room** → open wizard for the new room; wizard writes into `state.data` for that room as phases complete or on final apply (implementation choice: progressive apply vs. single commit).

### 6.3 UI — phase rail (Sprite-style)

- **Horizontal phase rail** (same visual language as Sprite Workbench `FLIGHTDECK_PHASES` / `#phase-rail`): **Layout | Terrain | Environment | Objects | Review & Export**.
- Current phase highlighted; **later phases locked** until prerequisites met (configurable).
- **Overlay** or **full-width wizard shell** inside `room-layout-editor.html` with `role="dialog"` / focus trap as needed.
- Reuse **btn-primary**, **btn-secondary**, design tokens from sidebar/header.
- **Per-tab preview panel:** fixed region (not the main canvas) — see [Per-tab preview panel](#per-tab-preview-panel).

### 6.4 Preview runtime

- Implement as **iframe** to `index.html` with room hash, **or** embedded minimal Phaser scene (must respect **no new external libs** — reuse Phaser if already loaded, or ship minimal stub in-repo).
- **Placeholder player** movement: mirror `index.html` movement constants where feasible.

### 6.5 Validation

- Before **Review** / export: **`validateLayout(state.data)`**; surface L1/L2 in plain language.
- After apply: toast + validation panel as today.

---

## 7. Implementation phases

| Phase | Scope | Done when |
|-------|--------|-----------|
| **P0** | Spec + this plan | You are reading it. |
| **P1** | **Add Room** → wizard shell + **phase rail** + **Layout** + **Review** (minimal) + `initializeData` | New room flows through wizard; no skip. |
| **P2** | **Terrain** (uneven terrain / platforms on footprint) + **Environment** stubs | Footprint from Layout drives editable walkable height variation. |
| **P3** | **Objects** + **asset import** + placeholders for **Asset Workbench** sync | Objects phase can attach imports; sync spec documented. |
| **P4** | **Per-tab preview** + placeholder player | Each phase tab has embedded preview separate from main canvas. |
| **P5** | Polish: locking, blocking copy, parity with sprite wizard UX | Feels like Sprite Workbench flight deck. |

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

1. **Discard guard** — Confirm before **Add Room** when `state.isDirty` if replacing unsaved work (recommended: yes).
2. **`meta.title`** — Add optional field to schema vs `meta.notes` line.
3. **Cold load** — Default still loads embedded seed / canonical; **wizard only on Add Room** (not auto on every load).
4. **Stage order (appendix §5.2)** — Meta vs room first for legacy “new layout” flows; **five-phase product order** is fixed for the new-room wizard.
5. **First room `global` placement** — Fixed `(600, 360)` vs centered in world.
6. **Preview implementation** — iframe vs embedded scene; performance budget; mobile touch.
7. **Asset JSON schema** — ids, URLs, workbench project references — define when Asset Workbench API exists.

---

## 11. References

- `room-layout-editor.html` — `loadData`, `addRoom`, `initializeData`, `ensureRoomShape`
- `room-layout-export-package.js` — `engine_hints` / `meta` alignment
- `tools/2d-sprite-and-animation/app/core-helpers.js` — `FLIGHTDECK_PHASES`, phase rail pattern
- `tools/2d-sprite-and-animation/app/workflow-shell.js` — wizard state (`wizard_state`, `step_statuses`, `blocking_reasons`)
- `index.html` — movement / physics reference for preview parity (optional)
- `docs/room-editor-creative-decisions.md`
- `docs/room-editor-agent-task-spec.md` — Global Constraints (preview may require spec exception for embedded runtime — track in Sprint 5)
