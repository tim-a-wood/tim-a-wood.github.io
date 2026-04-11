# Intense development orchestration (canonical)

**Purpose:** A reusable, host-agnostic workflow for high-risk or cross-cutting work: orchestrator-led scoping, minimum **Developer** + **QA** specialists, optional domain experts, mandatory research gates, implementation spec with atomic tasks, verification between slices, and founder checkpoints.

**Use this document when:** Refactors or features are large, correctness-critical, touch many files, need strong test discipline, or the user explicitly asks for multi-agent / “intense” delivery.

**Cross-platform:** Cursor, Claude Code, and Codex do not share one skill runtime. Treat this file as the **single source of truth**. Each host should use a short entry skill (or project rule pointer) whose first step is: **read this path in the active repo** —`docs/skills/intense-dev-orchestration.md`.

**Repository alignment (MV / Sprite Workbench):** Map MVP execution detail and evidence expectations stay in `prompts/project_plan.md` (Map MVP section) and `docs/handover-map-mvp-subagent-research-evidence.md`. This skill **extends** that pattern to any intense initiative, not only Map MVP.

---

## Operating modes

| Mode | When | Flow |
|------|------|------|
| **Intense** | High risk, multi-file, strict QA, or explicit request | Full pipeline below |
| **Light** | Small fix, single file, obvious tests | Single implementer + quick QA checklist; still read decisions/index if non-trivial |

---

## Roles

| Role | Responsibility |
|------|----------------|
| **Orchestrator** | Intake, classification, roster, integrate outputs, resolve conflicts. **Does not** replace specialist judgment or silently expand scope. |
| **Developer** | Implementation aligned with project standards, stack, and charters; owns code changes and local verification. |
| **QA** | Test strategy, TDD alignment where applicable, V&V between slices, regression and acceptance mapping. |
| **Research** (as needed) | Library index, prior scans, external API or version facts; short spikes with a stop rule. |
| **Domain specialists** (as needed) | Invoked only when **triggers** fire (see below). |

**Delegation:** Use each host’s native task/subagent mechanism. The contract is **outputs and gates**, not a specific tool name.

---

## Specialist triggers (add beyond Dev + QA)

Invoke extra specialists when the task **primarily** depends on that domain:

| Trigger | Example specialist |
|---------|-------------------|
| Raster/UI truth, screenshot acceptance, layout fidelity | Computer vision / visual review (human or dedicated agent) |
| Joints, IK, simulation, physical motion | Kinematics / physics |
| Filters, fusion, prediction, noisy sensors | State estimation / numerics |
| Auth, secrets, user data | Security |
| Latency budgets, hot paths | Performance |

Avoid **specialist sprawl:** default roster is Dev + QA (+ Research for non-trivial unknowns).

---

## Phase 1 — Intake and classification

Orchestrator captures:

- **Goal** and explicit **non-goals**
- **Constraints** (time, compatibility, “must not break X”)
- **Class:** product / infra / research / visual / numerical / other
- **Frozen inputs:** specs, decision logs, mocks (if UI)

Output: a one-paragraph **problem statement** the whole team can reuse.

---

## Phase 2 — Roster and pre-scope

Each assigned specialist states:

- **Scope I own** / **out of scope**
- **Assumptions** and **unknowns**
- **Must read** (project-specific), e.g.:
  - `AGENTS.md` (authority, research protocol, visual honesty gate)
  - `STYLE_GUIDE.md` / design charters for UI
  - `research/library/INDEX.md`, `research/dashboard.md`, `/decisions/`
  - Feature decision logs (e.g. `decisions/2026-03-31-room-environment-quality-pass.md` when relevant)
  - `prompts/project_plan.md`, `prompts/project_overview.md` when aligning with roadmap

---

## Phase 3 — Research plan

- **Mandatory:** decisions, security-sensitive areas, breaking APIs, anything already in the research library — **read before building**
- **Elective:** deeper topics; use a **time box** or **stop rule** (e.g. “enough to choose A vs B”)

**Research output (short):**

1. Conclusion (what we believe)
2. Sources (paths, docs, tickets)
3. Open questions
4. Recommended next step or experiment

---

## Phase 4 — Implementation specification

Single consolidated spec (doc or message) containing:

- Architecture or data-flow sketch
- **Files / modules** expected to change
- **Contracts** (APIs, schemas, events)
- **Test plan** (new tests, fixtures, acceptance rows)
- **Rollback** or feature-flag note if deployment-sensitive
- **Atomic tasks** — each with a clear **done** definition

### Slice contract (per slice)

For each delivery slice, define:

- **Inputs** (from prior slice or repo)
- **Outputs** (artifacts, behavior)
- **Acceptance criteria** (test + any manual/visual)
- **Out of scope** for this slice

### Risk register (lightweight)

Top risks (max ~3), each with **mitigation**. Revisit after each slice.

---

## Phase 5 — Execute in slices

Per slice:

1. **Implement** (Developer)
2. **V&V** (QA): unit/integration per project harness; map to `tests/acceptance_tests.md` where applicable; update `tests/test_report.md` per project rules when behavior changes
3. **Visual validation** (if appearance is a primary success criterion): follow project **visual validation honesty gate** in `AGENTS.md` — no positive visual claims without inspecting the cited artifact
4. **Evidence:** commands run, brief result summary; screenshots only when the slice is visual.

**Between slices:** orchestrator checks risk register and spec drift.

---

## Phase 6 — Founder checkpoint

Between slices or before major pivots, use **short interview-style prompts** (plain English):

- Prefer **decision-forcing** questions (tradeoffs, priorities) over open brainstorming unless discovering requirements
- Suggested shape: **3–7** questions, each answerable in a sentence or binary choice
- **Capture** the outcome in one line (decision log, ticket, or spec) so the next slice does not re-litigate

---

## Failure modes to avoid

| Mode | Mitigation |
|------|------------|
| Parallel edits without a contract | Serialize conflicting ownership or one implementer + read-only explorers |
| Orchestrator implements large diffs | Delegate implementation to Developer unless explicitly single-agent |
| Research without stop rule | Time box; ship slice with documented “deferred question” |
| QA as rubber stamp | QA defines V&V per slice in the spec |
| Claiming visual success unseen | Enforce honesty gate; involve CV/visual specialist when pixels matter |

---

## Optional: Evidence pack checklist

Use when handing off or closing a milestone:

- [ ] Problem statement and final spec (or link)
- [ ] Research bullets (if any)
- [ ] Tests run (command + pass/fail summary)
- [ ] Acceptance / test report updates (if required by repo)
- [ ] Decision log updates (if substantive choices changed)
- [ ] Screenshots or paths to visual artifacts (only if relevant)

---

## Maintenance

- When Map MVP **execution standard** changes, update `prompts/project_plan.md` and `docs/handover-map-mvp-subagent-research-evidence.md`; then adjust **Repository alignment** bullets here only if this skill’s scope changes.
- Personal or project **SKILL.md** stubs on Cursor / Codex / Claude should keep a **stable description** (third person, WHAT + WHEN) and instruct the agent to open **this file** first.
