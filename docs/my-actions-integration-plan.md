# My Actions — Agent OS integration plan

Engineering handoff: integrate the **My Actions** board from `my-actions-mockup.html` into `os-dashboard.html`, backed by live `*-status.json` data.

## 1. Target UX (frozen from mockup)

- **Workflow columns (horizontal):** Not Started → In Work → Complete (sticky header row).
- **Category rows (vertical):** Blocking → Decisions → Awaiting Review — full-width section titles with colored underlines, three drop lanes aligned under the column headers.
- **Drag-and-drop:** HTML5 DnD; a card may only move **between workflow columns** within the **same category row** (same `data-type`).
- **Counts:** Per-column totals, per-category totals across columns; optional nav badge = items not in **Complete** (founder “still open” work).

Reference implementation: `my-actions-mockup.html` (structure, CSS, and `updateCounts` / zone wiring).

## 2. Data sources today

| Source | Location in JSON | Maps to category |
|--------|------------------|------------------|
| Founder decisions | `founder_decisions[]` per agent file | **Decisions** by default; subset **Blocking** when flagged (see §3) |
| Needs review | `priorities[]` where `status === "needs-review"` | **Awaiting Review** (use `risk` for HIGH/MED chip) |

**Aggregation:** Scan the same static list the dashboard already uses for agent status files (repo root `*-status.json`, excluding non-agent files if any). Reuse or extend the existing status fetch/cache path in `os-dashboard.html` rather than duplicating fetch logic.

**Stable identity (required):** Kanban persistence (§4) needs a stable key per card.

- **Review items:** `"{agentSlug}:priority:{id}"` using the priority’s `id` from that file.
- **Founder decisions:** Prefer an explicit optional field `my_actions_id` (string, unique within the file) on each `founder_decisions` object. If absent, derive a deterministic fallback: `"{agentSlug}:founder:" + stableHash(title + "\0" + (source||"") + "\0" + (note||""))` (e.g. FNV-1a or simple string hash in JS) so refactors that don’t change text keep the same key.

**Orchestrator note:** `orchestration-status.json` may synthesize overlapping themes with other agents; de-dupe in the aggregator by **stable id** (or normalized title) so the board does not show duplicate cards unless product wants duplicates.

**Agent IDs:** Use the same keys as `AGENTS` in `os-dashboard.html` (e.g. `orchestrator`, not `orchestration`; `engineering` with UI label **Development** per `AGENTS.engineering.label`; `audio` → label **Audio Director**).

## 3. Blocking vs Decisions (founder_decisions)

`founder_decisions` objects today: `{ title, note, source? }` — no type.

**Recommended approach (a + b):**

1. Add optional boolean **`blocking`** on `founder_decisions` entries that actively unblock other work when the founder acts.
2. Optionally add **`my_actions_id`** (string) for stable keys and future deep links.

**Classification rules in the UI:**

- `blocking === true` → **Blocking** row.
- Else → **Decisions** row.

**Default:** `blocking` omitted → treat as **Decisions** (not blocking).

**Migration:** Tag the two orchestration items that currently match mockup “blocking” (`room file versioning…`, `Brand Guide…`) with `"blocking": true` in `orchestration-status.json` (or the owning file if split later). Validate with `python3 scripts/validate_status_files.py` after extending the validator to allow unknown properties on `founder_decisions` (today `founder_decisions` is not in `schemas/status-file.schema.json` — see §7).

**Not recommended:** Infer blocking from `note` text (fragile).

## 4. Kanban state persistence

Column placement is **personal progress**, not agent workflow state.

| Option | Pros | Cons |
|--------|------|------|
| **A. localStorage (recommended MVP)** | Works on `file://` and static hosting; no server | Per-browser, not shared across machines |
| B. `my-actions-state.json` + server POST | Shared, git-trackable if committed | Needs new supervisor/workbench route, auth story, merge conflicts |
| C. No persistence | Simple | Resets every load; poor UX |

**Server check:** `sprite_workbench_server.py` exposes many `POST` handlers for workbench projects, settings, room layout, etc. There is **no** existing endpoint for writing arbitrary repo-root JSON such as status files. Adding one is a larger security/design task.

**Recommendation:** **localStorage**, key e.g. `mv-agent-os-my-actions-v1`, value JSON:

```json
{
  "version": 1,
  "byId": {
    "orchestration:founder:…": { "column": "todo|doing|done", "order": 0 }
  }
}
```

