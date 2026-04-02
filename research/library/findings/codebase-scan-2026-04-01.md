---
title: Initial Codebase Scan — MV Toolchain
type: finding
date: 2026-04-01
author: Research Agent
status: final
tags: css, html, javascript, style-guide, room-editor, sprite-workbench, tech-debt, accessibility, bug, risk
summary: Initial comprehensive scan of primary source files identifying style violations, tech debt, bugs, and improvement opportunities across room-layout-editor.html, room-wizard-workbench-shell.css, tools/2d-sprite-and-animation/index.html, and tools/2d-sprite-and-animation/app/product-shell.css
---

# Initial Codebase Scan — MV Toolchain

**Date:** 2026-04-01
**Files scanned:** 4 primary source files
**Total lines:** ~16,419 (room-layout-editor.html: 9,607 · room-wizard-workbench-shell.css: 1,374 · sprite-workbench/index.html: 4,780 · product-shell.css: 658)

---

## Executive Summary

The MV toolchain codebase is well-structured and largely adheres to the design system, with no third-party dependencies and consistent use of CSS custom properties across the core palette. However, the initial scan found a meaningful set of issues concentrated in three areas: (1) the Sprite Workbench defines `--radius-sm`, `--radius-md`, and `--radius-lg` with values that conflict with the canonical AGENTS.md scale, creating a token drift risk between tools; (2) `product-shell.css` references `--text-dim`, a CSS variable that is not defined anywhere, causing a silent render failure for `.marketing-docs-linkout` text; and (3) `room-layout-editor.html` has no global `:focus-visible` style and injects unescaped user-controlled room IDs and names into `innerHTML`, representing the most significant accessibility gap and the clearest security-class risk in the codebase. Non-critical style violations (rem-based font sizes, off-grid gaps, hardcoded hex color tints) are widespread in both CSS files but are low-severity.

---

## P1 Issues (Critical / Blocking)

**1. Undefined CSS variable `--text-dim` causes silent render failure**
- **File:** `tools/2d-sprite-and-animation/app/product-shell.css`, line 585
- **Category:** Bug
- **Description:** `.marketing-docs-linkout` sets `color: var(--text-dim)`. This variable is not defined in `tools/2d-sprite-and-animation/index.html`'s `:root` block or anywhere else in the project. When `--text-dim` is unresolved, the browser falls back to the inherited color (usually `var(--text)` / `#cce8e0`), but this is an invisible failure — the intended faint/dim appearance is lost silently. The intent appears to be a lighter variant of `--text` (similar to `--text-faint: rgba(204,232,224,0.25)`). Fix: define `--text-dim` in the sprite workbench `:root`, or replace the reference with `var(--text-faint)` or `var(--muted)`.

**2. Unescaped user data in `innerHTML` — XSS risk**
- **File:** `room-layout-editor.html`, lines 4513–4515, 4537, 4543
- **Category:** Risk
- **Description:** Several `innerHTML` assignments interpolate `room.id`, `entry.id`, `entry.name`, `existingLink.targetRoomId`, and `sourceLabel`/`targetLabel` from `state.data.rooms` (parsed JSON from disk/server) without HTML-escaping. Examples: `<strong>${room.id}</strong>`, `<option value="${entry.id}">${entry.id} - ${entry.name}</option>`. The codebase already defines and uses `escapeHtml()` elsewhere (lines 3032, 3252–3280) — these specific callsites were missed. While this is a local tool with no external attack surface today, a malformed project file (e.g., a room with id `<script>alert(1)</script>`) would execute in the browser. Fix: wrap all data-derived interpolations with `escapeHtml()`.

**3. No global `:focus-visible` style in `room-layout-editor.html`**
- **File:** `room-layout-editor.html`
- **Category:** Accessibility
- **Description:** The room editor has no global `:focus-visible` rule. The CLAUDE.md new-page checklist mandates `:focus-visible { outline: 2px solid rgba(0,232,200,0.35); outline-offset: 2px; }`. The sprite workbench (`index.html`) defines it at line ~323, and `room-wizard-workbench-shell.css` defines it on specific interactive components (`.workflow-scope-chip`, `.phase-pill`, `.rw-env-tab`), but the room editor's native controls (buttons, inputs, selects) have no keyboard focus ring at all in the base HTML. This makes keyboard navigation invisible for the canvas toolbar, sidebar buttons, and all form controls.

