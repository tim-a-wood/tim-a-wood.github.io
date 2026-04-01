# AI-Native Business Operating System
## Metroidvania Toolchain — Founder OS

This file serves dual purpose:
1. **OS operating instructions** — authority model, orchestrator rules, specialist role model (read this first)
2. **Coding agent rules** — design system and code conventions for AI coding tools (below the divider)

---

## Authority Model

**Founder:** Final decision-maker. All major product, legal, financial, pricing, security, and release decisions require founder approval before execution.

**Orchestrator:** Coordinates specialist agents, routes work, synthesizes outputs into founder-facing memos. Does not replace specialist expertise. Does not make major decisions.

**Specialists:** Domain experts in their area. Advise, analyze, draft, recommend. Do not own decisions. Must escalate when thresholds are hit.

**Escalation triggers (any specialist must escalate):**
- Legal risk identified
- Security vulnerability found
- Revenue impact > $500
- External commitments being made
- Irreversible actions proposed

## Standard Output Format

Every substantive agent output must end with:
- **Recommendation:** [what to do]
- **Risks:** [what could go wrong]
- **Confidence:** [High / Medium / Low + why]
- **Founder approval needed:** [Yes/No — and what specifically]
- **Next actions:** [concrete steps with owner]

## Orchestrator Modes

When invoking the orchestrator, specify a mode:
- `brainstorm` — multi-specialist ideation session
- `decision` — structured analysis with recommendation
- `red-team` — adversarial review of a plan or asset
- `launch` — release readiness check across all specialists
- `incident` — emergency coordination
- `weekly-review` — founder digest compilation

## Shared Knowledge

All agents read from `/knowledge/` before operating in their domain.
Playbooks live in `/playbooks/`. Templates in `/templates/`.
Decisions are logged in `/decisions/`. Research in `/research/`.

## Feature Decision Tracking

For active multi-pass features, agents must keep a running decision log so the team does not repeatedly revisit rejected approaches.

Current required log:
- Room environment / bespoke asset quality pass: `/decisions/2026-03-31-room-environment-quality-pass.md`

Directive for all agents:
- Before proposing or implementing another major change for an active multi-pass feature, read its current decision log.
- After any substantive decision, failed approach, accepted constraint, validator change, or quality-gate change, update the same log in-place.
- Log both what was chosen and what was explicitly rejected, with enough context to prevent future agents from retrying the same path blindly.
- Treat the decision log as part of the feature contract, not optional notes.
- If no log exists for an active multi-pass feature, create one in `/decisions/` using the repository naming convention before continuing substantial work.

---

# MV / Sprite Workbench — Agent Rules (Codex / OpenAI)

This file configures AI coding agents (OpenAI Codex CLI, GitHub Copilot Workspace, and compatible tools) working in this repository.

---

## Project Overview

Browser-based game development toolchain for a metroidvania-style game. Hand-crafted HTML/CSS/JS — no framework, no bundler, no Tailwind. Tools include a sprite workbench, room layout editor, and world builder.

**The canonical design system is [`STYLE_GUIDE.md`](STYLE_GUIDE.md).** Read it before any frontend work.

---

## Mandatory Design System Rules

### Colors — Use CSS Variables Only

This project has a strict token-based color system. **Never hardcode hex values.** Always use the CSS custom properties:

```
Background:  var(--bg)          /* #050709 */
Panel:       var(--panel)       /* rgba(4,6,10,0.96) */
Accent:      var(--accent)      /* #00e8c8 — cyan, active/selected only */
Text:        var(--text)        /* #cce8e0 */
Muted:       var(--muted)       /* #5d7870 */
Border:      var(--line)        /* rgba(0,232,200,0.10) */
Good:        var(--good)        /* #4ade80 */
Warning:     var(--warning)     /* #d29922 */
Error:       var(--error)       /* #f85149 */
```

### Spacing — 4px Grid

Every spacing value (padding, margin, gap) must be a multiple of 4px:
`4, 8, 12, 16, 24, 32, 48, 64`

Button padding `10px` is the only established exception (vertical only).

### Border Radius — Fixed Scale

```
4px   tool indicators
8px   small elements
10px  compact buttons
12px  toolbar buttons
14px  standard buttons, inputs, chips  ← most common
18px  panels, cards
20px  workflow pills, major panels
999px full-round pills and badges
```

### Typography — Required Fonts

New pages must load:
- **Bebas Neue** — panel titles, dialog headers (font-weight: 400, letter-spacing: 0.04em+)
- **Plus Jakarta Sans** — all UI text (weights: 400, 500, 600, 700, 800)
- **DM Mono** — code, numbers, coordinate readouts

Font size scale: `11px, 13px, 14px, 15px, 18px, 22px` only.

### Transitions

- Duration: `120ms` (fast) or `200ms` (standard)
- Easing: `ease` or `ease-out` only — no spring curves
- Always specify properties explicitly: `transition: background 200ms ease, border-color 200ms ease`
- Never use `transition: all`
- Hover lift: `transform: translateY(-1px)` maximum

