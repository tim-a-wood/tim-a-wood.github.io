# Research Dashboard

> **Agent-readable dashboard.** Updated by the Research Agent after every scan, report, or library addition.
> Visual dashboard: open `research-dashboard.html` in a browser.

---

## Status

| Field | Value |
|-------|-------|
| Last scan | 2026-04-01 |
| Library documents | 2 |
| Open P1 issues | 3 |
| Open P2 issues | 10 |
| Open opportunities | 6 |
| Last updated | 2026-04-01 |

---

## Active Issues — P1 (Critical)

1. **Undefined CSS variable `--text-dim`** — `tools/2d-sprite-and-animation/app/product-shell.css` line 585
   - Bug: `.marketing-docs-linkout` references `var(--text-dim)` which is not defined anywhere, causing silent render failure (text shows inherited color instead of intended faint/dim appearance)

2. **Unescaped user data in `innerHTML`** — `room-layout-editor.html` lines 4513–4515, 4537, 4543
   - Risk: `room.id`, `entry.id`, `entry.name`, `existingLink.targetRoomId` inserted into innerHTML without `escapeHtml()` — XSS via malformed project file. `escapeHtml()` is already defined at line 3032 and used elsewhere.

3. **No global `:focus-visible` style** — `room-layout-editor.html`
   - Accessibility: No `:focus-visible` rule in the room editor, making keyboard navigation invisible for all native controls (buttons, inputs, selects). Mandatory per CLAUDE.md new-page checklist.

---

## Active Issues — P2 (Should Fix)

1. **Sprite Workbench radius tokens conflict with canonical scale** — `tools/2d-sprite-and-animation/index.html` lines 44–47
   - `--radius-sm: 14px`, `--radius-md: 18px` — should be 8px and 10px per AGENTS.md

2. **Widespread rem-based font sizes outside px scale** — `room-wizard-workbench-shell.css` (×5), `product-shell.css` (×14)
   - Style violation: rem units used where `var(--font-size-*)` tokens should be used

3. **Hardcoded hex color tints** — `product-shell.css` (×7), `room-layout-editor.html` (×2)
   - Style violation: `#cae8df`, `#151108`, `#cce3db`, `#c7ddd6`, `#c5dbd4`, `#caf8f1`, `#d7e8e2`, `#16120a`, `#081018` — should use CSS variables or `rgba()` of tokens

4. **Non-conforming transition durations** — `room-wizard-workbench-shell.css` lines 360, 406 · `product-shell.css` line 238
   - Style violation: `0.15s` and `160ms ease` (no property list) should be `var(--transition-fast)` with explicit properties

5. **`border-radius: 50%` on phase-number circle** — `room-wizard-workbench-shell.css` line 400
   - Style violation: use `var(--radius-full)` (999px) instead

6. **Off-grid spacing values** — `room-wizard-workbench-shell.css` (×4), `product-shell.css` (×2), `room-layout-editor.html` (×1)
   - Style violation: `gap: 10px`, `gap: 14px`, `gap: 5px`, `gap: 22px`, `gap: 26px` are not on 4px grid

7. **`var(--shadow)` used but not in canonical token set** — `product-shell.css` line 527
   - Tech debt: undocumented alias; replace with `var(--shadow-lg)` from canonical set

8. **Font sizes outside scale in room-layout-editor** — `room-layout-editor.html` lines 781, 788, 912 (×5 more)
   - Style violation: `font-size: 10px` (below `--font-size-xs: 11px`) and `font-size: 24px` (not in scale)

9. **`border-radius: 16px` not in radius scale** — `room-layout-editor.html` lines 775, 806, 930
   - Style violation: use `var(--radius-tight)` (14px) or `var(--radius-card)` (18px)

10. **`room-layout-editor.html` is a 9,607-line monolith** — `room-layout-editor.html`
    - Tech debt: ~7,500 lines of inline JS; 1,440 function/variable declarations in a single `<script>` block; no module structure

---

## Open Opportunities

1. **Extract shared CSS token block** into `tokens.css` — eliminates manual sync across 3+ HTML files (High impact)
2. **Create shared `nav.css`** — `.site-nav` is duplicated between room editor and sprite workbench (Medium impact)
3. **Align product-shell.css marketing section** to design system tokens — ~15 hardcoded colors, ~12 rem sizes (Medium impact)
4. **Extract JS from room-layout-editor.html** to external `.js` file(s) — maintainability and security auditability (High impact)
5. **Add global `:focus-visible` to room-layout-editor.html** — single rule, high a11y gain (High impact, trivial effort)
6. **Standardise sprite workbench radius tokens** — align to canonical scale (Medium impact, low risk)

---

## Recent Reports

| Date | Title | File | Type |
|------|-------|------|------|
| 2026-04-01 | Initial Codebase Scan — MV Toolchain | [findings/codebase-scan-2026-04-01.md](library/findings/codebase-scan-2026-04-01.md) | finding |
| 2026-04-01 | Passive income market scan | [findings/passive-income-market-scan-2026-04-01.md](library/findings/passive-income-market-scan-2026-04-01.md) | market |

---

## Library Quick Links

- [Master Index](library/INDEX.md)
- [Findings →](library/findings/)
- [Technical →](library/technical/)
- [Competitive →](library/competitive/)
- [Reports →](library/reports/)

---

*Last updated: 2026-04-01 by Research Agent (passive income market scan + library index update)*
