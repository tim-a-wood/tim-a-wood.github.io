# Room Editor Overhaul — AI Agent Task Specification

**Source plan:** `docs/room-editor-overhaul-plan.md`
**Target file:** `room-layout-editor.html`
**Date:** 2026-03-26

---

## How to Use This Document

This spec is structured for autonomous execution by an AI agent. Each sprint is a self-contained unit. Read the full sprint before writing any code. After completing each numbered task, run the verification step for that task before proceeding. Report progress using the format in the Progress Reporting section.

**Read first, always:**
1. Read `docs/room-editor-overhaul-plan.md` for full context and rationale.
2. Read `room-layout-editor.html` in full before making any changes.
3. Read `tools/2d-sprite-and-animation/app/product-shell.css` to understand the workbench design standard.
4. Read `tools/2d-sprite-and-animation/index.html` lines 1–100 for token reference.

**Preserve absolutely:**
- All canvas interaction logic (mouse down/move/up, hit detection, snap math, edge linking)
- All room data structures and their IDs
- All save/load logic (localStorage and server sync)
- All existing CSS class names used in JS (changing a class name in CSS without updating JS breaks the tool)

**Never do:**
- Change any JS event handler signatures or canvas rendering logic without reading them first
- Remove any element IDs referenced in JavaScript
- Split into multiple HTML files (stays as a single file)
- Use any CSS framework (Bootstrap, Tailwind) — custom CSS only
- Change the server API endpoints (those are Sprint 0 work handled separately)

---

## Progress Reporting

After completing each numbered task, output a progress line in this format:

```
✓ TASK [sprint].[task] — [one-line description] — [files modified]
```

Example:
```
✓ TASK 1.3 — Added missing design tokens to :root — room-layout-editor.html
```

If a task is blocked or produces an unexpected result, output:
```
⚠ BLOCKED [sprint].[task] — [what was attempted] — [what went wrong] — [proposed resolution]
```

At the end of each sprint — after the verification checklist AND after the demo — output a sprint summary:
```
━━━ SPRINT [n] COMPLETE ━━━
Tasks completed: [n/n]
Files modified: [list]
Verification status: [PASS / PARTIAL — describe]
Demo status: [PASS / PARTIAL / BLOCKED — screenshots taken, key observations]
Blockers carried forward: [none / describe]
Ready for next sprint: [YES / NO — reason if no]
```

The order is always: tasks → verification checklist → demo → sprint summary. Never skip the demo. Never move to the next sprint until the sprint summary is output with `Ready for next sprint: YES`.

---

## Demo Protocol

After completing each sprint's verification checklist, run a live demo before declaring the sprint done and before starting the next sprint. The demo is not optional — it is the gate between sprints.

### How to Run a Demo

```
1. Open the tool in the browser:
   open /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html

2. Wait 1 second for the page to load fully:
   sleep 1

3. Take a screenshot:
   screencapture -x /tmp/room-editor-demo-sprint-[N]-[label].png

4. Read the screenshot using the Read tool to visually inspect the result.

5. Perform any required interactions, re-screenshot, and re-read.

6. Output a demo report in the format below.
```

**Important:** The `screencapture -x` flag captures without playing a sound. Screenshots are saved to `/tmp/` and should be read immediately after capture. Take multiple screenshots for different states (default, item selected, settings open, etc.) as specified in each sprint's demo script.

### Demo Report Format

```
━━━ SPRINT [n] DEMO ━━━
Screenshots taken: [list of /tmp filenames]

Visual observations:
  [component name]: [what you see — be specific about colors, layout, spacing, text]
  [component name]: [what you see]
  ...

Feature verification:
  ✓ [feature] — [what was observed that confirms it works]
  ✗ [feature] — [what was observed that indicates a problem]

Regressions spotted: [none / describe]
Design quality vs. Sprite Workbench: [assessment — specific differences or matches]
Approved to proceed: [YES / NO — reason if no]
```

The "Design quality vs. Sprite Workbench" line is required. Open `tools/2d-sprite-and-animation/index.html` in the browser alongside the room editor and compare the visual standard directly. Note any gaps.

### What a Blocked Demo Looks Like

If the page fails to load, renders blank, or shows console errors visible in the screenshot, stop immediately:
```
⚠ DEMO BLOCKED — Sprint [n] — [describe what you see in the screenshot] — do not proceed to next sprint
```
Fix the issue, re-run verification, and re-demo before continuing.

---

## Pre-Flight Checklist

Before starting Sprint 1, verify these facts about the current file. If any fail, report as a blocker before proceeding.

```
□ room-layout-editor.html exists at repo root
□ File is a single HTML file (no imports of other .js or .css files, except Google Fonts)
□ :root block exists with --bg, --accent, --font-sans variables
□ canvas#roomCanvas exists with width="960" height="720"
□ canvas#globalCanvas exists with width="960" height="720"
□ .canvas-toolbar exists and contains buttons with data-tool attributes
□ .inspector exists with id="selectionInspector"
□ .view-control-bar exists (room zoom controls)
□ <details> element exists wrapping the JSON textarea
□ .app-shell grid exists with sidebar + main column
□ All JS is inline in a single <script> block at bottom of file
```

---

## Sprint 1 — Design System & Canvas Polish

**Goal:** Bring the room editor's visual standard to full parity with the Sprite Workbench. No behavior changes — pure UI/UX work.

**Files to modify:** `room-layout-editor.html` only.

**Estimated scope:** CSS additions/changes, HTML structure changes. No JS logic changes.

---

### Task 1.1 — Extend the Design Token Set

**Location:** The `:root { }` block at the top of the `<style>` section.

**What to do:** Add all tokens that the Sprite Workbench has but the room editor lacks. Do NOT remove any existing tokens. Do NOT change existing token values.

**Tokens to add (exact values):**
```css
/* Aliases matching workbench naming */
--border: rgba(0,232,200,0.07);
--border-strong: rgba(0,232,200,0.14);
--text-muted: #5d7870;
--text-faint: rgba(204,232,224,0.25);
--surface-hover: rgba(6, 9, 14, 0.98);
--bg-raised: rgba(4, 6, 10, 0.98);
--bg-soft: #07090c;
--accent-hover: #20f4d4;

/* Spacing scale */
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 24px;
--space-6: 32px;
--space-7: 48px;
--space-8: 64px;
--surface-gap: 12px;
--surface-pad: 14px;

/* Type scale */
--font-size-xs: 11px;
--font-size-sm: 13px;
--font-size-base: 14px;
--font-size-md: 15px;
--font-size-lg: 18px;
--font-size-xl: 22px;

/* Shadow scale */
--shadow-sm: 0 2px 8px rgba(0,0,0,0.18);
--shadow-md: 0 6px 20px rgba(0,0,0,0.26);
--shadow-lg: 0 12px 40px rgba(0,0,0,0.38);

/* Transition tokens */
--transition-fast: 120ms ease;
--transition-base: 200ms ease;

/* Nav height */
--nav-h: 52px;

/* Element type colors (keep existing, add missing) */
--color-key: #4ade80;
--color-ability: #a78bfa;
--color-mover: #fbbf24;
--color-start: #f0abfc;
```

