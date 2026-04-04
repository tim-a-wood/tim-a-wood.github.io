# Sprite Workbench Architecture Visualization — Master Feature Plan

**Status:** M2 — Agent OS shell **shipped**; **M3** (Structure live) next  
**Date:** 2026-04-03  
**Companion docs:** [Technical / extraction plan](./sprite-workbench-architecture-visualization-plan.md) · **HI-FI mockup:** [agent-os-sprite-arch-dashboard-mockup.html](../mockups/agent-os-sprite-arch-dashboard-mockup.html)

This document is the **end-to-end program plan**: who does what, in what order, how pieces connect, and how we know we are done. The companion doc stays the **technical contract** for extractors, manifest schema, and CI. **Design** owns the linked **hi-fi mockup** as the visual source of truth before engineering wires `os-dashboard.html`.

---

## 1. Vision (one paragraph)

Give founders and specialists a **truthful, refreshable map** of the sprite workbench (browser + Python server) inside **Agent OS**, with three lenses (structure, coupling, change), **deterministic** graph data from the repo, and an **AI inspector** that explains without replacing the graph—so onboarding, reviews, and refactors stay aligned with real code.

---

## 2. Success criteria (launch)

| ID | Criterion | Measurable signal |
|----|-----------|-------------------|
| SC-1 | Scoped slice only | Default manifest excludes game/room-editor; toggle documented |
| SC-2 | Deterministic core | Same commit SHA → same manifest bytes (sorted keys, pinned extractor version) |
| SC-3 | Three views ship | Structure, Relationship, Change each render from same manifest |
| SC-4 | OS integration | `sprite-arch` dashboard live in nav; product context includes sprite (and `all` if chosen) |
| SC-5 | Staleness visible | UI shows manifest `generated_at` + git SHA; CI regen on scoped path change |
| SC-6 | Heuristic honesty | Non-import JS edges labeled in UI + legend; AI cannot claim they are imports |
| SC-7 | Design parity | shipped UI matches **approved** hi-fi mockup (tokens, layout, hierarchy) within agreed deltas |
| SC-8 | QA gate | Extractor tests + schema validation in CI; optional architecture rules fail/warn |
| SC-9 | Inspector symbol depth | **I1** (`exports` in manifest): deterministic lists only; capped and sorted; **I2** (deep symbols): optional, collapsed, confidence-labeled — never implied as import edges |

*Inspector tiers I1/I2 are defined in the companion technical plan §4.1 (not the same labels as phased P0–P6).*

---

## 3. Workstreams and owners

| Workstream | Owner (agent) | Deliverables |
|------------|---------------|--------------|
| **A — Design** | Design | **HI-FI mockup** (`docs/mockups/agent-os-sprite-arch-dashboard-mockup.html`); component notes (legend, tabs, inspector, empty states); accessibility notes (focus, keyboard) |
| **B — Data & extractors** | Engineering | P0 manifest schema; HTML script-order + Python `ast` imports; merge script; artifact path policy; **I1** per-node `exports` when extractors ready; **I2** only if founder approves |
| **C — Agent OS UI** | Engineering + Design | `sprite-arch` view in `os-dashboard.html`; fetch manifest; graph library integration; inspector + view switcher per mockup |
| **D — CI & QA** | QA + Engineering | Workflow job; schema test; optional rules file; PR checklist |
| **E — Research** | Research | Acorn/Babel spike on IIFE globals; short write-up in `research/library/` or appendix |
| **F — Analytics** | Analytics | Churn/hotspot definitions in manifest or sidecar JSON; KPI card copy + thresholds (advisory) |
| **G — AI layer** | Engineering | Scoped explain endpoint + prompt template; no graph mutation |

Design **does not** implement production `os-dashboard.html` in this phase; Design **does** deliver mockup **first** so Engineering implements against pixels + tokens.

---

## 4. End-to-end architecture (logical)

```
┌─────────────────────────────────────────────────────────────────┐
│  CI / local: extractors (Node + Python) → manifest.json       │
│  (+ optional .dot / churn.json)                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ commit or serve
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Repo artifact OR GET /api/...  (supervisor read-only)            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Agent OS — dashboard `sprite-arch`                               │
│  • View switcher: Structure | Relationship | Change                 │
│  • Graph canvas (library renders manifest)                        │
│  • Inspector: facts + “Explain” → AI (context-bounded)            │
└─────────────────────────────────────────────────────────────────┘
```

