# Room layout validation (Level 1–3)

**Status:** Canonical technical reference for this repository.  
**Audience:** Engineers, technical writers, and agents maintaining the room editor.  
**Scope:** Describes validation **as implemented or planned** in `room-layout-editor.html`; not an external industry standard.

---

## Not an external “standard”

The three **levels** and **check IDs** (`L1-001`, `L2-001`, …) are **project conventions** for *Ashen Hollow* / Sprite Workbench tooling. They are **not** ISO, W3C, or engine-level standards. Other games or tools may use similar *ideas* (structural vs heuristic checks), but **these IDs and thresholds are specific to this repo** unless copied explicitly.

When publishing **end-user documentation** (help center, in-app tips), paraphrase for players (“structural issues” vs “layout suggestions”) and link or repeat the **User docs placeholder** section at the bottom of this file.

---

## Traceability

| Artifact | Role |
|----------|------|
| This file | Canonical definitions, IDs, severity, and doc placeholders |
| `docs/room-editor-overhaul-plan.md` | Phase 4 — original product intent for the pipeline |
| `docs/room-editor-agent-task-spec.md` — Sprint 3 | Agent implementation spec (tasks 3.1–3.2) |
| `room-layout-editor.html` | `validateLayout(data)`, `VALIDATION_L2`, `renderValidationResults`, UI |

**Runtime tuning:** Level 2 distance thresholds are in the `VALIDATION_L2` object (exposed as `window.VALIDATION_L2` in the browser).

---

## Level summary

| Level | Name | Intent | In UI / code today |
|-------|------|--------|---------------------|
| **1** | Structural correctness | Data is internally consistent and loadable (rooms, links, IDs, spawn). | **Yes** — failures are **`error`** severity. |
| **2** | Traversal sanity | Heuristic hints (platform steps, gaps, interactable proximity). | **Yes** — findings are **`warning`** severity (advisory). |
| **3** | Progression & content sanity | Branch order, soft-locks, full-graph progression. | **Planned** — report shape exists in overhaul plan; **not** implemented in `validateLayout` yet. |

---

## Level 1 — Structural checks (`L1-*`)

All are **`error`** severity when failed (they increment `summary.errors`).

| ID | Rule (summary) |
|----|----------------|
| `L1-001` | No duplicate room IDs |
| `L1-002` | Each room has at least 3 polygon vertices |
| `L1-003` | Door `targetRoom` and edge-link targets resolve to existing rooms |
| `L1-004` | Edge links reference valid edge indices for source and target polygons |
| `L1-005` | Element IDs unique within a room (platforms, doors, keys, abilities, moving platforms) |
| `L1-006` | At least one room has a valid `playerStart` |

**Implementation:** `validateLayout` → `fail(1, 'L1-00x', …)`.

---

## Level 2 — Traversal heuristics (`L2-*`)

All are **`warning`** severity (advisory; they increment `summary.warnings`). Pairing logic and numbers may change; see **`VALIDATION_L2`** in `room-layout-editor.html`.

| ID | Rule (summary) |
|----|----------------|
| `L2-001` | Vertical step to nearest “related” platform below exceeds configured max |
| `L2-002` | Horizontal gap between paired platforms exceeds configured max (only meaningful if gap limit &lt; pair cap) |
| `L2-003` | Door / key / ability farther than configured distance from any platform (rough proximity check) |

**Note:** Level 2 does **not** prove reachability or fair difficulty — only flags items for human review.

---

## Level 3 — Progression (`L3-*`) — planned

Examples from `room-editor-overhaul-plan.md` (not yet in `validateLayout`):

- Branch completion ordering / no soft-locks  
- Final gate consistency with progression state  

When implemented, this doc should gain an **`L3-*` table** and the JSON export contract should include `level_3` in the validation report.

---

## JSON report shape (implemented fields)

`validateLayout` returns (simplified):

```json
{
  "run_at": "<ISO-8601>",
  "level_1": { "passed": true, "checks": [ { "id": "L1-001", "room": "R1", "severity": "error", "message": "…" } ] },
  "level_2": { "passed": true, "checks": [ { "id": "L2-001", "room": "R2", "severity": "warning", "message": "…" } ] },
  "summary": { "errors": 0, "warnings": 0 }
}
```

`level_3` is reserved for a future iteration (see overhaul plan export examples).

---

## User-facing documentation (placeholder)

**Trace ID:** `DOC-ROOM-VALIDATION-001`

| Item | Status |
|------|--------|
| **Target surface** | TBD — e.g. Sprite Workbench “Room Creation” help, GitHub Pages docs, or in-app “?” panel |
| **Owner** | TBD |
| **Source for copy** | This file + non-technical summary of Level 1 vs 2 vs 3 |
| **Must explain** | Warnings ≠ broken game; Level 1 should be fixed before shipping shared JSON; Level 2 is suggestive |
| **Link to code** | Optional: mention “thresholds may be tuned per project” without exposing `VALIDATION_L2` names to casual users |

**Draft outline for user docs:**

1. What “Run validation” does in one sentence.  
2. **Red / structural** vs **yellow / suggestions** (map to Level 1 vs 2).  
3. “Level 3” not shown yet — future progression checks.  
4. How to act on a result (jump to room, fix data, or dismiss advisory warnings).  

---

## Changelog (doc maintenance)

| Date | Note |
|------|------|
| 2026-03-27 | Initial canonical doc; `DOC-ROOM-VALIDATION-001` placeholder for user docs. |
