# Standing Directive — Plain Language in Dashboards

**Issued:** 2026-03-30
**Applies to:** All agents that write to a `*-status.json` dashboard file.

---

## The Rule

When you write to any dashboard status file, write for the founder — not for engineers, product managers, or other agents.

Assume the reader is a smart, busy person who is not looking at code all day. They want to know: what's happening, does anything need their attention, and is anything blocked.

---

## What this means in practice

**Priority titles** — one plain sentence saying what you're doing and why it matters.
- Not: "Export schema: Version field + validation layer before next schema-touching feature"
- Yes: "Adding version numbers to saved files so future updates don't break them"

**Notes** — one or two sentences a non-technical person could read and understand.
- Not: "Ledger records API calls only; UX outcomes need explicit instrumentation + schema"
- Yes: "We can see how many AI calls happen, but not whether the suggestions were actually useful. That's the thing we need to fix."

**Founder decisions** — phrased as real questions.
- Not: "Define evaluation trigger criteria for Gemini 2.5 spatial benchmarks"
- Yes: "When should we test the newer AI model, and what does 'good enough to switch' look like?"

**Blockers** — say what is actually blocked and why, plainly.
- Not: "Blocked on external users and export telemetry"
- Yes: "We can't measure this yet because there are no external users. Placeholder until launch."

---

## What to avoid

- Code snippets, file names, function names in any dashboard-visible text
- Acronyms without explanation: no WCAG, P0, P1, API, SaaS, MVP, KPI, telemetry, schema, ledger, instrumentation
- Corporate jargon: no "leverage", "synergy", "north star metric", "flywheel" without explaining what you mean
- Technical shorthand that only makes sense to someone reading the code

---

## What is fine

- Product names (Aseprite, Gemini, Pixellab, Godot) — these are proper nouns
- Honest uncertainty: "We don't know yet" is better than a placeholder dash
- Short sentences. Plain words. Active voice.

---

This directive applies permanently unless explicitly revoked by the founder.
