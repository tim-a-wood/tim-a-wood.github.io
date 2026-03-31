# Dashboard Standard Guide

**All agent dashboards must follow this guide. It is the source of truth for what goes in a dashboard and how to write it.**

---

## Purpose of a dashboard

A dashboard is a read-only status report for the founder. It answers three questions at a glance:

1. What are we working on right now?
2. Is anything blocked or broken?
3. Do I need to make a decision?

A dashboard is not a list of things an agent could do. It is not a collection of buttons. It is not a place to explain how the system works.

---

## Structure: 4 sections maximum

Every dashboard has at most 4 sections. If you need more, you are combining two different things into one dashboard — split them, or cut sections.

| # | Section | Purpose |
|---|---------|---------|
| 1 | **Priorities** | What we're doing right now, in order. Plain one-sentence titles. |
| 2 | **Risk register** | Two panels: active blockers, and open founder decisions. |
| 3 | **Health / metrics** | Numbers that tell you if things are working. Max 4–8 cards. |
| 4 | **Domain-specific** | One section unique to this domain (e.g. competitors, coverage gaps, assumption register). Optional. |

The Engineering dashboard is the gold standard: Priorities → Risk Register → Services & Keys → AI pipeline. Follow this pattern.

---

## What goes in each section

### Priorities

- Use the `db-priority-list` component with `db-priority-row` items
- Each row: rank, one-sentence title, status pill, risk badge, note
- Maximum 5 priorities. If you have more, they are not priorities.
- Titles must be plain English sentences: "Fix the room editor crash on save" not "Resolve serialisation regression"

### Risk register

- Two panels side by side using `db-risk-grid`
- Left panel: P0 blockers (things that stop all work). Label: `BLOCKING ISSUES`
- Right panel: Founder decisions (questions only the founder can answer). Label: `FOUNDER DECISIONS`
- If empty, show the green "No active blockers" / "No pending decisions" placeholder
- Never add a third panel

### Health / metrics

- Use the `db-grid` component with `db-card` items (max 8 cards in a section)
- Each card: label, value, sub-label
- Tier badges: `LIVE` for data that updates automatically, `MANUAL` for data updated by hand, `POST-LAUNCH` for data that doesn't exist yet
- Values should be numbers, dates, or short plain-English status words
- No run buttons unless the card represents a genuine on-demand action that produces a visible result in the card value

### Domain-specific (optional)

- One section only
- Use a table or grid — not freeform prose
- Examples: competitor grid (Strategy), coverage gaps table (QA), assumption register (Strategy)

---

## Card rules

**Good card:**
```
Label:  "Tests passing"
Value:  169
Sub:    "of 169 total"
Tier:   LIVE
```

**Bad card:**
```
Label:  "QA Report"
Value:  —
Sub:    "Run when a release is in flight"
Button: "Run QA · report →"
```

Rules:
- Never put a run button on a card that has no live data. Cards with only a button and a `—` value are placeholders masquerading as content — remove them.
- Run buttons are only valid if clicking them produces a result that appears in that card's value field.
- `POST-LAUNCH` cards are acceptable placeholders for metrics that will exist after launch. They don't need run buttons.

---

## Language rules

Every word visible on a dashboard must pass this test: **could a non-technical person read this and immediately understand it?**

**Forbidden words and phrases** (use plain alternatives):
| Forbidden | Use instead |
|-----------|-------------|
| schema versioning | save file format version |
| instrumentation / telemetry | usage tracking |
| API / API key | connection key / service key |
| P0 / P1 / P2 | blocker / serious / minor |
| ledger | usage log |
| serialisation | saving |
| regression | bug introduced by a recent change |
| pipelines | automated steps |
| tokens | AI credits |

**No file paths** — never show paths like `projects-data/_usage_ledger.json` on the dashboard. Remove the `<p>` explanatory paragraphs that contain them.

**No `<p>` explanation paragraphs** — if a section needs a prose explanation to be understood, the section is too complex. Simplify the section instead of adding an explanation.

---

## Run button policy

Run buttons existed in the initial dashboard build as placeholders for future agent actions. The policy going forward:

- **Remove** any run button on a card where the value is always `—` and never changes
- **Keep** run buttons only when they trigger an action that writes a real value back to the JSON file

If you are unsure, remove the button. A card without a button is always cleaner than a card with a button that does nothing.

---

## Section count audit

Before publishing any dashboard update, count your sections. If you have more than 4:

1. Look for two sections that contain the same type of information — merge them
2. Look for sections that are all run buttons with no live data — remove them
3. Look for sections that only exist to explain how the system works — remove them

Reference counts (current):
- Engineering: 4 sections ✓ (gold standard)
- Orchestration: 4 sections ✓
- Design: 4 sections ✓
- QA: 5 sections ✓
- Analytics: 5 sections ✓
- Strategy: 5 sections ✓
- Marketing: 4 sections ✓

---

## Updated: 2026-03-30
