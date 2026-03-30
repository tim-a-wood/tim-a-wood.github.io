# Design agent handoff — Agent OS Home hub

## Status (2026-03-29)

Polish pass **implemented in repo** (`os-dashboard.html`): staggered entrance (`.os-dash-enter`), `prefers-reduced-motion` fallbacks, token-based hub glyph, chart `role="img"` + `aria-labelledby` / `aria-describedby`, skeleton + error layers (`setAgentOsChartCanvasState('loading'|'error'|'idle')` on `window`), donut reflow when canvas width &lt; 440px, taller donut card under 900px breakpoint.

**Remaining for Design:** STYLE_GUIDE.md cross-links if new patterns become canonical elsewhere; optional illustration assets; audit with real ledger data when available.

---

## Paste to Design agent (invocation)

```
You are the Design agent for the MV metroidvania toolchain (browser tools, no build step).

Read first:
- agents/design/charter.md
- STYLE_GUIDE.md (tokens are law)
- agents/design/os_home_dashboard_handoff.md (this file — deliver against “Flagship polish”)

Context: Agent OS lives in os-dashboard.html. A new default “Home” hub and Engineering “AI pipeline signal” section use canvas charts + existing CSS variables. Data are placeholders until Analytics/Engineering wire a ledger.

Your job: Ship flagship-grade polish for Home as the long-term OS landing surface — motion, responsive density, empty/loading/error states, and A11y for chart regions — without novel hex, off-grid spacing, forbidden radii, or transition:all. Coordinate token additions through STYLE_GUIDE.md if you need new semantics.

Deliverables: Concrete CSS/HTML/JS edits in os-dashboard.html (and STYLE_GUIDE.md only if tokens change), brief note in your reply on what changed and what to verify in browser.

End with: Recommendation / Risks / Confidence / Founder approval needed / Next actions.
```

---

**Context:** `os-dashboard.html` now includes a **Home** dashboard (default landing) and matching **AI pipeline signal** charts on **Engineering**. Charts are canvas-based, Sprite Workbench tokens only (no novel hex in chart CSS).

**Key selectors / areas:** `.os-home-hero`, `.os-home-kpi`, `.os-chart-grid`, `.os-chart-card`, `.os-chart-canvas-wrap`, canvas `[data-os-chart]`, `[data-os-mini-spark]`, Engineering block `#eng-os-chart-grid`.

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
