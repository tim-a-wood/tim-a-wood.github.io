# Design handoff — Agent OS left-rail Agents home

**Owner:** Design agent  
**Status:** Approved visual reference — `docs/mockups/agent-os-agents-home-mockup.html`  
**Implementation target:** `os-dashboard.html` + `scripts/os_dashboard_supervisor.py` (`POST /api/agent-chat`)

## Product intent

- A dedicated **Agents** block **above** the **Dashboards** section in the left navigation.
- **Two-column tile grid** of every selectable specialist agent (same roster as `AGENTS` / orchestration picker order).
- **Tile click** opens a **modal** (not a new dashboard view) with:
  - Agent title and charter path reference in the subtitle.
  - **Quick actions** row: at minimum *Focus in workflow panel*, *Open charter* (markdown preview), plus **one extra link per agent** where defined in implementation config (e.g. Design → STYLE_GUIDE.md).
  - **Task context** — a sticky textarea; contents are sent to the server on every chat turn as grounding for “the given task.”
  - **Chat** — same bubble / reasoning affordances as issue discussion; backend uses **OpenAI Chat Completions** with injected charter + project overview excerpt + task context.

## Mockup-first rule

This feature was specified under the Design standing directive **High-fidelity mockup before UI implementation** (see `agents/design/charter.md`). The live UI must match the mockup unless the founder explicitly approves a revision to the mockup first.

## Engineering notes (non-visual)

- Agent identity is validated server-side; charter text is read from `agents/<slug>/charter.md` (capped length).
- `prompts/project_overview.md` is included as capped context when present.
- Product context from the header select is passed through for grounding only.
