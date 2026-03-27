# Room Editor Production Overhaul Plan

**Date:** 2026-03-26
**Status:** Active
**Scope:** Full production-grade overhaul of the room editor, integrated with Sprite Workbench

---

## Executive Summary

The room editor is a strong geometry tool trapped in a prototype shell. It has the right canvas interactions, a solid room data model, and matches the Sprite Workbench's design language — but it lacks every system that would make it production-ready: project lifecycle management, a validation pipeline, a durable export contract, and architectural modularity.

At the same time, market research reveals a clear and unoccupied product position: no tool exists that combines AI-assisted sprite generation with AI-assisted level design for 2D metroidvanias. LDtk (the gold standard, built by the Dead Cells director) has zero AI features. PixelLab and AutoSprite have zero level design features. The gap is structural, not incremental.

This plan closes both gaps: lifting the room editor to Sprite Workbench production quality, and positioning the integrated toolchain as the first purpose-built AI-native room editor for 2D side-scrollers and metroidvanias.

---

## Audit Findings

### What the Room Editor Does Well

- Polygon room geometry editing: vertex add/move/delete with grid snap
- Platform, door, key, ability, mover placement — all working
- Edge linking between adjacent rooms with 5-strategy snap candidate search
- Dual canvas (room view + global map view)
- Identical design tokens to Sprite Workbench (CSS variables, typography, palette)
- Responsive layout (sidebar collapse at 840px)
- Persistent state via localStorage
- Room inventory metrics panel (badges, item lists)

### What's Holding It Back

**Architecture:**
- 4,539-line monolithic HTML file — no JS module separation
- Single global `room-layout-data.json` (not per-project)
- Thin standalone server (`layout_editor_server.py`) — no project API
- No shared code with Sprite Workbench (identical CSS, but siloed)

**Workflow:**
- No project lifecycle (no create / duplicate / archive)
- No wizard state or stage gating
- No undo/redo (only localStorage scratch save)
- No history or audit trail
- No conflict detection (overlapping rooms, unreachable doors)
- No layer/visibility management
- No multi-room batch operations

**Quality Pipeline:**
- No validation pipeline (no structural, traversal, or progression checks)
- No QA report artifact
- No export contract (can export JSON, but no runtime package)
- No downstream integration with Sprite Workbench project

**UX:**
- No empty states ("No rooms yet" flow)
- No loading states for async operations
- No error states for corrupt data
- No keyboard shortcut legend
- Element creation controls buried in scroll — not immediately discoverable

### What the Sprite Workbench Does That the Room Editor Needs

| Capability | Sprite Workbench | Room Editor |
|---|---|---|
| Per-project storage | Per-project dirs with artifact files | Single global JSON |
| Project lifecycle | create / duplicate / archive / list | None |
| Wizard state | 15+ stages with blocking + completion rules | None |
| Artifact versioning | History JSON, SHA export manifest | None |
| Validation pipeline | QA report with deterministic checks | None |
| Export contract | Runtime package (atlas, animations, manifest) | Raw JSON only |
| Server API | Full REST API (sprite_workbench_server.py) | GET/POST /api/layout |
| JS architecture | 20 modular files + CSS file | Monolithic HTML |
| Stage navigation | Visual step progress, locked/active/complete | None |
| Empty/loading/error states | Full system | None |

---

## Market Research Findings

### The Competitive Landscape (2026)

**AI sprite generation tools:** PixelLab, AutoSprite, Scenario, Leonardo AI, God Mode AI
**Level editors:** LDtk, Tiled, GameMaker built-in, Godot TileSet
**No tool combines both.** Every player operates in exactly one domain.

### LDtk — The Gold Standard to Learn From

LDtk (https://ldtk.io) was built by the director of Dead Cells specifically for this genre. Key UX patterns:
- **Auto-layers:** rule-based auto-tile placement (paint a collision map, tiles appear)
- **Entity system:** typed game objects with first-class schemas
- **World view:** entire game map as connected rooms, zoom in/out fluidly
- **Aseprite live reload:** art → editor → game loop without friction
- **JSON export:** clean, engine-agnostic, well-documented

What LDtk does NOT have: any AI features whatsoever.

### The Gap No One Owns

| Feature | Current state | Opportunity level |
|---|---|---|
| "Generate this room from description" | Nothing purpose-built for 2D | High |
| Style-locked tileset matching your character sprites | Not in any integrated tool | High |
| AI-suggested room connections / world map layout | Completely absent | High |
| Character concept → spritesheet → placed in level in one pipeline | 3 separate tools minimum | High |
| Biome-aware asset generation (sprites + tiles share palette) | Not available | Medium |
| Godot/Phaser export from the same tool that generated your sprites | Neither tool does the other's job | Medium |

### Target User Profile

**The programmer-first solo indie developer** building a metroidvania or 2D side-scroller who:
- Has game design and programming skills (Godot or Unity)
- Has zero or minimal pixel art ability
- Hits a wall at art + level design creation
- Is willing to pay for tools that solve both bottlenecks
- Has a specific genre aesthetic in mind with well-understood visual conventions

This person is underserved by PixelLab (sprite-only), LDtk (layout-only), and Rosebud AI (targets beginners, not serious genre devs).

### Metroidvania Market Context

- 2,200+ metroidvania games on Steam; 8–9% CAGR through 2030s
- Every commercially successful metroidvania in 2024–2025 used hand-crafted art
- The genre has strong aesthetic expectations — hand-crafted visual quality is the bar
- **Godot 4.4 is now the dominant engine** for new indie 2D projects (post-Unity pricing controversy)
- Typical indie team: 1–4 people; art is explicitly cited as the #1 barrier to entry

### Strategic Insight

The constraint of the metroidvania genre is actually an asset for AI tooling:
- The genre has **strong layout conventions** (interconnected rooms, ability gating, biomes)
- These conventions are amenable to **structured AI generation**
- Style coherence across a full game — sprites + tiles matching — is the #1 unsolved problem
- **Solving that single problem** for the metroidvania genre would be a genuine competitive moat

---

## Overhaul Architecture

### Design Principles

1. **Project-first:** Every room layout is project-scoped, not global
2. **Preserve the canvas:** The room editor's geometry interactions are its best asset — refactor the shell, not the core
3. **Match workbench quality:** Same wizard model, same validation pipeline, same export contract pattern
4. **LDtk-aware:** Learn from LDtk's best UX patterns; differentiate with AI integration
5. **Genre-native:** First-class support for metroidvania concepts (biomes, gating, ability unlocks, branch rooms)
6. **AI as a force multiplier, not a replacement:** AI assists, user controls

### Target End State

The room editor becomes the **Level Design** stage of the Sprite Workbench — a first-class project domain alongside character and animation. A user creates a project, generates their character, then moves to the Level Design stage where they:

1. Design their world map topology (rooms, connections, biomes)
2. Edit each room's geometry (the current editor's strength)
3. Place entities (platforms, doors, keys, abilities, movers)
4. Run validation (reachability, gating, structural soundness)
5. Export a runtime package that the game engine can consume