On load: merge aggregated cards with saved `column`/`order`; **new** cards without an entry default to **Not Started**. **Removed** cards (no longer in JSON): drop their keys from storage on next save to avoid unbounded growth.

## 5. Product context filter

Mirror `os-dashboard.html` behavior for Issues/Opportunities: if priorities include `os_contexts`, filter **Awaiting Review** (and optionally hide non-matching founder decisions if you add `os_contexts` to those later) using the same active product context as the rest of the OS.

## 6. Integration steps (`os-dashboard.html`)

1. **Nav:** Under **Dashboards → Work**, add `data-dashboard="my-actions"` with a distinct nav dot color; include a count badge element (update when view renders / context changes).
2. **View shell:** New `<div class="dashboard-view" data-dashboard-view="my-actions">` containing the board markup (or a mount point filled by JS).
3. **CSS:** Port token-aligned rules from `my-actions-mockup.html` into the dashboard `<style>` block with a **`ma-`** or **`my-actions-`** prefix to avoid collisions (e.g. `.ma-board-wrap`, `.ma-drop-zone`).
4. **JS modules (inline functions are fine):**
   - `aggregateMyActionsFromStatusCache()` → `{ blocking[], decisions[], reviews[] }` with `id`, `agent`, `title`, `note`, `source`, `risk?`, `agentColor` or slug for styling.
   - `renderMyActionsBoard(data)` → DOM or template fill.
   - `wireMyActionsDnD()` → same rules as mockup (type-matched drop zones).
   - `loadMyActionsState()` / `saveMyActionsState()` → localStorage merge.
5. **Lifecycle:** On `selectDashboard('my-actions')`, if cache is stale run the same refresh path as other views that depend on status JSON, then render. Debounce rapid re-entry.
6. **Accessibility:** `draggable` cards need keyboard alternative (future): for MVP document “mouse/trackpad only” or add “Move to…” `<select>` per card in a follow-up.
7. **Empty states:** If a category has zero items after filter, show a single muted line in that row’s lanes (match mockup `—` placeholder pattern).

## 7. Schema & validation

- **`schemas/status-file.schema.json`** does not currently define `founder_decisions`. Extend with an optional array and item properties: `title`, `note`, `source`, optional `blocking`, optional `my_actions_id`, optional `os_contexts` (if you want filtering parity).
- **`scripts/validate_status_files.py`:** Add optional checks: `blocking` boolean if present; `my_actions_id` string if present; no duplicate `my_actions_id` within one file.

## 8. Testing

- **Unit:** Extract `aggregateMyActionsFromStatusCache` (or pure aggregation over fixture objects) into a small `tests/my_actions_aggregate.test.js` run with `node --test` — fixtures: one file with `founder_decisions` + `blocking`, one with `needs-review` priority.
- **Manual:** Open My Actions, confirm 16-ish items match current JSON; drag within row; reload — state persists; change product context — filtered reviews update.

## 9. Open decisions for founder / PM

1. **Nav badge semantics:** Total open items vs. “not complete” vs. “blocking + high-risk only”?
2. **De-dupe:** Should orchestration synthesis dedupe against specialist files by title or shared `my_actions_id`?
3. **Server-backed state:** Defer until MVP proves localStorage is insufficient?

## 10. Files to touch (checklist)

| File | Change |
|------|--------|
| `os-dashboard.html` | Nav item, view, CSS, JS aggregation + DnD + storage |
| `my-actions-mockup.html` | Keep as design reference; optional small UX fixes only |
| `schemas/status-file.schema.json` | Optional `founder_decisions` + fields |
| `scripts/validate_status_files.py` | Optional validation for new fields |
| `orchestration-status.json` (and others as needed) | `blocking: true` where appropriate; optional `my_actions_id` |
| `tests/my_actions_aggregate.test.js` | New — aggregation determinism |
| `docs/my-actions-integration-plan.md` | This document |

---

**Recommendation:** Ship MVP with **localStorage**, explicit **`blocking`** on `founder_decisions`, stable **`my_actions_id`** only where hash stability is risky; reuse status cache and product context from `os-dashboard.html`.

**Risks:** Hash-based ids drift if copy edits; mitigated by `my_actions_id`. Duplicate cards across agents if aggregation does not dedupe.

**Confidence:** High for data shape and server capabilities; Medium for dedupe policy until product confirms.

**Founder approval needed:** Nav badge meaning and dedupe policy (§9).

**Next actions:** (1) Add schema + validator optional fields. (2) Tag blocking decisions in JSON. (3) Implement view in `os-dashboard.html`. (4) Add `node --test` aggregation test.
