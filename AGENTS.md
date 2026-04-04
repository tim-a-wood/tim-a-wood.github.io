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

## Research Library — Mandatory Check Protocol

The **Research Agent** maintains a knowledge library at `/research/library/`. This library contains codebase scan findings, technical assessments, competitive analysis, and synthesized reports.

**Directive for all agents:** Before starting any complex task (architecture changes, refactoring, new features, debugging non-trivial issues), you MUST:

1. **Check the library index** — `grep` or read `/research/library/INDEX.md` for relevant entries
2. **Read matching documents** — if a finding or report covers your topic, read it before proceeding
3. **Check the dashboard** — `/research/dashboard.md` shows current open issues and opportunities; don't duplicate known work
4. **Check decisions** — `/decisions/` logs resolved choices; do not re-litigate

Why this matters: The Research Agent discovers patterns, violations, and opportunities across the full codebase that individual task agents may miss. Reading prior findings prevents duplicate work, avoids re-introducing known issues, and ensures you have the complete picture before proposing changes.

If you discover something significant that is NOT in the library, note it in your output so the Research Agent can log it.

**Research Dashboard:** Open `research-dashboard.html` in a browser for a visual overview.
**Agent definition:** `.claude/agents/research.md` — invoke the Research Agent for scans and reports.

## My Actions dashboard — check after completing every request

The Agent OS **My Actions** view (`os-dashboard.html`, nav **My Actions** — the founder-facing task board, sometimes called *My Tasks*) aggregates, across all agent `*-status.json` files:

- `founder_decisions` (blocking and non-blocking items for the founder)
- `priorities` rows with `"status": "needs-review"`

**Directive for all agents (orchestrator and every specialist):** When you **finish** a request, session, or owned handoff, **review** **your** agent’s `*-status.json` (only the file for your role — e.g. `design-status.json` for Design). You **may add, edit, or remove** any **My Actions**–sourced rows **you own** in that file (`founder_decisions`, and `priorities` with `needs-review`) whenever the founder board should show new work, resolved work, or corrected copy — including **removing** a card that is obsolete or **adding** one the founder must see. Do **not** add, remove, or rewrite founder-facing rows in **another** agent’s `*-status.json` unless the founder explicitly asked for that cross-file edit. If nothing founder-facing changed for your agent, **no file change is required** — the obligation is to **check**, not to churn the JSON.

Follow `agents/design/dashboard-standard.md` when editing dashboards. Prefer running `python3 scripts/validate_status_files.py` on files you touch when the repo provides it.

This is additive to any per-agent **task-completion** or priority-hygiene rules in individual charters (e.g. orchestration `orchestration-status.json`, Design `design-status.json`).

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

## In-game pixel art (production gate)

For **game-facing sprites and raster art** during development, **[`docs/pixel-art-quality-standards.md`](docs/pixel-art-quality-standards.md)** is mandatory **alongside** the Ashen Hollow art bible ([`artifacts/ashen-hollow-art-bible-v0.2.md`](artifacts/ashen-hollow-art-bible-v0.2.md)). Standing directives in the **Animation**, **Creative**, **Level Design**, **Game Director**, **Engineering**, and **Orchestrator** charters require agents to read, apply, route, or implement against that gate as their role demands.

## Visual Validation Honesty Gate

For any task where the result is primarily judged by an image, screenshot, mockup, rendered artifact, or other visual output, agents must not claim improvement, success, readability, quality, or “better” results unless they have personally inspected the exact saved artifact being referenced.

Required proof before making a positive visual claim:
- Open the exact saved image artifact that will be cited.
- State that it was visually inspected.
- Include at least 3 concrete visible observations from that image, not abstract summaries.
- If the image is bad, say so plainly even if tests passed or one narrow sub-fix succeeded.

Forbidden behavior:
- Do not substitute code/tests/metrics for visual validation when the user is asking about how the image looks.
- Do not describe a visual result positively based only on a local subcomponent fix.
- Do not use placeholder, mock, fallback, or recovered artifacts as evidence without labeling them clearly.

If visual validation was not performed, the agent must explicitly say that it has not yet visually validated the artifact.

---

# MV / Sprite Workbench — Agent Rules (Codex / OpenAI)

This file configures AI coding agents (OpenAI Codex CLI, GitHub Copilot Workspace, and compatible tools) working in this repository.

---

## Project Overview

Browser-based game development toolchain for a metroidvania-style game. Hand-crafted HTML/CSS/JS — no framework, no bundler, no Tailwind. Tools include a sprite workbench, room layout editor, and world builder.

**The canonical design system is [`STYLE_GUIDE.md`](STYLE_GUIDE.md).** Read it before any frontend work.

### UI work: approved mockup first (align with Design)

The **Design** charter requires a **high-fidelity mockup before implementation** for UI and front-end component work (`agents/design/charter.md`, **Owns** and **Standing Directives**). As a coding agent:

- Implement **from an approved HI-FI mockup** (e.g. `docs/mockups/…` or a founder-specified reference) with **no visual drift** — no redesign mid-implementation.
- If the request is **non-trivial UI** and **no approved mockup** is provided, **pause** and ask for Design to supply one (or an explicit founder waiver). Do not invent a full layout and treat it as final without that step.
- **Trivial** edits (text, bugfixes, token compliance, non-layout JS) do not need a new mockup unless layout or composition changes.

### My Actions (founder task board) after coding tasks

If you edit **an** agent `*-status.json`, when you finish **review** **My Actions** (`os-dashboard.html`) for that file: you **may add, remove, or edit** founder-facing rows **owned by that file’s agent** when needed — see **My Actions dashboard — check after completing every request** **above the divider** in this file.

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