**After adding:** Find all hardcoded color values and hardcoded transition values in the existing CSS and replace them with their token equivalents. Specifically:
- Replace `120ms ease` → `var(--transition-fast)`
- Replace `200ms ease` → `var(--transition-base)`
- Replace `rgba(0, 232, 200, 0.1)` → `var(--line)` (already exists, just ensure it's used)
- Replace `0 12px 40px rgba(0,0,0,0.38)` → `var(--shadow-lg)`
- Replace `0 8px 24px rgba(0, 0, 0, 0.35)` → `var(--shadow-md)` (used in inspector)

**Verification:** Open the file in a browser. The tool should look identical to before. No visual changes yet — tokens are just being added to the vocabulary.

---

### Task 1.2 — Replace `<details>/<summary>` with Custom Collapsible

**Location:** Find the `<details>` element (around line 1023). It wraps the "Advanced Import / Scratch / Raw JSON" section.

**What to replace it with:**
```html
<div class="collapsible-section" id="advancedSection">
  <button class="collapsible-toggle" id="advancedToggle" aria-expanded="false">
    <span class="collapsible-label">Raw JSON / Debug Tools</span>
    <svg class="collapsible-chevron" width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3 5L7 9L11 5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </button>
  <div class="collapsible-body" id="advancedBody" hidden>
    <!-- move the existing <details> inner content here verbatim -->
  </div>
</div>
```

**CSS to add:**
```css
.collapsible-section {
  border: 1px solid var(--line);
  border-radius: 16px;
  overflow: hidden;
}
.collapsible-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 10px 14px;
  background: rgba(255,255,255,0.03);
  border: none;
  border-radius: 0;
  color: var(--muted);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  min-height: 40px;
  transition: background var(--transition-fast), color var(--transition-fast);
  text-align: left;
}
.collapsible-toggle:hover {
  background: rgba(255,255,255,0.06);
  color: var(--text);
  transform: none;
}
.collapsible-chevron {
  flex-shrink: 0;
  color: var(--muted);
  transition: transform var(--transition-fast);
}
.collapsible-toggle[aria-expanded="true"] .collapsible-chevron {
  transform: rotate(180deg);
}
.collapsible-body {
  padding: 14px;
  display: grid;
  gap: 10px;
  border-top: 1px solid var(--line);
}
.collapsible-body[hidden] {
  display: none;
}
```

**JS to add** (in the existing `<script>` block, after the existing init code):
```js
// Collapsible sections
document.querySelectorAll('.collapsible-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const expanded = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!expanded));
    const body = document.getElementById(btn.id.replace('Toggle', 'Body'));
    if (body) body.hidden = expanded;
  });
});
```

**Verification:**
- `<details>` element no longer present in the file
- "Raw JSON / Debug Tools" toggle button is visible
- Clicking it shows/hides the JSON textarea and buttons
- Chevron rotates on open/close
- Textarea still functional (import, export still work)

---

### Task 1.3 — View Switch: Replace `<select>` with Tab Strip

**Location:** Find the `<select id="viewMode">` element inside the "Current map" control card.

**Current HTML (find this):**
```html
<label>
  View
  <select id="viewMode">
    <option value="room">Room Editor</option>
    <option value="global">Global Map</option>
  </select>
</label>
```

**Replace with:**
```html
<div class="tab-strip" id="viewModeStrip">
  <button class="tab-btn active" data-view="room">Room View</button>
  <button class="tab-btn" data-view="global">Global Map</button>
</div>
```

**CSS to add:**
```css
.tab-strip {
  display: flex;
  gap: 4px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 3px;
}
.tab-btn {
  flex: 1;
  min-height: 32px;
  padding: 5px 10px;
  border-radius: 11px;
  border: none;
  background: none;
  color: var(--muted);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}
.tab-btn:hover {
  color: var(--text);
  background: rgba(255,255,255,0.06);
  transform: none;
}
.tab-btn.active {
  background: rgba(0,232,200,0.12);
  color: var(--text);
  border-color: transparent;
  box-shadow: none;
}
```

**JS: update the view-switch handler.** Find the existing `viewMode` change handler and update it to listen to the tab strip instead. The existing handler does something like:

```js
// Find the existing handler that reads viewMode.value
// It will be something like:
document.getElementById('viewMode').addEventListener('change', ...)
// or viewMode is read in a render function

// Replace the select listener with:
document.querySelectorAll('#viewModeStrip .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#viewModeStrip .tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const view = btn.dataset.view;
    // Replicate exactly what the old select onChange did, using `view` instead of `viewMode.value`
    // Typically: show/hide roomCanvasBox and globalCanvasBox, show/hide viewControls
  });
});
```

**Critical:** Read the existing JS handler for `viewMode` before touching this. Replicate its exact behavior.

**Verification:**
- Tab strip renders with two buttons: "Room View" and "Global Map"
- Clicking "Global Map" switches to global canvas (same behavior as old select)
- Clicking "Room View" switches back
- Active tab has cyan highlight
- No `<select id="viewMode">` remains in the file

---

### Task 1.4 — Canvas Toolbar: Color-Code Tool Buttons by Element Type

**Location:** The `.canvas-toolbar` div containing the `data-tool` buttons.

**What to do:** Add element-type color dots to each tool button using CSS `::before` pseudo-elements. Add keyboard shortcut hints as small badges.

**Current button HTML (example):**
```html
<button data-tool="platform">Add Platform</button>
```

**Update each button to include shortcut hint:**
```html
<button data-tool="select">Select <kbd>V</kbd></button>
<button data-tool="vertex">Add Vertex <kbd>E</kbd></button>
<button data-tool="platform">Add Platform <kbd>P</kbd></button>
<button data-tool="door">Add Door <kbd>D</kbd></button>
<button data-tool="key">Add Key <kbd>K</kbd></button>
<button data-tool="ability">Add Ability <kbd>A</kbd></button>
<button data-tool="mover">Add Mover <kbd>M</kbd></button>
<button data-tool="start">Set Start <kbd>S</kbd></button>
<button data-tool="room-move">Move Room <kbd>G</kbd></button>
```

**CSS to add for color dots and kbd badges:**
```css
/* Color dots on element-type tool buttons */
.canvas-toolbar button[data-tool="platform"]::before { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: var(--platform); margin-right: 6px; flex-shrink: 0; }
.canvas-toolbar button[data-tool="door"]::before      { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--door); margin-right: 6px; flex-shrink: 0; }
.canvas-toolbar button[data-tool="vertex"]::before    { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--vertex); margin-right: 6px; flex-shrink: 0; }
.canvas-toolbar button[data-tool="key"]::before       { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: var(--color-key); margin-right: 6px; flex-shrink: 0; }
.canvas-toolbar button[data-tool="ability"]::before   { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--color-ability); margin-right: 6px; flex-shrink: 0; }
.canvas-toolbar button[data-tool="mover"]::before     { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: var(--color-mover); margin-right: 6px; flex-shrink: 0; }
.canvas-toolbar button[data-tool="start"]::before     { content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--color-start); margin-right: 6px; flex-shrink: 0; }

/* Update canvas toolbar buttons to use flex for alignment */
.canvas-toolbar button {
  display: flex;
  align-items: center;
  min-height: 36px;
  padding: 6px 9px;
  font-size: var(--font-size-xs);
  text-align: left;
  border-radius: 12px;
}

/* Keyboard shortcut badge */
.canvas-toolbar kbd {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-faint);
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 4px;
  padding: 0 4px;
  min-width: 18px;
  text-align: center;
  line-height: 16px;
}

/* Visual separation: action buttons vs. tool buttons */
.canvas-toolbar .toolbar-divider {
  height: 1px;
  background: var(--line);
  margin: 4px 0;
}

/* Action buttons (Delete, Duplicate, etc.) are slightly more muted */
.canvas-toolbar button#deleteSelected,
.canvas-toolbar button#duplicatePlatform,
.canvas-toolbar button#toggleSelectedEdge,
.canvas-toolbar button#centerRoom {
  color: var(--muted);
  font-size: var(--font-size-xs);
}
.canvas-toolbar button#deleteSelected:hover,
.canvas-toolbar button#duplicatePlatform:hover,
.canvas-toolbar button#toggleSelectedEdge:hover,
.canvas-toolbar button#centerRoom:hover {
  color: var(--text);
}
```

**Note on keyboard shortcuts:** If the existing JS does NOT already handle these key bindings, add them. If it does, verify the key bindings match the `<kbd>` labels added above.

**Verification:**
- Each element-type tool button has a color dot matching its element color
- Keyboard shortcut badges visible on the right of each button label
- Action buttons (Delete, Duplicate, etc.) are visually distinct from tool mode buttons
- All existing tool selection behavior still works

---

### Task 1.5 — View Control Bar: Replace "Pan L/U/D/R" with Arrow Buttons

**Location:** `.view-control-bar` divs inside `#roomCanvasBox` and `#globalCanvasBox`.

**Current HTML:**
```html
<button id="roomPanLeft">Pan L</button>
<button id="roomPanUp">Pan U</button>
<button id="roomPanDown">Pan D</button>
<button id="roomPanRight">Pan R</button>
```

**Replace with:**
```html
<div class="pan-controls">
  <button id="roomPanUp" class="pan-btn pan-up" title="Pan Up (↑)">
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 9V3M6 3L3 6M6 3L9 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
  </button>
  <div class="pan-middle-row">
    <button id="roomPanLeft" class="pan-btn pan-left" title="Pan Left (←)">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M9 6H3M3 6L6 3M3 6L6 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </button>
    <div class="pan-center-dot"></div>
    <button id="roomPanRight" class="pan-btn pan-right" title="Pan Right (→)">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M3 6H9M9 6L6 3M9 6L6 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
    </button>
  </div>
  <button id="roomPanDown" class="pan-btn pan-down" title="Pan Down (↓)">
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 3V9M6 9L3 6M6 9L9 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
  </button>
</div>
```

Do the same replacement for global pan buttons (`globalPanLeft`, `globalPanUp`, etc.).

**Also update the zoom buttons:**
- Change `<button id="roomZoomOut">-</button>` → `<button id="roomZoomOut" title="Zoom Out (-)">−</button>`
- Change `<button id="roomZoomIn">+</button>` → `<button id="roomZoomIn" title="Zoom In (+)">+</button>`
- Add `<button id="roomZoomFit" title="Fit Room">Fit</button>` after the zoom readout group

**CSS:**
```css
.pan-controls {
  display: grid;
  grid-template-rows: auto auto auto;
  gap: 2px;
  align-items: center;
  justify-items: center;
}
.pan-middle-row {
  display: flex;
  gap: 2px;
  align-items: center;
}
.pan-btn {
  width: 28px;
  min-height: 28px;
  padding: 0;
  display: grid;
  place-items: center;
  border-radius: 8px;
  color: var(--muted);
}
.pan-btn:hover {
  color: var(--text);
  transform: none;
}
.pan-center-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--line);
  margin: 0 2px;
}
```

**JS:** The existing button IDs (`roomPanLeft`, `roomPanUp`, etc.) are unchanged. The JS should work without modification. If a "Fit" handler doesn't exist, add one:
```js
document.getElementById('roomZoomFit')?.addEventListener('click', () => {
  // Reset zoom and pan so room fits canvas
  // Read how roomZoom and roomPan are set in existing zoom-reset handler
  // and replicate for fit-to-bounds
  if (typeof fitRoomToCanvas === 'function') fitRoomToCanvas();
  else { state.roomZoom = 1; state.roomPan = {x:0, y:0}; renderRoom(); }
});
```

**Verification:**
- No text "Pan L/U/D/R" visible in UI
- Arrow icon buttons visible in a D-pad arrangement
- Clicking each arrow still pans the canvas (existing pan behavior unchanged)
- "Fit" button zooms to fit room in viewport
- Zoom readout still shows current zoom level

---

### Task 1.6 — Inspector: Dock as Right Rail, Remove Float

**Location:** The `.inspector` div currently positioned `position: absolute; top: 64px; right: 12px;`.

**What to do:**
1. Remove the `position: absolute` positioning from `.inspector`
2. Move the inspector HTML element to be outside `.canvas-box`, positioned as a sibling
3. Update the canvas layout to be a side-by-side grid when an item is selected

**Current structure:**
```html
<div class="canvas-box" id="roomCanvasBox">
  <div class="canvas-toolbar">...</div>
  <div class="view-control-bar">...</div>
  <div class="inspector" id="selectionInspector">...</div>  ← inside canvas-box
  <canvas id="roomCanvas">...</canvas>
</div>
```

**New structure:**
```html
<div class="canvas-with-inspector" id="canvasWithInspector">
  <div class="canvas-box" id="roomCanvasBox">
    <div class="canvas-toolbar">...</div>
    <div class="view-control-bar">...</div>
    <canvas id="roomCanvas">...</canvas>
  </div>
  <div class="inspector" id="selectionInspector">  ← outside canvas-box, sibling
    <div class="inspector-header">
      <div class="inspector-type-icon" id="inspectorTypeIcon"></div>
      <div class="inspector-title" id="inspectorTitle">Selection</div>
      <button class="inspector-close" id="inspectorClose" title="Deselect (Esc)">×</button>
    </div>
    <!-- existing field rows stay exactly as-is -->
    ...existing field rows...
    <button id="applyProps" class="good">Apply</button>
  </div>
</div>
```

**CSS changes:**
```css
/* Remove the absolute positioning from inspector */
.inspector {
  /* Remove: position: absolute; top: 64px; right: 12px; */
  width: 240px;
  flex-shrink: 0;
  background: linear-gradient(180deg, rgba(11, 16, 20, 0.98), rgba(7, 10, 13, 0.98));
  border: 1px solid var(--line-strong);
  border-radius: 18px;
  padding: 12px;
  display: grid;
  gap: 8px;
  box-shadow: var(--shadow-md);
  align-self: start;
  /* Still hidden by default */
}
.inspector.hidden {
  display: none;
}

/* Canvas + inspector side-by-side layout */
.canvas-with-inspector {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  min-height: 0;
}
.canvas-with-inspector .canvas-box {
  flex: 1;
  min-width: 0;
}

/* Inspector header with type icon + close */
.inspector-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--line);
}
.inspector-type-icon {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex-shrink: 0;
}
.inspector-title {
  flex: 1;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text);
}
.inspector-close {
  width: 24px;
  min-height: 24px;
  padding: 0;
  border-radius: 6px;
  font-size: 14px;
  color: var(--muted);
  line-height: 1;
  display: grid;
  place-items: center;
}
.inspector-close:hover {
  color: var(--text);
  transform: none;
}

/* Compact inspector inputs */
.inspector input,
.inspector select {
  min-height: 32px;
  padding: 6px 10px;
  font-size: var(--font-size-xs);
}
.inspector label {
  font-size: 10px;
}
```

**JS updates:**
1. Find where `selectionInspector.classList.remove('hidden')` is called — add inspector type icon color update:
```js
// When showing inspector for a selected item, set the type icon color
function showInspector(type, id) {
  const typeColors = {
    vertex: 'var(--vertex)',
    platform: 'var(--platform)',
    door: 'var(--door)',
    key: 'var(--color-key)',
    ability: 'var(--color-ability)',
    mover: 'var(--color-mover)',
    start: 'var(--color-start)',
  };
  const icon = document.getElementById('inspectorTypeIcon');
  if (icon) icon.style.background = typeColors[type] || 'var(--muted)';
  document.getElementById('selectionInspector').classList.remove('hidden');
}
```

2. Add close button handler:
```js
document.getElementById('inspectorClose')?.addEventListener('click', () => {
  // Deselect: replicate what pressing Escape does in the existing code
  state.selectedItemId = null;
  state.selectedVertexIndex = -1;
  document.getElementById('selectionInspector').classList.add('hidden');
  renderRoom();
});
```

**Verification:**
- Inspector no longer floats over the canvas
- Inspector appears as a right-side panel when an item is selected
- Inspector is hidden when nothing is selected
- Type icon shows correct color for selected element type
- Close button (×) deselects and hides inspector
- Canvas full area is visible when nothing is selected
- All existing property fields still work

---

### Task 1.7 — Status Bar: State-Aware Visual Treatment

**Location:** `<div class="status" id="statusText">Loading layout data…</div>`

**Current CSS:**
```css
.status {
  font-size: 12px;
  color: var(--muted);
  min-height: 20px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.03);
}
```

**Replace with:**
```css
.status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-xs);
  color: var(--muted);
  min-height: 36px;
  padding: 8px 14px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.03);
  transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast);
}
.status::before {
  content: "●";
  font-size: 8px;
  flex-shrink: 0;
  color: var(--muted);
}
.status.status-success {
  background: var(--good-soft);
  border-color: rgba(74,222,128,0.24);
  color: #dff7ec;
}
.status.status-success::before { color: var(--good); }
.status.status-error {
  background: var(--error-soft);
  border-color: rgba(248,81,73,0.24);
  color: #fdd8d6;
}
.status.status-error::before { color: var(--error); }
.status.status-warning {
  background: var(--warning-soft);
  border-color: rgba(210,153,34,0.24);
  color: #f5e6c0;
}
.status.status-warning::before { color: var(--warning); }
```

**JS: add a `setStatus` helper** in the `<script>` block. Find how `statusText.textContent = ...` is called throughout the file and replace all of them with calls to this helper:

```js
function setStatus(message, type = 'info') {
  const el = document.getElementById('statusText');
  if (!el) return;
  el.textContent = message;
  el.className = 'status' + (type !== 'info' ? ` status-${type}` : '');
  if (type === 'success') {
    clearTimeout(el._clearTimer);
    el._clearTimer = setTimeout(() => {
      el.className = 'status';
      el.textContent = 'Ready';
    }, 2500);
  }
}
```

Replace all existing `statusText.textContent = '...'` calls:
- Save success messages → `setStatus('Layout saved', 'success')`
- Error messages → `setStatus('Error: ...', 'error')`
- Warning messages → `setStatus('Warning: ...', 'warning')`
- Info/loading messages → `setStatus('...')` (no type = info)

**Verification:**
- Status bar has a colored dot prefix
- Saving layout shows green "Layout saved" that auto-clears after 2.5s
- Errors show red styling and persist
- Default/info state looks subtly different from before (dot prefix, slightly taller)

---

### Task 1.8 — Typography: Apply Token Scale

**What to do:** Find all hardcoded `font-size` values in the CSS and replace with tokens. This is a find-replace pass — no visual changes, just using the vocabulary.

**Replacements:**
```
11px  →  var(--font-size-xs)     [where used for labels, eyebrows, hints]
12px  →  var(--font-size-xs)     [where used for small text]
13px  →  var(--font-size-sm)     [nav links, secondary text]
14px  →  var(--font-size-base)   [body text, control cards]
15px  →  var(--font-size-md)     [h2, h3 headings in panels]
18px  →  var(--font-size-lg)     [section headings if any]
```

**Also update:**
```css
h2, h3 {
  font-size: var(--font-size-base);   /* was 15px, now uses token */
}
```

**Also:** Update the `h1` in `.brand` to be consistent:
```css
.brand h1 {
  font-family: var(--font-display);
  font-size: 38px;       /* keep — display heading, no token needed */
  line-height: 0.9;
  letter-spacing: 0.04em;
}
```

**Verification:** Tool looks identical — this is purely a maintenance pass. Check that no `font-size` values became `var(--font-size-base)` incorrectly (e.g., the `canvas h1` at 40px should stay at 40px and not get a token).

---

### Task 1.9 — Button Polish: `:active` State and Transition Tokens

**What to do:** Two small additions to the global `button` styles.

**Find the existing button CSS and add `:active`:**
```css
button:active {
  transform: translateY(0);
  box-shadow: none;
}
```

**Replace all `transition:` values in button rules with tokens:**
```css
/* Was: transition: background 120ms ease, border-color 120ms ease, color 120ms ease, transform 120ms ease; */
/* Replace with: */
button {
  transition: background var(--transition-fast), border-color var(--transition-fast), color var(--transition-fast), transform var(--transition-fast);
}
```

**Verification:** Buttons visually snap back on release. No other changes.

---

### Sprint 1 Verification Checklist

Run through this before marking sprint complete:

```
□ :root has all new tokens (border, text-muted, space-*, font-size-*, shadow-*, transition-*)
□ No <details> or <summary> elements remain in the file
□ Collapsible section opens/closes with chevron rotation
□ View mode switch is a tab strip, not a <select>
□ Tab strip correctly switches between room and global canvas
□ Canvas toolbar buttons have color dots for element types
□ Canvas toolbar buttons have <kbd> shortcut badges
□ "Pan L/U/D/R" text buttons are gone
□ Arrow icon buttons for pan are functional
□ "Fit" button added to zoom group
□ Inspector no longer floats over canvas
□ Inspector shows/hides as right rail when item selected/deselected
□ Inspector type icon shows correct color per element type
□ Inspector close button (×) works
□ Status bar has dot prefix and state-aware colors
□ Success messages auto-clear after 2.5s
□ Typography uses --font-size-* tokens throughout
□ button:active added
□ No canvas interaction regressions (select, drag, snap all work)
□ Both canvases (room + global) render correctly
□ Save/load still works
```

---

### Sprint 1 Demo Script

Run this exact sequence after the verification checklist passes.

**Step 1 — Default state screenshot**
```bash
open /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
sleep 1
screencapture -x /tmp/demo-s1-default.png
```
Read `/tmp/demo-s1-default.png`. Report:
- Does the page have the correct dark background (`#050709`)?
- Is the top nav visible and styled (blur backdrop, 52px height)?
- Is the canvas toolbar visible on the left of the canvas with color dots on the element-type buttons?
- Are `<kbd>` shortcut badges visible on the right of each toolbar button label?
- Is the view switch visible as a tab strip (two pill-shaped buttons, not a dropdown)?
- Is the inspector hidden (no floating panel visible over the canvas)?
- Is the status bar visible at the bottom with a dot prefix?

**Step 2 — Click a platform to trigger the inspector**
```bash
# After the page is open, click on a platform element on the canvas
# (Cannot automate click — instead, verify inspector HTML structure directly)
grep -c 'class="inspector"' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep 'position: absolute' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html | grep inspector
```
Report:
- Does the inspector element exist in the file?
- Is `position: absolute` removed from the inspector CSS?
- Does the inspector have a `.inspector-header` with `.inspector-type-icon`?

**Step 3 — Verify collapsible replaces `<details>`**
```bash
grep -c '<details' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'collapsible-toggle' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report:
- `<details>` count should be 0
- `collapsible-toggle` count should be ≥ 1

**Step 4 — Verify design token completeness**
```bash
grep -c '\-\-font-size-xs' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c '\-\-space-4' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c '\-\-transition-fast' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c '\-\-shadow-md' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report: all four counts should be ≥ 1.

**Step 5 — Open Sprite Workbench for side-by-side comparison**
```bash
open /Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html
sleep 1
screencapture -x /tmp/demo-s1-workbench.png
screencapture -x /tmp/demo-s1-roomeditor.png
```
Read both screenshots. Compare:
- Nav bar height, blur, border treatment
- Button styling and hover states
- Typography: label size, font weight, uppercase eyebrow treatment
- Panel background color and border
- Overall visual weight — does the room editor feel like it belongs in the same product family?

Output full demo report before proceeding to Sprint 2.

---

## Sprint 2 — Layout Restructure, Panels & Lifecycle

**Goal:** Restructure the main layout to reduce visual noise, upgrade the inventory sidebar to a rich component, add empty/loading/error states, and complete the dirty-state / micro-interaction system.

**Files to modify:** `room-layout-editor.html` only.

---

### Pre-Sprint Spec Corrections

Two bugs were identified in this sprint's spec during review. Apply these corrections as you encounter the relevant tasks — they override the original spec text.

**Correction A — `room.movers` → `room.movingPlatforms` (affects Task 2.2)**

The spec's `renderInventory` function uses `room.movers` but the actual data model throughout the file uses `room.movingPlatforms`. Every reference to `room.movers` in Task 2.2 must be changed to `room.movingPlatforms`. The UI label stays "Movers". The `invCountMovers` / `invListMovers` IDs are correct and unchanged.

**Correction B — `saveBtn.textContent` destroys dirty dot span (affects Task 2.5c)**

The spec's 2.5c code uses `saveBtn.textContent = 'Saved ✓'` which would destroy the `<span class="dirty-dot">` child added in Task 2.4. Replace the 2.5c implementation with an approach that only changes the button's text node:

```js
// In the existing save success handler, after setDirty(false):
const saveBtn = document.getElementById('savePermanent');
const dot = document.getElementById('dirtyDot');
// Temporarily replace text node only — do NOT touch the dirty dot span
const textNode = Array.from(saveBtn.childNodes).find(n => n.nodeType === Node.TEXT_NODE);
const originalText = textNode ? textNode.textContent : 'Save';
if (textNode) textNode.textContent = ' Saved ✓ ';
setTimeout(() => {
  if (textNode) textNode.textContent = originalText;
}, 1800);
```

**Correction C — `globalZoom` range input must be preserved (affects Task 2.1)**

The existing `<input id="globalZoom" type="range">` is referenced by the JS event system and must not be removed. Include it in the collapsible settings panel. Add it to the `settings-row` in `canvasSettingsBody`:

```html
<label class="setting-item">Global Zoom
  <input id="globalZoom" type="range" min="40" max="200" step="5" value="100" />
</label>
```

---

### Task 2.1 — Restructure the 3-Card Header into a Compact Toolbar Strip

**Location:** The `.canvas-header` / `.canvas-controls` block above the canvas (the 3 control cards).

**Current structure:**
- 3 `control-card` sections: "Current map", "Editing controls", "Save and share"
- Inside "Current map": room selector, view mode select, room width/height inputs, add/delete room buttons
- Inside "Editing controls": grid snap, global zoom, open game, reload
- Inside "Save and share": save device, export JSON, sync canonical

**New structure — replace the entire `.canvas-header` with:**
```html
<div class="canvas-header-bar">
  <!-- Left: Room selector -->
  <div class="canvas-header-group">
    <label class="header-label">Room
      <select id="roomSelect" class="header-select"></select>
    </label>
  </div>

  <!-- Center: View tab strip (moved here from task 1.3) -->
  <div class="tab-strip" id="viewModeStrip">
    <button class="tab-btn active" data-view="room">Room View</button>
    <button class="tab-btn" data-view="global">Global Map</button>
  </div>

  <!-- Right: Primary actions -->
  <div class="canvas-header-actions">
    <button id="savePermanent" class="btn-save good">Save</button>
    <button id="downloadJson" class="btn-secondary">Export</button>
    <button id="openGameWithLayout" class="btn-secondary">Open Game</button>
    <button class="btn-icon" id="settingsToggle" title="Canvas Settings">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
        <circle cx="7" cy="7" r="2" stroke="currentColor" stroke-width="1.5"/>
        <path d="M7 1v1M7 12v1M1 7h1M12 7h1M2.5 2.5l.7.7M10.8 10.8l.7.7M2.5 11.5l.7-.7M10.8 3.2l.7-.7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </button>
  </div>
</div>

<!-- Collapsible settings (hidden by default) -->
<div class="canvas-settings-panel collapsible-body" id="canvasSettingsBody" hidden>
  <div class="settings-row">
    <label class="setting-item">Grid Snap
      <select id="snapSize">
        <option value="0">Off</option>
        <option value="8">8px</option>
        <option value="16">16px</option>
        <option value="32" selected>32px</option>
        <option value="64">64px</option>
      </select>
    </label>
    <label class="setting-item">Room Width
      <input id="roomWidth" type="number" step="32" min="320" />
    </label>
    <label class="setting-item">Room Height
      <input id="roomHeight" type="number" step="32" min="320" />
    </label>
    <div class="setting-actions">
      <button id="addRoom" class="btn-sm">+ Add Room</button>
      <button id="deleteRoom" class="btn-sm btn-danger">Delete Room</button>
      <button id="reloadJson" class="btn-sm">Reload Disk</button>
      <button id="syncCanonicalJson" class="btn-sm">Sync Canonical</button>
    </div>
  </div>
</div>
```

**CSS to add:**
```css
.canvas-header-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
  background: rgba(255,255,255,0.025);
  flex-wrap: wrap;
}
.canvas-header-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-xs);
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  white-space: nowrap;
}
.header-select {
  min-height: 32px;
  padding: 4px 10px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.04);
  color: var(--text);
  font-size: var(--font-size-sm);
  font: inherit;
  width: auto;
  min-width: 160px;
}
.canvas-header-actions {
  display: flex;
  gap: 6px;
  margin-left: auto;
  align-items: center;
}
.btn-save {
  min-height: 32px;
  padding: 6px 14px;
  width: auto;
  font-size: var(--font-size-sm);
}
.btn-secondary {
  min-height: 32px;
  padding: 6px 12px;
  width: auto;
  font-size: var(--font-size-sm);
  background: rgba(255,255,255,0.04);
  color: var(--muted);
  border-color: var(--line);
}
.btn-secondary:hover { color: var(--text); }
.btn-icon {
  width: 32px;
  min-height: 32px;
  padding: 0;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: var(--muted);
  width: auto;
  padding: 0 8px;
}
.btn-icon:hover { color: var(--text); transform: none; }
.btn-sm {
  min-height: 28px;
  padding: 4px 10px;
  width: auto;
  font-size: var(--font-size-xs);
  border-radius: 10px;
}
.btn-danger {
  color: var(--error);
  border-color: rgba(248,81,73,0.2);
}
.btn-danger:hover {
  background: var(--error-soft);
  border-color: rgba(248,81,73,0.4);
}
.canvas-settings-panel {
  padding: 12px 14px;
  border-bottom: 1px solid var(--line);
  background: rgba(255,255,255,0.02);
}
.settings-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
}
.setting-item {
  display: grid;
  gap: 4px;
  font-size: var(--font-size-xs);
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.setting-item input,
.setting-item select {
  min-height: 32px;
  padding: 4px 10px;
  font-size: var(--font-size-sm);
  width: auto;
  min-width: 80px;
}
.setting-actions {
  display: flex;
  gap: 6px;
  align-items: flex-end;
  padding-bottom: 2px;
}
```

**JS: wire settings toggle:**
```js
document.getElementById('settingsToggle')?.addEventListener('click', () => {
  const body = document.getElementById('canvasSettingsBody');
  if (body) body.hidden = !body.hidden;
});
```

**Remove from the file:** The old `.canvas-controls` grid and the three `.control-card` sections. Ensure all element IDs that existed in those cards are preserved in the new structure (roomSelect, snapSize, roomWidth, roomHeight, addRoom, deleteRoom, reloadJson, syncCanonicalJson, openGameWithLayout, savePermanent, downloadJson).

**Verification:**
- 3 control cards are gone
- Compact header bar is visible
- Room selector is functional
- Save / Export / Open Game buttons work
- Settings gear opens collapsible panel with advanced controls
- Grid snap, room width/height, add/delete room still work
- No element IDs lost

---

### Task 2.2 — Room Inventory Sidebar: Expandable Sections

**Location:** The right `.panel.sidebar-panel` section containing `.metric-grid` and item lists.

**Current:** Badge grid (counts) + flat chip list.

**New structure:**
```html
<section class="panel sidebar-panel">
  <div class="sidebar-header">
    <div class="eyebrow">Active Room</div>
    <h2 id="inventoryRoomName">Room Contents</h2>
    <div class="inventory-meta">
      <span class="validation-badge" id="inventoryValidationBadge"></span>
    </div>
  </div>

  <!-- Metric grid stays — just add validation badge slot -->
  <div class="metric-grid">
    <!-- existing badges stay exactly as-is -->
  </div>

  <!-- Expandable inventory sections -->
  <div class="inventory-sections" id="inventorySections">

    <div class="inventory-section" data-type="platforms">
      <button class="inventory-section-header" aria-expanded="true">
        <span class="inventory-section-dot" style="background: var(--platform)"></span>
        <span class="inventory-section-title">Platforms</span>
        <span class="inventory-section-count" id="invCountPlatforms">0</span>
        <svg class="collapsible-chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
      <div class="inventory-section-body" id="invListPlatforms"></div>
    </div>

    <div class="inventory-section" data-type="doors">
      <button class="inventory-section-header" aria-expanded="true">
        <span class="inventory-section-dot" style="background: var(--door)"></span>
        <span class="inventory-section-title">Doors</span>
        <span class="inventory-section-count" id="invCountDoors">0</span>
        <svg class="collapsible-chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
      <div class="inventory-section-body" id="invListDoors"></div>
    </div>

    <div class="inventory-section" data-type="keys">
      <button class="inventory-section-header" aria-expanded="true">
        <span class="inventory-section-dot" style="background: var(--color-key)"></span>
        <span class="inventory-section-title">Keys</span>
        <span class="inventory-section-count" id="invCountKeys">0</span>
        <svg class="collapsible-chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
      <div class="inventory-section-body" id="invListKeys"></div>
    </div>

    <div class="inventory-section" data-type="abilities">
      <button class="inventory-section-header" aria-expanded="true">
        <span class="inventory-section-dot" style="background: var(--color-ability)"></span>
        <span class="inventory-section-title">Abilities</span>
        <span class="inventory-section-count" id="invCountAbilities">0</span>
        <svg class="collapsible-chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
      <div class="inventory-section-body" id="invListAbilities"></div>
    </div>

    <div class="inventory-section" data-type="movers">
      <button class="inventory-section-header" aria-expanded="true">
        <span class="inventory-section-dot" style="background: var(--color-mover)"></span>
        <span class="inventory-section-title">Movers</span>
        <span class="inventory-section-count" id="invCountMovers">0</span>
        <svg class="collapsible-chevron" width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
      <div class="inventory-section-body" id="invListMovers"></div>
    </div>

  </div>
</section>
```

**CSS:**
```css
.inventory-sections {
  display: grid;
  gap: 2px;
  margin-top: 14px;
}
.inventory-section {
  border: 1px solid var(--line);
  border-radius: 14px;
  overflow: hidden;
}
.inventory-section + .inventory-section {
  margin-top: 4px;
}
.inventory-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: rgba(255,255,255,0.03);
  border: none;
  border-radius: 0;
  color: var(--text);
  font-size: var(--font-size-sm);
  font-weight: 500;
  min-height: 36px;
  cursor: pointer;
  text-align: left;
}
.inventory-section-header:hover {
  background: rgba(255,255,255,0.06);
  transform: none;
}
.inventory-section-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}
.inventory-section-title {
  flex: 1;
}
.inventory-section-count {
  font-size: var(--font-size-xs);
  color: var(--muted);
  font-weight: 400;
  margin-right: 4px;
}
.inventory-section-body {
  display: grid;
  gap: 2px;
  padding: 4px;
  border-top: 1px solid var(--line);
}
.inventory-section-body:empty::after {
  content: "None";
  display: block;
  padding: 8px 10px;
  font-size: var(--font-size-xs);
  color: var(--muted);
  text-align: center;
}
.inventory-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 10px;
  cursor: pointer;
  font-size: var(--font-size-xs);
  transition: background var(--transition-fast);
  border: 1px solid transparent;
}
.inventory-item:hover {
  background: rgba(255,255,255,0.05);
  border-color: var(--line);
}
.inventory-item.active {
  background: var(--accent-soft);
  border-color: rgba(0,232,200,0.2);
}
.inventory-item-id {
  font-family: var(--font-mono);
  color: var(--muted);
  font-size: 10px;
  flex-shrink: 0;
}
.inventory-item-info {
  flex: 1;
  min-width: 0;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.inventory-item-delete {
  width: 20px;
  min-height: 20px;
  padding: 0;
  border-radius: 6px;
  opacity: 0;
  color: var(--muted);
  font-size: 12px;
  display: grid;
  place-items: center;
  transition: opacity var(--transition-fast), color var(--transition-fast);
}
.inventory-item:hover .inventory-item-delete {
  opacity: 1;
}
.inventory-item-delete:hover {
  color: var(--error);
  background: var(--error-soft);
  transform: none;
}
.validation-badge {
  font-size: var(--font-size-xs);
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}
.validation-badge.pass { background: var(--good-soft); color: var(--good); }
.validation-badge.warn { background: var(--warning-soft); color: var(--warning); }
.validation-badge.fail { background: var(--error-soft); color: var(--error); }
```

**JS: replace the existing inventory render function.** Find the existing function that populates the room inventory (it reads the room's platforms, doors, keys, etc. and renders chips). Replace it with a new function `renderInventory(room)` that:

```js
function renderInventory(room) {
  if (!room) return;

  // Update room name heading
  const nameEl = document.getElementById('inventoryRoomName');
  if (nameEl) nameEl.textContent = room.name || room.id;

  // Update count badges (existing IDs)
  document.getElementById('vertexCount').textContent = (room.polygon || []).length;
  document.getElementById('platformCount').textContent = (room.platforms || []).length;
  document.getElementById('doorCount').textContent = (room.doors || []).length;
  document.getElementById('keyCount').textContent = (room.keys || []).length;
  document.getElementById('abilityCount').textContent = (room.abilities || []).length;
  document.getElementById('moverCount').textContent = (room.movers || []).length;

  // Update section counts and bodies
  renderInventorySection('platforms', room.platforms || [], p => `x:${p.x} y:${p.y} len:${p.len}`, 'invListPlatforms', 'invCountPlatforms');
  renderInventorySection('doors', room.doors || [], d => `${d.label || ''} → ${d.targetRoom || '?'} (${d.kind})`, 'invListDoors', 'invCountDoors');
  renderInventorySection('keys', room.keys || [], k => k.label || k.id, 'invListKeys', 'invCountKeys');
  renderInventorySection('abilities', room.abilities || [], a => a.label || a.id, 'invListAbilities', 'invCountAbilities');
  renderInventorySection('movers', room.movers || [], m => `(${m.x1},${m.y1})→(${m.x2},${m.y2})`, 'invListMovers', 'invCountMovers');
}

function renderInventorySection(type, items, labelFn, listId, countId) {
  const list = document.getElementById(listId);
  const count = document.getElementById(countId);
  if (!list) return;
  if (count) count.textContent = items.length;
  list.innerHTML = '';
  items.forEach(item => {
    const row = document.createElement('div');
    row.className = 'inventory-item';
    row.dataset.id = item.id;
    if (state.selectedItemId === item.id) row.classList.add('active');
    row.innerHTML = `
      <span class="inventory-item-id">${item.id}</span>
      <span class="inventory-item-info">${labelFn(item)}</span>
      <button class="inventory-item-delete" data-item-id="${item.id}" title="Delete">×</button>
    `;
    row.addEventListener('click', e => {
      if (e.target.classList.contains('inventory-item-delete')) return;
      // Select this item and jump canvas to it
      // Replicate what clicking a chip used to do
      selectItemById(item.id);
    });
    row.querySelector('.inventory-item-delete').addEventListener('click', e => {
      e.stopPropagation();
      deleteItemById(item.id);
    });
    list.appendChild(row);
  });
}
```

Note: `selectItemById` and `deleteItemById` should call whatever the existing item selection/deletion functions are. Read the existing JS to find those function names.

**Wire section toggle buttons:**
```js
document.querySelectorAll('.inventory-section-header').forEach(btn => {
  btn.addEventListener('click', () => {
    const expanded = btn.getAttribute('aria-expanded') !== 'false';
    btn.setAttribute('aria-expanded', String(!expanded));
    btn.querySelector('.collapsible-chevron').style.transform = expanded ? 'rotate(-90deg)' : '';
    const body = btn.nextElementSibling;
    if (body) body.style.display = expanded ? 'none' : '';
  });
});
```

**Verification:**
- Each element type has an expandable section with color dot
- Clicking an inventory item selects it on the canvas
- Delete button (×) appears on hover and deletes the item
- Section counts update when items are added/removed
- Empty sections show "None" placeholder
- Active (selected) item is highlighted in the inventory

---

### Task 2.3 — Empty States

**What to add:** Three empty state conditions. Each uses a shared `.empty-state` component pattern.

**CSS:**
```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
  text-align: center;
  min-height: 200px;
}
.empty-state-icon {
  font-size: 32px;
  opacity: 0.3;
  line-height: 1;
}
.empty-state-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--text);
}
.empty-state-sub {
  font-size: var(--font-size-sm);
  color: var(--muted);
  line-height: 1.5;
  max-width: 280px;
}
.empty-state .btn-primary {
  min-height: 36px;
  padding: 8px 16px;
  width: auto;
  font-size: var(--font-size-sm);
  background: rgba(0,232,200,0.1);
  border-color: rgba(0,232,200,0.24);
  color: var(--accent);
}
.empty-state .btn-primary:hover {
  background: rgba(0,232,200,0.18);
}
```

**Add to HTML — three states:**

1. **No rooms empty state** (render inside canvas area when `rooms.length === 0`):
```html
<div class="empty-state" id="emptyStateNoRooms" style="display:none;">
  <div class="empty-state-icon">⬡</div>
  <div class="empty-state-title">No rooms yet</div>
  <div class="empty-state-sub">Add your first room to start building your level layout.</div>
  <button class="btn-primary" onclick="document.getElementById('addRoom').click()">+ Add Room</button>
</div>
```

2. **Empty canvas state** (render inside canvas when a room has no geometry):
The canvas itself renders this — add a JS function `renderEmptyRoomHint()` that draws centered text on the canvas:
```js
function renderEmptyRoomHint() {
  const room = getCurrentRoom();
  if (!room || (room.polygon && room.polygon.length > 0)) return;
  // Draw hint text on canvas
  const ctx = roomCanvas.getContext('2d');
  ctx.save();
  ctx.fillStyle = 'rgba(93, 120, 112, 0.6)';
  ctx.font = '14px "Plus Jakarta Sans", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Click to place vertices and define this room\'s shape', roomCanvas.width / 2, roomCanvas.height / 2 - 10);
  ctx.font = '12px "Plus Jakarta Sans", sans-serif';
  ctx.fillStyle = 'rgba(93, 120, 112, 0.4)';
  ctx.fillText('Hold Shift and click to close the polygon', roomCanvas.width / 2, roomCanvas.height / 2 + 14);
  ctx.restore();
}
```

3. **No data loaded state** (when localStorage is empty and server is unreachable):
```html
<div class="empty-state" id="emptyStateNoData" style="display:none;">
  <div class="empty-state-icon">📂</div>
  <div class="empty-state-title">No layout data</div>
  <div class="empty-state-sub">No saved layout found. Import a JSON file or create rooms from scratch.</div>
  <button class="btn-primary" onclick="document.getElementById('advancedToggle').click()">Import JSON</button>
</div>
```

**JS: show/hide empty states** by updating the existing load/render functions to call:
```js
function updateEmptyStates() {
  const noRooms = !state.data || !state.data.rooms || state.data.rooms.length === 0;
  document.getElementById('emptyStateNoRooms').style.display = noRooms ? 'flex' : 'none';
  document.getElementById('roomCanvas').style.display = noRooms ? 'none' : 'block';
}
```

Call `updateEmptyStates()` after every operation that adds or removes rooms.

**Verification:**
- Deleting all rooms shows the "No rooms yet" empty state with Add Room button
- Having rooms hides the empty state and shows the canvas
- Empty canvas renders a hint when a room has no polygon vertices

---

### Task 2.4 — Dirty State Indicator on Save Button

**What to do:** Add a visual "unsaved changes" indicator on the Save button.

**HTML:** Add a dirty indicator dot to the save button:
```html
<button id="savePermanent" class="btn-save good">
  Save
  <span class="dirty-dot" id="dirtyDot" style="display:none;"></span>
</button>
```

**CSS:**
```css
.dirty-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fff;
  opacity: 0.7;
  display: inline-block;
  margin-left: 4px;
  vertical-align: middle;
}
```

**JS:** Add a `setDirty(bool)` helper and call it appropriately:
```js
function setDirty(isDirty) {
  state.isDirty = isDirty;
  const dot = document.getElementById('dirtyDot');
  if (dot) dot.style.display = isDirty ? 'inline-block' : 'none';
  // Update page title
  document.title = isDirty
    ? '• Room Layout Editor'
    : 'Room Layout Editor';
}
```

- Call `setDirty(true)` in every mutation handler (vertex move, platform add, etc.)
- Call `setDirty(false)` after successful save
- Read the existing save handler to find the right place to reset dirty state

**Verification:**
- Making any change shows the white dot on the Save button
- Saving clears the dot
- Page title shows `•` prefix when dirty

---

### Task 2.5 — Micro-Interactions

Four small interaction enhancements. Each is isolated and should not touch canvas logic.

**2.5a — Element glow pulse on placement**

Add a CSS keyframe and apply it to newly placed elements. When the canvas renders a freshly-added element (one whose ID matches `state.lastPlacedId`), draw it with a brief brighter color. Reset `state.lastPlacedId` after 600ms.

```js
// In whatever function places a new element (addPlatform, addDoor, etc.):
state.lastPlacedId = newElement.id;
setTimeout(() => { state.lastPlacedId = null; renderRoom(); }, 600);
```

In the canvas render function, check `id === state.lastPlacedId` and use a brighter fill color if so.

**2.5b — Room switch canvas fade**

When switching rooms (via room selector), add a very brief opacity fade:
```js
// In the existing room-change handler:
roomCanvas.style.transition = 'opacity 80ms ease';
roomCanvas.style.opacity = '0';
setTimeout(() => {
  renderRoom(); // existing render call
  roomCanvas.style.opacity = '1';
}, 80);
```

**2.5c — Save confirmation in title area**

After successful save, briefly show "Saved ✓" near the save button:
```js
// In the existing save success handler, after setDirty(false):
const saveBtn = document.getElementById('savePermanent');
const original = saveBtn.textContent;
saveBtn.textContent = 'Saved ✓';
saveBtn.style.background = ''; // let .good class handle it
setTimeout(() => { saveBtn.textContent = original; }, 1800);
```

**2.5d — Inspector slide-in**

Add a CSS transition so the inspector animates in when shown:
```css
.inspector {
  transform-origin: top right;
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}
.inspector.hidden {
  display: none; /* keep hidden, but also: */
}
/* When showing inspector (removing .hidden), add .showing briefly */
.inspector.showing {
  animation: inspectorIn 120ms ease forwards;
}
@keyframes inspectorIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

In JS, when showing inspector:
```js
selectionInspector.classList.remove('hidden');
selectionInspector.classList.add('showing');
setTimeout(() => selectionInspector.classList.remove('showing'), 120);
```

**Verification:**
- Newly placed elements briefly appear brighter
- Switching rooms has a quick fade (not jarring, just smooth)
- Save button text changes to "Saved ✓" for 1.8s after saving
- Inspector slides in when an item is selected

---

### Sprint 2 Verification Checklist

```
□ 3 control cards replaced with compact header bar
□ Room selector in header bar works
□ Save / Export / Open Game buttons in header work
□ Settings toggle opens/closes collapsible panel with all advanced controls
□ All advanced control IDs preserved (snapSize, roomWidth, roomHeight, addRoom, deleteRoom, reloadJson, syncCanonicalJson)
□ Inventory sidebar has expandable sections for each element type
□ Each section has color dot, count, collapse toggle
□ Clicking inventory item selects it on canvas
□ Delete button (×) on inventory items works
□ Empty section shows "None" placeholder
□ "No rooms" empty state shown when rooms array is empty
□ Canvas hint text shown when room has no vertices
□ Dirty dot appears on Save button after changes
□ Dirty dot clears after save
□ Page title shows • prefix when dirty
□ Element glow pulse on placement (brief, subtle)
□ Room switch has 80ms canvas fade
□ Save button shows "Saved ✓" for 1.8s after save
□ Inspector slides in (120ms) when item selected
□ No regressions: all canvas interactions work, save/load works
```

---

### Sprint 2 Demo Script

**Step 1 — Default state: compact header bar**
```bash
open /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
sleep 1
screencapture -x /tmp/demo-s2-default.png
```
Read `/tmp/demo-s2-default.png`. Report:
- Are the 3 control cards gone?
- Is there a single compact header bar at the top of the canvas area?
- Does it contain: a Room selector label+dropdown, the view tab strip, and Save/Export/Open Game buttons on the right?
- Is there a settings gear icon button (⚙)?
- Does the layout feel less cluttered than before?

**Step 2 — Settings panel open/close**
```bash
grep -c 'canvasSettingsBody' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep 'settingsToggle' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html | head -5
```
Report:
- `canvasSettingsBody` element exists with `hidden` attribute by default
- `settingsToggle` click handler is wired

**Step 3 — Inventory sidebar structure**
```bash
grep -c 'inventory-section' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'inventory-section-header' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'invListPlatforms\|invListDoors\|invListKeys\|invListAbilities\|invListMovers' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report:
- `inventory-section` count should be ≥ 5 (one per element type)
- `inventory-section-header` count should be ≥ 5
- All 5 list container IDs should be present

**Step 4 — Empty state presence**
```bash
grep -c 'emptyStateNoRooms\|emptyStateNoData' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'empty-state' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report: both IDs present, `empty-state` class count ≥ 2.

**Step 5 — Dirty state wiring**
```bash
grep -c 'setDirty' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'dirtyDot' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report: `setDirty` called in ≥ 3 places (on mutations); `dirtyDot` ID present in HTML.

**Step 6 — Visual quality screenshot of inventory sidebar**
```bash
screencapture -x /tmp/demo-s2-sidebar.png
```
Read screenshot. Report:
- Are the expandable inventory sections visible in the right sidebar?
- Do the section headers have color dots matching element type colors (blue for platforms, orange for doors, etc.)?
- Is the layout clean — sections separated by subtle borders, not raw chip lists?
- Is the "Room Contents" heading replaced with a dynamic room name heading?

**Step 7 — Full-page quality assessment**
```bash
screencapture -x /tmp/demo-s2-full.png
```
Read screenshot. Specifically assess:
- Does the canvas area feel more spacious now that 3 control cards are gone?
- Is information hierarchy clear: header bar → canvas → inventory → validation?
- Does this feel like a professional level editor, not a prototype?

Output full demo report before proceeding to Sprint 3.

---

## Sprint 3 — Validation Pipeline

**Goal:** Implement the three-tier validation system and surface results in the UI.

**Canonical doc (maintain in sync with code):** [`room-layout-validation.md`](./room-layout-validation.md) — project convention for levels/IDs; **not** an external industry standard. User-facing excerpt placeholder: **DOC-ROOM-VALIDATION-001**.

**Files to modify:** `room-layout-editor.html` only.

**Important:** Sprint 3 adds new JS logic. Read all existing room data access patterns in the JS before writing any validation code.

---

### Task 3.1 — Validation Engine (JS)

Add a `validateLayout(data)` function to the script block. This function is pure — it takes the layout data object and returns a structured report. It does NOT modify state or render anything.

```js
function validateLayout(data) {
  const report = {
    run_at: new Date().toISOString(),
    level_1: { passed: true, checks: [] },
    level_2: { passed: true, checks: [] },
    summary: { errors: 0, warnings: 0 }
  };

  function fail(level, id, room, message) {
    report[`level_${level}`].passed = false;
    report[`level_${level}`].checks.push({ id, room, severity: 'error', message });
    report.summary.errors++;
  }
  function warn(level, id, room, message) {
    report[`level_${level}`].checks.push({ id, room, severity: 'warning', message });
    report.summary.warnings++;
  }

  const rooms = (data && data.rooms) || [];
  const roomIds = new Set(rooms.map(r => r.id));

  // ── Level 1: Structural Correctness ────────────────────────────────────

  // L1-001: No duplicate room IDs
  const seen = {};
  rooms.forEach(r => {
    if (seen[r.id]) fail(1, 'L1-001', r.id, `Duplicate room ID: ${r.id}`);
    seen[r.id] = true;
  });

  rooms.forEach(room => {
    const rid = room.id;

    // L1-002: Room has at least 3 vertices
    if (!room.polygon || room.polygon.length < 3)
      fail(1, 'L1-002', rid, `Room ${rid} has fewer than 3 vertices (has ${(room.polygon||[]).length})`);

    // L1-003: All door targetRoom references resolve
    (room.doors || []).forEach(door => {
      if (door.targetRoom && !roomIds.has(door.targetRoom))
        fail(1, 'L1-003', rid, `Door ${door.id} targets non-existent room: ${door.targetRoom}`);
    });

    // L1-004: All edgeLinks reference valid edge indices
    (room.edgeLinks || []).forEach(link => {
      const polyLen = (room.polygon || []).length;
      const targetRoom = rooms.find(r => r.id === link.targetRoomId);
      if (link.edgeIndex >= polyLen)
        fail(1, 'L1-004', rid, `Edge link in ${rid} references edge index ${link.edgeIndex} but room only has ${polyLen} edges`);
      if (targetRoom) {
        const targetPolyLen = (targetRoom.polygon || []).length;
        if (link.targetEdgeIndex >= targetPolyLen)
          fail(1, 'L1-004', rid, `Edge link in ${rid} targets edge index ${link.targetEdgeIndex} in ${link.targetRoomId} which only has ${targetPolyLen} edges`);
      } else {
        fail(1, 'L1-003', rid, `Edge link in ${rid} targets non-existent room: ${link.targetRoomId}`);
      }
    });

    // L1-005: Element IDs are unique within room
    const elementIds = new Set();
    ['platforms','doors','keys','abilities','movers'].forEach(type => {
      (room[type] || []).forEach(el => {
        if (elementIds.has(el.id))
          fail(1, 'L1-005', rid, `Duplicate element ID ${el.id} in room ${rid}`);
        elementIds.add(el.id);
      });
    });
  });

  // L1-006: At least one room has a playerStart
  const hasPlayerStart = rooms.some(r => r.playerStart && r.playerStart.x != null);
  if (!hasPlayerStart)
    fail(1, 'L1-006', null, 'No player start position defined in any room');

  // ── Level 2: Traversal Sanity ───────────────────────────────────────────
  // Uses platform geometry to check reachability constraints

  rooms.forEach(room => {
    const rid = room.id;
    const platforms = room.platforms || [];
    if (platforms.length < 2) return;

    // Sort platforms by Y position (top to bottom in world space)
    const sorted = [...platforms].sort((a, b) => a.y - b.y);

    for (let i = 0; i < sorted.length - 1; i++) {
      const a = sorted[i];
      const b = sorted[i + 1];
      const verticalDelta = Math.abs(b.y - a.y);
      const aRight = a.x + (a.len || 1) * 32;
      const bLeft = b.x;
      const bRight = b.x + (b.len || 1) * 32;
      const aLeft = a.x;
      const horizontalGap = Math.max(0, Math.max(bLeft - aRight, aLeft - bRight));

      // L2-001: Step height <= 120px
      if (verticalDelta > 120)
        warn(2, 'L2-001', rid, `Platforms ${a.id} and ${b.id} in ${rid}: vertical step ${verticalDelta}px exceeds 120px limit`);

      // L2-002: Horizontal gap <= 220px
      if (horizontalGap > 220)
        warn(2, 'L2-002', rid, `Platforms ${a.id} and ${b.id} in ${rid}: horizontal gap ${horizontalGap}px exceeds 220px limit`);
    }

    // L2-003: Interactions within 140px of a platform
    const allInteractable = [
      ...(room.doors || []),
      ...(room.keys || []),
      ...(room.abilities || [])
    ];
    allInteractable.forEach(item => {
      if (item.x == null || item.y == null) return;
      const nearPlatform = platforms.some(p => {
        const pRight = p.x + (p.len || 1) * 32;
        const dx = Math.max(0, Math.max(p.x - item.x, item.x - pRight));
        const dy = Math.abs(item.y - p.y);
        return Math.sqrt(dx*dx + dy*dy) <= 140;
      });
      if (!nearPlatform)
        warn(2, 'L2-003', rid, `Element ${item.id} in ${rid} is more than 140px from any platform`);
    });
  });

  report.level_1.passed = report.level_1.checks.filter(c => c.severity === 'error').length === 0;
  report.level_2.passed = report.level_2.checks.filter(c => c.severity === 'error').length === 0;

  return report;
}
```

**Verification:** Call `validateLayout(state.data)` in the browser console after loading the tool. It should return a report object without throwing. Test with a known-valid layout and confirm `level_1.passed === true`.

---

### Task 3.2 — Validation UI Panel

**What to add:** A new `.panel` section below the canvas area (or inside the right sidebar panel) that shows validation results.

**HTML:**
```html
<section class="panel validation-panel" id="validationPanel">
  <div class="validation-header">
    <div>
      <div class="eyebrow">Level Design</div>
      <h2>Validation</h2>
    </div>
    <div class="validation-header-actions">
      <span class="validation-summary-badge" id="validationSummaryBadge"></span>
      <button id="runValidation" class="btn-sm">Run Validation</button>
    </div>
  </div>
  <div id="validationResults" class="validation-results">
    <div class="empty-state" style="min-height: 100px; padding: 20px 0;">
      <div class="empty-state-sub">Run validation to check your level's structural soundness and traversal rules.</div>
    </div>
  </div>
</section>
```

**CSS:**
```css
.validation-panel {
  /* Same as .panel */
}
.validation-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.validation-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.validation-summary-badge {
  font-size: var(--font-size-xs);
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
}
.validation-summary-badge.pass { background: var(--good-soft); color: var(--good); }
.validation-summary-badge.fail { background: var(--error-soft); color: var(--error); }
.validation-summary-badge.warn { background: var(--warning-soft); color: var(--warning); }
.validation-results {
  display: grid;
  gap: 6px;
}
.validation-result-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.02);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}
.validation-result-item:hover {
  background: rgba(255,255,255,0.04);
  border-color: var(--line-strong);
}
.validation-result-item.error {
  border-color: rgba(248,81,73,0.2);
  background: var(--error-soft);
}
.validation-result-item.warning {
  border-color: rgba(210,153,34,0.2);
  background: var(--warning-soft);
}
.validation-result-icon {
  font-size: 12px;
  flex-shrink: 0;
  margin-top: 1px;
}
.validation-result-item.error .validation-result-icon::before { content: "✕"; color: var(--error); }
.validation-result-item.warning .validation-result-icon::before { content: "⚠"; color: var(--warning); }
.validation-result-body {
  flex: 1;
  min-width: 0;
}
.validation-result-id {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
}
.validation-result-msg {
  font-size: var(--font-size-xs);
  color: var(--text);
  line-height: 1.4;
  margin-top: 2px;
}
.validation-result-room {
  font-size: 10px;
  color: var(--muted);
  margin-top: 2px;
}
.validation-pass-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 12px;
  background: var(--good-soft);
  border: 1px solid rgba(74,222,128,0.2);
  font-size: var(--font-size-sm);
  color: var(--good);
  font-weight: 600;
}
```

**JS: run validation and render results:**
```js
document.getElementById('runValidation')?.addEventListener('click', () => {
  const report = validateLayout(state.data);
  state.lastValidationReport = report;
  renderValidationResults(report);
});

function renderValidationResults(report) {
  const container = document.getElementById('validationResults');
  const badge = document.getElementById('validationSummaryBadge');
  if (!container) return;

  const allChecks = [
    ...report.level_1.checks,
    ...report.level_2.checks
  ];

  // Update badge
  if (badge) {
    if (report.summary.errors > 0) {
      badge.textContent = `${report.summary.errors} error${report.summary.errors > 1 ? 's' : ''}`;
      badge.className = 'validation-summary-badge fail';
    } else if (report.summary.warnings > 0) {
      badge.textContent = `${report.summary.warnings} warning${report.summary.warnings > 1 ? 's' : ''}`;
      badge.className = 'validation-summary-badge warn';
    } else {
      badge.textContent = 'All checks passed';
      badge.className = 'validation-summary-badge pass';
    }
  }

  if (allChecks.length === 0) {
    container.innerHTML = `
      <div class="validation-pass-row">✓ All structural and traversal checks passed</div>
    `;
    return;
  }

  container.innerHTML = allChecks.map(check => `
    <div class="validation-result-item ${check.severity}" data-room="${check.room || ''}">
      <div class="validation-result-icon"></div>
      <div class="validation-result-body">
        <div class="validation-result-id">${check.id}</div>
        <div class="validation-result-msg">${check.message}</div>
        ${check.room ? `<div class="validation-result-room">Room: ${check.room}</div>` : ''}
      </div>
    </div>
  `).join('');

  // Click-to-jump: clicking an error jumps to the relevant room
  container.querySelectorAll('.validation-result-item[data-room]').forEach(item => {
    const roomId = item.dataset.room;
    if (!roomId) return;
    item.addEventListener('click', () => {
      // Switch to that room
      const roomSelect = document.getElementById('roomSelect');
      if (roomSelect) {
        roomSelect.value = roomId;
        roomSelect.dispatchEvent(new Event('change'));
      }
    });
  });
}
```

**Verification:**
- "Run Validation" button is visible
- Clicking it shows all Level 1 + Level 2 check results
- Errors show red styling, warnings show yellow
- Pass state shows green "All checks passed" row
- Badge shows error/warning/pass count
- Clicking an error with a room ID switches the canvas to that room

---

### Sprint 3 Verification Checklist

```
□ validateLayout() function exists and returns a structured report
□ validateLayout() runs without throwing on current room-layout-data.json
□ L1-001 through L1-006 checks all execute
□ L2-001 through L2-003 checks all execute
□ Validation panel is visible in the UI
□ "Run Validation" button triggers validation and renders results
□ Errors show with red styling, warnings with yellow
□ All-pass state shows green confirmation row
□ Summary badge updates to show error/warning/pass state
□ Clicking a result with a room ID switches to that room in the canvas
□ No canvas interaction regressions
```

---

### Sprint 3 Demo Script

**Step 1 — Validation engine: functional test via file inspection**
```bash
grep -A5 'function validateLayout' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html | head -8
grep -c 'L1-001\|L1-002\|L1-003\|L1-004\|L1-005\|L1-006' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'L2-001\|L2-002\|L2-003' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report:
- `validateLayout` function exists
- All L1 check IDs present (count should be 6)
- All L2 check IDs present (count should be 3)

**Step 2 — Validation panel screenshot**
```bash
open /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
sleep 1
screencapture -x /tmp/demo-s3-default.png
```
Read `/tmp/demo-s3-default.png`. Report:
- Is the validation panel visible below or alongside the canvas area?
- Does it have a "Run Validation" button?
- Is the empty/pre-run state shown (prompt text, no results yet)?
- Is there a summary badge area (currently empty or showing nothing)?

**Step 3 — Inject a known validation error and verify UI response**

The current `room-layout-data.json` is the ground truth. To test the error state without corrupting live data, open the browser console and run:
```js
// This will be the instruction to the agent to verify by reading the file:
// Look for a door with a targetRoom reference and verify that L1-003 would catch a bad reference
```
Instead of modifying live data, verify the error rendering path exists in the code:
```bash
grep -c 'validation-result-item error\|validation-result-item warning' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'renderValidationResults' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'runValidation' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report: all three should be ≥ 1.

**Step 4 — Run validation against current data via Node (headless check)**
```bash
node -e "
const fs = require('fs');
const html = fs.readFileSync('/Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html', 'utf8');
// Extract validateLayout function and test it
const funcMatch = html.match(/function validateLayout\(data\) \{[\s\S]+?\n\}/);
console.log(funcMatch ? 'validateLayout function found, length: ' + funcMatch[0].length : 'NOT FOUND');
"
```
Report: function found and has substantial length (> 500 chars).

**Step 5 — Validation results visual states**
```bash
grep -c 'validation-pass-row' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'validation-summary-badge' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'validation-result-msg' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report: all three class names present in file (CSS + HTML).

**Step 6 — Jump-to-room from validation result**
```bash
grep -A3 'validation-result-item.*data-room' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html | head -10
grep 'roomSelect.*dispatchEvent\|dispatchEvent.*roomSelect' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report: click handler dispatches change event on room select when error item is clicked.

**Step 7 — Screenshot of validation panel in context**
```bash
screencapture -x /tmp/demo-s3-validation-panel.png
```
Read screenshot. Report:
- Is the validation panel visually consistent with the rest of the design (same border, background, radius)?
- Does it sit naturally in the page flow?
- Is the "Run Validation" button clearly visible and does it look like a primary action?
- Does the panel feel like part of a production QA system, not an afterthought?

Output full demo report before proceeding to Sprint 4.

---

## Sprint 4 — Export Contract & Workbench Integration

**Goal:** Produce a structured runtime export package, and add a Level Design stage card inside the Sprite Workbench.

**Files to modify:**
- `room-layout-editor.html` (export UI)
- `tools/2d-sprite-and-animation/index.html` (Level Design stage card)

**Read before starting:**
- `docs/room-editor-workbench-integration-plan.md` (full integration architecture)
- `docs/sprite-workbench-runtime-export-contract.md` (existing export contract pattern)
- `tools/2d-sprite-and-animation/index.html` — read the existing stage card structure (find any existing stage/step panel HTML pattern)

---

### Task 4.1 — Export Package Generator (JS)

**Add to room-layout-editor.html script block:**

```js
function generateExportPackage(data, validationReport) {
  const timestamp = new Date().toISOString();

  // Per-room files
  const roomFiles = {};
  (data.rooms || []).forEach(room => {
    // Strip editor-only fields, keep runtime-relevant fields
    roomFiles[`${room.id}.json`] = {
      id: room.id,
      name: room.name,
      polygon: room.polygon,
      size: room.size,
      global: room.global,
      platforms: room.platforms,
      doors: room.doors,
      keys: room.keys,
      abilities: room.abilities,
      movers: room.movers,
      playerStart: room.playerStart,
      edgeLinks: room.edgeLinks,
    };
  });

  // World graph
  const worldGraph = {
    rooms: (data.rooms || []).map(room => ({
      id: room.id,
      name: room.name,
      global: room.global,
      size: room.size,
      connections: (room.edgeLinks || []).map(link => ({
        toRoom: link.targetRoomId,
        fromEdge: link.edgeIndex,
        toEdge: link.targetEdgeIndex,
      })),
      doors: (room.doors || []).map(d => ({
        id: d.id,
        targetRoom: d.targetRoom,
        kind: d.kind,
        locked: d.locked || false,
      })),
    })),
  };

  // Simple hash (non-cryptographic, for change detection)
  const dataStr = JSON.stringify(data);
  let hash = 0;
  for (let i = 0; i < dataStr.length; i++) {
    hash = ((hash << 5) - hash) + dataStr.charCodeAt(i);
    hash |= 0;
  }
  const hexHash = (hash >>> 0).toString(16).padStart(8, '0');

  // Manifest
  const manifest = {
    exported_at: timestamp,
    room_count: (data.rooms || []).length,
    validation_passed: validationReport ? validationReport.level_1.passed : null,
    validation_level: validationReport ? (validationReport.level_2.passed ? 2 : 1) : null,
    sha_simple: hexHash,
    engine_hints: {
      grid_size: data.meta?.grid || 32,
      world_width: data.meta?.worldWidth || 1600,
      world_height: data.meta?.worldHeight || 1200,
    },
  };

  return { roomFiles, worldGraph, manifest, roomLayout: data };
}

async function downloadExportPackage() {
  if (!state.data) { setStatus('No layout data to export', 'error'); return; }
  const report = state.lastValidationReport || validateLayout(state.data);
  const pkg = generateExportPackage(state.data, report);

  // Download each file as a separate JSON download
  // (Browser cannot create ZIP natively without a library; use sequential downloads)
  const downloads = [
    { name: 'level-export/level_manifest.json', data: pkg.manifest },
    { name: 'level-export/room_layout.json', data: pkg.roomLayout },
    { name: 'level-export/world_graph.json', data: pkg.worldGraph },
    ...Object.entries(pkg.roomFiles).map(([name, data]) => ({
      name: `level-export/rooms/${name}`,
      data
    }))
  ];

  // Download manifest first, then prompt user about remaining files
  const blob = new Blob([JSON.stringify(pkg.manifest, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'level_manifest.json';
  a.click();
  URL.revokeObjectURL(url);

  // Download room_layout.json (the full canonical file)
  const layoutBlob = new Blob([JSON.stringify(state.data, null, 2)], { type: 'application/json' });
  const layoutUrl = URL.createObjectURL(layoutBlob);
  const a2 = document.createElement('a');
  a2.href = layoutUrl;
  a2.download = 'room_layout.json';
  a2.click();
  URL.revokeObjectURL(layoutUrl);

  setStatus(`Exported ${(state.data.rooms||[]).length} rooms — manifest + layout downloaded`, 'success');
}
```

**Wire to Export button:**
```js
// Replace or supplement the existing downloadJson handler:
document.getElementById('downloadJson')?.addEventListener('click', downloadExportPackage);
```

**Verification:**
- Clicking "Export" downloads `level_manifest.json` and `room_layout.json`
- Manifest contains correct room count, timestamp, hash, and engine hints
- Manifest `validation_passed` is null if validation hasn't been run, or true/false if it has

---

### Task 4.2 — Level Design Stage Card in Sprite Workbench

**Read first:** Find how existing stage cards are structured in `tools/2d-sprite-and-animation/index.html`. Look for the stage navigation pattern and the panel/card structure used for each pipeline stage.

**What to add:** A new stage entry in the workbench stage list, and a new stage panel showing the level design summary.

**Find the stage navigation list** (look for a `<nav>` or list of stage buttons). Add an entry:
```html
<button class="stage-nav-item" data-stage="level-design">
  <span class="stage-nav-icon">⬡</span>
  <span class="stage-nav-label">Level Design</span>
  <span class="stage-nav-status" id="levelDesignStageStatus"></span>
</button>
```

**Add the stage panel** (after the last existing stage panel, using the same `.panel` + stage structure):
```html
<div class="stage-panel" id="stage-level-design" style="display:none;">
  <div class="stage-header">
    <div>
      <div class="eyebrow">Stage 5</div>
      <h2>Level Design</h2>
      <div class="sub">Design room layouts, place entities, and validate level traversal.</div>
    </div>
    <div class="stage-header-status" id="levelDesignStatus">
      <span class="stage-badge" id="levelDesignBadge">Not started</span>
    </div>
  </div>

  <div class="stage-summary-grid">
    <div class="badge">
      <div class="badge-label">Rooms</div>
      <div class="badge-value" id="ldRoomCount">—</div>
    </div>
    <div class="badge">
      <div class="badge-label">Validation</div>
      <div class="badge-value" id="ldValidationStatus">—</div>
    </div>
    <div class="badge">
      <div class="badge-label">Last Saved</div>
      <div class="badge-value" id="ldLastSaved" style="font-size:13px;">—</div>
    </div>
  </div>

  <div class="stack" style="margin-top: 16px;">
    <a href="../../room-layout-editor.html" target="_blank" class="btn-open-editor good">
      Open Room Editor ↗
    </a>
    <div class="hint">Room layouts are stored per-project. Open the room editor to design and validate your level.</div>
  </div>

  <div class="stage-validation-note" id="ldValidationNote" style="display:none;">
    <div class="eyebrow" style="margin-bottom:6px;">Validation</div>
    <div id="ldValidationDetail"></div>
  </div>
</div>
```

**CSS (add to workbench index.html inline styles or product-shell.css):**
```css
.btn-open-editor {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 8px 18px;
  border-radius: 14px;
  text-decoration: none;
  font-size: var(--font-size-sm);
  font-weight: 600;
  width: 100%;
  text-align: center;
  /* .good styles apply if using the existing button.good pattern */
}
.stage-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 14px;
}
.stage-validation-note {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,0.02);
  font-size: var(--font-size-xs);
}
```

**Verification:**
- Level Design stage is visible in the workbench stage navigation
- Clicking it shows the Level Design panel
- "Open Room Editor ↗" link opens room-layout-editor.html in a new tab
- Badge areas show "—" placeholder (actual data population is Sprint 0 / server work)

---

### Sprint 4 Verification Checklist

```
□ generateExportPackage() function exists in room-layout-editor.html
□ Export button downloads level_manifest.json
□ Export button downloads room_layout.json
□ Manifest contains: exported_at, room_count, validation_passed, sha_simple, engine_hints
□ Level Design stage entry is visible in Sprite Workbench nav
□ Clicking Level Design stage shows the panel
□ Panel has room count, validation, last saved badges
□ "Open Room Editor" link works and opens room-layout-editor.html
□ No regressions in existing workbench stage navigation
```

---

### Sprint 4 Demo Script

This is the final sprint demo. It covers both the room editor export feature and the Sprite Workbench integration. It also performs the definitive end-to-end visual comparison.

**Step 1 — Export function structure**
```bash
grep -c 'function generateExportPackage' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'level_manifest\|world_graph\|engine_hints' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'downloadExportPackage\|downloadJson' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report:
- `generateExportPackage` function present
- Export key names present (manifest, world_graph, engine_hints)
- Export function is wired to the download button

**Step 2 — Export output test (headless)**
```bash
node -e "
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('/Users/timwood/Desktop/projects/PWA/MV/room-layout-data.json', 'utf8'));
console.log('rooms:', data.rooms ? data.rooms.length : 'MISSING');
console.log('meta:', data.meta ? JSON.stringify(data.meta) : 'MISSING');
console.log('first room id:', data.rooms && data.rooms[0] ? data.rooms[0].id : 'NONE');
"
```
Report: confirms the source data file is valid and has expected structure.

**Step 3 — Workbench Level Design stage**
```bash
grep -c 'stage-level-design\|level-design' /Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html
grep -c 'Open Room Editor\|room-layout-editor' /Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html
grep -c 'ldRoomCount\|ldValidationStatus\|ldLastSaved' /Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html
```
Report:
- Level Design stage ID present in workbench
- "Open Room Editor" link present
- Badge IDs present

**Step 4 — Workbench screenshot with Level Design stage visible**
```bash
open /Users/timwood/Desktop/projects/PWA/MV/tools/2d-sprite-and-animation/index.html
sleep 1
screencapture -x /tmp/demo-s4-workbench.png
```
Read `/tmp/demo-s4-workbench.png`. Report:
- Is "Level Design" visible in the stage navigation list?
- Does it have an icon and label in the same style as other stage items?
- Does clicking it surface a panel with Room count, Validation, and Last Saved badges?
- Is the "Open Room Editor ↗" button visible and styled with the `.good` (gold) treatment?

**Step 5 — Room editor final screenshot**
```bash
open /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
sleep 1
screencapture -x /tmp/demo-s4-room-editor-final.png
```
Read `/tmp/demo-s4-room-editor-final.png`. Perform a comprehensive visual assessment:

For each section below, describe what you actually see:

```
NAV BAR:
  - Height and styling consistent with workbench?
  - Project context visible?

HEADER BAR (above canvas):
  - Room selector, tab strip, action buttons all present?
  - Compact — not taking excessive vertical space?

CANVAS TOOLBAR (left of canvas):
  - Color dots on element-type buttons?
  - Shortcut <kbd> badges visible?
  - Action buttons visually distinct from tool buttons?

CANVAS:
  - Room polygon visible?
  - Grid visible (if snap enabled)?
  - No floating inspector panel occluding canvas?

INSPECTOR (right rail):
  - Hidden when nothing selected?

VIEW CONTROLS (above canvas):
  - Tab strip for Room/Global?
  - Arrow icon pan buttons?
  - Fit button?

STATUS BAR:
  - Dot prefix visible?
  - Readable text?

VALIDATION PANEL:
  - Visible below canvas?
  - "Run Validation" button present?

INVENTORY SIDEBAR:
  - Expandable sections with color dots?
  - Not a flat chip list?
```

**Step 6 — Side-by-side final comparison**
```bash
screencapture -x /tmp/demo-s4-workbench-nav.png
screencapture -x /tmp/demo-s4-room-editor-nav.png
```
Open both and compare. Report on:
- Do the nav bars look like they belong to the same product?
- Do the panel cards use identical border, background, and radius?
- Is the typography (font weights, label treatment, eyebrow style) consistent?
- Overall: would a user feel they are using two tools from the same suite?

**Step 7 — Regression check: core canvas interactions**
```bash
# Verify no canvas JS was touched unintentionally
grep -c 'mousedown\|mousemove\|mouseup\|touchstart' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
grep -c 'snapToGrid\|edgeLink\|hitTest\|detectHit' /Users/timwood/Desktop/projects/PWA/MV/room-layout-editor.html
```
Report: mouse event handlers still present; core canvas function names still present.

**Final demo report:** Output the full demo report with "Approved to proceed: YES" if the room editor is visually at production quality and matches the Sprite Workbench standard. If not, list the specific remaining gaps and recommend targeted fixes before sign-off.

---

## Global Constraints (Apply to All Sprints)

These rules apply throughout. Check before every PR or sprint review.

### Must Never Break
- Canvas hit detection (clicking elements selects them)
- Vertex drag (moving a vertex updates the polygon)
- Platform/door/key/ability/mover drag
- Edge linking (global map, select edge, link to target)
- Room switching (select from dropdown, canvas updates)
- Grid snap (platform/vertex positions snap to grid)
- localStorage save (persists between sessions)
- Server sync (if server running, layout saves to disk)
- Room polygon close detection
- Zoom / pan on both canvases

### Must Not Add
- Any external JS library
- Any CSS framework
- Additional HTML files (stays single file per tool)
- New HTTP endpoints (Sprint 0 work, separate)
- Any `console.log` left in final code (clean up debug logs)

### Must Maintain
- All existing element IDs referenced in JS
- All `data-tool` attributes on toolbar buttons
- The `state` global object structure
- The `room-layout-data.json` format (existing data must still load)

### Code Style
- Indent: 2 spaces
- Semicolons: yes
- Prefer `const`/`let` over `var`
- Function declarations over arrow functions for top-level functions
- Arrow functions acceptable for callbacks and event handlers

---

## Verification Protocol (End-to-End)

Run this after each sprint and before considering the sprint done.

```
1. Open room-layout-editor.html in browser (file:// or via local server)
2. Verify page loads without console errors
3. Verify all rooms load (room selector populated)
4. Select a room → canvas renders room polygon
5. Click a platform → inspector shows with correct color icon
6. Drag a vertex → polygon updates
7. Add a new platform → platform appears on canvas + in inventory
8. Switch to global map → global canvas renders all rooms
9. Save → success toast + dirty dot clears
10. Reload page → saved state persists
11. Run validation → results appear
12. For any sprint that modified workbench: open Sprite Workbench, verify Level Design stage visible
```

---

## Blocked State Handling

If a task cannot be completed as specified:

1. **HTML structure differs from expected:** Read the actual HTML for that section before attempting the change. Do not guess at element IDs or class names. If the actual structure is significantly different from what this spec describes, note the actual structure and adapt the implementation to match, preserving the intent.

2. **JS function not found:** Search the entire `<script>` block for the function by name fragment. If the function doesn't exist, read the surrounding code to understand the actual pattern and adapt.

3. **Visual regression after CSS change:** Revert the specific CSS change that caused it. Do not proceed to the next task with a broken layout.

4. **Element ID conflict:** Never rename an ID that is referenced in JS without also updating every reference to that ID in the JS.

5. **Sprint cannot complete in one pass:** Mark the incomplete tasks clearly in a blockers note and proceed to the next sprint only if the blockers are non-blocking for later work.
