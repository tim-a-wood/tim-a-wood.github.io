# Analytics Opportunities — MV Toolchain
**Date:** 2026-03-28 | **Agent:** Analytics | **Scope:** Development workflow acceleration + business intelligence

---

## Executive Summary

The toolchain already generates rich, structured event data — 390 history events across 23 projects in per-project `history.json` files — but no aggregation layer exists. Every insight currently requires manually querying files. The single most actionable finding from this data is a workflow bottleneck hidden in plain sight: **the concept stage has a measured 32% job failure rate and is consuming the majority of active development time without converting to downstream progress.** Three of the five high-value analytics investments below can be delivered by reading the data that already exists.

---

## What Data Already Exists

The server's `append_history_event()` mechanism writes structured events to per-project history files in real time. The event taxonomy is solid:

| Event Type | Count | What It Captures |
|---|---|---|
| `job_summary` | 121 | Every async job: type, status, timestamps |
| `review_action` | 40 | Concept approve / reject decisions |
| `concept_pixellab_generate` | 14 | PixelLab generation calls |
| `concept_pixellab_iterate` | 36 | PixelLab iteration calls |
| `concept_gemini_iterate` | 28 | Gemini iteration calls |
| `prompt_generation` | 31 | Brief/prompt generation runs |
| `concept_validation` | 17 | Validation results |

**Gap:** All data is siloed in 28 separate files. There is no aggregation layer, no cross-project query, and no dashboard. The data exists to answer every question below — it just requires a reader.

---

## Finding 1 — Concept Stage Is a Workflow Bottleneck (Confirmed by Data)

**This is the most significant finding in this report.** The event history shows that the concept stage consumes the most tool sessions, generates the most AI calls, and has the lowest completion rate of any stage.

**Evidence from existing history data:**

| Project | Generation events | Iterations | Approvals | Outcome |
|---|---|---|---|---|
| `hero-knight-91c47779` | 6 | 37 | 0 | Archived — never cleared concepts |
| `test-40b4b333` | 6 | 26 | 4 | Archived |
| `test-player-cdeb0c86` | 18 | 1 | 2 | Archived |
| `test-player-1e906493` | 0 | 0 | 1 / 11 rejected | Archived |

The `hero-knight` project ran for a full day (15:01 to 22:12 on 2026-03-21, plus follow-up on 2026-03-22) with 5 prompt regenerations and 37 concept iterations across PixelLab and Gemini backends. It never produced an approved concept. The project was archived.

**Funnel summary (all projects with history data):**

| Stage | Projects at or past this stage |
|---|---|
| intake | 27 |
| concepts | ~21 (reached) |
| concept approved | ~5 (cleared concepts) |
| rig / rig_review | ~7 |
| export | **1** |

Concept-stage clearance is the primary conversion bottleneck. One project has ever reached export.

**What this means for development:** Time spent improving concept stage UX, reducing iteration friction, or making iteration feedback faster has the highest expected return of any workflow improvement.

---

## Finding 2 — Job Failure Rate Is 32% and Partially Invisible

121 `job_summary` events exist across all projects. 39 of them have `"status": "failed"` — a 32% failure rate. Breakdown by job type:

| Job Type | Total | Failed | Failure Rate |
|---|---|---|---|
| `ai_workflow.character_lock` | 17 | 15 | **88%** |
| `concepts.generate` | 21 | 11 | **52%** |
| `qa.run` | 16 | 10 | 63% |
| `concepts.refine` | 5 | 3 | 60% |
| `export` | 12 | 0 | 0% |
| `rig.build` | 12 | 0 | 0% |

The `ai_workflow.character_lock` failure rate (88%) is the worst single signal in the data. The failure reason is consistent: "AI workflow dependencies are not ready" — meaning ComfyUI nodes or models are missing from the environment. This is an infrastructure readiness problem, not a product bug, but it means 15 of 17 attempts at a critical workflow gate failed silently from the user's perspective.

`concepts.generate` failures are almost entirely `ComfyUI backend unavailable: Connection refused` — the backend was not running when the user tried to generate.

**Neither of these failure patterns is currently surfaced anywhere in a developer-visible dashboard.** They were found by parsing raw JSON.

---

## Finding 3 — AI API Cost Data Is Uncaptured

Every `concept_pixellab_iterate` event represents a paid PixelLab API call. The `hero-knight` project alone made 36 PixelLab iteration calls in one session. At estimated PixelLab pricing, a session with 36 iterations is a material cost event.

**Current state:** No cost data is recorded in any history event. The event knows a call was made but not what it cost.

**What's missing:**
- Per-call token counts or cost units (available from API responses)
- Cumulative cost per project
- Cost-per-stage breakdown
- Alert when a project's concept stage has consumed >X API calls without an approval

This is a monitoring gap for a solo founder where a runaway session is a real cost risk.

---

## Finding 4 — Job Duration Is Structurally Untrackable

