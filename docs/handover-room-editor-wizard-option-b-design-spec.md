# Design spec — Room Editor Wizard, Option B (Stage-First Drawer)

**Status:** Approved direction for production translation (HI-FI mockup is source of truth for layout and chrome).  
**Date:** 2026-04-14  
**Visual source:** `docs/mockups/room-editor-wizard-option-b-stage-first.html`  
**Design system:** `STYLE_GUIDE.md` — production must use canonical tokens (`--bg`, `--accent`, `--text`, spacing/radius scale); mockup uses parallel `--fs-*` / `--s*` names; map to `editor-tokens.css` during implementation.

---

## 1. Product intent

- **Stage-first:** The **Layout** phase keeps the user on a **full-height editing stage** (room title, metrics strip, canvas, floating tools, bottom task drawer). Other phases trade the live stage for a **focus workspace** so authoring stays guided without competing with the canvas.
- **Solo metroidvania author:** Plain-language labels, phase tasks in the drawer, inspector content that matches the active phase — no silent AI mutation of layout (aligns with `prompts/project_plan.md` room editor intent).

---

## 2. Shell structure (top → bottom)

| Region | Behavior |
|--------|----------|
| **App grid** | `grid-template-rows: 52px auto 1fr` — topbar, phase bar, main. |
| **Topbar** | Brand, crumb, global actions (command palette stub, Validate, Export, Save). |
| **Phase bar** | Scope chips (World / Room / Art Direction) + **centered horizontal phase rail** (pills) + **Prev / Next** actions. |
| **Main** | **Layout:** `1fr | 360px` — stage + right inspector. **Non-layout:** `1fr` only — inspector column hidden; focus panel fills width below top chrome. |

---

## 3. Phase model

**Ordered phases:** `identity` → `layout` → `environment` → `entities` → `review`.

**Mock implementation:** `#optb-app[data-phase="…"]` drives visibility; `setPhase(phase)` updates pills, inspector copy, wizard panes, drawer header, and layout vs focus UI.

### 3.1 Layout phase

- Show **full stage stack:** `stage-bar` + `canvas-wrap` with grid, sample geometry, **floating tool palette**, optional HUD cards, **task drawer** anchored to canvas bottom.
- Show **right inspector** (360px): header + body with **active** `.wizard-pane[data-pane="layout"]`.
- **Hide** `#optb-stage-focus`.

### 3.2 Non-layout phases

- **Hide** full layout stack (`#optb-stage-layout` uses `.is-hidden`).
- **Show** `#optb-stage-focus`: scrollable panel with **wide grid** `minmax(0,1fr) | min(280px, 30vw)`:
  - **Main column:** Teleported inspector header + body (same DOM nodes as layout inspector — see Section 5).
  - **Reference rail:** Sticky aside; phase-specific blocks (`.focus-block[data-focus="…"]`); thumbnails; **Open … preview** opens modal.
- **Hide** `#optb-inspector` column (entire right rail removed from grid).

### 3.3 Navigation

- **Pills:** click sets phase; `aria-selected` on active pill.
- **Prev / Next:** cycle order (mock wraps; product may clamp or block locked phases).
- **Keyboard:** `ArrowLeft` / `[` and `ArrowRight` / `]` change phase when focus is **not** in `input` / `textarea` / `contenteditable`; no modifier keys. `Escape` closes preview modal.

---

## 4. Canvas chrome (Layout only)

### 4.1 Stage bar

- **Left:** Room display name (`Bebas`), monospace line: room id, canvas size, grid pitch.
- **Right:** **Zoom** segmented control (Fit, 25%, 50%, 100%, 200%) — text labels in mock; optional future iconography is out of scope unless Design extends mockup.
- **Icon buttons** (after zoom): Grid toggle, Snap, Undo, Redo — see Section 6.

### 4.2 Floating tool palette

- **Position:** `absolute`, `left`/`top` =12px from canvas edge (use token spacing).
- **Container:** Frosted panel, `border-radius: 14px`, column `gap: 4px`, inner padding `6px`.
- **Tool cells:** `36×36px`, `border-radius: 10px`.
- **States:** default muted; hover light fill; **active** accent soft fill + inset ring (matches segmented active language).
- **Shortcut badge:** `position: absolute`, `right: -2px`, `bottom: -2px`, mono `8px`, small chip on `--panel-3`.

### 4.3 Task drawer

- **Position:** Overlay bottom of canvas; gradient fade into panel background.
- **Grid:** handle + horizontal task scroller + actions column.
- **Tasks:** cards with done / active / pending styling; active task uses accent border + soft glow (same family as active pill).

### 4.4 HUD (optional)

- Top-right stack of small cards (cursor, selection summary, warnings). Product may merge with status bar; mock shows composition only.

---

## 5. Inspector “teleport” (critical engineering contract)

- On **Layout:** `#optb-ins-head` and `#optb-ins-body` are children of `#optb-inspector`.
- On **non-layout:** The **same two nodes** are **moved** into `#optb-wide-head-slot` and `#optb-wide-main-slot` (DOM `appendChild`), so state and focus are preserved if implementation shares one inspector instance.
- **Wizard panes:** Multiple `.wizard-pane[data-pane="…"]` in body; exactly one has `.active` and is not `hidden` for the current phase.

