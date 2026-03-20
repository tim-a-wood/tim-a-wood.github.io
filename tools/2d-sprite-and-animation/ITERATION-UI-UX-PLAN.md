# Sprite Workbench — UI/UX Overhaul Iteration Plan

## Design Option Comparison

### Option A: Signal
- Strongest focus on the work itself; chrome stays quiet and technical depth is tucked away cleanly.
- Best fit if the tool should feel fast, sharp, and low-distraction rather than expressive or brand-heavy.
- Vertical indexed navigation makes phase order obvious, but the experience is intentionally austere.
- Mobile bottom-sheet navigation is efficient, though it relies on one extra tap to expose the full phase list.

### Option B: Studio
- Most overtly creative and branded direction; it feels like a professional art workstation rather than a utility.
- Primary actions read clearly because the chapter rail and warm accent colour create strong visual hierarchy.
- The reduced status tray is the most contextual approach, but it shows less system state at once than the other options.
- Mobile keeps the important action area prominent, though the horizontal chapter rail is denser than the other patterns.

### Option C: Atlas
- Most structured and trustworthy option; complex workflow state feels legible without looking heavy.
- The context bar plus developer toggle gives the cleanest separation between everyday use and advanced data.
- Project selector saves space, but it makes the project list feel less tactile than a persistent drawer or card list.
- Mobile bottom tabs map well to the five phases, though the visual language is more product-dashboard than studio tool.

**Iteration goal:** Overhaul the UI/UX of `tools/2d-sprite-and-animation/index.html` to deliver a complete, modern, production-ready visual and interaction design. The functional pipeline (Python server, API integrations, job processing) is out of scope for this iteration and must not be broken.

**Definition of Done (Iteration):** The UI/UX is complete and production-ready across MacBook Air (≈1280–1440px) and iPhone 16 Pro portrait (393px). A user can load the tool, select a project, navigate all five phases forward and backward, interact with all panels, and see a polished, consistent design with no raw or placeholder UI. All existing functionality continues to work without regression.

**Hard Constraints:**
- `tests/test_sprite_workbench.py` acceptance tests must not be modified without explicit Product Owner approval
- All server API endpoints must remain unchanged
- The tool must remain a single `index.html` file (embedded CSS + JS)
- No third-party CSS frameworks (Bootstrap, Tailwind, etc.) — custom CSS only
- Existing data attributes (`data-wizard-view`, etc.) and server-polling behaviour must be preserved unless a specific replacement is agreed

**Working Assumptions:**
- Implemented by AI agents; sprints are verified by demo to Product Owner, not by calendar time
- Agent may restructure internal HTML/CSS/JS architecture freely within the single-file constraint
- Agent must not change functional behaviour — UI changes only (layout, styling, interaction, progressive disclosure)

---

## Sprint 0 — Design Language Selection

**Objective:** Present three distinct design language options as static HTML prototypes. The Product Owner selects one (or a hybrid). No changes are made to `index.html` in this sprint.

**Agent instructions:**

Create three standalone static HTML files in `tools/2d-sprite-and-animation/design-options/`:
- `option-a-signal.html`
- `option-b-studio.html`
- `option-c-atlas.html`

Each prototype must contain:
1. The five-phase navigator (Describe / Concepts / Character / Animations / Review & Export) in whatever navigation paradigm fits the language
2. A representative "active phase" panel showing a form, a card grid, and a status indicator
3. The activity dock / progress indicator
4. The status row (5 cards) — or its redesigned equivalent
5. A project list in whatever form fits the language
6. Correct mobile layout for 393px (iPhone 16 Pro portrait) — use a `@media (max-width: 430px)` block

The prototypes are **non-functional** (no JavaScript polling, no API calls) but must demonstrate real interaction states using CSS `:hover`, `:focus`, and a few `class` toggles (selected, active, locked) inline in the HTML.

---

### Option A: "Signal" — Minimal Dark Craft

