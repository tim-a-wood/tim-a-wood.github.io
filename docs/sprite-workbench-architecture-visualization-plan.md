# Sprite Workbench — Architecture Visualization (Cross-Team Plan)

**Status:** Draft for founder review  
**Date:** 2026-04-03 (updated: Agent OS dashboard + design-system section)  
**Sponsors (conceptual):** Engineering (Developer agent), QA, Research, Design, Analytics  

This document is an **implementable plan** to visualize the Sprite Workbench slice of the MV repo: fast onboarding, real dependency structure, diagrams that stay current, change-impact review, and architecture tracking—with **three primary views** and an **AI explanation layer** that is explicitly non-authoritative (explanations) while **graphs remain deterministic** (truth).

---

## 1. Problem statement

| # | Goal | Success looks like |
|---|------|-------------------|
| 1 | Understand the sprite workbench quickly | A scoped map (folders, entrypoints, server vs browser) with no game/room-editor noise unless opted in |
| 2 | See real module relationships | Edges derived from static analysis and declared load order—not hand-drawn boxes |
| 3 | Keep diagrams current | Regenerated on a schedule and on PR; diffs visible in CI |
| 4 | Review change impact | Select a PR or path set → highlighted subgraph + “touched boundaries” |
| 5 | Track architecture | Versioned boundary rules + violations; trend of coupling/churn over time |

---

## 2. Scope (what “sprite workbench” means in this repo)

**In scope (default visualization bundle):**

| Area | Paths (representative) |
|------|-------------------------|
| Browser tool | `tools/2d-sprite-and-animation/` (`index.html`, `app/*.js`, `app/product-shell.css`, `workflows/*.json`, `stage-maturity.json`) |
| Python backend | `scripts/sprite_workbench_server.py`, `scripts/workbench_*.py`, shared helpers the server imports that are workbench-specific |
| Tests & fixtures | `tests/` entries that reference sprite workbench (e.g. `test_sprite_workbench.py`, fixtures under `tests/fixtures/sprite_workbench/`) |
| Persistence contracts | Documented shapes under `projects-data/` as *interfaces* (not full data scan) |

**Out of scope (v1 toggle-off by default):** `index.html` game, `room-layout-editor.html`, other Agent OS dashboards not related to this feature—optional “mono-repo expand” for *additional* products later.

**In scope (UI):** A **dedicated Agent OS dashboard** hosts the three views (Structure, Relationship, Change) for sprite workbench architecture—see §7.

**Reality check — front-end module system:** The workbench loads **ordered `<script src>` tags** in `index.html` (no ES `import` graph). “Module” = **one file = one node** for v1; **load order** is a hard, deterministic edge set. Static **call/coupling** edges are **heuristic** (see §6) and must be labeled as such in the UI.

---

## 3. Three views (product spec)

### 3.1 Structure view — “Where things live and how layers stack”

**Purpose:** Folders, logical layers, declared boundaries, and **load-order dependency** (browser) plus **import graph** (Python).

**Shows:**

- Tree: `app/` vs `workflows/` vs server scripts (grouped).
- **Layer lanes:** e.g. `helpers → stages → runtime → shell` derived from naming + config, not only folders.
- **Boundaries:** Curated rules (see §8)—e.g. “stages must not import `sprite_workbench_server`” (trivially true) or “`product-shell.js` only talks to declared APIs.”
- **Edges (deterministic):**  
  - **Script order graph:** parse `index.html` for `./app/*.js` order → directed edges `A → B` if B loads after A (document as *load-after*, not necessarily “imports”).  
  - **Python:** `import` edges from `ast` parse of scoped files.

**Does not claim:** that load-after implies semantic “depends on” without human/AI interpretation—UI copy must say **load order** vs **static reference**.

### 3.2 Relationship view — “Who calls whom, where it hurts”

**Purpose:** Tighter coupling, hotspots, cycles (where applicable), risky hubs.

**Edge types (versioned in manifest):**

| Edge kind | Source | Deterministic? | Notes |
|-----------|--------|------------------|-------|
| `python_import` | AST | Yes | Full accuracy for top-level imports in scoped files |
| `html_script_order` | HTML parse | Yes | Order of script tags |
| `js_static_ref` | Parser (Acorn) | Mostly | Identifiers referencing global bindings defined in other files; **false positives/negatives** possible—badge edges “heuristic” |
| `shared_global` | Optional manual map | Yes | Curated `window.Foo` registry if introduced later |

**Hotspots (Analytics):** Composite score, e.g. in-degree + churn + cycle participation + boundary violations.

### 3.3 Change view — “What moved, what keeps moving”

