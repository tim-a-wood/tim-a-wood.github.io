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

## The `actions` section

Every dashboard may include an `actions` array as a fifth section. Each entry follows this schema:

```json
{
  "id": "action-id",
  "name": "Human-Readable Name",
  "description": "One sentence — what this action does and what it produces.",
  "trigger": "When to run it — the condition or event that makes this action relevant.",
  "last_run": "YYYY-MM-DD or null",
  "output_location": "Where the output was written, or null if never run."
}
```

**Rules for action cards:**

- **No empty run buttons.** If an action has never been run (`last_run: null`), the dashboard may show it but must not display a prominent run button — use a muted "never run" state instead.
- **`output_location` is required after first run.** Once an action has been run, `output_location` must be filled in. `"in-session"` is acceptable if the output was verbal only.
- **`last_run` updates every time the action is executed** — see `agents/directives/task-completion-update.md`.
- **4 actions maximum per agent.** More than 4 action cards defeats the 30-second scan goal.

---

## Why this exists

The dashboards grew verbose over time — too many sections, too many buttons, too much technical language. A founder reading their own dashboard should be able to scan it in 30 seconds and know exactly what matters. That is the only measure of success.

---

*Issued: 2026-03-30 · Design agent*