The AI layer adds:
- Room generation from text description
- Style-coherent tileset suggestions matching the project's character palette
- Layout suggestions based on biome + progression context

---

## Phase Plan

### Phase 0 — Foundations (Pre-Overhaul)

**Goal:** Lock the integration boundary and prevent future rework.

**Deliverables:**
1. Define `room_layout.json` as a first-class project artifact
2. Write migration function from global `room-layout-data.json`
3. Add room layout endpoints to `sprite_workbench_server.py`:
   - `GET /api/projects/:id/room-layout`
   - `POST /api/projects/:id/room-layout`
   - `POST /api/projects/:id/room-layout/validate`
4. Prove persistence: copy current canonical layout into one test project
5. Keep `layout_editor_server.py` running in parallel until new path is proven

**Room Layout Artifact Contract:**
```json
{
  "project_id": "<id>",
  "version": 1,
  "updated_at": "<ISO-8601>",
  "meta": {
    "worldWidth": 1600,
    "worldHeight": 1200,
    "grid": 32,
    "biome": null,
    "notes": ""
  },
  "rooms": []
}
```

**Exit criteria:**
- Workbench project can own a room layout
- Duplicate project duplicates room layout
- Project API returns room layout as part of integrated state

---

### Phase 1 — JS Architecture Extraction

**Goal:** Break the 4,539-line monolith into a maintainable module structure, matching Sprite Workbench patterns.

**Target module structure:**
```
room-editor/
├── room-editor.html            (shell only, ~300 lines)
├── app/
│   ├── room-shell.js           (navigation, project lifecycle, toasts)
│   ├── room-project.js         (project CRUD, state management)
│   ├── room-canvas.js          (canvas rendering, zoom/pan)
│   ├── room-geometry.js        (vertex, polygon, edge-link interactions)
│   ├── room-elements.js        (platform, door, key, mover placement)
│   ├── room-inspector.js       (element property inspector panel)
│   ├── room-inventory.js       (room metrics sidebar)
│   ├── room-global-map.js      (world map canvas + room positioning)
│   ├── room-validation.js      (structural, traversal, progression checks)
│   ├── room-export.js          (runtime package generation)
│   └── room-api.js             (server API calls, project endpoint calls)
└── styles/
    └── room-editor.css         (room-specific styles; imports shared tokens)
```

**Why extract:**
- Enables targeted editing without full-file reads
- Allows parallel development of canvas vs. shell vs. validation
- Mirrors Sprite Workbench's 20-module architecture
- Makes future AI feature additions localized

**Exit criteria:**
- Room editor renders identically from modular structure
- All existing interactions preserved
- No regressions in geometry, snap, or persistence

---

### Phase 2 — Project Lifecycle Integration

**Goal:** Room editor operates as a project-scoped tool, not a standalone utility.

**Work:**
1. Wire room editor to workbench project APIs (replace `layout_editor_server.py` calls)
2. Add project selector panel (list workbench projects, select active)
3. Add project context header (name, last saved, room count)
4. Add per-project room layout load/save/dirty-state tracking
5. Add create-new-project flow (from within room editor)
6. Add import canonical layout action (migrate from `room-layout-data.json`)
7. Add history events: `room_layout_saved`, `room_layout_imported`, `room_layout_validated`

**State model (matching workbench):**
```js
state = {
  projectId: null,
  projectName: null,
  layout: null,          // room_layout.json contents
  isDirty: false,        // unsaved changes
  lastSaved: null,
  selectedRoomId: null,
  selectedItemId: null,
  // ... canvas state, tool state, etc.
}
```

**Exit criteria:**
- User can select any workbench project and load its room layout
- Save/auto-save writes to project-scoped endpoint
- Duplicate project carries room layout correctly

---

### Phase 3 — UI/UX Overhaul (Match Sprite Workbench Production Value)

**Goal:** Room editor reaches the visual and interaction quality of the Sprite Workbench.

#### 3A — Shell & Navigation

**Current:** Basic nav bar with links.
**Target:** Full workbench-quality shell.

- Sticky 52px nav with project context (name, save indicator, breadcrumb)
- Sidebar with project list (collapsible to 64px rail)
- Stage progress indicator showing: `World Map → Room Edit → Validate → Export`
- Keyboard shortcut modal (`?` key trigger)
- Command palette (Cmd+K) for room navigation and actions

