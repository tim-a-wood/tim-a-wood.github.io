# Directive: Task-Completion Priority Update — All Agents

**This is a standing directive. It applies to every agent that owns a `*-status.json` file.**

---

## When this applies

At the end of every task — whether the task was triggered by the founder, the orchestrator, or a specialist peer — you must update your `*-status.json` before closing the session.

Do not wait to be asked. Do not defer until your next scheduled report.

---

## What to update (source of truth)

### `priorities` array

After every task, review the full priorities list and apply the following rules:

1. **Mark completions.** Any priority you finished this session: set `"status": "done"`.
2. **Promote unblocked items.** If completing this task unblocked another priority, change its status from `"paused"` or `"queued"` to `"in-progress"` and move it up in the list if appropriate.
3. **Add new items.** If the work surfaced a new priority, risk, or follow-on, add it to the list immediately — do not rely on remembering it for the next session.
4. **Prune stale entries.** Remove any `"status": "done"` items that have appeared in the list for more than two update cycles. Completed work does not need to live in the priorities list indefinitely.
5. **Maintain `proposed_solution`.** Every active or blocked priority item must include a brief, plain-English `proposed_solution` describing the current best next step.

**Important:** In this system, "actions" on the Actions dashboard means these priority/action items (`priorities` array), not callable operation cards.

### `updated` field

Always update the top-level `"updated"` field to today's date.

---

## Priority lifecycle

```
queued → in-progress → needs-review → done → [pruned after 2 cycles]
```

- `queued`: identified, not yet started
- `in-progress`: actively being worked
- `needs-review`: work complete, awaiting founder or peer sign-off
- `done`: confirmed complete — stays in the list for up to 2 update cycles, then removed

---

## Why this exists

Priority lists that are only updated on request go stale within days. A stale priorities list is noise — it tells the founder what was true last week, not what is true now. An agent whose list is current is an agent the founder can trust at a glance. The cost of updating is 60 seconds. The cost of a stale list is a founder making decisions on outdated information.

---

*Issued: 2026-03-30 · Founder directive via Orchestrator*