**Inspiration:** Linear, Raycast, Obsidian — tools where the interface disappears and only the work is visible.

**Visual language:**
- Background: `#0c0e11` (near-black, cool, no blue tint)
- Surface: `#14181d` panels with a `1px solid rgba(255,255,255,0.07)` border — no glassmorphism
- Text: `#e8edf2` primary, `#7a8a9a` muted
- Accent: `#5b8cf5` (electric blue) — used only for interactive states and the active phase indicator
- No gradients, no backdrop-blur, no shadows except a single drop shadow on floating overlays
- Font: system-ui / -apple-system / "SF Pro Text" stack — no Google Fonts imports

**Phase navigation:**
- Vertical indexed list in the sidebar (numbers 01–05, phase name, compact status chip)
- Active phase highlighted with left border in accent blue
- Locked phases shown at reduced opacity with a lock glyph

**Status information:**
- Collapse "status-row" and "metric-grid" into a single compact header bar at the top of the main column (one line, 5 values separated by dividers) — visible but never occupies primary space
- Technical detail (generation mode, job ID, credit balance) hidden behind a `(i)` icon that opens a small popover

**Progressive disclosure philosophy:**
- Everything not needed for the current phase step is visually quiet (muted text, collapsed)
- Advanced/technical fields behind a `▸ Advanced` disclosure toggle styled as a subdued text link

**Mobile (iPhone):**
- Sidebar slides in as a bottom sheet — a persistent bottom tab bar shows phase icons
- Bottom sheet triggered by tapping the active phase indicator

---

### Option B: "Studio" — Creative Workstation

**Inspiration:** Figma, DaVinci Resolve, Affinity Photo — tools designed for creative professionals who work with visual assets.

**Visual language:**
- Background: `#161412` (warm dark brown-black)
- Panels: `#1f1b18` with `1px solid rgba(255,200,100,0.1)` — warm amber border tint
- Text: `#f0e8dc` primary (warm white), `#8a7a6a` muted
- Accent: `#e8a842` (rich amber/gold) — elevated from the current `#d4a752` — used for active state, primary buttons, and the brand
- Supporting colours: deep teal for success (`#4aaa8a`), terracotta for error (`#c06050`)
- Subtle radial gradient on each panel surface `radial-gradient(ellipse at top right, rgba(240,180,80,0.04), transparent)`
- Font: "IBM Plex Sans" retained (fits the professional tool aesthetic)

**Phase navigation:**
- Horizontal phase "chapter rail" at the top of the main column — large numbered pills with chapter labels
- Sidebar becomes a collapsible project drawer only — toggled by a hamburger icon
- Active phase shown with a filled pill; completed phases with a check mark; locked with a lock

**Status information:**
- Status cards retained but redesigned as a compact "tray" below the chapter rail — only the 2–3 most contextually relevant cards shown per phase (e.g., on the Concepts phase: Active Project + Pixel Lab Credits + Checks; on Animations: Active Project + Current Step + Checks)
- Metric cards merged into the relevant phase header as small inline counters

**Progressive disclosure:**
- Technical detail inside collapsible `<details>` blocks styled as "Lab Notes" — a secondary visual treatment that signals "this is for advanced use"
- Each phase panel has a prominent "primary action" area and a quieter "details" area below

**Mobile (iPhone):**
- Chapter rail collapses to a horizontal scrollable pill strip
- Project drawer becomes a bottom sheet
- Phase panel takes full width; primary action always visible without scroll

---

### Option C: "Atlas" — Structured Journey

**Inspiration:** Vercel dashboard, Railway, Supabase — modern developer SaaS products that make complex workflows feel legible and trustworthy.

**Visual language:**
- Background: `#0d1117` (GitHub-dark family)
- Panels: `rgba(22, 30, 42, 0.96)` with `1px solid rgba(255,255,255,0.09)` — cool, neutral
- Text: `#e6edf3` primary, `#8b949e` muted (GitHub dark palette)
- Accent: `#4493f8` (GitHub blue) — interactive elements, links, active states
- Secondary accent: `#3fb950` (green) for success/complete states; `#f85149` for errors
- Clean, no-decoration panels — whitespace does the heavy lifting
- Font: "Inter" (loaded from local system or bundled, no external fetch)