---

## P2 Issues (Should Fix)

**1. Sprite Workbench radius tokens conflict with canonical scale**
- **File:** `tools/2d-sprite-and-animation/index.html`, lines 44–47
- **Category:** Style Violation / Tech Debt
- **Description:** The sprite workbench `:root` defines `--radius-sm: 14px`, `--radius-md: 18px` — but the canonical AGENTS.md scale defines `--radius-sm: 8px` (small elements) and `--radius-md: 10px` (compact buttons). The room editor uses the correct values (8px, 10px). This creates a divergence where any shared component using `var(--radius-sm)` will render at 14px in the workbench and 8px in the room editor. Fix: align sprite workbench `:root` to the canonical scale, and use `var(--radius-tight)` (14px) where 14px radius is intended.

**2. Widespread rem-based font sizes outside the defined px scale**
- **Files:** `room-wizard-workbench-shell.css` (lines 53, 520, 533, 556, 568) · `tools/2d-sprite-and-animation/app/product-shell.css` (lines 191, 214, 258, 302, 312, 333, 366, 376, 414, 421, 462, 550, 586, 611)
- **Category:** Style Violation
- **Description:** Both CSS files make heavy use of rem units for font sizes (e.g., `0.76rem`, `0.98rem`, `1.08rem`, `1.25rem`). The defined scale is px-based: 11px, 13px, 14px, 15px, 18px, 22px. Rem values are ambiguous relative to the root font size and make font-size semantics harder to audit. The marketing sections in `product-shell.css` are the primary offenders, using `0.76rem`, `0.88rem`, `0.92rem`, `0.95rem`, `1.08rem`, `1.18rem` — none of which map cleanly to the defined scale. Fix: convert to `var(--font-size-*)` tokens; use `--font-size-xs: 11px` in place of `0.76rem` etc.

**3. Hardcoded hex color tints throughout `product-shell.css`**
- **File:** `tools/2d-sprite-and-animation/app/product-shell.css`, lines 190, 250, 301, 365, 553, 580, 609
- **Category:** Style Violation
- **Description:** The marketing sections use hardcoded hex tints for text: `#cae8df`, `#151108`, `#cce3db`, `#c7ddd6`, `#c5dbd4`, `#caf8f1`, `#d7e8e2`. These are variants of `var(--text)` (`#cce8e0`) at different opacities or slight hue shifts. Additionally `room-layout-editor.html` line 446 uses `color: #16120a` (dark brown for gold button text) and line 601 uses `background: #081018` (canvas dark fill) as hardcoded values. Fix: replace with the nearest design token (`var(--text)`, `var(--text-faint)`) or an `rgba()` of the token; the gold button text color should be extracted as a semantic token.

**4. Non-conforming transition durations**
- **Files:** `room-wizard-workbench-shell.css` (lines 360, 406) · `tools/2d-sprite-and-animation/app/product-shell.css` (line 238)
- **Category:** Style Violation
- **Description:** Three locations use non-standard transition timings:
  - `room-wizard-workbench-shell.css` line 360: `transition: border-color 0.15s, box-shadow 0.15s, background 0.15s, opacity 0.15s` — should use `var(--transition-fast)` (120ms)
  - `room-wizard-workbench-shell.css` line 406: `transition: background 0.15s, border-color 0.15s, color 0.15s` — same issue
  - `product-shell.css` line 238: `transition: 160ms ease` — uses no property list (effectively `transition: all`) and uses 160ms (not 120ms or 200ms). Fix: replace with `transition: background var(--transition-fast), border-color var(--transition-fast)` etc.

**5. `border-radius: 50%` on `.phase-number` icon circle**
- **File:** `room-wizard-workbench-shell.css`, line 400
- **Category:** Style Violation
- **Description:** `.phase-number` uses `border-radius: 50%` to create a circle. Per AGENTS.md, `border-radius: 50%` on panels is forbidden; the correct approach for circular elements is `var(--radius-full)` (999px), which is already defined in the token set and achieves the same visual result. This is a minor but explicit anti-pattern.