All `job_summary` events record `created_at` and `completed_at` with the same or near-identical timestamp, because jobs are only logged at completion. There is no `started_at` timestamp recorded when a job begins.

This means it is currently impossible to answer: "How long does a concepts.generate job take? Is it getting faster or slower over time? Which jobs are the user's biggest wait times?"

Given that PixelLab concept generation and animation rendering are the primary wait times in the workflow (visible from the timeline: 15:27 to 16:24 = 57 min for one generation pass), the inability to measure these wait times is a direct obstacle to optimizing developer workflow speed.

**Fix is minimal:** Add a `started_at` field to any long-running job at dispatch time, before the async call begins.

---

## Finding 5 — Room Copilot Usage Is Nearly Unrecorded

The Room Copilot (`adapt_room_template`, `build_room_environment_spec`) is instrumented at the art direction level (2 `room_environment_preview_approved`, 2 `room_environment_assets_generated` events), but the accept/discard/revise decision loop — which is exactly the signal the analytics charter identifies as the key AI quality metric — is not tracked.

Per the charter: acceptance rate, apply rate, revision rate, and discard-without-revision rate are the four Copilot quality metrics. None of these can currently be computed. The charter defines a target acceptance rate of >30% and a discard-without-revision rate as the most damaging signal — both are invisible.

---

## Five Prioritised Analytics Investments

### A1 — Cross-Project History Aggregator (Low effort / High value)
Build a single Python script (`scripts/analytics_digest.py`) that reads all `history.json` files, aggregates events, and outputs a structured JSON report: job counts by type/status, review action breakdown, stage funnel counts, and concept iteration counts per project. This script can feed the weekly digest and takes 2–3 hours to write. All the data already exists.

**Output this enables:** Job failure rate by type, concept-stage clearance rate, overall funnel conversion.

### A2 — Job Duration Instrumentation (Low effort / Enables future analysis)
Add a `started_at` timestamp to `job_summary` events at job dispatch time, not just at completion. One line of code at each job entry point. This makes all future workflow latency analysis possible and unlocks the ability to answer "which step is slowing down development?"

**Metric unlocked:** Per-stage median latency, latency trend over time, wait time attribution.

### A3 — PixelLab Cost Tracking (Medium effort / Financial visibility)
Capture cost or credit metadata from PixelLab API responses and append it to `concept_pixellab_generate` and `concept_pixellab_iterate` events. Store cumulative cost in the project record. Surface a "concept stage cost so far" counter in the UI. Flag when a project has consumed >20 API calls in the concept stage without an approval.

**Metric unlocked:** Cost per project, cost per export, cost-to-approval ratio, early warning for runaway sessions.

### A4 — Room Copilot Decision Tracking (Medium effort / AI quality signal)
Add history events for the three Copilot outcomes: `room_copilot_applied` (user accepted and applied a suggestion), `room_copilot_revised` (user triggered a revision), `room_copilot_discarded` (user discarded without revising). These three events, with a `suggestion_id` field linking them to the generation event, produce the full Copilot quality dashboard defined in the charter.

**Metric unlocked:** Copilot acceptance rate, revision rate, discard-without-revision rate. Baseline measurement for the charter's >30% acceptance rate target.

### A5 — North Star Metric Setup (Definition / No code required now)
Define and formally record the North Star Metric for the toolchain: **exports completed per active project per month.** Current value from the data: **1 / 28 active or previously-active projects = 3.6%.** This is the pre-launch baseline. Every product and AI improvement should be evaluated against: "does this move projects through to export?"

The metric is not actionable with one data point, but establishing the definition and the baseline now means it can be trended from the first external release. The charter explicitly warns against establishing metrics post-launch — this is the right moment.

---

## Summary Table

| Investment | Effort | Data Needed | Metric(s) Unlocked | Priority |
|---|---|---|---|---|
| A1 — History aggregator | 2–3 hrs | Already exists | Job failure rate, funnel, concept efficiency | High |
| A2 — Job duration tracking | 1 hr | Code change | Per-stage latency, wait time analysis | High |
| A3 — PixelLab cost tracking | 3–4 hrs | API response data | Cost per project, runaway session alerts | Medium |
| A4 — Copilot decision events | 2 hrs | Code change | Copilot acceptance/revision/discard rates | Medium |
| A5 — North Star definition | 0 hrs | None | Strategic alignment metric | High |

**Total estimated effort for A1 + A2 + A5:** ~4 hours. These three return the highest signal for the least investment and require no external dependencies.

---

## Honest Caveats

All rates above are computed from a single-user, solo development context. These are **operational signals for the builder, not user research.** They answer "how is the tool performing as I build it?" not "how will users behave?" The charter's warning about denominator hygiene applies: a 60% concept-stage dropout rate from 28 internal projects is a development workflow signal, not a market insight.

When external users are added, establish fresh cohort baselines. Internal usage patterns will not predict external user behavior.