**Phase navigation:**
- Left sidebar retains the phase list, but each phase is a "card-link" with a progress indicator embedded (a tiny arc/ring showing steps completed within the phase)
- Sidebar top: brand + project selector (dropdown, not a list) — saves vertical space for the nav
- Completed phases get a filled ring; current phase has a pulsing partial ring; locked phases are greyed

**Status information:**
- Status row collapsed into a persistent "context bar" — a 40px fixed bar at the top of the main column showing: breadcrumb (`Project › Phase`) + 3 inline status chips + a Pixel Lab credit badge
- This bar is always visible when scrolling — it replaces the status-row and metric-grid sections entirely
- Full metrics available in a slide-out panel triggered by a "Details" button in the context bar

**Progressive disclosure:**
- All technical fields (generation mode, job ID, scaffold JSON, skeleton data) hidden by default
- Revealed via a "Developer" toggle in the context bar that adds a `.dev-mode` class to the body, making `.dev-only` elements visible
- This is a deliberate toggle, not scattered expand/collapse buttons

**Mobile (iPhone):**
- Sidebar hidden; context bar becomes the navigation anchor
- Bottom navigation tab bar with 5 phase icons
- Tapping phase icon scrolls to that panel (smooth scroll, sticky panel headers)

---

### Sprint 0 Demo

**Agent must prepare:**
1. Three static HTML files as described above — open in Safari on desktop and in Safari mobile simulation (or resize to 393px)
2. A brief comparison note at the top of this file (below a `## Design Option Comparison` heading) summarising the key trade-offs in 3–5 bullet points per option

**Product Owner evaluates:**
- Does the design language feel right for a solo creative tool?
- Does the phase navigation feel natural and easy to use?
- Is the progressive disclosure approach appropriate?
- Which option (or hybrid) should the full implementation follow?

**Sprint 0 is done when:** Product Owner has selected a design direction and confirmed any specific hybrid choices. Agent records the decision in a `## Approved Direction` section at the bottom of this file before proceeding to Sprint 1.

---

## Sprint 1 — Design System Foundation + App Shell

**Prerequisite:** Sprint 0 approved direction is recorded in this file.

**Objective:** Replace the current CSS design system and app shell structure in `index.html` with the approved design language. All five phases must be navigable and the page must load without errors. No panel content is restyled in this sprint — only the shell (sidebar/nav, outer chrome, typography scale, colour tokens, spacing system, and the status/context bar).

**Agent instructions:**

### 1.1 CSS design system

Replace the `:root` CSS variables block with the approved design language's token set. At minimum define:

```
--bg, --bg-soft, --bg-raised
--surface, --surface-hover
--border, --border-strong
--text, --text-muted, --text-faint
--accent, --accent-hover, --accent-soft
--success, --success-soft
--warning, --warning-soft
--error, --error-soft
--radius-sm, --radius-md, --radius-lg
--space-1 through --space-8 (4px scale: 4, 8, 12, 16, 24, 32, 48, 64)
--font-sans, --font-mono
--font-size-xs (11px), --font-size-sm (13px), --font-size-base (14px), --font-size-md (15px), --font-size-lg (18px), --font-size-xl (22px)
--shadow-sm, --shadow-md, --shadow-lg
--transition-fast (120ms ease), --transition-base (200ms ease)
```

### 1.2 App shell

Implement the approved navigation paradigm for the app shell:
- Sidebar structure (if retained) or replacement nav component
- Phase navigation list/rail/tabs with correct active/complete/locked states driven by existing JS state
- Project selector/list in its approved position
- Brand mark

### 1.3 Context / status bar

