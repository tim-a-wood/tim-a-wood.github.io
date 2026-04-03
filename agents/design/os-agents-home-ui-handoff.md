# Design handoff — Agent OS Home dashboard (agent tiles)

**Owner:** Design agent  
**Status:** Approved visual reference — `docs/mockups/agent-os-agents-home-mockup.html`  
**Implementation target:** `os-dashboard.html` + `scripts/os_dashboard_supervisor.py` (`POST /api/agent-chat`)

## Product intent

- **Left navigation:** Under **Start**, a single **Home** link (no agent tiles in the sidebar).
- **Home dashboard:** A normal `dashboard-view` in the **main column** with a responsive **tile grid** of every selectable specialist (same roster as `AGENTS` / orchestration picker order), filtered by **product context** like other OS scoping.
- **Tile click** opens the **modal** (not navigation) with:
  - Agent title and charter path reference in the subtitle.
  - **Quick actions** row: *Focus in workflow panel*, *Open charter* (markdown preview), optional **extra doc links** from config (e.g. Design → STYLE_GUIDE.md), *Open dashboard*.
  - **Task context** — sticky textarea; sent on every chat turn.
  - **Chat** — same bubble / reasoning affordances as issue discussion; backend **OpenAI Chat Completions** with charter + project overview excerpt + task context.

## Mockup-first rule

Specified under the Design standing directive **High-fidelity mockup before UI implementation** (see `agents/design/charter.md`). Revise the mockup first if the founder wants visual changes.

## Engineering notes (non-visual)

- `DASHBOARDS.home` uses `agents: []` so the right-rail picker still lists all agents via `orderedAgentIdsForPicker`.
- Agent identity is validated server-side; charter text is read from `agents/<slug>/charter.md` (capped length).
- `prompts/project_overview.md` is included as capped context when present.
- Product context from the header select is passed through for grounding only.