**Purpose:** Overlay git history on the same node set as Structure/Relationship.

**Inputs:**

- `git log --name-only` / `git diff` for a ref range or PR.
- Churn: touches per file per month; “unstable” = high churn + high fan-in (configurable).

**Outputs:**

- Heat overlay on graph nodes/edges.
- “Boundary breach” list if changed files cross a forbidden pair (rule engine).
- Optional: link to GitHub compare URL.

---

## 4. AI explanation layer (non-truth)

**Principle:** **Graph JSON + snippets are ground truth for structure;** natural language is **assistive** and must cite node IDs and file paths.

**UX (Design-aligned):**

- Click node → **inspector** in the `sprite-arch` dashboard (right column or slide-over): deterministic facts (path, layer, in/out degree, last changed, linked tests).
- “Explain this module” → calls supervisor or workbench-local endpoint with **fixed prompt template** + **allowed context** (file header, exported-ish top-level functions list from AST, 1-hop neighbors from manifest).
- Follow-up chat: same session; **no silent graph mutation**.

**Guardrails:** Reuse MV “truthfulness / evidence” standing directives; label speculative coupling when AI discusses heuristic edges.

---

## 5. Research: free / OSS tooling matrix

| Tool | Role | Fits MV? | Notes |
|------|------|----------|-------|
| **[dependency-cruiser](https://github.com/sverweij/dependency-cruiser)** | JS/TS dependency rules + **json/html/dot** output | Partial | Best with **imports**; for workbench v1 use for **any** future ES modules or a **thin adapter** that emits synthetic “imports” from HTML order |
| **[Madge](https://www.npmjs.com/package/madge)** | Circular deps, graphs | Partial | Same as above |
| **Acorn** (or `@babel/parser`) | Parse JS to AST | **Yes** | Build **custom** “global reference” edges; small Node script in repo |
| **Python `ast`** | Import graph | **Yes** | Zero extra deps for import edges |
| **pydeps** | Python dep graph SVG | Optional | Nice diagrams; add if py stdlib is too bare |
| **Graphviz `dot`** | Render static SVG/PNG from manifest | **Yes** | CI-friendly; deterministic with pinned layout flags |
| **D3.js / Cytoscape.js / vis-network** | In-browser graph from **static JSON** | **Yes** | Load only generated `manifest.json`; no runtime crawling of repo in browser for v1 |
| **Mermaid** (generated) | Docs + PR comments | Optional | Good for **changelog** diagrams; not the only source of truth |
| **Code2flow** (historical) | Call graphs | Low priority | Often stale/heavy; prefer custom Acorn pass |

**Conclusion:** **No single off-the-shelf tool** covers “monolithic HTML + ordered scripts + Python server.” **Recommended stack:** custom **Node extractor** (HTML + Acorn) + **Python extractor** (ast) → **unified JSON schema** → **Graphviz** and/or **web viewer** reading JSON.

---

## 6. Deterministic pipeline (Engineering)

### 6.1 Outputs (artifacts)

Check into `artifacts/sprite-workbench-arch/` (or `docs/generated/`—pick one; prefer `artifacts/` with `.gitignore` optional for local only, **or** commit snapshots for PR diff—founder choice in §10).

Suggested files:

- `manifest.json` — schema version, git SHA, extractor versions, node/edge lists  
- `structure.dot` / `structure.svg`  
- `relationship-heuristic.dot` — clearly named  
- `churn.json` — numeric series keyed by path  
- `boundaries.json` — rule definitions + current violations

### 6.2 Extractors

1. **`scripts/extract_sprite_workbench_graph.py`** (or split):  
   - Parse `tools/2d-sprite-and-animation/index.html` → ordered script list.  
   - Walk scoped `scripts/workbench_*.py` + server → `python_import` edges.  

2. **`tools/2d-sprite-and-animation/_dev/extract-js-graph.mjs`** (Node, dev-only):  
   - Acorn parse each `app/*.js` → top-level function declarations, assignments to `window.*` if any.  
   - Cross-file identifier use → `js_static_ref` with confidence flag.  

3. **Unified merge** → `manifest.json` with sorted keys for **deterministic** diff.

### 6.3 CI

- Job: run extractors on `push` / `pull_request` when scoped paths change.  
- Fail (QA): optional **architecture rules** (dependency-cruiser-style) implemented as JSON rules on manifest—e.g. “`legacy-*` may not add new edges into `review-export-stage.js`” (example only—needs real policy).

---

## 7. Agent OS dashboard (primary surface) + UI options

### 7.1 Primary: new dashboard in `os-dashboard.html`

The **main** place to use the three views is **Agent OS**, not only a standalone page. This matches how Engineering, QA, and leadership already review toolchain health in one shell.

| Field | Proposal |
|-------|-----------|
| **Dashboard id** | `sprite-arch` (kebab-case; `data-dashboard` / `data-dashboard-view`) |
| **Nav label** | “Sprite arch” or “Workbench architecture” (short for sidebar) |
| **Nav placement** | **Work** group in the left rail, adjacent to **Workbench** (`workbench`)—same product context as sprite tooling |
| **Config** | Extend `DASHBOARDS` with `{ label, color, agents: ['engineering'] }` (primary owner); picker still allows Design, QA, Research, Analytics |
| **Product context** | Add `sprite-arch` to `OS_PRODUCT_CONTEXT_SETS.sprite` (and **`all`** if your convention is to show every dashboard under “all”—mirror how `workbench` is included) |
| **Layout** | One `dashboard-view` panel containing: lede copy → **segmented three-way control** (Structure \| Relationship \| Change\) → main canvas → optional **inspector** column/sheet for node facts + “Explain” (AI) |
| **Data loading** | Prefer **GET** of a generated `manifest.json` (same schema as §6) via **supervisor static allowlist** (pattern already used for `docs/`, markdown viewer) or a thin **`GET /api/sprite-workbench-arch-manifest`** that reads the committed/cached artifact and returns JSON with `Content-Type: application/json`. No non-deterministic graph mutation in that endpoint. |
| **Graph rendering** | Initialize **Cytoscape.js**, **vis-network**, or **D3** inside the dashboard view only—**inputs are manifest JSON**; layout algorithm version pinned in manifest for reproducibility where possible |

**Implementation notes (mirror existing OS patterns):**

- Reuse **mode-pill** or **segmented** styling already in `os-dashboard.html` for the three views (same hover/active tokens as other dashboards).
- Register the view in **`loadDashboardData`** if the manifest should refresh when the dashboard opens (optional fetch + timestamp in UI).
- If the graph library needs a **container with explicit height**, use flex: `min-height: 0` on the scroll region and a token-based `min-height` on the canvas (multiples of **4px** only).

### 7.2 Secondary / dev fallbacks

| Option | Use |
|--------|-----|
| **A — Static HTML** | Generated page under `tools/2d-sprite-and-animation/docs/arch-map.html` for quick local preview **without** Agent OS—still must use **STYLE_GUIDE.md** tokens if it ships in-repo |
| **B — Workbench chrome** | Optional later: link from sprite workbench **Docs** view to Agent OS `sprite-arch` or to static HTML—avoid duplicating full graph UI in two places in v1 |

### 7.3 Design system compliance (`STYLE_GUIDE.md` + `CLAUDE.md`)

All new markup/CSS for this dashboard must follow the **canonical** MV toolchain rules:

| Area | Rule |
|------|------|
| **Color** | Only CSS variables: `var(--bg)`, `var(--panel)`, `var(--text)`, `var(--muted)`, `var(--accent)`, `var(--line)`, `var(--stroke)`, `var(--good)` / `var(--warning)` / `var(--error)` for semantic overlays. **No** ad hoc hex or named colors. |
| **Typography** | `var(--font-display)` for dashboard section titles if used; `var(--font-sans)` for UI; `var(--font-mono)` for paths, commit SHAs, manifest version. Use only **`--font-size-xs` … `--font-size-xl`**. |
| **Spacing** | Padding, margin, gap: **multiples of 4px** only; prefer `--space-*` and `--surface-pad` / `--surface-gap`. |
| **Radius** | `--radius-tight`, `--radius-card`, `--radius-full`, etc.—no off-scale values (e.g. no `6px`). |
| **Controls** | Buttons/inputs: **min-height 44px** (or **28px** compact where an existing pattern exists), **14px** radius for standard controls, explicit **200ms** transitions on named properties—**never** `transition: all`. Hover lift **at most** `translateY(-1px)`. |
| **Focus** | Global `:focus-visible`: `outline: 2px solid rgba(0,232,200,0.35); outline-offset: 2px;` — graph nodes must expose **keyboard-focusable** wrappers or a **side panel** selection model that is focusable. |
| **Panels** | Graph + inspector: use existing **db-** / **panel** patterns (`border: 1px solid var(--line)`, `background: rgba(…)` with tokens, optional `backdrop-filter` only where the shell already does). |
| **Graph aesthetics** | Node fill/stroke from tokens (e.g. default node `var(--os-control)`, selected `var(--accent-soft)` + `var(--accent)` border, warning/hotspot `var(--warning-soft)`). Edge colors: `var(--line)` / `var(--muted)` for deterministic edges; **dashed** or **muted** stroke for heuristic edges—**legend required** in UI copy. |
| **Canvas** | If any **pixel** preview appears inside this dashboard, use **`image-rendering: pixelated`** on that canvas/image. |

**Design agent checklist:** Before merge, cross-check against `STYLE_GUIDE.md` §2–§8 and the **Anti-Pattern** tables in `CLAUDE.md` / `.cursor/rules/frontend-design.mdc`.

---

## 8. Boundaries & architecture rules (QA + Engineering)

- Maintain **`sprite-workbench-architecture-rules.json`** (name TBD): list of allowed/forbidden dependency patterns **on the manifest**, not on hand diagrams.  
- QA defines **smoke checks:** “extractor exit 0”, “manifest schema validates”, “no new `js_static_ref` cycle” (if cycles tracked).  
- **Review checklist** for PRs that touch `app/*.js`: show auto-generated diff of manifest subset.

---

## 9. Analytics metrics

| Metric | Definition | Use |
|--------|------------|-----|
| Churn | Commits touching file in window | Change view heat |
| Fan-in | Edge count to node | Hotspot |
| Boundary violations | Rule engine hits | Tech debt signal |
| Extractor drift | Diff size of manifest week-over-week | Ops health |

Optional: feed summary into existing dashboards JSON later—out of scope for v1 implementation in this plan.

**Agent OS alignment:** Hotspot and churn numbers from §9 can surface as **read-only KPI cards** on the `sprite-arch` dashboard (same `db-card` patterns as other views) with links into **Change** / **Relationship** views.

---

## 10. Phased delivery (implementable)

| Phase | Deliverable | Owner emphasis |
|-------|-------------|----------------|
| **P0** | Scope doc + `manifest.json` schema v1 + HTML script-order + Python imports only | Engineering |
| **P1** | **Agent OS:** register `sprite-arch` dashboard (nav, `DASHBOARDS`, product context), empty shell + **Structure** placeholder + manifest fetch; tokens-compliant layout skeleton | Engineering + Design |
| **P2** | **Structure** view wired to real manifest (graph or tree from JSON); optional Graphviz SVG embed | Engineering + Design |
| **P3** | Acorn-based `js_static_ref` (labeled heuristic) + **Relationship** view | Engineering + Research validation |
| **P4** | Git churn overlay + **Change** view | Engineering + Analytics |
| **P5** | Rule file + CI fail/warn + PR comment with manifest diff | QA + Engineering |
| **P6** | Inspector + **AI explain** (supervisor endpoint, scoped context); legend for edge types | Engineering + Design |

**Deprecated order note:** Previous P1 “static HTML only” is **demoted** to optional dev fallback (§7.2); **P1** is now the Agent OS shell so design review happens in the real chrome early.

Each phase should be **shippable** without the next.

---

## 11. Open decisions (founder)

1. **Commit generated artifacts** vs generate only in CI (affects PR noise vs always having latest in clone).  
2. **Strictness** of `js_static_ref`: show only high-confidence vs all with filters.  
3. **Where AI runs** (supervisor OpenAI vs local-only)—same security model as other MV tools.  
4. Whether to **incrementally migrate** one or two `app/*.js` files to ES modules to unlock dependency-cruiser for those subtrees only.  
5. **Exact nav label** (“Sprite arch” vs “Workbench architecture”) and whether `sprite-arch` appears under **all** product contexts or **sprite + all** only.

---

## 12. Next actions

| # | Action | Owner |
|---|--------|-------|
| 1 | Approve scope + phase order + nav label | Founder |
| 2 | Add P0 extractor + schema + one CI job | Engineering |
| 3 | Add `sprite-arch` `dashboard-view` + nav item + `DASHBOARDS` + `OS_PRODUCT_CONTEXT_SETS` | Engineering |
| 4 | Design review: segmented control + graph canvas + inspector layout (tokens only) | Design |
| 5 | Add Research spike note: evaluate Acorn vs Babel parser for globals in IIFEs | Research |
| 6 | Wire acceptance criteria for “manifest regen on PR” + dashboard loads without JS errors | QA |
| 7 | (Optional) Static HTML fallback with tokens for local dev | Design + Engineering |

---

*This plan is a collaboration artifact: Research supplied the OSS landscape; Engineering the pipeline and Agent OS integration; QA the gates; Design the UX and **STYLE_GUIDE.md** compliance; Analytics the change/hotspot metrics. Implementation tickets should reference this file and update `/decisions/` when major tool choices are locked.*