**6. Off-grid spacing values — multiple locations**
- **Files:** `room-wizard-workbench-shell.css` · `tools/2d-sprite-and-animation/app/product-shell.css` · `room-layout-editor.html`
- **Category:** Style Violation
- **Description:** Several gap and margin values are not on the 4px grid:
  - `room-wizard-workbench-shell.css` line 71: `gap: 10px` (→ 8px or 12px)
  - `room-wizard-workbench-shell.css` lines 507, 529: `gap: 14px` (→ 12px or 16px)
  - `room-wizard-workbench-shell.css` line 643: `gap: 5px` (→ 4px or 8px)
  - `product-shell.css` lines 296, 433: `gap: 22px`, `gap: 26px` (→ 24px or 32px)
  - `room-layout-editor.html` line 378: `gap: 10px` (the `.stack` utility class; → 8px or 12px)
  - Note: `gap: 10px` in buttons and `padding: 6px 10px` are established exceptions per AGENTS.md — those should not be changed.

**7. `product-shell.css` uses `var(--shadow)` without ensuring it's defined**
- **File:** `tools/2d-sprite-and-animation/app/product-shell.css`, line 527
- **Category:** Tech Debt / Risk
- **Description:** `.marketing-docs-hero`, `.marketing-docs-nav`, `.marketing-docs-card` use `box-shadow: var(--shadow)`. The sprite workbench `:root` defines `--shadow: 0 12px 40px rgba(0,0,0,0.38)` (line 75), so this works currently. However `--shadow` is not in the canonical AGENTS.md token set (only `--shadow-sm`, `--shadow-md`, `--shadow-lg` are canonical). This is an undocumented alias that could become undefined if the token block is regenerated from the canonical set. Fix: replace `var(--shadow)` with `var(--shadow-lg)`.

**8. Font sizes outside scale in `room-layout-editor.html`**
- **File:** `room-layout-editor.html`, lines 781, 788, 912, 968, 984, 1486, 1669, 1679
- **Category:** Style Violation
- **Description:** Several components in the room editor use `font-size: 10px` (badge labels, canvas readouts) and `font-size: 24px` (badge values). 10px is below the defined minimum (`--font-size-xs: 11px`) and may cause readability issues. 24px falls between `--font-size-lg: 18px` and `--font-size-xl: 22px` and is not in the scale. Fix: replace `10px` with `var(--font-size-xs)` (11px) and `24px` with `var(--font-size-xl)` (22px).

**9. `border-radius: 16px` not in defined radius scale**
- **File:** `room-layout-editor.html`, lines 775, 806, 930
- **Category:** Style Violation
- **Description:** Three locations use `border-radius: 16px`, which is not in the canonical radius scale (4, 8, 10, 12, 14, 18, 20, 999px). The closest values are `var(--radius-tight): 14px` or `var(--radius-card): 18px`. Fix: replace with nearest semantic radius token.

**10. `room-layout-editor.html` is a 9,607-line monolith**
- **File:** `room-layout-editor.html`
- **Category:** Tech Debt
- **Description:** The room editor puts ~7,500 lines of JavaScript inline in the HTML file, making it extremely difficult to navigate, test, or refactor. The file contains 1,440 function/variable declarations. There is no module structure. All editor state, rendering, API calls, and UI event handling live in a single `<script>` block. This is the largest maintainability risk in the codebase. Fix: extract JS to one or more `.js` files (does not require a build step — plain `<script src="...">` works fine).

---

## Opportunities

**1. Extract shared CSS token block into a shared include**
- **File:** `room-layout-editor.html`, `tools/2d-sprite-and-animation/index.html`, `research-dashboard.html`
- **Rationale:** All three HTML files define near-identical `:root` CSS variable blocks (~30–40 lines each). Any future token change must be replicated manually in each file. A shared `tokens.css` (or injected via JS) would eliminate drift and reduce maintenance surface.
- **Estimated impact:** High (future-proofs all new tool pages; prevents the radius-token drift issue from recurring)