Replace the existing `.status-row` and `.metric-grid` sections with the approved compact status presentation (context bar, tray, or header bar per the chosen option). Wire the same JS update functions (`renderStatus()`) to the new elements by keeping the same element IDs where possible, or updating the JS to target new IDs.

### 1.4 Typography

Apply the approved type scale. Ensure:
- Headings use the approved font and size
- Body text is the approved size and line-height
- Monospace sections (prompts, JSON, paths) use `--font-mono`

### 1.5 Mobile shell

Implement the mobile navigation approach for ≤430px as defined by the chosen option. The mobile shell must be fully functional (open/close, navigate between phases).

### 1.6 Preservation rules

- All panel section IDs (`#intake`, `#concepts`, `#character`, `#animations`, `#review-export`, `#activity-log`) must be preserved
- All JS event listeners and API wiring must continue to function — CSS class/ID renames must be reflected in JS
- Wizard mode switching (`isWizardMode()`, body class toggling) must continue to work

---

### Sprint 1 Demo

**Agent must prepare:**
1. `index.html` loads cleanly in browser with no console errors
2. All five phases are visible in the new navigation — clicking each scrolls to the correct panel
3. A project can be selected from the project list/selector — the status bar updates to show the project name
4. The page renders correctly at 1280px (MacBook Air) and 393px (iPhone portrait)
5. The activity dock remains visible and styled correctly

**Product Owner evaluates at demo:**
- Does the shell feel right? Is this the design language we approved?
- Is the phase navigation clear and easy to use?
- Is the status/context information legible without being overwhelming?
- Does the mobile shell feel native?

**Sprint 1 is done when:** Product Owner approves the shell. Agent notes any approved deviations in a `## Sprint 1 Approved Changes` section at the bottom of this file.

---

## Sprint 2 — Phase Navigation System

**Prerequisite:** Sprint 1 approved.

**Objective:** Fully implement the phase navigation experience — active/complete/locked states, back navigation, step context headers, and transition behaviour. The wizard experience must feel purposeful: users always know where they are, where they can go, and how to go back.

**Agent instructions:**

### 2.1 Phase state rendering

Each phase in the navigation must visually reflect one of four states:
- **Locked** — not yet reachable (reduced opacity, disabled interaction, lock glyph or indicator)
- **Available** — reachable but not started (default state, no completion indicator)
- **In-progress** — currently active (accent colour, bold label)
- **Complete** — finished (check mark or filled indicator, muted accent)

These states must be computed from the existing project data structure (specifically `project.wizard_state` or equivalent fields loaded from the server). Wire into the existing `renderModeShell()` or equivalent function.

### 2.2 Phase panel headers

Each of the five phase panels (`#intake`, `#concepts`, `#character`, `#animations`, `#review-export`) must have a consistent, styled "phase header" block at the top of the panel containing:
- Phase number and name (large, prominent)
- One-line description of what happens in this phase
- Phase completion status badge
- A "Back to previous phase" affordance (link or button) that navigates to the prior phase — visible whenever the phase is not the first
- A contextually relevant primary action button (e.g., "Save & Continue" on Describe, "Generate Concept" on Concepts) — this replaces any duplicate buttons currently scattered in the panel

### 2.3 Wizard step flow

The current `WIZARD_STEPS_PIXEL_LAB_UI` five-step flow must be reflected in phase navigation. When a user completes the primary action of a phase and advances:
- The current phase transitions to "complete" state in the navigator
- The next phase becomes "in-progress"
- Navigation focus moves to the next phase (smooth scroll or panel reveal)

### 2.4 Back navigation

A user must be able to navigate to any previously completed phase from the navigator, with no loss of data. Back navigation must:
- Show the phase in its completed state (form values populated, generated content visible)
- Allow editing (forms re-editable, re-generation possible)
- Not require re-doing downstream phases unless the user explicitly changes an upstream decision

### 2.5 Phase transition animation

Implement a subtle, purposeful CSS transition when switching between phases:
- Duration: 160ms, `ease-out`
- Effect: the incoming panel fades in and translates up by 8px (de-emphasises mechanical jumping)
- Must respect `prefers-reduced-motion` — no animation if set