#### 3B — Canvas & Tooling

**Current:** Canvas with floating inspector, toolbar with icon buttons.
**Target:** Professional-grade canvas environment.

- **Tool palette** (left rail, like Figma/Aseprite):
  - Select (V), Vertex (V+V), Platform (P), Door (D), Key (K), Ability (A), Mover (M), Player Start (S)
  - Active tool highlighted, tooltip with keyboard shortcut
- **Canvas toolbar** (top of canvas):
  - Zoom controls (Fit, 25%, 50%, 100%, 200%)
  - Grid toggle + grid size selector
  - Snap toggle
  - Room/Global view switcher
  - Undo/Redo (Cmd+Z, Cmd+Shift+Z)
- **Canvas overlays:**
  - Scale reference (pixel ruler at canvas edges)
  - Room size readout (W × H at top-left of room bounds)
  - Validation error markers (red highlight on invalid elements)
- **Inspector panel** (right side, not floating):
  - Context-sensitive property editing for selected element
  - Validation status per element
  - Quick-delete and duplicate actions

#### 3C — Undo/Redo System

**Current:** None.
**Target:** Full command history.

```js
// Command pattern
history.push({ type: 'MOVE_VERTEX', roomId, vertexIndex, from, to })
history.push({ type: 'ADD_PLATFORM', roomId, platform })
history.push({ type: 'DELETE_DOOR', roomId, doorId, doorData })

// Ctrl/Cmd+Z = undo last command
// Ctrl/Cmd+Shift+Z = redo
// History depth: 50 commands
```

#### 3D — Empty States & Onboarding

**Current:** None — no guidance when no data exists.
**Target:** Guided empty states at every level.

- **No project selected:** Centered card — "Open a project or create one to start designing your world"
- **No rooms:** Centered prompt — "Add your first room to begin layout" with `+ Add Room` CTA
- **Room selected but empty:** Subtle overlay — "Click the canvas to place your first platform"
- **No validation run yet:** Info state in validation panel — "Run validation to check your level's reachability"

#### 3E — Loading & Error States

- **Loading:** Skeleton screens for project list, canvas spinner for layout fetch
- **Save:** Optimistic UI with "Saved" badge (2s auto-dismiss) or "Saving..." indicator
- **Error:** Toast + persistent error banner for failed saves; retry button
- **Corrupt data:** Inline error with "Show raw JSON" escape hatch

#### 3F — Room Inventory Panel Upgrade

**Current:** Badges with counts, flat item list.
**Target:** Rich inventory sidebar matching workbench panel quality.

- Expandable sections per room (platforms, doors, keys, abilities, movers)
- Validation status icon per room (green check / yellow warning / red error)
- Click-to-select: clicking an item jumps canvas to it
- Search/filter within inventory
- Per-room notes field (editable inline)
- Room biome tag (for future theming)

#### 3G — Global Map View Upgrade

**Current:** Functional but sparse.
**Target:** LDtk-quality world view.

- Room labels with room names (not just IDs)
- Color-coded by biome/branch type (A, B, C branches, hub, final)
- Edge links visualized as arrows between rooms
- Validation errors shown on world map (red border on problem rooms)
- Drag to reposition rooms on the world map
- Mini-map inset when zoomed into room view

---

### Phase 4 — Validation Pipeline

**Goal:** Room editor has a first-class validation system matching Sprite Workbench's QA pipeline.

**Canonical reference (IDs, severity, traceability, user-doc placeholder):** [`room-layout-validation.md`](./room-layout-validation.md) — **DOC-ROOM-VALIDATION-001** for published user-facing help.

**Three validation levels:**

**Level 1 — Structural Correctness**
- All rooms have at least 3 vertices
- No duplicate room IDs
- All `targetRoom` references in doors resolve to existing rooms
- All `edgeLinks` reference valid edge indices
- Player start exists in at least one room
- No orphaned element IDs

**Level 2 — Traversal Sanity** (from existing `room-layout-iteration-plan.md`)
- Step-up between consecutive required ledges ≤ 120px
- Horizontal gap between required ledges ≤ 220px
- Required interactions reachable within ≤ 140px from stable standing positions
- Branch completion route allows return to R2 without optional jumps
- Critical-path transitions reachable from floor-level fallback

**Level 3 — Progression & Content Sanity**
- All branches completable in any order (A→B→C, A→C→B, C→A→B)
- Branch B hard-gate correctly locked before Branch A ability
- Final gate unlockable via real branch progression
- No soft-lock states (player can always reach a transition)

**Validation output contract:**
```json
{
  "project_id": "<id>",
  "run_at": "<ISO-8601>",
  "level_1": { "passed": true, "checks": [] },
  "level_2": { "passed": false, "checks": [
    { "id": "L2-007", "room": "R3", "severity": "error", "message": "Step from R3-P4 to R3-P5 is 148px, exceeds 120px limit" }
  ]},
  "level_3": { "passed": null, "checks": [] },
  "summary": { "errors": 1, "warnings": 0, "passed": false }
}
```

**Validation UX:**
- "Validate" button in stage header (always accessible)
- Per-room validation badge in inventory sidebar
- Jump-to-error: clicking a validation error centers canvas on the offending element
- Validation gate before export (same pattern as Sprite Workbench QA gate)

---

### Phase 5 — Export Contract

**Goal:** Room editor produces a runtime-consumable package, not just a JSON dump.

**Export package structure:**
```
project-<id>/
└── level-export/
    ├── room_layout.json          (canonical room data)
    ├── level_validation.json     (Level 1+2+3 report)
    ├── level_manifest.json       (export metadata, timestamps, checksums)
    ├── rooms/
    │   ├── R1.json               (per-room data, ready for Phaser/Godot)
    │   ├── R2.json
    │   └── ...
    └── world_graph.json          (room topology: nodes, edges, gating rules)
```