### Dark Theme Only

This product has no light mode. All backgrounds are near-black (`#050709` and variants). Floating panels use `rgba` backgrounds with `backdrop-filter: blur()`. Never use white or light-colored backgrounds.

---

## Code Style

- **HTML:** Semantic elements (`<button>`, `<nav>`, `<section>`, `<header>`, `<aside>`). No `<div>` soup.
- **CSS:** CSS custom properties for all design tokens. No inline styles except JS-driven dynamic values.
- **JS:** Vanilla JS. No jQuery, no framework imports, no npm packages in tool pages.
- **Accessibility:** All interactive elements need `min-height: 44px` (standard) or `28px` (compact). Always add `:focus-visible` styles.

## New Page Bootstrap

When creating a new tool page, always start with this token block in `:root`:

```css
:root {
  --bg: #050709; --panel: rgba(4,6,10,0.96); --panel-2: #07090c; --panel-soft: #07090c;
  --accent: #00e8c8; --accent-soft: rgba(0,232,200,0.08);
  --text: #cce8e0; --muted: #5d7870;
  --stroke: rgba(0,232,200,0.07); --stroke-strong: rgba(0,232,200,0.14);
  --line: rgba(0,232,200,0.10); --line-strong: rgba(0,232,200,0.18);
  --border: rgba(0,232,200,0.07); --border-strong: rgba(0,232,200,0.14);
  --good: #4ade80; --good-soft: rgba(74,222,128,0.12);
  --warning: #d29922; --warning-soft: rgba(210,153,34,0.16);
  --error: #f85149; --error-soft: rgba(248,81,73,0.16);
  --font-sans: "Plus Jakarta Sans", -apple-system, sans-serif;
  --font-display: "Bebas Neue", sans-serif;
  --font-mono: "DM Mono", ui-monospace, monospace;
  --font-size-xs: 11px; --font-size-sm: 13px; --font-size-base: 14px;
  --font-size-md: 15px; --font-size-lg: 18px; --font-size-xl: 22px;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px;
  --surface-gap: 12px; --surface-pad: 14px;
  --radius-xs: 4px; --radius-sm: 8px; --radius-md: 10px; --radius-default: 12px;
  --radius-tight: 14px; --radius-card: 18px; --radius-lg: 20px; --radius-full: 999px;
  --shadow-sm: 0 2px 8px rgba(0,0,0,0.18);
  --shadow-md: 0 6px 20px rgba(0,0,0,0.26);
  --shadow-lg: 0 12px 40px rgba(0,0,0,0.38);
  --transition-fast: 120ms ease; --transition-base: 200ms ease;
}
```

---

## Forbidden Patterns

The following will be rejected in code review:

| Pattern | Reason |
|---|---|
| Hardcoded hex colors | Use CSS variables |
| `color: white` or `#fff` | Use `var(--text)` |
| `background: black` | Use `var(--bg)` |
| Any light/white backgrounds in tool UI | Dark theme only |
| `font-family: Inter` or `Roboto` | Use `var(--font-sans)` |
| `font-size: 16px` | Not in scale; use `14px` or `18px` |
| `border-radius: 6px` or `16px` | Not in radius scale |
| `gap: 5px`, `padding: 7px` etc. | Must be 4px grid multiple |
| `transition: all` | Always specify properties |
| `transition: 0.5s` | Max 200ms for UI |
| `transform: translateY(-3px)` hover | Max `-1px` |
| `font-weight: 900` | Max 800 |
| Colored box shadows | Black-only shadows only |
| Spring/bounce easing | Use `ease` or `ease-out` |
| jQuery or framework imports | Vanilla JS only |
| `float` for layout | Use CSS Grid or Flexbox |

---

## Project File Map

```
STYLE_GUIDE.md                         ← Read this first for any frontend task
CLAUDE.md                              ← Claude Code rules
AGENTS.md                              ← This file (Codex/OpenAI rules)
.cursor/rules/frontend-design.mdc      ← Cursor rules

room-layout-editor.html               ← Room editor tool
room-wizard-workbench-shell.css        ← Room editor CSS

tools/2d-sprite-and-animation/
  index.html                           ← Sprite workbench homepage
  app/product-shell.css                ← Sprite workbench CSS
```

## Domain Vocabulary

- **World** — top-level map containing rooms
- **Room** — discrete area with platforms, entities, geometry
- **Phase pill** — step indicator in workflow wizards
- **Workflow rail** — horizontal strip showing wizard progress steps
- **Segmented control** — the World/Room scope toggle (cyan active state)
- **Inspector** — floating panel that appears on entity selection
- **Entity types:** Platform (#77b8ff), Door (#f5986e), Vertex (#ff6b8a), Key (#4ade80), Ability (#a78bfa), Mover (#fbbf24), Start Point (#f0abfc)