---

## 6. Toolbar iconography (actionable)

**Rules:**

- **Format:** Inline **SVG** only (no icon font, no emoji, no ambiguous Unicode).
- **Color:** `stroke="currentColor"` / `fill="currentColor"` (or fill on select pointer only). Stage bar icons inherit muted/text; tool icons inherit tool color.
- **Sizing:** Stage bar glyphs **18×18** viewBox 24×24; palette glyphs **20×20** in **36×36** hit target.
- **Stroke:** `1.5` px in a 24×24 viewBox, `round` caps/joins unless fill-only.
- **Accessibility:** Every icon-only control has **`title`** + **`aria-label`**; decorative SVGs `aria-hidden="true"`.
- **Focus:** `button:focus-visible` outline `2px solid rgba(0,232,200,0.35)`, `outline-offset: 2px`.

**Stage bar**

| Control | Semantics | Mock treatment |
|--------|-----------|----------------|
| Grid | Toggle grid overlay | Four-cell grid (two strokes each axis) |
| Snap | Snap to grid | Corner brackets + center dot |
| Undo | History back | Curved arrow left |
| Redo | History forward | Curved arrow right |

**Floating tools** (entity tint via CSS `color: var(--ent-*)` matching domain colors in mock `:root`)

| Tool | Shortcut | Icon treatment |
|------|----------|----------------|
| Select | V | Filled pointer (distinct at small size) |
| Vertex | N | Stroked diamond |
| Platform | P | Horizontal bar (`rect`) |
| Door | D | Door frame + knob dot |
| Key | K | Circle + key shaft strokes |
| Ability | A | Four-point star (stroke) |
| Mover | M | Horizontal double-arrow |
| Start | S | Flag / marker (post + banner) |
| Pan | H | Center dot + four rays |

**Entity color tokens (mock — align to `STYLE_GUIDE` / editor entity keys):**

- Platform `#4a9eff`, Door `#ff9750`, Vertex `#ff6aa3`, Key `#6ee792`, Ability `#a77dff`, Mover `#f5d54b`, Start `#d0b0ff`.

---

## 7. Focus workspace & preview modal

- **Reference rail** title: uppercase eyebrow “Reference”.
- **Thumbnails:** `mini-canvas` with optional decor overlay class for non-layout previews.
- **CTAs:** e.g. “Open layout preview”, “Open decorated preview” — open `#optb-modal` with backdrop, dialog role, title swap (layout vs decor), `Escape` to close.
- **Modal body:** Read-only snapshot area; production loads live room snapshot or cached render.

---

## 8. Content mapping (inspector copy)

Mock uses a single JS `copy` map per phase (eyebrow, title, description). Production should drive the same strings from wizard config or i18n table so **phase rail**, **inspector header**, and **drawer subtitle** stay synchronized.

---

## 9. Implementation checklist (Engineering)

1. [ ] Match **grid structure** and **phase visibility** rules to Sections 2–3 (including `data-phase` or router equivalent).
2. [ ] Implement **inspector relocation** per Section 5 without duplicating form markup.
3. [ ] **Layout-only:** floating tools + drawer + stage bar; wire tools to real editor tool state.
4. [ ] **Icons:** Ship SVG set per Section 6; verify **contrast** on `--panel-3` and canvas background.
5. [ ] **Keyboard:** Phase navigation + modal close; respect focus-in-field guard.
6. [ ] **Tokens:** Replace mock hard-coded hex with `editor-tokens.css` / `STYLE_GUIDE` variables where production forbids literals.
7. [ ] **A11y:** Tab order: topbar → phase rail → main landmark → tools → drawer → inspector; modal focus trap when open.
8. [ ] **Tests:** Add or extend editor UI tests if wiring introduces regressions (tool selection, phase change); visual parity optional screenshot compare against mock.

---

## 10. Out of scope / follow-ups

- **Zoom icons:** Mock uses text; add only if Design updates HI-FI.
- **Option A / C:** Different shell contracts — do not merge without founder decision.
- **Hybrid B mockup** (`room-editor-wizard-hybrid-b-sprite-aligned-mockup.html`): May differ in rail density; Option B file above is the **authoritative** Option B contract.

---

## 11. Handoff recipients

| Role | Action |
|------|--------|
| **Design** | Sign off production screenshots vs mockup; extend mock if zoom/tool variants are needed. |
| **Engineering** | Implement Section 9 checklist against `room-layout-editor.html` + `css/` + `js/editor/` per `prompts/project_plan.md`. |
| **QA** | Phase transitions, inspector teleport, modal, keyboard nav, tool active states, regression on export/validate. |

---

**Recommendation:** Treat the mockup HTML as a **pixel-composition reference**, not copy-paste production code — translate classes into existing editor shell modules to avoid drift.  
**Risks:** Inspector teleport is easy to get wrong with duplicate IDs or stale layout if two inspector instances exist.  
**Confidence:** High for information architecture; medium for final spacing until compared in browser side-by-side.  
**Founder approval needed:** Only if deviating from Option B (e.g. dropping drawer or changing phase set).  
**Next actions:** Engineering spikes inspector move + `data-phase` shell; Design schedules mockup vs build review after first integration.
