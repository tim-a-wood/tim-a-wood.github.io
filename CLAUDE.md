# MV / Sprite Workbench — Claude Code Rules

This project is a browser-based game development toolchain (sprite editor, room layout editor, world builder) for a metroidvania-style game. The frontend is hand-crafted HTML/CSS/JS — no build step, no framework.

---

## Style Guide Enforcement

**ALL frontend work MUST conform to [`STYLE_GUIDE.md`](STYLE_GUIDE.md).**

Before writing any HTML, CSS, or frontend JS, read the relevant section of the style guide. The style guide is the canonical design system and was reverse-engineered from production code — it represents actual design decisions, not aspirational guidelines.

### UI work: approved mockup first (Design charter)

The **Design** agent owns **HI-FI mockup before implementation** — see `agents/design/charter.md` (**Owns** and **Standing Directives**). Coding agents must align with that workflow:

- **If an approved high-fidelity mockup exists** (e.g. under `docs/mockups/`, or another path the founder named as the visual source of truth): implement the real UI as a **faithful translation** — same layout, spacing hierarchy, and chrome. **Do not redesign** during implementation; treat token/style-guide fixes as compliance, not a visual refresh.
- **If the task is a non-trivial UI or new front-end component and there is no approved HI-FI mockup:** **stop** and ask the founder to have Design produce one (or to explicitly waive mockup-first for this task). **Do not** skip straight to a self-authored layout and present it as the final design.
- **Trivial changes** (copy, bugfix, single-token swap, wiring only) do not require a new mockup unless they change layout or composition.

---

### Non-negotiables

**Colors:** Use only the CSS variables defined in `STYLE_GUIDE.md § 2`. Never introduce arbitrary hex values. Never use `#fff`, `#000`, or color names like `red`, `blue`. Always use `var(--accent)`, `var(--text)`, `var(--muted)`, etc.

**Typography:** Always load the required fonts (`Bebas Neue`, `Plus Jakarta Sans`, `DM Mono`) in any new page. Use only the `--font-size-*` scale. Headings and panel titles use `var(--font-display)`. Body uses `var(--font-sans)`. Code/numbers use `var(--font-mono)`.

**Spacing:** Every padding, margin, and gap must be a multiple of 4px. Use `--space-*` variables or explicit 4px-grid values. Never use 5px, 7px, 9px, 11px, 13px, 15px.

**Border radius:** Use only the defined radius scale (`--radius-xs` through `--radius-full`). Standard buttons/inputs → `14px`. Panels → `18px–20px`. Full-round pills → `999px`.

**Interactions:** Hover lifts use `translateY(-1px)` only. Transition duration is `120ms` (fast) or `200ms` (base). Always specify transition properties explicitly — never `transition: all`.

**Dark theme only:** This product has no light mode. Backgrounds are always near-black (`#050709` and variants). Floating panels use `rgba` with `backdrop-filter: blur()`.

---

## Project Structure

```
/MV
├── index.html                        # Game canvas (runtime, not a tool)
├── room-layout-editor.html           # Room editor tool
├── room-wizard-workbench-shell.css   # Room editor styles
├── STYLE_GUIDE.md                    # Canonical design system
├── tools/
│   └── 2d-sprite-and-animation/
│       ├── index.html                # Sprite workbench homepage
│       └── app/
│           └── product-shell.css     # Sprite workbench styles
└── assets/                           # Shared static assets
```

## File Conventions

- **No build tooling.** All CSS is authored CSS. No SCSS, no Tailwind, no CSS Modules.
- **CSS variables at `:root`.** All design tokens declared at root level in `<style>` blocks or external `.css` files.
- **Semantic HTML.** Use `<button>`, `<nav>`, `<section>`, `<header>`, `<aside>` correctly.
- **No third-party component libraries.** All UI components are hand-crafted to the design system.
- **`image-rendering: pixelated`** on all canvas elements and sprite preview images.

## New Page Checklist

When creating a new HTML page or tool:

1. Include the CSS token block from `STYLE_GUIDE.md § 13`
2. Load fonts: `Bebas Neue`, `Plus Jakarta Sans`, `DM Mono` from Google Fonts
3. Set `body { background: var(--bg); color: var(--text); font-family: var(--font-sans); }`
4. Add `*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }`
5. Ensure all interactive elements have `min-height: 44px` (standard) or `min-height: 28px` (compact)
6. Add `:focus-visible { outline: 2px solid rgba(0,232,200,0.35); outline-offset: 2px; }` globally

## Anti-Pattern Enforcement

If you catch yourself about to do any of the following, stop and use the correct approach:

| Anti-Pattern | Correct Approach |
|---|---|
| `color: white` or `color: #fff` | `color: var(--text)` |
| `background: black` | `background: var(--bg)` |
| `background: #0ae8c8` (novel cyan) | `background: var(--accent)` |
| `border-radius: 6px` | `border-radius: var(--radius-sm)` (8px) |
| `gap: 10px` (not on 4px grid) | `gap: 8px` or `gap: 12px` |
| `font-size: 16px` | `font-size: var(--font-size-base)` (14px) or `var(--font-size-lg)` (18px) |
| `transition: all 0.3s` | `transition: background 200ms ease, border-color 200ms ease` |
| `font-family: Inter` | `font-family: var(--font-sans)` |
| `box-shadow: 0 4px 12px red` | Never use colored shadows |
| `border-radius: 50%` on a panel | Panels use `--radius-card` (18px) |

## Domain Context

This is a metroidvania game development tool. Key domain concepts:

- **World** — the top-level map containing multiple rooms
- **Room** — a discrete area with platforms, doors, enemies, items
- **Entity types** — Platform (blue), Door (orange), Vertex (pink), Key (green), Ability (purple), Mover (yellow), Start Point (light purple)
- **Sprite workbench** — tool for creating/animating pixel art sprites
- **Room layout editor** — visual tool for placing entities and drawing room geometry
- **Workflow rails** — step-by-step phase indicators for room/world creation wizards

## Working with the Room Editor

The room editor (`room-layout-editor.html` + `room-wizard-workbench-shell.css`) uses:
- A floating canvas toolbar (absolute positioned, `z-index: 3`)
- An inspector panel (slides in on entity selection, `z-index: 10`)
- A workflow rail (fixed at top, `z-index: 5`)
- A segmented World/Room scope toggle (centred in the rail header)

Never restructure the shell layout without reading the full CSS file first.

## Agent OS — My Actions after every task

After completing a task, check whether **your** agent `*-status.json` needs updates so the **My Actions** founder board in `os-dashboard.html` stays accurate (`founder_decisions`, `priorities` with `needs-review`). See `AGENTS.md` (**My Actions dashboard — check after completing every request**). Update when needed; no edit if nothing founder-facing changed.

## Commit Style

- Keep commits scoped: UI changes in one commit, logic changes in another
- Never commit minified or generated files
- CSS variables changes always go with the component changes that use them