**2. Create shared `nav.css` or nav partial**
- **File:** `room-layout-editor.html` (lines 98–157), `tools/2d-sprite-and-animation/app/product-shell.css` (lines 1–123)
- **Rationale:** Both tools define a `.site-nav` component with nearly identical structure and styling. The room editor defines it inline in `<style>`, while the sprite workbench defines it in its CSS file. This is duplicated code that will diverge over time. Extracting to a shared `shared-nav.css` would unify the two tools' navigation chrome.
- **Estimated impact:** Medium (reduces duplication; ensures nav changes apply everywhere)

**3. Align product-shell.css marketing section to design system tokens**
- **File:** `tools/2d-sprite-and-animation/app/product-shell.css`, lines 183–660
- **Rationale:** The marketing section of the sprite workbench uses ~15 hardcoded hex colors and ~12 rem-based font sizes. Converting these to design tokens would make the marketing surface consistent with the tool UI and easier to theme or iterate on.
- **Estimated impact:** Medium (design consistency; smaller maintenance burden)

**4. Extract JavaScript from room-layout-editor.html into external file(s)**
- **File:** `room-layout-editor.html`
- **Rationale:** With ~7,500 lines of inline JS, the room editor is difficult to navigate and audit. Extracting to an external `.js` file would enable proper code search, makes the XSS issues more findable in code review, and sets the foundation for eventual modularization.
- **Estimated impact:** High (maintainability; reviewability; security auditability)

**5. Add global `:focus-visible` rule to `room-layout-editor.html`**
- **File:** `room-layout-editor.html`
- **Rationale:** A single global rule restores keyboard-accessible focus indicators for all interactive elements. The pattern is already established in `research-dashboard.html` and `tools/2d-sprite-and-animation/index.html`.
- **Estimated impact:** High (accessibility compliance, keyboard usability)

**6. Standardise radius tokens in sprite workbench**
- **File:** `tools/2d-sprite-and-animation/index.html`, lines 44–47
- **Rationale:** Aligning `--radius-sm` and `--radius-md` to the canonical scale eliminates the inter-tool divergence. Low risk change as the marketing surface is the only area currently using these tokens in the sprite workbench CSS.
- **Estimated impact:** Medium (design system integrity)

---

## Standard Output Footer

- **Recommendation:** Fix P1 issues immediately in priority order: (1) define `--text-dim` in sprite workbench `:root`; (2) wrap unescaped `room.id`, `entry.id`, `entry.name`, `existingLink.targetRoomId` with `escapeHtml()` at lines 4513–4515, 4537, 4543; (3) add global `:focus-visible` rule to `room-layout-editor.html`. P2 style violations can be addressed as a focused CSS cleanup pass. The monolith refactor (P2.10) is a longer-term initiative requiring founder prioritisation.
- **Risks:** The XSS issue (P1.2) is low-exploitability in a local-only tool but represents a code hygiene failure that could escalate if the tool ever accepts untrusted project files from a network source. The undefined `--text-dim` (P1.1) is an invisible silent failure — it may have been present for a long time unnoticed. The radius token drift (P2.1) could cause visual regressions if shared components are ever moved between tools.
- **Confidence:** High — all findings are based on direct reading of the source files and validated against AGENTS.md and STYLE_GUIDE.md. No speculative or hypothetical issues included.
- **Founder approval needed:** No — P1 fixes are straightforward code corrections with no design impact. P2 style cleanup and the JS extraction (P2.10) should be reviewed as a batch before execution.
- **Next actions:**
  - [Research Agent] Update dashboard.md and INDEX.md with these findings (this session)
  - [Research Agent] Populate research-dashboard.html with RESEARCH_DATA (this session)
  - [Coding Agent] Fix P1.1: define `--text-dim` in sprite workbench index.html `:root`
  - [Coding Agent] Fix P1.2: wrap innerHTML interpolations in `escapeHtml()` at lines 4513–4515, 4537, 4543 in room-layout-editor.html
  - [Coding Agent] Fix P1.3: add `:focus-visible` global rule to room-layout-editor.html
  - [Founder] Decide prioritisation of P2 cleanup pass and JS extraction initiative
