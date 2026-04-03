# Sprite Workbench — Architecture Visualization (Cross-Team Plan)

**Status:** Draft for founder review  
**Date:** 2026-04-03  
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

**Out of scope (v1 toggle-off by default):** `index.html` game, `room-layout-editor.html`, Agent OS dashboards—optional “mono-repo expand” later.

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

- Click node → side panel: deterministic facts (path, layer, in/out degree, last changed, linked tests).
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

## 7. UI options (Design)

**Option A — Minimal (fastest):** Generated **SVG + static HTML** page under `tools/2d-sprite-and-animation/docs/arch-map.html` using tokens from `STYLE_GUIDE.md`; three tabs switch which edge sets are visible.

**Option B — Integrated:** A “Architecture” subview inside the workbench (`view-docs` or new rail) loading **only** checked-in JSON (no filesystem access from browser).

**Design requirements:** Dark theme, tokens only, 4px grid, no `transition: all`, focus-visible—per `STYLE_GUIDE.md`.

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

---

## 10. Phased delivery (implementable)

| Phase | Deliverable | Owner emphasis |
|-------|-------------|----------------|
| **P0** | Scope doc + `manifest.json` schema v1 + HTML script-order + Python imports only | Engineering |
| **P1** | Graphviz SVG + static HTML viewer (Structure view) | Engineering + Design |
| **P2** | Acorn-based `js_static_ref` (labeled heuristic) + Relationship view | Engineering + Research validation |
| **P3** | Git churn overlay + Change view | Engineering + Analytics |
| **P4** | Rule file + CI fail/warn + PR comment with manifest diff | QA + Engineering |
| **P5** | AI explain panel (supervisor endpoint, scoped context) | Engineering + Design |

Each phase should be **shippable** without the next.

---

## 11. Open decisions (founder)

1. **Commit generated artifacts** vs generate only in CI (affects PR noise vs always having latest in clone).  
2. **Strictness** of `js_static_ref`: show only high-confidence vs all with filters.  
3. **Where AI runs** (supervisor OpenAI vs local-only)—same security model as other MV tools.  
4. Whether to **incrementally migrate** one or two `app/*.js` files to ES modules to unlock dependency-cruiser for those subtrees only.

---

## 12. Next actions

| # | Action | Owner |
|---|--------|-------|
| 1 | Approve scope + phase order | Founder |
| 2 | Add P0 extractor + schema + one CI job | Engineering |
| 3 | Add Research spike note: evaluate Acorn vs Babel parser for globals in IIFEs | Research |
| 4 | Wire acceptance criteria for “manifest regen on PR” | QA |
| 5 | Mock Structure tab in static HTML (tokens) | Design |

---

*This plan is a collaboration artifact: Research supplied the OSS landscape; Engineering the pipeline; QA the gates; Design the UX constraints; Analytics the change/hotspot metrics. Implementation tickets should reference this file and update `/decisions/` when major tool choices are locked.*
