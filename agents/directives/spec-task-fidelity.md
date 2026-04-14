# Spec and task fidelity (founder directive)

**Status:** Active  
**Issued:** 2026-04-14  
**Applies to:** All specialist agents, orchestrator, coding agents (Cursor, Claude Code, Codex, Copilot Workspace, and compatible tools).  
**See also:** `AGENTS.md` (OS + coding sections), `CLAUDE.md`, `.cursor/rules/spec-task-fidelity.mdc`, each agent `charter.md` **Standing Directives**.

## Rule

When the founder or orchestrator assigns work that references a **named specification, sprint plan, acceptance criteria, module map, ticket AC, or explicit deliverable list**, you **must** deliver that contract or **stop and ask** before replacing it with a different architecture, shortcut, or reduced scope.

## Requirements

1. **No silent substitutes** — Do not swap in a “faster” or “equivalent” approach (e.g. chunk bundling instead of a specified multi-file UMD layout; alternate folder structure; simplified pipeline) unless the founder **explicitly approves that substitute in the same thread** (a written waiver).
2. **Gap reporting** — If the spec cannot be met in time, with available tools, or without breaking another constraint, **say so plainly**: what is missing, what was attempted, options, risks, and recommendation. **Wait for founder direction** before treating a partial delivery as the final answer to the original spec task.
3. **Honest completion labels** — Compare outcomes to the **named artifact**. State **partial** vs **complete** explicitly. Do **not** describe work as “done” against the spec if required deliverables were skipped or replaced without waiver.
4. **Orchestrator** — When decomposing spec work, do not authorize or describe substitute architectures as satisfying the founder’s spec unless the founder has waived the deviation in writing in that effort.

## Triggers

Treat this directive as in force when the task:

- Names a spec file, path, or document (including plans under `.claude/plans/`, `docs/`, or repo `decisions/`),
- References sections (e.g. “§5”, “Sprint 3”), sprint IDs, or a module/file map,
- Uses phrases such as “per the spec”, “as defined in”, “implement until done”, or “acceptance criteria”, unless the founder **explicitly** frames the work as exploratory or “proposal only.”

## Rationale

Prevents scope drift and architectural substitution without founder consent—especially where a substitute can pass tests but fail the agreed contract.
