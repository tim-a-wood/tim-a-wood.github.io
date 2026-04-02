# Sprite Workbench — Frontend Style Guide

> **Canonical design system reference for MV / Sprite Workbench.** All frontend work — components, pages, tools, and wizards — must conform to this guide. This document was reverse-engineered from the production codebase and is the single source of truth for visual language decisions.

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Color System](#2-color-system)
3. [Typography](#3-typography)
4. [Spacing System](#4-spacing-system)
5. [Border Radius](#5-border-radius)
6. [Shadows & Depth](#6-shadows--depth)
7. [Transitions & Animation](#7-transitions--animation)
8. [Component Library](#8-component-library)
   - [Buttons](#81-buttons)
   - [Inputs & Form Controls](#82-inputs--form-controls)
   - [Cards & Panels](#83-cards--panels)
   - [Navigation & Toolbars](#84-navigation--toolbars)
   - [Segmented Controls & Tabs](#85-segmented-controls--tabs)
   - [Workflow Rails & Phase Pills](#86-workflow-rails--phase-pills)
   - [Status Indicators & Badges](#87-status-indicators--badges)
   - [Wait bars & estimated progress](#88-wait-bars--estimated-progress)
   - [Toasts & notification stack](#89-toasts--notification-stack)
   - [Modals & Dialogs](#810-modals--dialogs)
   - [Collapsible Sections](#811-collapsible-sections)
   - [Canvas & Drawing Areas](#812-canvas--drawing-areas)
   - [Inspector / Sidebar Panels](#813-inspector--sidebar-panels)
   - [Inventory Lists](#814-inventory-lists)
   - [Metric / Stat Cards](#815-metric--stat-cards)
9. [Layout Patterns](#9-layout-patterns)
10. [Interaction Patterns](#10-interaction-patterns)
11. [Domain Color Palette](#11-domain-color-palette)
12. [Marketing & Splash Surfaces](#12-marketing--splash-surfaces)
13. [CSS Variables Reference](#13-css-variables-reference)
14. [Anti-Patterns](#14-anti-patterns)
15. [Agent Dashboard Charts](#15-agent-dashboard-charts)
    - [Chart type taxonomy](#151-chart-type-taxonomy)
    - [Color palette](#152-color-palette)
    - [Chart card shell](#153-chart-card-shell)
    - [Empty and pre-launch states](#154-empty-and-pre-launch-states)
    - [Legend and typography](#155-legend-and-typography)
    - [Motion policy](#156-motion-policy)
    - [Anti-patterns](#157-anti-patterns)

---

## 1. Design Philosophy

The Sprite Workbench design language is a **dark, precision-tool aesthetic** — purpose-built for a game development toolchain. It draws inspiration from professional creative software (Figma, Linear, Vercel) and game engines (Godot, Unity) while maintaining a distinctive neon-cyan identity.

### Core Principles

**Opacity over shadows for depth.** Layering is achieved through white opacity tiers (`rgba(255,255,255,0.025)` → `0.08`) rather than heavy drop shadows. Surfaces feel weightless, not stacked.

**Cyan accent = active, selected, interactive.** `#00e8c8` is the single primary accent. Everything that communicates "this is clickable, selected, or in focus" uses it. Do not introduce secondary accents without strong reason.

**Restraint in color.** The palette is intentionally narrow: near-black backgrounds, cyan accent, warm gold for primary CTAs, and semantic colours for system states. Entity-type colours (platform, door, vertex, etc.) are the only domain-specific exceptions.

**4px grid. Always.** Every spacing value is a multiple of 4px. Never use arbitrary values like 5px, 7px, 11px, or 15px for spacing.

**Pixel-sharp but soft.** Border radii are generous (14–20px on panels) but consistent. The goal is "professional software" not "website card."

**Animation is subtle.** Hover lifts are `translateY(-1px)`. Transition durations are 120ms or 200ms. Nothing bounces, wobbles, or flies in. Interactions feel responsive, not theatrical.

---

## 2. Color System

### Core Palette

```
Background (darkest)  #040608
Background            #050709
Background (lightest) #060b0e
Background gradient   linear-gradient(180deg, #040608, #050709 52%, #060b0e)
```

### Surface Colors

```
--panel:      rgba(4, 6, 10, 0.96)    /* Primary panel / sidebar surface */
--panel-2:    #07090c                  /* Secondary panel layer */
--panel-soft: #07090c                  /* Soft panel variant */
```

### Accent (Primary Interactive)

```
--accent:        #00e8c8               /* Cyan — active, selected, focused */
--accent-hover:  #20f4d4               /* Lighter cyan for hover states */
--accent-soft:   rgba(0, 232, 200, 0.08)  /* Subtle accent fill */
```

### Text Colors

```
--text:        #cce8e0    /* Primary text — light cyan-gray */
--muted:       #5d7870    /* Secondary / label text */
--text-faint:  rgba(204, 232, 224, 0.25)  /* Placeholder / decorative */
```

### Border & Stroke

```
--stroke:        rgba(0, 232, 200, 0.07)   /* Default panel border */
--stroke-strong: rgba(0, 232, 200, 0.14)   /* Elevated / hover border */
--line:          rgba(0, 232, 200, 0.10)   /* Subtle divider */
--line-strong:   rgba(0, 232, 200, 0.18)   /* Prominent divider */
--border:        rgba(0, 232, 200, 0.07)   /* Alias for --stroke */
--border-strong: rgba(0, 232, 200, 0.14)   /* Alias for --stroke-strong */
```

### Semantic Colors

```
--good:          #4ade80                    /* Success / valid */
--good-soft:     rgba(74, 222, 128, 0.12)  /* Success fill */

--warning:       #d29922                    /* Caution / degraded */
--warning-soft:  rgba(210, 153, 34, 0.16)  /* Warning fill */

--error:         #f85149                    /* Error / destructive */
--error-soft:    rgba(248, 81, 73, 0.16)   /* Error fill */
```

### Gold / Primary CTA

The warm gold is reserved for primary marketing CTAs and project selection active states — not general interactive elements.

```
Gold base:    #d4a752
Gold light:   #f1d9a2
Gold text:    #151108   /* Dark text on gold backgrounds */

Button gold gradient:
  linear-gradient(180deg, rgba(245, 208, 116, 0.92), rgba(220, 176, 73, 0.92))
Button gold hover:
  linear-gradient(180deg, rgba(249, 216, 132, 0.98), rgba(226, 184, 84, 0.96))
```

---

## 3. Typography

### Font Stack

```css
--font-sans:    "Plus Jakarta Sans", -apple-system, sans-serif;  /* UI text */
--font-display: "Bebas Neue", sans-serif;                          /* Headers, panel titles */
--font-serif:   "Iowan Old Style", Georgia, serif;                 /* Branding only */
--font-mono:    "DM Mono", ui-monospace, monospace;                /* Code, hex values */
```

### Size Scale

```css
--font-size-xs:  11px;   /* Labels, chips, uppercase tags */
--font-size-sm:  13px;   /* Secondary UI text, nav links */
--font-size-base: 14px;  /* Default body text */
--font-size-md:  15px;   /* Slightly emphasised body */
--font-size-lg:  18px;   /* Section subtitles */
--font-size-xl:  22px;   /* Panel / dialog headers */
--font-size-2xl: 26px;   /* Section headers */
--font-size-3xl: 38px;   /* Page headers */
--font-size-4xl: 40px;   /* Hero / display */
```

Responsive display sizes use `clamp()`:
```css
/* Hero headline */
font-size: clamp(2.4rem, 4vw, 4rem);
```

### Weight Scale

```
400  Regular    Body text, descriptions
500  Medium     Nav links, secondary labels
600  Semi-Bold  Emphasized labels, tab labels
700  Bold       Primary labels, CTA text
800  Extra-Bold Marketing headlines
```

### Letter Spacing

```
Headers (display):    0.03em – 0.06em
Uppercase labels:     0.08em – 0.18em
Chip/tag labels:      0.10em – 0.16em
Normal UI text:       normal (unset)
```

### Line Height

```
Tight (display):   0.9 – 0.94
Standard (body):   1.45
Relaxed (prose):   1.65 – 1.80
```

### Usage Rules

- **`--font-display` (Bebas Neue)** — panel titles, dialog headers, section headers, workflow step titles. Font-weight 400. Always with generous letter-spacing (0.04em+).
- **`--font-sans` (Plus Jakarta Sans)** — all UI text: buttons, labels, inputs, nav, descriptions.
- **`--font-mono` (DM Mono)** — hex values, coordinate readouts, code snippets, numeric data.
- **Uppercase labels** — `font-size: var(--font-size-xs); font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase` — for section headings inside panels, metric card labels.

---

## 4. Spacing System

All spacing is a strict multiple of **4px**.

```css
--space-1:  4px;
--space-2:  8px;
--space-3:  12px;
--space-4:  16px;
--space-5:  24px;
--space-6:  32px;
--space-7:  48px;
--space-8:  64px;

/* Component-specific */
--surface-gap: 12px;   /* Gap between panels / cards */
--surface-pad: 14px;   /* Default inner padding for panels */
```

### Common Spacing Patterns

| Context | Value |
|---|---|
| Button inner padding (standard) | `10px 12px` |
| Button inner padding (small) | `4px 10px` |
| Button inner padding (toolbar) | `6px 9px` |
| Panel inner padding | `14px` |
| Toolbar outer padding | `10px` |
| Section gap (within panel) | `10px` |
| Card grid gap | `8px` |
| Nav link padding | `6px 12px` |
| Inventory item padding | `6px 8px` |

---

## 5. Border Radius

```css
--radius-xs:     4px;     /* Inline indicators, tool-type dots */
--radius-sm:     8px;     /* Small buttons, micro elements */
--radius-md:     10px;    /* Small buttons (alt), compact elements */
--radius-default: 12px;   /* Toolbar items, status indicators */
--radius-tight:  14px;    /* Standard: buttons, inputs, chips, cards */
--radius-card:   18px;    /* Panel containers, control cards */
--radius-lg:     20px;    /* Workflow pills, major panels */
--radius-full:   999px;   /* Pill shapes, eyebrow badges */
```

### Decision Guide

- Single-action buttons → `14px` (`--radius-tight`)
- Toolbar icon buttons → `12px` (`--radius-default`)
- Input fields → `14px` (`--radius-tight`)
- Panel containers → `18px–20px` (`--radius-card` / `--radius-lg`)
- Segmented controls → `14px` outer, `11px` inner tab
- Full-round pills (badges, eyebrows) → `999px` (`--radius-full`)
- Tool indicators (square) → `2px`; (circle) → `50%`

---

## 6. Shadows & Depth

```css
--shadow-sm:  0 2px 8px rgba(0, 0, 0, 0.18);
--shadow-md:  0 6px 20px rgba(0, 0, 0, 0.26);
--shadow-lg:  0 12px 40px rgba(0, 0, 0, 0.38);

/* Inset highlight — applied on panel top edges */
inset 0 1px 0 rgba(255, 255, 255, 0.045)
inset 0 1px 0 rgba(255, 255, 255, 0.025)
```

### Accent Glow (Active States Only)

```css
/* Workflow pill active state glow */
box-shadow:
  0 0 0 3px rgba(0, 232, 200, 0.08),
  inset 0 1px 0 rgba(0, 232, 200, 0.10),
  0 0 20px rgba(0, 232, 200, 0.06);
```

### Floating Surfaces (Toolbars, Inspectors)

Floating elements use `backdrop-filter: blur()` + `--shadow-md`:
```css
background: rgba(7, 10, 13, 0.92);
backdrop-filter: blur(10px);
box-shadow: var(--shadow-md);
```

---

## 7. Transitions & Animation

```css
--transition-fast: 120ms ease;   /* Hover reveals, icon state changes */
--transition-base: 200ms ease;   /* Default: button hover, panel reveals */
```

### Standard Transition Properties

Buttons: `background, border-color, color, transform`
Panels/inspectors: `opacity, transform` (slide-in)
Chevrons/icons: `transform`

### Keyframes

```css
/* Inspector / floating panel entrance */
@keyframes slideIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}
/* Usage: animation: slideIn 120ms ease forwards; */
```

### Rules

- **No durations above 300ms** for UI interactions. Longer is only for page-level transitions.
- **No easing curves with bounce or spring.** Use `ease`, `ease-out` only.
- Hover lift: `transform: translateY(-1px)` — never more.
- Active/press: `transform: translateY(0)` (return to baseline).

---

## 8. Component Library

### 8.1 Buttons

All buttons share a base structure: `1px solid` border, transition on background/border/color/transform, min-height to ensure touch targets.

#### Standard Button (Default)
```css
min-height: 44px;
padding: 10px 12px;
border-radius: 14px;          /* --radius-tight */
border: 1px solid var(--line);
background: rgba(255, 255, 255, 0.045);
color: var(--text);
font-family: var(--font-sans);
font-size: var(--font-size-sm);
font-weight: 600;
transition: background 200ms ease, border-color 200ms ease,
            color 200ms ease, transform 200ms ease;
cursor: pointer;

/* Hover */
border-color: var(--line-strong);
background: rgba(255, 255, 255, 0.08);
transform: translateY(-1px);

/* Active */
border-color: var(--accent);
background: rgba(0, 232, 200, 0.12);
box-shadow: inset 0 0 0 1px var(--line);
transform: translateY(0);

/* Disabled */
opacity: 0.45;
cursor: not-allowed;
pointer-events: none;
```

#### Small Button
```css
min-height: 28px;
padding: 4px 10px;
border-radius: 10px;          /* --radius-md */
font-size: var(--font-size-xs);
```

#### Toolbar Button
```css
min-height: 36px;
padding: 6px 9px;
border-radius: 12px;          /* --radius-default */
```

#### Primary / Gold CTA Button
```css
min-height: 44px;
padding: 10px 18px;
border-radius: 14px;
background: linear-gradient(180deg,
  rgba(245, 208, 116, 0.92),
  rgba(220, 176, 73, 0.92));
border: 1px solid rgba(245, 208, 116, 0.48);
color: #16120a;               /* Dark text on gold */
font-weight: 700;

/* Hover */
background: linear-gradient(180deg,
  rgba(249, 216, 132, 0.98),
  rgba(226, 184, 84, 0.96));
border-color: rgba(249, 216, 132, 0.62);
```

#### Danger Button
```css
color: var(--error);
border-color: rgba(248, 81, 73, 0.20);
background: transparent;

/* Hover */
background: var(--error-soft);
border-color: rgba(248, 81, 73, 0.35);
```

#### Secondary Button (ghost-style)
```css
background: rgba(255, 255, 255, 0.03);
color: var(--text);
border: 1px solid var(--line);
```

---

### 8.2 Inputs & Form Controls

#### Text Input
```css
width: 100%;
min-height: 44px;
padding: 10px 12px;
border-radius: 14px;
border: 1px solid var(--line);
background: rgba(255, 255, 255, 0.04);
color: var(--text);
font-family: var(--font-sans);
font-size: var(--font-size-base);
outline: none;
transition: border-color 200ms ease;

/* Focus */
border-color: rgba(0, 232, 200, 0.35);
outline: 2px solid rgba(0, 232, 200, 0.20);
outline-offset: 2px;
```

#### Small Input
```css
min-height: 32px;
padding: 6px 10px;
border-radius: 10px;
font-size: var(--font-size-xs);
```

#### Focus-Visible (keyboard navigation)
```css
outline: 2px solid rgba(0, 232, 200, 0.35);
outline-offset: 2px;
```

---

### 8.3 Cards & Panels

#### Standard Card
```css
padding: 14px;
border-radius: 14px;             /* --radius-tight */
border: 1px solid var(--stroke);
background: rgba(255, 255, 255, 0.03);
box-shadow: var(--shadow-sm);
```

#### Control Card (elevated, for editor panels)
```css
padding: 14px;
border-radius: 18px;             /* --radius-card */
border: 1px solid var(--line);
background: linear-gradient(180deg,
  rgba(255, 255, 255, 0.035),
  rgba(255, 255, 255, 0.02)),
  rgba(6, 10, 14, 0.88);
box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
```

#### Panel Container (sidebar / app shell)
```css
background: var(--panel);        /* rgba(4,6,10,0.96) */
border: 1px solid var(--stroke);
border-radius: 18px;
```

---

### 8.4 Navigation & Toolbars

#### Site Navigation Bar
```css
height: 52px;
background: rgba(8, 11, 16, 0.92);
backdrop-filter: blur(18px);
border-bottom: 1px solid var(--stroke);
```

#### Nav Link
```css
padding: 6px 12px;
border-radius: 10px;
font-size: var(--font-size-sm);
font-weight: 500;
color: var(--muted);
transition: color 200ms ease, background 200ms ease;

/* Hover */
color: var(--text);
background: rgba(255, 255, 255, 0.05);
```

#### Floating Canvas Toolbar
```css
position: absolute;
padding: 10px;
border-radius: 16px;
border: 1px solid var(--line);
background: rgba(7, 10, 13, 0.92);
backdrop-filter: blur(10px);
box-shadow: var(--shadow-md);
```

#### Sidebar
```css
background: rgba(8, 11, 16, 0.88);
backdrop-filter: blur(14px);
border-right: 1px solid var(--stroke);
padding: 18px 14px 16px;
```

---

### 8.5 Segmented Controls & Tabs

#### Segmented Control (scope toggle)
```css
/* Container */
display: flex;
padding: 3px;
border-radius: 14px;
border: 1px solid var(--line);
background: rgba(255, 255, 255, 0.04);

/* Each chip */
min-width: 6.5rem;
min-height: 40px;
padding: 10px 18px;
border-radius: 14px;
border: 1px solid transparent;
background: linear-gradient(180deg,
  rgba(255, 255, 255, 0.04),
  rgba(255, 255, 255, 0.025));
box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.025);
font-size: var(--font-size-xs);
font-weight: 600;
letter-spacing: 0.10em;
text-transform: uppercase;
color: var(--muted);
transition: all 200ms ease;

/* Active chip */
border-color: var(--accent);
background: rgba(0, 232, 200, 0.12);
color: var(--text);
box-shadow: inset 0 0 0 1px rgba(0, 232, 200, 0.08);
```

#### Tab Strip
```css
/* Strip container */
background: rgba(255, 255, 255, 0.04);
border: 1px solid var(--line);
border-radius: 14px;
padding: 3px;

/* Tab button */
min-height: 32px;
padding: 5px 10px;
border-radius: 11px;
border: none;
background: none;
color: var(--muted);
font-size: var(--font-size-sm);
font-weight: 500;

/* Active tab */
background: rgba(0, 232, 200, 0.12);
color: var(--text);
```

---

### 8.6 Workflow Rails & Phase Pills

#### Rail Container
```css
background: rgba(4, 6, 10, 0.92);
backdrop-filter: blur(10px);
border: 1px solid var(--border);
border-radius: 20px;
box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
```

#### Phase Pill — Locked
```css
opacity: 0.28;
pointer-events: none;
```

#### Phase Pill — Available
```css
background: var(--panel-soft);
border: 1px solid var(--border);
border-radius: 20px;
padding: 14px;
min-height: 84px;
```

#### Phase Pill — Active
```css
border: 2px solid var(--accent);
background: linear-gradient(160deg,
  rgba(0, 232, 200, 0.07) 0%,
  transparent 70%),
  var(--panel);
box-shadow:
  0 0 0 3px rgba(0, 232, 200, 0.08),
  inset 0 1px 0 rgba(0, 232, 200, 0.10),
  0 0 20px rgba(0, 232, 200, 0.06);
```

#### Phase Pill Layout
```css
display: flex;
flex-direction: column;
gap: 8px;
```

---

### 8.7 Status Indicators & Badges

#### Status Bar
```css
display: flex;
align-items: center;
gap: 8px;
font-size: var(--font-size-xs);
color: var(--muted);
min-height: 36px;
padding: 8px 14px;
border-radius: 12px;
border: 1px solid var(--line);
background: rgba(255, 255, 255, 0.03);

/* Status dot */
&::before {
  content: "●";
  font-size: 8px;
  color: var(--muted);
}
```

#### Status Variants
```css
/* Success */
background: var(--good-soft);
border-color: rgba(74, 222, 128, 0.24);
color: #dff7ec;

/* Error */
background: var(--error-soft);
border-color: rgba(248, 81, 73, 0.24);
color: #fdd8d6;

/* Warning */
background: var(--warning-soft);
border-color: rgba(210, 153, 34, 0.24);
color: #f5e6c0;
```

#### Eyebrow Badge (marketing)
```css
display: inline-flex;
align-items: center;
min-height: 34px;
padding: 0 12px;
border-radius: 999px;
background: rgba(255, 255, 255, 0.06);
color: #cae8df;
font-size: 0.76rem;
font-weight: 700;
letter-spacing: 0.16em;
text-transform: uppercase;
```

---

### 8.8 Wait bars & estimated progress

**Use for:** Long-running or server-bound work (AI generation, saves, batch previews) where duration is unknown. Prefer **one** primary surface: in-panel wait bar and/or floating **activity dock** — do not also fire an informational toast for the same phase (success, warning, and error toasts stay).

**Semantic color:** Fill uses **`var(--warning)`** (warm amber), not primary CTA gold and not **`var(--accent)`**. This reads as “work in flight / indeterminate” and avoids implying completion or clickable primary action.

**In-panel wait bar** — use class **`workbench-waitbar`** (room editor also keeps `.rw-waitbar`; sprite keeps `.pixellab-char-progress` for JS hooks). Structure: **`.workbench-waitbar-detail`** (or `.small-note` + detail) → **`.progress-track`** / **`.progress-fill`** → **`.progress-meta`**.

```css
.workbench-waitbar {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.workbench-waitbar-detail {
  margin-bottom: 8px;
}
```

**Page `:root` must define** `--radius-full`, `--radius-card`, `--radius-lg`, `--radius-sm`, and `--radius-default` wherever `room-wizard-workbench-shell.css` is loaded (room layout editor), or progress pills and wizard chrome lose `border-radius`.

**Detail line** above the track: `small-note` / muted body; optional `aria-live="polite"` on the container.

**Progress track & fill** (shared: room wizard dock, floating activity dock, sprite workbench in-panel):

```css
.progress-track {
  width: 100%;
  height: 10px;
  border-radius: var(--radius-full);
  overflow: hidden;
  background: color-mix(in srgb, var(--text) 8%, transparent);
}

.progress-fill {
  height: 100%;
  width: 0%; /* set inline or via JS */
  border-radius: var(--radius-full);
  background: linear-gradient(
    135deg,
    var(--warning),
    color-mix(in srgb, var(--warning) 55%, var(--text))
  );
  transition: width 200ms ease-out;
}
```

**Meta row** (percentage + short disclaimer), `.progress-meta` or `.activity-progress-meta`:

```css
display: flex;
justify-content: space-between;
align-items: center;
gap: 12px;
margin-top: 8px;
color: var(--muted);
font-size: var(--font-size-xs);
```

**Copy pattern:** e.g. “Progress is estimated until the server finishes.”

**Floating activity dock** (`z-index: 38`, bottom-right): Same track/fill/meta tokens; pairs with in-panel wait bar for visibility when the wizard scrolls away. Implementations live in `room-wizard-workbench-shell.css` (selectors include `.activity-dock`).

**Governance note:** If `color-mix` is unsupported in a target browser, fall back to `rgba(255, 255, 255, 0.08)` for the track only; keep fill on tokens above. See `docs/design/workbench-feedback-root-cause.md` for why the guide lagged implementations.

---

### 8.9 Toasts & notification stack

**Placement:** Fixed **top-right** stack (`#toast-stack`), not a single bottom toast — multiple messages can queue without overlapping the canvas toolbar.

```css
.toast-stack {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 40;
  display: grid;
  gap: 12px;
  width: min(360px, calc(100vw - 32px));
  pointer-events: none;
}

.toast {
  padding: 12px 16px;
  border-radius: var(--radius-card);
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--text);
  box-shadow: var(--shadow-lg);
  font-size: var(--font-size-xs);
  line-height: 1.4;
  pointer-events: auto;
}

.toast strong {
  display: block;
  margin-bottom: 4px;
  font-size: var(--font-size-sm);
  color: var(--text);
}

.toast p {
  margin: 0;
  color: var(--muted);
}
```

**Variants** (border + background tuning; pair with icon or title — not color alone):

```css
/* Info (default) */
.toast.info { border-color: var(--line-strong); }

/* Success */
.toast.success {
  border-color: rgba(74, 222, 128, 0.24);
  background: rgba(4, 16, 10, 0.96);
}

/* Warning */
.toast.warning {
  border-color: rgba(210, 153, 34, 0.24);
  background: rgba(23, 17, 6, 0.96);
}

/* Error */
.toast.error {
  border-color: rgba(248, 81, 73, 0.24);
  background: rgba(25, 9, 11, 0.96);
}
```

**Duration:** ~4s default; ~6.5s for `error`. **Content:** `<strong>` title + `<p>` body; escape user text in JS.

---

### 8.10 Modals & Dialogs

```css
/* Overlay */
background: rgba(2, 4, 8, 0.75);
backdrop-filter: blur(14px);
z-index: 250;

/* Dialog panel */
border-radius: var(--radius-tight);   /* 14px */
border: 1px solid var(--border-strong);
background: var(--panel);
box-shadow: var(--shadow-lg);

/* Dialog header */
padding: 12px 16px;
border-bottom: 1px solid var(--border);
background: rgba(4, 6, 10, 0.98);

/* Dialog title (display font) */
font-family: var(--font-display);
font-size: 22px;
letter-spacing: 0.06em;
font-weight: 400;
color: var(--text);
```

---

### 8.11 Collapsible Sections

```css
/* Toggle button */
width: 100%;
padding: 10px 14px;
background: rgba(255, 255, 255, 0.03);
border: none;
border-radius: 0;
color: var(--muted);
font-size: var(--font-size-sm);
font-weight: 500;
min-height: 40px;
display: flex;
align-items: center;
justify-content: space-between;
cursor: pointer;

/* Toggle hover */
background: rgba(255, 255, 255, 0.06);
color: var(--text);

/* Chevron */
transition: transform var(--transition-fast);
/* Expanded state: */
transform: rotate(180deg);

/* Body */
padding: 14px;
border-top: 1px solid var(--line);
display: grid;
gap: 12px;
```

---

### 8.12 Canvas & Drawing Areas

```css
background: linear-gradient(
  0deg,
  rgba(255, 255, 255, 0.02),
  rgba(255, 255, 255, 0.02)
), #081018;
border: 1px solid var(--line-strong);
border-radius: 18px;

/* For pixel art rendering */
image-rendering: pixelated;
```

---

### 8.13 Inspector / Sidebar Panels

```css
width: 240px;
padding: 12px;
border-radius: 18px;
border: 1px solid var(--line-strong);
background: linear-gradient(180deg,
  rgba(11, 16, 20, 0.98),
  rgba(7, 10, 13, 0.98));
box-shadow: var(--shadow-md);

/* Entrance animation */
animation: slideIn 120ms ease forwards;
```

---

### 8.14 Inventory Lists

```css
/* Section container */
border-radius: 14px;
border: 1px solid var(--line);

/* Section header */
padding: 8px 12px;
background: rgba(255, 255, 255, 0.03);
font-size: var(--font-size-sm);
font-weight: 600;
cursor: pointer;
display: flex;
align-items: center;
justify-content: space-between;

/* Header hover */
background: rgba(255, 255, 255, 0.06);

/* Item */
padding: 6px 8px;
border-radius: 10px;
border: 1px solid transparent;
cursor: pointer;
display: flex;
align-items: center;
gap: 8px;

/* Item hover */
background: rgba(255, 255, 255, 0.05);
border-color: var(--line);

/* Item active / selected */
background: var(--accent-soft);
border-color: rgba(0, 232, 200, 0.20);
```

---

### 8.15 Metric / Stat Cards

```css
padding: 12px;
border-radius: 16px;
border: 1px solid var(--line);
background: linear-gradient(180deg,
  rgba(255, 255, 255, 0.04),
  rgba(255, 255, 255, 0.02));

/* Label */
font-size: 10px;
color: var(--muted);
text-transform: uppercase;
letter-spacing: 0.12em;
font-weight: 700;

/* Value */
font-size: 24px;
line-height: 1;
font-weight: 700;
color: var(--text);
```

---

## 9. Layout Patterns

### App Shell Grid

```css
/* Default: sidebar + main content */
display: grid;
grid-template-columns: 300px minmax(0, 1fr);

/* Collapsed sidebar */
grid-template-columns: 64px minmax(0, 1fr);

/* Mobile */
@media (max-width: 840px) {
  grid-template-columns: 1fr;  /* Sidebar overlays */
}
```

### Stage Layout (Primary Editor Split)
```css
display: grid;
grid-template-columns: minmax(280px, 0.46fr) minmax(320px, 0.54fr);
gap: 16px;
```

### Phase Rail Grids
```css
/* World workflow (4 steps) */
grid-template-columns: repeat(4, minmax(0, 1fr));
gap: 8px;

/* Room workflow (5 steps) */
grid-template-columns: repeat(5, minmax(0, 1fr));
gap: 8px;
```

### Common Grid Subdivisions
```css
2-column:  grid-template-columns: 1fr 1fr; gap: 8px;
3-column:  grid-template-columns: repeat(3, 1fr); gap: 8px;
4-column:  grid-template-columns: repeat(4, 1fr); gap: 8px;
3-uniform: grid-template-columns: repeat(3, minmax(0, 1fr));
```

### Responsive Breakpoints

| Breakpoint | Behaviour |
|---|---|
| `max-width: 1300px` | 3-col editorial → 1-col |
| `max-width: 1280px` | Phase rails: 4-col → 2-col |
| `max-width: 1100px` | Artifact blocks → 1-col |
| `max-width: 900px`  | Room rails: 2-col → 1-col |
| `max-width: 840px`  | App shell: sidebar collapses |
| `max-width: 760px`  | Mobile layout |
| `max-width: 560px`  | World phase rails → 1-col |

---

## 10. Interaction Patterns

### Hover States

| Element | Hover Effect |
|---|---|
| Button | `translateY(-1px)` + brightened background |
| Nav link | Background reveal + text brightens |
| Card | Border brightens to `--line-strong` |
| Inventory item | Background `rgba(255,255,255,0.05)` + border appears |
| Collapsible toggle | Background brightens, text to `var(--text)` |

### Active / Selected States

Always uses cyan accent:
- `border-color: var(--accent)`
- `background: rgba(0, 232, 200, 0.12)` (`--accent-soft` or stronger)
- Optional: `box-shadow: inset 0 0 0 1px rgba(0,232,200,0.08)`

### Focus States (Keyboard Navigation)

```css
:focus-visible {
  outline: 2px solid rgba(0, 232, 200, 0.35);
  outline-offset: 2px;
}
```

### Disabled States

```css
opacity: 0.28 – 0.45;
cursor: not-allowed;
pointer-events: none;
```

Use `0.28` for locked/inaccessible workflow states. Use `0.45` for temporarily disabled controls.

---

## 11. Domain Color Palette

These colors represent room/world editor entity types. Used for tool indicators, inspector headers, and entity-type chips. Do not use these for generic UI.

```
Platform:    #77b8ff    /* Blue — solid terrain */
Door:        #f5986e    /* Orange — transitions */
Vertex:      #ff6b8a    /* Pink — geometry points */
Key:         #4ade80    /* Green — collectibles */
Ability:     #a78bfa    /* Purple — powerups */
Mover:       #fbbf24    /* Yellow — dynamic objects */
Start Point: #f0abfc    /* Light purple — spawn */
```

### Tool Indicator Shapes

```css
/* Platform — square indicator */
width: 8px; height: 8px;
border-radius: 2px;           /* --radius-xs */
background: #77b8ff;

/* Round indicators (door, vertex, ability, start) */
width: 8px; height: 8px;
border-radius: 50%;
background: [entity-color];
```

---

## 12. Marketing & Splash Surfaces

Marketing surfaces (homepage hero, feature sections) use the same token system but allow broader gradients and bolder layouts.

### Splash / Hero Background
```css
background:
  linear-gradient(180deg,
    rgba(5, 9, 13, 0.28) 0%,
    rgba(5, 9, 13, 0.60) 48%,
    rgba(5, 9, 13, 0.92) 100%),
  url("../assets/splash-image.png") center / cover no-repeat;
```

### Ambient Radial Overlays
```css
/* Cyan glow — top-left */
background: radial-gradient(
  circle at 18% 24%,
  rgba(0, 232, 200, 0.12),
  transparent 26%);

/* Gold glow — top-right */
background: radial-gradient(
  circle at 78% 16%,
  rgba(212, 167, 82, 0.08),
  transparent 22%);
```

### Marketing CTA Button
```css
min-height: 46px;
padding: 0 18px;
border-radius: 14px;
border: 1px solid rgba(255, 255, 255, 0.08);
background: rgba(255, 255, 255, 0.04);
font-weight: 700;
transition: transform 200ms ease, background 200ms ease, border-color 200ms ease;

/* Hover */
transform: translateY(-1px);
background: rgba(255, 255, 255, 0.06);
border-color: rgba(255, 255, 255, 0.16);
```

---

## 13. CSS Variables Reference

Paste this block into any new page's `<style>` or into a shared `tokens.css`:

```css
:root {
  /* Colors */
  --bg:            #050709;
  --panel:         rgba(4, 6, 10, 0.96);
  --panel-2:       #07090c;
  --panel-soft:    #07090c;
  --accent:        #00e8c8;
  --accent-soft:   rgba(0, 232, 200, 0.08);
  --text:          #cce8e0;
  --muted:         #5d7870;
  --stroke:        rgba(0, 232, 200, 0.07);
  --stroke-strong: rgba(0, 232, 200, 0.14);
  --line:          rgba(0, 232, 200, 0.10);
  --line-strong:   rgba(0, 232, 200, 0.18);
  --border:        rgba(0, 232, 200, 0.07);
  --border-strong: rgba(0, 232, 200, 0.14);
  --good:          #4ade80;
  --good-soft:     rgba(74, 222, 128, 0.12);
  --warning:       #d29922;
  --warning-soft:  rgba(210, 153, 34, 0.16);
  --error:         #f85149;
  --error-soft:    rgba(248, 81, 73, 0.16);

  /* Typography */
  --font-sans:    "Plus Jakarta Sans", -apple-system, sans-serif;
  --font-display: "Bebas Neue", sans-serif;
  --font-serif:   "Iowan Old Style", Georgia, serif;
  --font-mono:    "DM Mono", ui-monospace, monospace;
  --font-size-xs:   11px;
  --font-size-sm:   13px;
  --font-size-base: 14px;
  --font-size-md:   15px;
  --font-size-lg:   18px;
  --font-size-xl:   22px;

  /* Spacing */
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

  /* Border Radius */
  --radius-xs:      4px;
  --radius-sm:      8px;
  --radius-md:      10px;
  --radius-default: 12px;
  --radius-tight:   14px;
  --radius-card:    18px;
  --radius-lg:      20px;
  --radius-full:    999px;

  /* Shadows */
  --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.18);
  --shadow-md: 0 6px 20px rgba(0, 0, 0, 0.26);
  --shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.38);

  /* Transitions */
  --transition-fast: 120ms ease;
  --transition-base: 200ms ease;
}
```

---

## 14. Anti-Patterns

Do not do any of the following. These violate the design language:

### Colors
- **Never use white text** (`#ffffff`). Use `var(--text)` (`#cce8e0`).
- **Never use pure black** as a background. Use `var(--bg)` (`#050709`).
- **Never invent new accent colors.** The accent is `#00e8c8`. Period.
- **Never use fully opaque backgrounds** for floating panels — use rgba with backdrop-filter.
- **Never use colored buttons** for non-primary actions. Only gold gradient for primary CTA, cyan-tinted for active states.

### Typography
- **Never use system default fonts** for headings (Arial, Helvetica, Inter). Load `Bebas Neue` for display.
- **Never mix `--font-display` into body paragraphs.**
- **Never use font sizes outside the scale** (e.g., `16px`, `17px`, `19px`).
- **Never set `font-weight: 900`** — max is 800.

### Spacing
- **Never use odd pixel values** for spacing: 5px, 7px, 9px, 11px, 13px, 15px, etc. Round to nearest 4px.
- **Never use `margin: auto` to center panels** in a tool layout — use CSS Grid.

### Border Radius
- **Never use `border-radius: 6px` or `border-radius: 24px`.** These are not in the radius scale.
- **Never use inconsistent radii** across matching components.

### Interactions
- **Never animate `width`, `height`, or layout properties** — use `transform` and `opacity` only.
- **Never use `transition: all`** — always specify the properties being transitioned.
- **Never exceed `translateY(-2px)`** for hover lift.
- **Never use cubic-bezier spring curves** — use `ease` or `ease-out` only.

### Shadows
- **Never use colored shadows** (except the cyan glow on active phase pills).
- **Never add box-shadow to every element** — reserve shadows for floating/elevated surfaces.

### Layout
- **Never hard-code pixel widths** for the main content area — use `minmax(0, 1fr)`.
- **Never use `float`-based layouts.**
- **Never put form controls below 44px min-height** (accessibility).

### Brand Identity
- **Never use light/white backgrounds** anywhere in the tool UI — this is a dark-theme-only product.
- **Never use rounded icon-only buttons without a visible border** — always keep the 1px border at `var(--line)`.

---

## 15. Agent Dashboard Charts

Each agent's main dashboard view may contain **up to 3 charts**. Charts replace the priorities table in the main view. Priorities are covered by the Issues / Opportunities / Tasks lanes; the chart section answers a different question: *how is this domain performing over time?*

Every chart must map to a specific decision the founder can make. Decorative charts are not permitted.

---

### 15.1 Chart Type Taxonomy

Select the chart type from the data shape. Never select a chart type for aesthetic reasons.

| Data shape | Chart type | Class modifier |
|---|---|---|
| Trend over time (continuous) | Area | `os-chart-card--area` |
| Comparison across discrete categories | Bar (vertical) | `os-chart-card--bar` |
| Part-to-whole (≤5 slices) | Donut | `os-chart-card--donut` |
| Single current value with context | Metric card (§ 8.15) | — (not a chart) |
| Ranked list with values | Horizontal bar | `os-chart-card--hbar` |

**Rules:**
- Pie charts are not used. Use donut — the center hole provides a slot for a summary value.
- Donut charts must have ≤ 5 slices. If you have more categories, group the tail as "Other."
- Area charts use a single data series per chart. Do not stack two series in the same area chart — use a bar chart for multi-series comparison.
- Metric cards (§ 8.15) are the correct choice for single KPI values. Do not render a chart for one number.

---

### 15.2 Color Palette

#### Agent identity colors

Each agent has a designated identity color used for nav dots, chart primary series, and card accents. These are defined in `os-dashboard.html :root` and must be referenced by token, never by hex value.

| Agent | Token | Value |
|---|---|---|
| Orchestrator | `--c-orchestrator` | `#00e8c8` |
| Engineering | `--c-engineering` | `#38bdf8` |
| Design | `--c-design` | `#818cf8` |
| QA | `--c-qa` | `#77b8ff` |
| Analytics | `--c-analytics` | `#4ade80` |
| Marketing | `--c-marketing` | `#f5986e` |
| Legal | `--c-legal` | `#a78bfa` |
| Finance | `--c-finance` | `#f0abfc` |
| Strategy | `--c-strategy` | `#fbbf24` |
| Research | `--c-research` | `#e879f9` |
| Cybersecurity | `--c-cybersecurity` | `#f85149` |
| Support | `--c-support` | `#fbbf24` |
| Audio | `--c-audio` | `#fb923c` |
| Animation | `--c-animation` | `#34d399` |
| Narrative | `--c-narrative` | `#c084fc` |
| Creative | `--c-creative` | `#f472b6` |
| Game Director | `--c-game-director` | `#e2e8f0` |
| Game Systems | `--c-game-systems` | `#67e8f9` |
| Level Design | `--c-level-design` | `#86efac` |

#### Chart series colors

When a chart requires multiple data series, use this fixed sequence. Never invent new series colors.

```
Series 1 (primary):  var(--agent-color)           /* agent identity color */
Series 2:            rgba(255, 255, 255, 0.35)     /* neutral secondary */
Series 3:            var(--warning)                /* #d29922 — only if the third series represents a caution/risk dimension */
Series 3 (neutral):  rgba(255, 255, 255, 0.18)    /* if the third series is not a risk dimension */
```

Do not use `--good`, `--error`, or `--accent` as generic series colors — these carry semantic meaning (success, failure, primary action) and will be misread.

#### Chart grid and axis colors

```css
/* Grid lines */
border-color: rgba(255, 255, 255, 0.06);

/* Axis labels */
color: var(--muted);   /* #5d7870 */
font-family: var(--font-mono);
font-size: var(--font-size-xs);  /* 11px */
```

#### Tooltip

```css
background: var(--panel-2);            /* #07090c */
border: 1px solid var(--stroke-strong);
border-radius: var(--radius-sm);       /* 8px */
color: var(--text);
font-size: var(--font-size-sm);        /* 13px */
padding: var(--space-2) var(--space-3); /* 8px 12px */
box-shadow: var(--shadow-md);
```

---

### 15.3 Chart Card Shell

All charts live inside `.os-chart-card`. Do not build custom chart wrappers. The existing shell components in `os-dashboard.html` are the spec.

```html
<div class="os-chart-card [os-chart-card--donut|--bar|--area|--hbar]">
  <div class="os-chart-card-head">
    <h3 class="os-chart-card-title" id="[agent]-chart-[type]-title">[Chart title]</h3>
    <span class="os-chart-card-tier">[LIVE | MANUAL | POST-LAUNCH]</span>
  </div>
  <div class="os-chart-canvas-wrap [os-chart-canvas-wrap--tall]"
       data-os-canvas-state="idle"
       role="img"
       aria-labelledby="[agent]-chart-[type]-title"
       aria-describedby="[agent]-chart-[type]-desc">
    <div class="os-chart-skeleton" aria-hidden="true"></div>
    <div class="os-chart-error" role="alert" aria-live="polite"></div>
    <canvas data-os-chart="[chart-id]" aria-hidden="true"></canvas>
  </div>
  <p class="os-chart-foot" id="[agent]-chart-[type]-desc">[One-sentence data provenance note.]</p>
</div>
```

**Tier badges:**
- `LIVE` — data updates automatically from a server or file read
- `MANUAL` — data is updated by hand when the agent runs
- `POST-LAUNCH` — data does not yet exist; displayed as an honest placeholder

**`os-chart-canvas-wrap` states** (set via `data-os-canvas-state`):
- `idle` — canvas renders normally
- `loading` — skeleton shimmer shows, canvas hidden
- `error` — error message shows, canvas hidden
- `empty` — custom empty state shows (see § 15.4), canvas hidden

**Title rules:**
- Use sentence case, not title case: "Priority breakdown by risk" not "Priority Breakdown by Risk"
- Include the time window if relevant: "Open issues · last 30 days"
- Max 50 characters — truncate with `text-overflow: ellipsis` if longer

---

### 15.4 Empty and Pre-Launch States

Charts without data must communicate why they are empty. Do not show an empty axis, a chart of all zeros, or a spinner with no resolution.

#### Three distinct states

**Loading** (`data-os-canvas-state="loading"`) — data is being fetched. The skeleton shimmer shows. Use only during actual async loads; do not leave a chart in loading state permanently.

**Error** (`data-os-canvas-state="error"`) — data fetch failed. The `.os-chart-error` div renders with a plain-English message. Format: "Couldn't load [metric name]. Check the server connection." No stack traces visible to the user.

**Empty / Pre-launch** (`data-os-canvas-state="empty"`) — data does not exist yet. This is the honest pre-launch state. Render an inline message inside `.os-chart-canvas-wrap`:

```html
<div class="os-chart-empty" aria-live="polite">
  <span class="os-chart-empty-label">No data yet</span>
  <span class="os-chart-empty-sub">Tracking begins after first [event that produces data].</span>
</div>
```

```css
.os-chart-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  height: 100%;
  min-height: 120px;
  color: var(--muted);
}

.os-chart-empty-label {
  font-size: var(--font-size-base);
  font-family: var(--font-sans);
  font-weight: 600;
  color: var(--muted);
}

.os-chart-empty-sub {
  font-size: var(--font-size-sm);
  font-family: var(--font-sans);
  color: var(--muted);
  text-align: center;
  max-width: 240px;
  line-height: 1.5;
}
```

**The `POST-LAUNCH` tier badge on the card head is the companion signal** — it tells the founder at a glance that this chart is a placeholder, not a system error. Always pair `POST-LAUNCH` badge + `empty` canvas state.

---

### 15.5 Legend and Typography

Chart.js renders legends via its own DOM. Always disable Chart.js's default legend and render custom legends in HTML for token consistency.

#### Legend placement

Legends appear **below the chart canvas**, inside `.os-chart-foot` or a `.os-chart-legend` sibling.

```html
<div class="os-chart-legend">
  <span class="os-chart-legend-item">
    <span class="os-chart-legend-dot" style="background: var(--c-[agent])"></span>
    [Series label]
  </span>
</div>
```

```css
.os-chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  padding-top: var(--space-2);
}

.os-chart-legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);   /* 11px */
  font-family: var(--font-sans);
  color: var(--muted);
}

.os-chart-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}
```

#### Axis labels (Chart.js config)

```js
scales: {
  x: {
    ticks: {
      font: { family: "'DM Mono', monospace", size: 11 },
      color: '#5d7870',   /* var(--muted) resolved value */
    },
    grid: { color: 'rgba(255,255,255,0.06)' }
  },
  y: {
    ticks: {
      font: { family: "'DM Mono', monospace", size: 11 },
      color: '#5d7870',
    },
    grid: { color: 'rgba(255,255,255,0.06)' }
  }
}
```

#### Donut center label

For donut charts, render the summary value in the chart center using the Chart.js `afterDraw` plugin hook, not a positioned HTML element.

```js
{
  id: 'centerLabel',
  afterDraw(chart) {
    const { ctx, chartArea: { width, height, left, top } } = chart;
    const cx = left + width / 2;
    const cy = top + height / 2;
    ctx.save();
    ctx.font = `600 22px "Plus Jakarta Sans", sans-serif`;
    ctx.fillStyle = '#cce8e0';  /* var(--text) */
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(centerValue, cx, cy - 8);
    ctx.font = `400 11px "DM Mono", monospace`;
    ctx.fillStyle = '#5d7870';  /* var(--muted) */
    ctx.fillText(centerLabel, cx, cy + 12);
    ctx.restore();
  }
}
```

---

### 15.6 Motion Policy

Chart entry animation is permitted but constrained.

**On initial render:** data points animate in over `400ms` using Chart.js's built-in `animation.duration`. Easing: `easeOutQuart`. This is the one permitted exception to the 200ms base duration — chart data entry reads as natural at 400ms because data points are numerous.

**On data update (re-render):** no animation. Update data silently via `chart.data.datasets[0].data = newData; chart.update('none')`. Animated re-renders on polling updates cause visual noise.

**Card entry animation:** `.os-chart-card` fades in with the `.os-dash-enter` class sequence already defined in `os-dashboard.html`. No per-agent additions needed.

**No hover animations on chart elements beyond tooltip.** Chart.js hover mode should be set to `mode: 'index'` for bars and areas, `mode: 'nearest'` for donuts. No segment scale-up on hover — it causes layout reflow in SVG fallbacks.

```js
// Standard Chart.js animation config for all agent charts
animation: { duration: 400, easing: 'easeOutQuart' },
hover: { animationDuration: 0 },
responsiveAnimationDuration: 0
```

---

### 15.7 Anti-Patterns

| Anti-Pattern | Why Rejected | Correct Approach |
|---|---|---|
| More than 3 charts per agent dashboard | Exceeds founder attention budget; visual richness ≠ signal | Maximum 3. If a fourth seems necessary, one of the first three is wrong. |
| Pie chart | No center slot for summary value; harder to read than donut | Use donut (`os-chart-card--donut`) |
| Donut with 6+ slices | Slices below ~5° are unreadable | Group tail as "Other" — max 5 slices |
| Empty axis with zero data | Reads as broken, not honest | Use `data-os-canvas-state="empty"` + `POST-LAUNCH` badge |
| Chart.js default legend | Uses system fonts; breaks token system | Disable and render custom `.os-chart-legend` |
| Stacked area chart with 2+ series | Too visually complex for small card | Use bar chart for multi-series comparison |
| Animated re-renders on polling updates | Causes visual flicker every poll cycle | `chart.update('none')` on data refreshes |
| `rgba` series colors with `< 0.15` opacity | Effectively invisible on dark background | Minimum fill alpha `0.15`; stroke alpha `0.85` |
| Novel hex colors for series | Breaks token audit trail | Use agent identity token + neutral sequence only |
| `transition: all` on `.os-chart-card` | Catches layout properties; causes reflow | Card entry is handled by `.os-dash-enter` — do not add per-chart transitions |
