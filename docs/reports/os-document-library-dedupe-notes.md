# OS document library — dedupe notes

Generated: `2026-04-03T12:41:05Z`

## Relationship tiers (not duplicates)

- docs/brand-charter.html is the concise executive anchor; docs/mv-business-brand-guide-pamphlet.html is the expanded operational system. They complement each other.
- docs/room-layout-validation.md and tools/2d-sprite-and-animation/docs/Room-Layout-Validation.md share a topic but are not byte-identical; keep both until converged.
- Agent charters (agents/*/charter.md) overlap thematically with AGENTS.md / CLAUDE.md at different altitudes: charters = role scope; AGENTS/CLAUDE = tool enforcement.
- Documents under .claude/worktrees/ are excluded from this catalog to avoid stale duplicates; treat repo-root paths as canonical.
- To retire a policy: use Archive on a card (supervisor) or scripts/archive_policy_document.py — files move to docs/archived-policies/ with a reference report; other files are not auto-edited.

## Filename clusters

### `dashboard-standard.md`
- **different bytes**
  - `agents/design/dashboard-standard.md`
  - `agents/directives/dashboard-standard.md`
- Same filename, different contents — review both; do not assume parity.