**`level_manifest.json` structure:**
```json
{
  "project_id": "<id>",
  "exported_at": "<ISO-8601>",
  "room_count": 11,
  "validation_passed": true,
  "validation_level": 2,
  "sha256": "<hash of room_layout.json>",
  "engine_hints": {
    "grid_size": 32,
    "world_width": 1600,
    "world_height": 1200
  }
}
```

**Export gate rules:**
- Level 1 validation must pass (structural) — hard block
- Level 2 validation recommended — soft warning (can override with explicit confirm)
- Exported rooms include only fields the runtime needs (strips editor-only metadata)

---

### Phase 6 — AI Feature Layer

**Goal:** Introduce AI assistance as a force multiplier, not a replacement for the editor.

This is the product's market differentiator: **no other 2D level editor has any AI integration**.

#### 6A — Room Generation from Description

The #1 unoccupied product feature in the competitive landscape.

**User flow:**
1. User has a room selected (or creates new empty room)
2. Clicks "Generate Layout" in the room inspector
3. Types a description: *"Flooded underground library, tall vertical climb, secret passage in left wall, 3 key platforms over water"*
4. Selects genre constraint: Metroidvania / Platformer / Dungeon
5. Sets constraint mode: Strict (respect reachability rules) / Creative (suggestions only)
6. AI returns: polygon suggestion + platform placements + element placements
7. Preview in canvas before applying (apply to clean room or merge with existing)
8. User edits result — AI generation is a starting point, not a finish

**Technical approach:**
- Prompt LLM (Claude API) with room description + metroidvania constraint rules
- Output structured JSON matching room schema
- Apply validation checks before presenting to user
- Show diff of what will change if merging with existing room

#### 6B — Style-Coherent World Theming

**User flow:**
1. Project has a character locked (from Sprite Workbench character pipeline)
2. In Level Design stage, user selects biome type per room (hub, branch-A, branch-B, branch-C, final)
3. System suggests color palette per biome based on character's dominant colors
4. Platform tint assignments auto-suggest per biome (can be overridden)
5. Future: tileset generation matching character palette

**Technical approach:**
- Extract dominant palette from character's approved concept art
- Apply palette rotation per biome (hue shift, value range constraints)
- Map palette to existing tint slots (tint 0–4)
- Store theming in `room_layout.meta.biome_themes`

#### 6C — Layout Validation Suggestions

**User flow:**
1. Validation runs and reports "Step from R3-P4 to R3-P5 is 148px, exceeds 120px limit"
2. User clicks "Suggest Fix" on the error
3. AI suggests: "Add an intermediate platform at (420, 680) to break the jump into two 74px steps"
4. User accepts (auto-places platform) or dismisses

**Technical approach:**
- Package validation error + room geometry context into structured prompt
- Ask Claude API for platform placement suggestion that resolves the constraint
- Apply suggestion as a proposal (user can confirm/reject)

---

### Phase 7 — Workbench Integration

**Goal:** Room editor stage lives inside the Sprite Workbench pipeline as a first-class stage.

**Workbench stage flow (updated):**
1. Describe (character brief)
2. Concepts (AI generation)
3. Character (sprite model, parts)
4. Animations (idle, walk, attacks)
5. **Level Design** ← new stage
   - World Map (room topology + biome theming)
   - Room Edit (geometry + element placement)
   - Validate (structural + traversal checks)
6. Review & Export (character + level bundled)

**Level Design stage card (in workbench sidebar):**
- Room count and biome tags
- Validation status badge
- Last saved timestamp
- "Open Room Editor" → launches full canvas view
- "Run Validation" → runs inline, updates badge
- Blocking rules: stage is "complete" when Level 1 validation passes

**Bundled export (workbench Review & Export):**
```
project-<id>/
├── sprite-export/          (existing: atlas, animations, frames)
│   ├── spritesheet.png
│   ├── atlas.json
│   └── animations.json
└── level-export/           (new)
    ├── room_layout.json
    ├── level_manifest.json
    └── rooms/
```

---

---

## UI/UX Polish Inventory

Phase 3 in the sprint plan covers UI/UX at a high level. This section is the component-by-component breakdown of every specific gap vs. the Sprite Workbench standard, and what the target state is for each.

---

### 1. Design Token Gaps

The room editor is missing ~15 tokens the Sprite Workbench defines. These need to be added to `:root` and used throughout.

**Missing from room editor:**
```css
/* Missing aliases */
--border: rgba(0,232,200,0.07);        /* room editor uses --line */
--border-strong: rgba(0,232,200,0.14); /* room editor uses --line-strong */
--text-muted: #5d7870;                 /* room editor only has --muted */
--text-faint: rgba(204,232,224,0.25);
--surface-hover: rgba(6, 9, 14, 0.98);
--bg-raised: rgba(4, 6, 10, 0.98);
--accent-hover: #20f4d4;

/* Missing spacing scale */
--space-1: 4px;  --space-2: 8px;   --space-3: 12px;  --space-4: 16px;
--space-5: 24px; --space-6: 32px;  --space-7: 48px;  --space-8: 64px;
--surface-gap: 12px;
--surface-pad: 14px;

/* Missing type scale */
--font-size-xs: 11px;   --font-size-sm: 13px;  --font-size-base: 14px;
--font-size-md: 15px;   --font-size-lg: 18px;  --font-size-xl: 22px;

/* Missing shadow scale */
--shadow-sm: 0 2px 8px rgba(0,0,0,0.18);
--shadow-md: 0 6px 20px rgba(0,0,0,0.26);
--shadow-lg: 0 12px 40px rgba(0,0,0,0.38);

/* Missing transition tokens */
--transition-fast: 120ms ease;
--transition-base: 200ms ease;

/* Missing nav height token */
--nav-h: 52px;
```