**AI path (non-authoritative):** Inspector sends `node_id`, manifest slice, allowed file snippet → model → streamed or block reply; graph JSON unchanged.

---

## 5. User journeys (acceptance narratives)

1. **New engineer:** Opens Agent OS → Workbench architecture → Structure → sees folders/load order → clicks `workbench-runtime.js` → inspector shows path + in-degree → Explain summarizes role.
2. **Reviewer before merge:** Opens Change → selects branch range → touched nodes highlight → boundary violations list if any.
3. **Maintainer:** Opens Relationship → filters heuristic edges → identifies hub → files issue to split module.
4. **Design QA:** Compares shipped dashboard to mockup in three breakpoints (1280, 900, 600) — spacing, tokens, focus rings.

---

## 6. Milestones (ordered)

| Milestone | Contents | Depends on |
|-----------|----------|------------|
| **M0 — Design lock** | Founder approves hi-fi mockup + view switcher + inspector layout | Mockup complete |
| **M1 — Manifest P0** | Schema + extractors + one committed sample manifest | M0 for UI copy alignment |
| **M2 — OS shell** | Nav + `sprite-arch` dashboard shell + **stub** manifest fetch + error state + view tabs (Structure / Relationship / Change) placeholders | M0 (mockup); M1 nice-to-have for real manifest bytes — **done** (stub manifest + supervisor allowlist + `loadSpriteArchManifest`) |
| **M3 — Structure live** | Graph from manifest (load-order + python layers); inspector **I1 exports** when manifest includes `exports` | M2 |
| **M4 — Relationship** | Heuristic JS edges + legend + filters | M3 + Research spike |
| **M5 — Change** | Git overlay + churn heat | M3 |
| **M6 — CI + rules** | Regen job + tests + optional fail | M1 |
| **M7 — AI explain** | Endpoint + inspector integration | M3 |

Parallel tracks: **E (Research)** can start at M0; **F (Analytics)** can finalize KPI formulas during M1–M3.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Heuristic JS graph misleads | Legend + default-off or low-emphasis styling; docs; AI must cite edge kind |
| Manifest drift / forgot regen | CI + visible stale banner if SHA mismatch optional |
| Graph perf on large repos | Manifest caps + lazy expand; v1 scope is workbench-only |
| Mockup–prod drift | Design sign-off checklist; Engineering PR template links mockup |
| Third-party graph lib token drift | Wrap theme in one adapter module mapping manifest kinds → CSS vars |
| Inspector overload (too many symbols) | **I1** cap + collapse; **I2** off by default; graph stays file-level |

---

## 8. Open decisions (rollup)

See companion doc §11. Add: **mockup approval** as a formal gate (M0).

---

## 9. File map (after implementation)

| Artifact | Purpose |
|----------|---------|
| `docs/mockups/agent-os-sprite-arch-dashboard-mockup.html` | Design HI-FI reference |
| `docs/sprite-workbench-architecture-visualization-plan.md` | Extractors, schema, tools |
| `docs/sprite-workbench-architecture-visualization-master-plan.md` | This program plan |
| `artifacts/sprite-workbench-arch/manifest.json` | Generated truth (policy TBD) |
| `os-dashboard.html` | Production dashboard |
| `scripts/extract_sprite_workbench_graph.py` (TBD) | Python part |
| `tests/…` (TBD) | Schema + golden manifest |

---

## 10. Next steps (immediate)

1. **Founder:** Review HI-FI mockup in browser; note changes.  
2. **Design:** Revise mockup per feedback; optional inspector wireframe for **I1** collapsed/expanded.  
3. **Engineering:** **M3 next:** wire Structure view to real manifest (extractors / M1); graph library. M2 delivered: `sprite-arch` in `os-dashboard.html`, stub `artifacts/sprite-workbench-arch/manifest.json`, supervisor static allowlist.  
4. **QA:** PR checklist + schema test (stub manifest JSON valid).  
5. **Research:** Acorn spike (2–4h) on three `app/*.js` files — prioritize **I1** export list accuracy before **I2**.

---

*When implementation starts, log major choices in `/decisions/` and keep this file’s milestone table in sync.*
