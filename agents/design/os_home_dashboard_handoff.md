# Design agent handoff — Agent OS Home hub

**Context:** `os-dashboard.html` now includes a **Home** dashboard (default landing) and matching **AI pipeline signal** charts on **Engineering**. Charts are canvas-based, Sprite Workbench tokens only (no novel hex in chart CSS).

## Flagship polish (your queue)

1. **Motion** — Staggered entrance for `.os-home-hero` and `.os-chart-card` (120–200ms, `ease` only; no `transition: all`). Consider one subtle shimmer on first paint only if it stays on-brand.
2. **Density** — Review breakpoints: donut legend vs. narrow two-column grid; optional collapse to single column with legend below ring.
3. **Data states** — Empty / error / loading skeletons when the internal ledger JSON replaces `OS_CHART_PLACEHOLDER` in JS (spinner or muted “waiting for supervisor” strip).
4. **Accessibility** — Ensure each chart has a visible title + summary in prose; add `role="img"` + `aria-labelledby` on canvas wrappers when real data ships.
5. **Brand cohesion** — Audit emoji vs. display type: Home header uses ◆; align with DESIGN charter if a custom glyph system emerges.

## Non-goals

- Do not replace tokens with arbitrary palettes; extend `:root` only via `STYLE_GUIDE.md` patterns.
- Do not add npm chart libraries unless Engineering approves a build step (current policy: none).

## Collaboration

- **Analytics charter** — Owns metric definitions when charts bind to real events.
- **Engineering** — Owns API shape for `/api/dashboard-data` extensions (e.g. `ai_usage_series`).

When this brief is satisfied, remove or shrink this file and record the outcome in `design-status.json` if you maintain one.