**Rule:** Once tokens are added, do a find-replace pass to use them everywhere instead of hardcoded values. The workbench applies `transition: background var(--transition-fast)` etc. throughout.

---

### 2. Canvas Toolbar — Text Labels → Icon + Label

**Current:** 9 tool buttons with text only: "Select", "Add Vertex", "Add Platform", "Add Door", etc.

**Problems:**
- No icons — all other similar tool panels in the domain (Aseprite, Figma, LDtk) use icons
- No keyboard shortcut hints
- No color-coding by element type — platforms should show in `--platform` blue, doors in `--door` orange etc.
- No visual distinction between **tool mode buttons** (Select, Add Platform…) and **action buttons** (Delete, Duplicate, Center Room) — they're all the same style in a single column
- Toolbar sits at `top: 92px, left: 12px` fixed — when the view control bar is visible, these can visually conflict

**Target state:**
```
[Tool palette — vertical icon strip, left edge of canvas]
  ▣  Select          (V)
  ⬡  Vertex          (E)
  ▬  Platform        (P)
  ⬤  Door            (D)
  ◆  Key             (K)
  ✦  Ability         (A)
  ⟺  Mover           (M)
  ☆  Player Start    (S)
  ⟳  Move Room       (Shift+M)

  ─────────────── divider

  ✕  Delete          (Del)
  ⧉  Duplicate       (Cmd+D)
  ⊕  Center Room     (C)
  ∻  Toggle Edge     (T)

  ─────────────── divider

  [Shortcut hint: ?]
```

- Active tool: `--accent` border + soft background
- Element-type tools: small colored dot matching element color (platform = `#77b8ff`, door = `#f5986e`, etc.)
- Action buttons: slightly muted vs. tool buttons, grouped separately
- Tooltip on hover: full label + keyboard shortcut
- Keyboard shortcut badge on each button (small `--muted` tag)

---

### 3. View Control Bar — "Pan L/U/D/R" → Proper Controls

**Current:** `-`, `+`, `100%` zoom buttons + `Pan L`, `Pan U`, `Pan D`, `Pan R` text buttons.

**Problems:**
- "Pan L/U/D/R" is extremely crude — arrow keys or click-drag should be the primary pan; these are fallbacks
- Buttons are unequal widths (zoom readout is `min-width: 62px`, buttons have no consistent sizing)
- No "Fit to Room" button
- The view switch (Room / Global) is a `<select>` buried inside a control card — should be a prominent tab strip

**Target state:**
```
[View control bar — top of canvas, full width]
  [Room View] [Global Map]    ← tab strip, not a dropdown

  ← view-specific controls after the tab →

  Zoom: [-] [100%] [+]  [Fit]   ← zoom group
  ↑ ← ↓ →                       ← pan arrow buttons (icon only, small, grouped)
  [Grid: 32 ▾]  [Snap: ON]       ← canvas options
```

- View switch as segmented control (`.tab-strip`), not a `<select>`
- Zoom readout as editable input (click to type custom %)
- Pan arrows as icon-only buttons (16×16), secondary visual weight
- "Fit" button: fits the room to viewport
- Grid and snap as compact toggles, not buried in a control card

---

### 4. Inspector Panel — Floating → Docked Right Rail

**Current:** Absolutely positioned floating panel (`position: absolute; top: 64px; right: 12px; width: 220px`) overlaid on the canvas.

**Problems:**
- Occludes canvas content, especially in the top-right area
- Generic title "Selection" — doesn't show what type of element is selected
- Requires explicit "Apply Properties" button — no live update on field change
- No element type indicator (icon + color)
- Input fields have no validation feedback
- `min-height: 44px` on inspector inputs makes the panel very tall

**Target state:**
- Docked right rail (below the canvas toolbar row), 240px wide, part of the layout grid — does not float over canvas
- Header: element type icon + color dot + ID (e.g., `⬤ Platform R1-P3`)
- Live update: fields apply on `input` event with 300ms debounce (no Apply button)
- Validation: red border + tooltip on invalid values
- Compact inputs: `min-height: 32px` for inspector fields (smaller than main form fields)
- Keyboard: Tab between fields, Enter to confirm, Esc to deselect
- "Delete" as a danger button at the bottom of the inspector (red border, not in toolbar)

---

### 5. The `<details>/<summary>` Element — Replace Entirely

**Current:** Native `<details>` + `<summary>` for "Advanced Import / Scratch / Raw JSON".

**Problem:** This is the only native browser disclosure element in the entire tool. It uses browser-default styling that cannot be reliably themed, and it renders with a browser-native triangle disclosure arrow that clashes with the custom design language.

**Target state:**
- Replace with a custom collapsible `<div>` using the same pattern as the rest of the app
- Use a button with chevron icon as the toggle trigger
- The section itself becomes a `.control-card` within the main panel flow
- Label it clearly: "Raw JSON / Import" or "Debug Tools"

---

### 6. Status Bar — Stateless Bar → Rich Status Row

**Current:** Plain `.status` div: `font-size: 12px; color: var(--muted); border: 1px solid var(--line);` — just a box with text.

**Problems:**
- No visual differentiation between info/success/error/warning states
- Looks like an `<input>` due to the border + padding treatment
- Positioned between canvas and the inventory panel — breaks visual flow

