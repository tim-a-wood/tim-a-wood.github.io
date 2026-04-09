# Directive: Dashboard Standard — All Agents

**This is a standing directive. It applies to every agent that owns a dashboard.**

---

## When this applies

Any time you create, update, or rewrite a `*-status.json` file, or when a user asks you to update your dashboard, you must follow the standard in:

**[`agents/design/dashboard-standard.md`](../design/dashboard-standard.md)**

Read it before writing any dashboard content.

---

## The non-negotiables

1. **4 sections maximum.** Priorities → Risk Register → Health/Metrics → one domain-specific section. No more.

2. **Plain English only.** No file paths. No technical terms. No jargon. Write for the founder, not for engineers.

3. **No empty run buttons.** Do not include a run button on any card where the value is `—` and will stay `—`. Remove it.

4. **No `<p>` explanation paragraphs.** If a section needs a prose explanation, the section is too complex. Simplify it.

5. **Match the Engineering dashboard.** When in doubt, look at how the Engineering dashboard is structured. It is the gold standard.

---

## Action items in dashboards

The founder-facing Actions dashboard reads from each agent's `priorities` array. Treat `priorities` as the canonical action-item list.

If an agent also keeps an `actions` array for callable operations, that is secondary metadata and must not replace `priorities`.

`priorities` entries should always include:

```json
{
  "id": 1,
  "title": "Plain-English action item",
  "status": "queued|in-progress|needs-review|paused|done",
  "risk": "low|med|high",
  "note": "Detail, context, or blocker in plain English."
}
```

**Rules for action items:**

- **Keep order meaningful.** Order in `priorities` is the priority ranking.
- **Update after every task.** Apply lifecycle updates from `agents/directives/task-completion-update.md`.
- **Plain English only.** `title` and `note` must be founder-readable in 30 seconds.

---

## Why this exists

The dashboards grew verbose over time — too many sections, too many buttons, too much technical language. A founder reading their own dashboard should be able to scan it in 30 seconds and know exactly what matters. That is the only measure of success.

---

*Issued: 2026-03-30 · Design agent*