### 2.6 Mobile phase navigation

Ensure the mobile navigation (bottom bar, bottom sheet, or pill strip per chosen option) reflects phase state correctly on iPhone 16 Pro portrait. Tapping a phase in mobile nav must smoothly bring the user to that phase.

---

### Sprint 2 Demo

**Agent must prepare:**

Load an existing project that has concepts generated and character approved (i.e., multiple phases completed). Demonstrate:

1. The phase navigator showing correct locked/complete/in-progress/available states for that project
2. Clicking each unlocked phase navigates to it correctly
3. The phase header shows the correct title, description, status badge, and back link
4. The transition animation plays when switching phases
5. On mobile (resize to 393px): tap each phase in the mobile nav, confirm it navigates correctly
6. Starting from the Animations phase, click "Back" — confirm it goes to Character with data intact

**Product Owner evaluates:**
- Does the phase navigation feel intuitive and clear?
- Is the state visualization (locked/complete/in-progress) immediately legible?
- Do the phase headers give enough context to orient quickly?
- Is the transition smooth and not jarring?

**Sprint 2 is done when:** Product Owner approves the navigation system.

---

## Sprint 3 — Panel Content & Progressive Disclosure

**Prerequisite:** Sprint 2 approved.

**Objective:** Redesign the content of all five phase panels and the activity system. Apply the approved design language to every form, card, grid, preview, and action element. Implement progressive disclosure throughout — technical detail must be hidden by default and revealed only on demand.

**Agent instructions:**

### 3.1 Progressive disclosure principle

Audit every visible element in every panel and classify it as one of:
- **Primary** — needed by a typical user on every use (always visible)
- **Secondary** — useful context but not needed every time (visible but quiet — muted text, smaller size)
- **Technical** — debugging/advanced info (hidden behind a disclosure toggle)

Apply this classification consistently:
- Primary elements: full visual weight
- Secondary elements: muted text (`--text-muted`), reduced font size
- Technical elements: inside a `<details>` block or behind a `.dev-mode` toggle (per chosen option), styled with `--text-faint` and `--font-mono`

Technical items to hide by default include: job IDs, generation mode labels, scaffold JSON, seed values, prompt text (except where the user explicitly built the prompt), credit cost values, internal state flags, and file paths.

### 3.2 Describe panel (`#intake`)

- Project name: prominent, large text input at the top
- Character brief textarea: full width, comfortable height (min 5 rows), with placeholder text that guides
- The 6 art-direction fields: styled as a 2-column card grid (label + input pairs) — not a vertical list of bare inputs
- Reference images section: card-based with clear add/remove affordance, image thumbnail preview when a reference is loaded
- Save button: single primary button, full-width on mobile
- Technical: source/backend selector hidden under `▸ Generation settings` disclosure

### 3.3 Concepts panel (`#concepts`)