**Target state:**
- Replace with a proper status row component:
  - State-aware: `.status-info`, `.status-success`, `.status-error`, `.status-warning`
  - Icon prefix matching state (info = `ℹ`, success = `✓`, error = `✕`, warning = `⚠`)
  - Auto-dismiss for success states (2s)
  - Error states persist until dismissed or overwritten
  - Positioned as a sticky footer inside the canvas panel, not between sections

---

### 7. Canvas — Fixed Size → Responsive Fill

**Current:** `<canvas id="roomCanvas" width="960" height="720">` — fixed pixel dimensions.

**Problems:**
- Does not fill available viewport height
- On a 1280px MacBook, 960px canvas leaves dead space
- No scale reference (pixel ruler)
- No visible grid overlay (grid is in state but not clearly toggled)

**Target state:**
- Canvas fills the available panel area (use `ResizeObserver` to recalculate on container resize)
- Scale indicator: small ruler at canvas left and top edges showing world-space pixel values at current zoom
- Grid overlay: visible on canvas when grid snap is active (faint `--line` colored grid lines)
- Canvas background: subtle dot-grid pattern at `--line` opacity (matching design tools like Figma/Penpot)

---

### 8. Control Cards Layout — Reorganize the 3-Column Header Area

**Current:** 3 control cards: "Current map" (room/view select + dimensions) + "Editing controls" (snap + zoom) + "Save and share" (save/export buttons).

**Problems:**
- View mode switch (`Room Editor` / `Global Map`) is in the first control card — it should be a top-level tab, not a dropdown in a control card
- "Room Width" and "Room Height" inputs are prominent when they rarely need changing
- The 3-column card layout adds visual noise before you even see the canvas
- "Global Zoom" as a range slider inside a control card is an odd placement

**Target state — consolidate to a toolbar strip + collapsible settings:**
```
[Top area — compact toolbar strip]
  Project: [Ashen Hollow ▾]  |  Room: [R1 - Spawn Chamber ▾]
  [+ Add Room]  [⌫ Delete Room]

  |  separator

  [Room View] [Global Map]   ← prominent tabs

  |  separator

  [Save] [Export] [Open Game]   ← right-aligned

[Collapsible advanced settings panel — hidden by default]
  Grid: [32 ▾]   Room Width: [___]   Room Height: [___]
  Global Zoom: [slider]   [Reload] [Sync Canonical]
```

- Primary controls always visible
- Advanced/rarely-used controls in a collapsible section
- Removes the 3-card header block that pushes the canvas down the page

---

### 9. Global Map Link Panel — Polish the Edge Linking UI

**Current:** Floating panel (`global-link-panel`) with plain dropdowns and buttons: "Select an edge in the global map to create or edit a room connection."

**Problems:**
- No visual treatment — just default dropdowns and buttons
- "Select an edge in the global map to create or edit a room connection" as a plain text summary is good but not styled
- Buttons "Link Edge", "Clear Link", "Snap Room" are standard size but the panel is tiny

**Target state:**
- `.panel` treatment matching the main design system
- Summary line as styled callout (`.hint` or contextual banner)
- Dropdowns with proper `--line` border, `var(--text)` color, `var(--font-sans)` font
- Destructive action (Clear Link) with red/error visual treatment
- "Snap Room" as a secondary action button
- Animate in/out when edge is selected vs. deselected

---

### 10. Room Inventory Sidebar — Complete Redesign

**Current:** Badges (counts only) + flat list of chips per element type.

**Problems:**
- Badge grid is visually fine but has no status — a room with 0 keys looks identical to one with 3 keys with no visual distinction
- Chips are just IDs (e.g., "R1-P1") — no context, no position info, no quick action
- No expandable/collapsible sections per element type
- No search within inventory
- No validation status per room

**Target state:**
```
[Room Inventory sidebar]
  ▼ R1 — Spawn Chamber  [✓ valid]  [3 platforms] [2 doors] [1 key]

  Platforms (3)                ← expandable section header
    ▬ R1-P1   x:120  y:1048  len:12   [tint 0] [select] [delete]
    ▬ R1-P2   x:480  y:900   len:8    [tint 1] [select] [delete]
    ▬ R1-P3   x:840  y:760   len:6    [tint 0] [select] [delete]

  Doors (2)                    ← expandable section
    ⬤ R1-D1   To R2   transition   [unlocked]  [select]
    ⬤ R1-D2   Final   gate         [locked]    [select]

  Keys (1)
    ◆ R1-K1   x:700  y:680   Key A   [select]

  [Validation]  ⚠ 1 issue   [Show]
```

- Expandable sections per element type (default: expanded)
- Each item row: type icon (color-coded) + ID + key properties + action buttons
- Click item → jumps canvas to element and selects it
- Inline delete button (small `✕`)
- Validation badge per room (✓ / ⚠ / ✕)
- Element type icons use the established color palette

---

### 11. Typography Alignment

**Current:** `h2, h3 { font-size: 15px }` — flat, no scale. No `--font-size-*` token usage.

**Target:** Adopt the workbench type scale:
```css
.eyebrow   { font-size: var(--font-size-xs); text-transform: uppercase; letter-spacing: 0.14em; }
h1         { font-family: var(--font-display); font-size: 38px; line-height: 0.9; }
h2         { font-size: var(--font-size-lg); font-weight: 600; }
h3         { font-size: var(--font-size-base); font-weight: 600; }
.sub       { font-size: var(--font-size-sm); color: var(--text-muted); }
.hint      { font-size: var(--font-size-xs); color: var(--text-muted); }
.mono      { font-family: var(--font-mono); font-size: var(--font-size-xs); }
```

---

### 12. Missing Micro-Interactions

The Sprite Workbench has a complete micro-interaction system. The room editor is missing:

