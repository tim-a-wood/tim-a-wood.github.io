# Handover: Map MVP — Expert Subagents, Training, Research, and Evidence

**Date:** 2026-04-09  
**Owners:** Development (Engineering) · QA · Orchestration (delegation)  
**Canonical source:** `prompts/project_plan.md` → section **Map MVP Execution Plan** → **Execution standard — expert subagents, training, research, and evidence** (keep in sync when the plan changes)  
**Status:** Active — applies to all Map MVP activities (10–15 minute in-game run track)

---

## Purpose

Orchestration and implementing agents must **choose subagents by expertise**, complete **mandatory pre-flight research**, and ship an **evidence pack** with each handoff, PR, or activity closure. This prevents default generalist work where a specialist fit exists and documents research so prior findings are not ignored or duplicated.

---

## Role ownership

| Role | Charter / status | Map MVP focus |
|------|------------------|---------------|
| **Development (Engineering)** | `agents/engineering/charter.md`, `engineering-status.json` | Implementation and refactors in `index.html`, `tests/`, CI-aligned commands |
| **QA** | `agents/qa/charter.md`, `qa-status.json` | Release readiness, test strategy, regression evidence, severity triage (especially Activities 5–10) |

Engineering executes code; QA validates against frozen specs and tests—per charters, not ad hoc.

---

## 1. Choose subagents by expertise (not convenience)

Before splitting work, classify the task:

| Need | Prefer | Avoid |
|------|--------|--------|
| Wide repo search, file discovery, “where is X?” | Readonly explore / codebase map | Guessing paths without searching |
| Git, CI, scripted verification | Shell specialist | Manual copy-paste only |
| Library index, prior scans, competitive or technical research | **Research** subagent + `research/library/INDEX.md` | Re-deriving findings already in the library |
| Multi-step implementation touching `index.html` / `tests/` | Development-led implementation (single agent or `generalPurpose` with explicit file list) | Parallel edits without a contract doc read first |

**Tooling note:** In Cursor, delegation may use the Task tool with types such as `explore`, `shell`, `generalPurpose`, `Research`—match type to the table above.

**Cross-functional alignment**

- Navigation / comprehension–heavy work (e.g. Activity 7): involve **Level Design** review inputs where appropriate.
- Progression logic (Activities 3–4, 6): stay aligned with **Game Systems** and frozen specs.

---

## 2. Training and mandatory research (pre-flight)

Anyone executing or reviewing Map MVP work completes the following **before** substantive edits and cites it in the evidence pack:

1. **`AGENTS.md` — Research Library protocol:** Search `research/library/INDEX.md` for relevant keywords (e.g. `gate`, `progression`, `Phaser`); read matching entries; check `research/dashboard.md`; check `/decisions/` so resolved choices are not re-litigated.
2. **Frozen contracts for this track:** At minimum, the activity’s authoritative docs, e.g. `docs/map-mvp-constraints.md`, `docs/map-graph-v1.md`, `docs/progression-unlocks-v1.md`, `docs/gate-state-spec-v1.md`, `docs/pacing-tuning-v1.md` (as applicable).
3. **QA:** `tests/acceptance_tests.md` and gate-state / sequence coverage implied by `docs/gate-state-spec-v1.md` (transition matrix, invalid paths).
4. **Development:** `CLAUDE.md` / `STYLE_GUIDE.md` for any tool UI touch; `tests/README.md` and existing `tests/game-logic.test.js` patterns before changing progression helpers.

**Negative search:** If nothing in the library applies, the evidence pack must still include a short **INDEX grep / read result** (keywords tried, no match) so absence of prior art is documented, not assumed.

---

## 3. Evidence pack (required for handoff, PR, or activity closure)

Each completed activity (or PR that advances one) must leave **verifiable** evidence—not claims:

| Evidence type | Attach |
|---------------|--------|
| **Research** | Paths + titles of INDEX entries read, or grep/log of keywords searched; list of `decisions/` files consulted |
| **Subagent routing** | Table or bullets: task slice → subagent type or owner role → output artifact (path or transcript reference). If no subagents were used, state **why** (e.g. single small change, one file) |
| **Implementation** | Commit hash or PR link; for logic changes, `node --test tests/game-logic.test.js` (or relevant test file) with exit status and command as run locally or in CI |
| **QA / release** | Updates to `tests/test_report.md` per repo rules; for browser-only checks (e.g. Activity 5 smoke), dated notes with **what was observed** (not “looks fine”). Visual claims: **`AGENTS.md` Visual Validation Honesty Gate** (inspect saved screenshots if asserting UI quality) |
| **Playtests (Activities 9–10)** | Observer notes, aggregates, triage board—per plan bullets—under `docs/` or `artifacts/` with a stable filename, referenced from the plan or status JSON |

**Definition of done for “trained and researched”:** Pre-flight list is satisfied **and** the evidence pack for that slice references it.

---

## Related repository rules

- `AGENTS.md` — Research Library mandatory check; My Actions review after tasks; Visual Validation Honesty Gate
- `tests/acceptance_tests.md` / `tests/test_report.md` — manual and automated test accounting

---

## Introduced in git

This handover documents the execution standard added to the project plan. Introducing commit: `a65710bb` (`docs(plan): Map MVP execution standard for expert subagents and evidence`). Subsequent edits may amend this file or `prompts/project_plan.md`; prefer a single source of truth in the plan and a short pointer here.