- Concept grid: clean card layout with image thumbnail, triage state badge (approved / favourite / rejected / none), and action buttons on hover/focus (no permanent button clutter)
- Selected concept large preview: takes ≥60% of available width on desktop; full width on mobile
- Zoom/pan controls: minimal floating control strip over the preview image (not a separate section)
- Concept triage buttons (approve / favourite / reject): icon+label buttons below the large preview, clearly separated from iteration controls
- Iteration controls (inpaint/regenerate): collapsed under `▸ Iterate on this concept` — expands inline below the large preview
- Prompt scaffold display: hidden under `▸ View generated prompt` disclosure (it's technical detail)
- Generation/import buttons: prominent section with clear primary (Generate) and secondary (Import) actions

### 3.4 Character panel (`#character`)

- Direction grid (4 or 8 directions): clean sprite preview grid with direction labels
- Skeleton overlay: toggled by a visible button over the sprite preview — not a permanently visible complex section
- Approve character button: prominent, full-width primary button with a clear prerequisite checklist (skeleton estimated, directions look correct)
- Skeleton editing (manual pose modal trigger): secondary button, not primary
- Generation settings (direction count, reference weight): collapsed under `▸ Generation settings`

### 3.5 Animations panel (`#animations`)

- Template animation clips: card grid per clip (idle, walk, etc.) — each card shows clip name, a short animated GIF preview loop when generated, and a "Regenerate" action
- Custom animation input: text field with placeholder guidance ("Describe an action: e.g. swinging a sword"), a primary Generate button, and a collapsible `▸ Advanced parameters` for timing/speed
- Animation preview: plays the generated clip inline on the card — not in a separate section
- SkelForm/skeleton guidance: collapsed under `▸ Skeleton guidance` disclosure
- Build clips button: prominent, appears after all required clips are generated

### 3.6 Review & Export panel (`#review-export`)

- QA checklist: visual checklist with pass/fail/pending per check — clear green/red icons, not raw text
- Export button: disabled until all required QA checks pass; shows what's blocking it
- Export summary: once exported, shows the output file paths in a clean card (with monospace font) and a "View export" link
- Technical QA detail (check reasons, raw JSON): collapsed under `▸ QA details`

### 3.7 Activity system

**Activity dock** — redesign as a slide-up notification panel (not a persistent bar):
- Hidden when no job is running
- Slides up from the bottom when a job starts — shows job type, label, and progress bar
- Dismissable while running (clicking away or pressing Escape minimises it to a floating badge in the bottom-right corner)
- The floating badge shows a spinner + percentage — clicking it re-opens the full dock
- On job completion: dock transitions to a success/error state, auto-dismisses after 3 seconds

**Toast notifications** — redesign:
- Appear top-right on desktop; top-centre on mobile
- Use the approved design language's colour tokens
- Success: green border/icon, 3.5s timeout
- Error: red border/icon, persistent until dismissed (requires a close button)
- Info: neutral, 3.5s timeout

### 3.8 Modals

Redesign both modals (zoom modal, manual pose modal) with:
- Clean centred card with clear close affordance (× button top-right + Escape key)
- Backdrop: `rgba(0,0,0,0.7)` with no blur (blur creates visual noise behind complex images)
- Modal card uses `--surface` background, `--border` border, `--radius-lg`
- Mobile: modals take full screen height on ≤430px with a bottom swipe-to-close affordance

---

### Sprint 3 Demo

**Agent must prepare:**

Load a project that has progressed through Concepts and Character and has at least one animation generated. Walk through:

1. **Describe**: Open the panel — show that art-direction fields are in the card grid layout; open the Generation settings disclosure and confirm it reveals the technical backend selector
2. **Concepts**: Show the concept grid with triage badges; select a concept and show the large preview with zoom strip; expand the Iterate section and confirm it opens inline
3. **Character**: Show the direction sprite grid; toggle the skeleton overlay; confirm Generation settings disclosure works
4. **Animations**: Show the animation cards with GIF previews; show the custom animation input; expand Advanced parameters disclosure
5. **Review & Export**: Show the QA checklist with visual pass/fail; confirm export button is gated by QA
6. **Activity dock**: Trigger a generation job and demonstrate the slide-up dock, the floating badge on minimise, and the auto-dismiss on completion
7. **Mobile (393px)**: Run through each panel — confirm primary actions are always reachable without horizontal scroll

**Product Owner evaluates:**
- Is the technical detail appropriately hidden? Does it feel less cluttered?
- Are the primary actions on each panel immediately obvious?
- Do the concept grid, sprite preview, and animation cards feel polished?
- Does the activity dock behaviour feel natural?

**Sprint 3 is done when:** Product Owner approves all five panels and the activity system.

---

## Sprint 4 — Polish, States & Production Readiness

**Prerequisite:** Sprint 3 approved.

**Objective:** Apply the final layer of polish that separates "functional redesign" from "production-ready UI". This sprint covers all edge-case states (empty, loading, error), micro-interactions, accessibility, and a final responsive pass across both target screens.

**Agent instructions:**

### 4.1 Empty states

Every panel must have a designed empty state — shown when no project is selected or when the phase has not been started:
- A centred illustration-free message (icon glyph + heading + 1-line description + primary CTA)
- Examples:
  - No project selected: "No project selected — create one or choose from the list"
  - Concepts phase, no concepts generated: "No concepts yet — describe your character and generate the first batch"
  - Character phase, no character generated: "Character not generated — complete the Concepts phase first"
- Empty states must use `--text-muted` for the description and `--accent` for the CTA button

### 4.2 Loading states

Every async operation must have a distinct loading state:
- Concept grid loading: skeleton cards (animated shimmer in `--surface` colour) — one row of 4 placeholder cards
- Large preview loading: a centred spinner over a `--bg-soft` background
- Character sprites loading: placeholder direction grid with shimmer
- Animation clip loading: shimmer card per clip slot
- Shimmer animation: `@keyframes shimmer` using a gradient sweep — must respect `prefers-reduced-motion` (static colour if set)

### 4.3 Error states

Every operation that can fail must have a visible, actionable error state:
- Inline error on a card: red border, error icon, brief message, retry button
- Full-panel error (e.g., server unreachable): a banner at the top of the panel with red accent, message, and a "Retry" or "Check server" action
- Toast errors (already covered in Sprint 3) for transient failures
- Error text must always explain what happened and what the user can do — never raw stack traces or JSON

### 4.4 Micro-interactions

Apply consistent, subtle transitions to interactive elements:
- Buttons: `transform: translateY(-1px)` + box-shadow increase on `:hover`; `transform: translateY(0)` + shadow decrease on `:active` — 120ms ease
- Cards (concept thumbnails, project cards): `transform: translateY(-2px)` + shadow on hover — 160ms ease
- Phase navigation items: background fill transition on hover — 120ms ease
- Triage buttons (approve/favourite/reject): filled background flash on click — 80ms, then settle to tinted state
- All transitions must respect `prefers-reduced-motion`

### 4.5 Focus states

Ensure all interactive elements have a visible, on-brand focus ring:
- Use `outline: 2px solid var(--accent); outline-offset: 2px` on all focusable elements
- Remove the browser default outline and replace with this token-based ring
- Test with keyboard navigation: Tab through all controls in each panel and confirm focus is always visible

### 4.6 Accessibility pass

- All images and icon-only buttons must have `aria-label` or `alt` text
- The activity dock must retain `aria-live="polite"` on its live region
- Toast stack must retain `aria-live="polite"`
- Phase navigation items must have `aria-current="page"` (or `aria-selected`) on the active phase
- Colour contrast: run a manual check — all `--text` on `--bg` combinations must meet WCAG AA (4.5:1 for body text)
- All modals must trap focus while open and restore focus to the trigger on close

### 4.7 Final responsive pass — MacBook Air

Target: 1280×800 (MacBook Air 13" native). Verify:
- No horizontal scroll at 1280px
- No panel content overflow
- Sidebar and main column proportion feels balanced (sidebar should not feel either cramped or wastefully wide)
- Status/context bar is fully legible at this resolution
- Concept grid shows ≥3 columns; animation clip grid shows ≥2 columns

### 4.8 Final responsive pass — iPhone 16 Pro portrait

Target: 393×852 (iPhone 16 Pro logical resolution). Verify:
- Mobile navigation is fully functional
- No horizontal scroll
- Primary action buttons are ≥44px tall (touch target minimum)
- Forms are comfortable to fill (input fields at least 16px font — avoids iOS auto-zoom)
- Concept large preview fills available width
- Activity dock / floating badge does not obscure primary actions
- Export panel QA checklist is readable without horizontal scroll

### 4.9 Print/share stylesheet (optional, low-priority)

If time permits: a minimal `@media print` style that hides navigation and shows the current phase content cleanly. This is the lowest priority in Sprint 4 and may be deferred.

---

### Sprint 4 Demo — Final Demo to Product Owner

**Agent must prepare a complete end-to-end demo walk:**

**Scenario A — First-time user (empty state flow):**
1. Open the tool with no project selected
2. Show empty state on the main area ("no project selected")
3. Create a new project — show the Describe panel in its initial empty state
4. Fill in the brief form — show the art-direction card grid, reference image add flow
5. Save and advance — observe phase navigation update

**Scenario B — Active project full flow:**
Load a project with data at every phase. Navigate:
1. Describe → show populated form, art-direction cards, generation settings collapsed
2. Concepts → show concept grid with triage badges, select a concept, zoom/pan, open iteration section
3. Character → show sprite direction grid, toggle skeleton, confirm skeleton data visible via disclosure
4. Animations → show clip cards with animated GIF previews, show custom action input, advanced params disclosure
5. Review & Export → show QA checklist, export package output card

**Scenario C — Mobile (resize to 393px):**
Repeat Scenario B navigating only via the mobile nav — confirm every phase is reachable and primary actions are tappable

**Scenario D — Loading and error states:**
1. With the server running, trigger a concept generation — show the shimmer loading state in the grid, the activity dock slide-up, the floating badge on minimise, the completion auto-dismiss
2. Stop the server; attempt an action — show the error banner/toast with actionable message

**Scenario E — Keyboard navigation:**
Tab through the Describe panel and confirm visible focus rings on all inputs and buttons.

**Product Owner evaluates:**
- Does the full experience feel complete and production-ready?
- Are there any panels or states that still feel rough or unfinished?
- Is the progressive disclosure working as intended — does it feel less cluttered?
- Does the mobile experience feel like a first-class citizen?
- Any final blocking issues before declaring the UI/UX iteration done?

**Sprint 4 / Iteration is done when:** Product Owner declares the UI/UX production-ready and signs off on all five demo scenarios.

---

## Appendix A — Current Architecture Reference

| Item | Detail |
|---|---|
| Main file | `tools/2d-sprite-and-animation/index.html` (~491KB, ~11,017 lines) |
| Five phases | Describe (`#intake`), Concepts (`#concepts`), Character (`#character`), Animations (`#animations`), Review & Export (`#review-export`) |
| Current nav | Anchor links in sidebar: `<a href="#intake">Describe</a>` etc. |
| Current status | `.status-row` (5 cards) + `.metric-grid` (4 cards) |
| Current activity | `.activity-dock` fixed at bottom, `aria-live="polite"` |
| Wizard mode | Body class `wizard-mode`; panels toggled via `data-wizard-view` attribute |
| JS state | Global `state` object; project data polled from `/api/projects/{id}` |
| Key render fns | `renderStatus()`, `renderActivity()`, `renderProjectList()`, `renderConceptGrid()`, `renderModeShell()` |
| Backend API | Unchanged — all endpoints at `/api/...` must continue to work |
| Breakpoints | `≤760px` mobile, `≤1180px` tablet/laptop, `≥1181px` large desktop |

## Appendix B — Key Design Decisions Log

*(Agent: record all Product Owner decisions and approved deviations here as the iteration progresses)*

### Approved Design Direction
- Approved base direction: Round 2 `hybrid-3-flightdeck` shell
- Layout direction: retain the Studio-inspired chapter rail and two-column phase workspace
- Colour direction: use the Atlas blue/green palette rather than the warmer Studio palette
- Header direction: keep the process-forward graphical header that previews production state and outputs
- Sidebar requirement: the left project panel must be collapsible toward the left edge as part of the app shell

### Sprint 1 Approved Changes
*(to be filled after Sprint 1)*

### Sprint 2 Approved Changes
*(to be filled after Sprint 2)*

### Sprint 3 Approved Changes
*(to be filled after Sprint 3)*

### Sprint 4 Approved Changes
*(to be filled after Sprint 4)*