| Interaction | Current | Target |
|---|---|---|
| Button hover | `transform: translateY(-1px)` ✓ | Same — already correct |
| Button active/pressed | Missing `transform: translateY(0)` on `:active` | Add `transform: translateY(0); box-shadow: none` |
| Selection state feedback | Canvas highlight only | + Inspector panel slide-in (120ms ease) |
| Save confirmation | Toast only | + Nav bar "Saved ✓" indicator (2s) in the title area |
| Room switch | Instant snap | Add 80ms canvas fade transition |
| Element placed | Nothing | Brief glow pulse on newly placed element (CSS keyframe) |
| Validation run | Nothing | Brief "checking..." then state badge update |
| Dirty state | Nothing | `•` dot on the save button when there are unsaved changes |

---

### Summary: UI/UX Polish Checklist

This is the full set of UI/UX polish items, ordered by visual impact:

**Critical (visible to any user, immediately):**
- [ ] Replace `<details>/<summary>` with custom collapsible (biggest design system break)
- [ ] Canvas toolbar: add element-type color coding to tool buttons
- [ ] Inspector: dock as right rail, remove float-over-canvas
- [ ] View switch: replace `<select>` with tab strip
- [ ] Status bar: add state-aware visual treatment (success/error/warning)

**High (affects daily usability):**
- [ ] Add all missing design tokens to `:root`
- [ ] Canvas: responsive fill + dot-grid background
- [ ] View control bar: replace "Pan L/U/D/R" with icon arrow buttons
- [ ] Add "Fit to Room" zoom control
- [ ] Control cards: consolidate 3-card header into compact toolbar strip
- [ ] Dirty-state indicator on save button

**Medium (polish and consistency):**
- [ ] Typography: apply `--font-size-*` token scale throughout
- [ ] Inspector: live update on field change (remove "Apply Properties" button)
- [ ] Room inventory: expandable sections + type icons + inline actions
- [ ] Global map link panel: `.panel` treatment + styled summary
- [ ] Canvas: scale ruler at edges

**Low (final shine):**
- [ ] Canvas toolbar: keyboard shortcut badges on each button
- [ ] Element placement: brief glow pulse on newly placed elements
- [ ] Room switch: 80ms canvas fade transition
- [ ] Validation run: animated "checking..." state
- [ ] Inspector: slide-in animation on element selection

---

## Sprint Structure

### Sprint 0 — Foundations (1 week)
- Phase 0: `room_layout.json` contract + migration
- Phase 0: Room layout endpoints in workbench server
- Phase 1: Extract JS modules from monolithic HTML
- **Exit criteria:** Editor works from modular files, project-scoped persistence proven

### Sprint 1 — Design System & Canvas (1 week)
- Add all missing design tokens (border, text-muted, spacing scale, font-size scale, shadow scale, transition tokens)
- Replace `<details>/<summary>` with custom collapsible
- Canvas toolbar: element-type color coding, icon + label, keyboard shortcut badges, action/tool visual separation
- View control bar: tab strip for room/global switch, icon arrow pan buttons, Fit button, compact zoom input
- Inspector: dock as right rail, live field update, element type icon + color header, compact input sizing
- Status bar: state-aware visual treatment (success/error/warning/info)
- Canvas: responsive fill with ResizeObserver, dot-grid background
- Phase 3A: Shell & navigation
- Phase 3C: Undo/redo system
- **Exit criteria:** All critical + high UI/UX polish items complete; room editor visually matches workbench standard

### Sprint 2 — Project Lifecycle & Panels (1 week)
- Phase 2: Project lifecycle integration
- Control cards: consolidate 3-card header into compact toolbar strip
- Global map link panel: `.panel` treatment + styled summary
- Canvas scale ruler at edges
- Typography: apply `--font-size-*` token scale throughout
- Phase 3D: Empty states
- Phase 3E: Loading & error states
- Phase 3F: Room inventory panel (expandable sections, type icons, inline actions, validation badge)
- Phase 3G: Global map view upgrade (room labels, biome colors, validation indicators)
- Dirty-state indicator on save button
- Micro-interactions: selection slide-in, element glow pulse, room switch fade, save confirmation
- **Exit criteria:** Full project lifecycle working, all states handled, all medium + low polish items complete

### Sprint 3 — Validation Pipeline (1 week)
- Phase 4: All three validation levels
- Validation UX (per-room badges, jump-to-error)
- `level_validation.json` artifact
- **Exit criteria:** Validation runs and surfaces errors in canvas

### Sprint 4 — Export & Integration (1 week)
- Phase 5: Export contract + runtime package
- Phase 7: Workbench stage integration (Level Design stage card)
- Bundled export in Review & Export
- **Exit criteria:** Workbench can produce a bundled character + level export package

### Sprint 5 — AI Features (1–2 weeks)
- Phase 6A: Room generation from description
- Phase 6B: Style-coherent world theming
- Phase 6C: Layout validation suggestions
- **Exit criteria:** AI features functional, gated by project having character lock

---

## Design Language Consistency

The room editor already uses the correct design tokens. The overhaul must maintain this. All new UI components use:

**Colors:**
- Background: `--bg: #050709`
- Panel: `rgba(4, 6, 10, 0.96)`
- Border: `rgba(0, 232, 200, 0.07)` / `0.14` strong
- Text: `--text: #cce8e0`, `--muted: #5d7870`
- Accent: `--accent: #00e8c8`
- Success/Warning/Error: `#4ade80` / `#d29922` / `#f85149`

**Element type colors (keep existing):**
- Platforms: `#77b8ff`
- Doors: `#f5986e`
- Vertices: `#ff6b8a`
- Keys: `#4ade80`
- Abilities: `#a78bfa`
- Movers: `#fbbf24`

**Typography:**
- Body: `Plus Jakarta Sans`
- Display/headings: `Bebas Neue`
- Code/JSON: `DM Mono`

**New component patterns to add (matching workbench):**
- `.stage-header` — stage title + status + primary CTA
- `.stage-card` — content area matching workbench panel cards
- `.stage-progress` — step progress indicator
- `.validation-badge` — inline pass/warn/fail indicators
- `.ai-assist-button` — distinct from primary actions (uses purple accent)
- `.empty-state` — centered illustration + headline + CTA

---

## What Not to Do

1. **Do not merge HTML before persistence is unified** — this creates duplicated save logic and brittle state drift.
2. **Do not rewrite the canvas interaction layer** — it's the best part of the current editor; refactor its shell only.
3. **Do not couple room editing to character pipeline internals** — the level design domain should be parallel, not nested.
4. **Do not add AI features before the core tool is production-grade** — AI on top of a broken foundation is noise.
5. **Do not over-engineer the export contract** — match the sprite workbench pattern; don't invent a new one.
6. **Do not target LDtk users directly in early versions** — they have a free, polished tool they love. Target the programmer-first devs who don't have a workflow yet.

---

## Success Metrics (Definition of Production-Ready)

**Structural:**
- [ ] All room layouts are project-scoped (no global `room-layout-data.json` dependency)
- [ ] JS modules extracted (no 4000+ line monolith)
- [ ] Undo/redo functional (50-command history)
- [ ] Workbench server owns all room layout endpoints

**Quality pipeline:**
- [ ] Level 1 validation runs and reports all structural errors
- [ ] Level 2 validation runs and reports all traversal errors
- [ ] `level_validation.json` artifact written per validation run
- [ ] Validation gate blocks export until Level 1 passes

**Export:**
- [ ] Runtime package produces `rooms/`, `world_graph.json`, `level_manifest.json`
- [ ] Bundled workbench export includes both sprite and level packages
- [ ] Export manifest includes SHA and validation state

**UX:**
- [ ] Empty states defined for all zero-data views
- [ ] Loading states shown for all async operations
- [ ] Error states handled with recovery actions
- [ ] Keyboard shortcuts documented (`?` modal)
- [ ] Validation errors are jump-navigable in canvas
- [ ] Responsive: works on MacBook Air (1280px) and iPhone 16 Pro portrait (393px)

**AI features (Sprint 5):**
- [ ] Room generation from description produces valid room JSON
- [ ] Generated rooms pass Level 1 validation before being presented to user
- [ ] Style theming applies project character palette to room biomes
- [ ] Validation suggestions produce actionable, targeted platform placement proposals

---

## Risks

### Risk 1: Canvas regression during extraction
Extracting 4,539 lines of interleaved HTML/CSS/JS risks subtle rendering and interaction regressions.
**Mitigation:** Extract modules incrementally, test after each module extraction. Keep original as fallback during Sprint 0.

### Risk 2: Server endpoint conflicts during migration
Adding room layout to the workbench server while the standalone server still runs creates double-write risk.
**Mitigation:** New endpoints are read-write only to project-scoped paths; old server only touches global path. Run both until migration is proven end-to-end.

### Risk 3: AI room generation produces invalid rooms
AI-generated polygon + platform layouts may fail reachability or structural rules.
**Mitigation:** Run Level 1 validation on AI output before presenting to user. Show validation report alongside generated layout. Never auto-apply AI output without user review.

### Risk 4: AI theming conflicts with user's manual tint choices
Auto-assigned biome colors overwrite intentional user choices.
**Mitigation:** Theming is suggestion-only, not auto-applied. User explicitly accepts per biome. Per-element tint overrides always take precedence.

### Risk 5: Over-scoping AI features pushes core work out
If AI work starts before the core tool is solid, bugs compound.
**Mitigation:** AI features are Sprint 5 only. Sprints 0–4 contain zero AI work.

---

## Appendix: Canonical Room Layout Schema (v2)

```json
{
  "project_id": "string",
  "version": 2,
  "updated_at": "ISO-8601",
  "meta": {
    "worldWidth": 1600,
    "worldHeight": 1200,
    "grid": 32,
    "notes": "string",
    "biome_themes": {
      "hub": { "tint_0": "#77b8ff", "tint_1": "#a5c8f0", "tint_2": "#3a7abf" },
      "branch_a": null,
      "branch_b": null,
      "branch_c": null,
      "final": null
    }
  },
  "rooms": [
    {
      "id": "R1",
      "name": "string",
      "biome": "hub | branch_a | branch_b | branch_c | final | custom",
      "notes": "string",
      "global": { "x": 0, "y": 0 },
      "polygon": [[x, y]],
      "size": { "width": 0, "height": 0 },
      "platforms": [
        { "id": "R1-P1", "x": 0, "y": 0, "len": 0, "tint": 0 }
      ],
      "doors": [
        {
          "id": "R1-D1",
          "x": 0, "y": 0,
          "kind": "transition | branch | return | gate | secret",
          "label": "string",
          "targetRoom": "R2",
          "locked": false,
          "gateCondition": null
        }
      ],
      "keys": [
        { "id": "R1-K1", "x": 0, "y": 0, "kind": "key_item | ability | ability_unlock | misc", "label": "string" }
      ],
      "movers": [
        { "id": "R1-M1", "x1": 0, "y1": 0, "x2": 0, "y2": 0, "speed": 1, "easing": "linear", "locked": false }
      ],
      "playerStart": { "x": 0, "y": 0 },
      "edgeLinks": [
        { "edgeIndex": 0, "targetRoomId": "R2", "targetEdgeIndex": 1 }
      ],
      "validation": {
        "level_1": null,
        "level_2": null
      }
    }
  ]
}
```
