---
title: Agent Guardrail Enforcement Audit
type: report
date: 2026-04-02
author: Research Agent
status: final
tags: agents, guardrails, enforcement, security, process, compliance
summary: Complete inventory of every agent guardrail in the MV / Sprite Workbench project, classified by enforcement type, with a gap analysis and concrete proposals to replace prompt-only compliance with deterministic checks.
---

# Agent Guardrail Enforcement Audit — 2026-04-02

## Purpose

This report answers a single question: which guardrails in this project rely entirely on the LLM doing what it is told, with no automated fallback that would catch a violation regardless of what the model outputs?

Every guardrail has been read from the source files. Enforcement classification is based on what was actually found — no assumptions were made about checks that do not exist.

**Files read:**
- `CLAUDE.md`, `AGENTS.md`, `STYLE_GUIDE.md`
- All files under `agents/` (19 charter files, 3 directive files, 1 design standard)
- All `*-status.json` files (19 agent status files)
- `scripts/os_dashboard_supervisor.py` (the only runtime that touches status files)
- `reporting/escalation-rules.yaml`, `reporting/schedules.yaml`, `reporting/recipients.yaml`
- `tests/home_internal_snapshot.test.py` and the full test suite listing
- `.git/hooks/` (all files are `.sample` — no active hooks)
- `.github/` — does not exist; no CI pipeline present

---

## Section 1: Complete Guardrail Inventory

Guardrails are grouped by the file where they originate. Every distinct rule is listed separately.

---

### Group A — Frontend Code Quality (CLAUDE.md, AGENTS.md, STYLE_GUIDE.md, .cursor/rules/frontend-design.mdc)

**A-1: No hardcoded hex color values in CSS or HTML**
- What it says: all color values must use CSS custom properties from the design system (e.g. `var(--accent)`). Direct hex values like `#fff`, `#000`, or novel hex codes are forbidden.
- Where it lives: `CLAUDE.md § Non-negotiables`, `AGENTS.md § Colors`, `STYLE_GUIDE.md § 14`, `.cursor/rules/frontend-design.mdc`
- Enforcement type: **prompt-only**
- Note: The Design agent runs a `token-audit` action described as scanning CSS files for off-token values, but this is invoked manually by asking the agent. No script, no hook, no CI check runs this automatically.

**A-2: Spacing must be on the 4px grid**
- What it says: every padding, margin, and gap value must be a multiple of 4px. Values like 5px, 7px, 9px, 11px, 13px, 15px are forbidden.
- Where it lives: `CLAUDE.md § Non-negotiables`, `AGENTS.md § Spacing`, `STYLE_GUIDE.md § 4`
- Enforcement type: **prompt-only**

**A-3: Border radius must use only defined token values**
- What it says: radius values must map to named tokens (`--radius-xs` through `--radius-full`). Values like 6px, 16px, or `50%` on panels are rejected.
- Where it lives: `CLAUDE.md`, `AGENTS.md`, `STYLE_GUIDE.md § 5`, `agents/design/charter.md § Must Never`
- Enforcement type: **prompt-only**

**A-4: Transitions must be explicit and within defined durations**
- What it says: `transition: all` is forbidden. Duration must be 120ms or 200ms. Always name the CSS properties being transitioned. No spring/bounce curves.
- Where it lives: `CLAUDE.md`, `AGENTS.md`, `STYLE_GUIDE.md § 7`, `agents/design/charter.md § Must Never`
- Enforcement type: **prompt-only**

**A-5: Typography — fonts and scale**
- What it says: new pages must load Bebas Neue, Plus Jakarta Sans, and DM Mono from Google Fonts. Font sizes must come from the `--font-size-*` token scale only. `font-family: Inter` or `Roboto` is forbidden.
- Where it lives: `CLAUDE.md`, `AGENTS.md`, `STYLE_GUIDE.md § 3`
- Enforcement type: **prompt-only**

**A-6: Dark theme only — no light backgrounds**
- What it says: no light-colored backgrounds anywhere in tool UI. All backgrounds near-black. No `color: white`, `background: white`.
- Where it lives: `CLAUDE.md`, `AGENTS.md`, `agents/design/charter.md § Must Never`
- Enforcement type: **prompt-only**

**A-7: No third-party component libraries or frameworks**
- What it says: no React, Vue, Svelte, jQuery, or any frontend framework. No npm packages in tool pages. Vanilla JS only.
- Where it lives: `CLAUDE.md § File Conventions`, `AGENTS.md § Forbidden Patterns`, `agents/engineering/charter.md § Must Never`
- Enforcement type: **prompt-only**

**A-8: No build tooling**
- What it says: no webpack, Vite, Rollup, Babel. The no-build constraint is described as non-negotiable.
- Where it lives: `CLAUDE.md`, `agents/engineering/charter.md § Must Never`
- Enforcement type: **prompt-only**

**A-9: Semantic HTML — no div soup**
- What it says: use `<button>`, `<nav>`, `<section>`, `<header>`, `<aside>` correctly. No `<div>` in place of semantic elements.
- Where it lives: `CLAUDE.md § File Conventions`, `AGENTS.md § Code Style`
- Enforcement type: **prompt-only**

**A-10: image-rendering: pixelated on canvas elements**
- What it says: all canvas elements and sprite preview images must set `image-rendering: pixelated`. Default browser interpolation is incorrect for pixel art.
- Where it lives: `CLAUDE.md`, `agents/design/charter.md`
- Enforcement type: **prompt-only**

**A-11: Accessibility — minimum touch target sizes**
- What it says: all interactive elements must have `min-height: 44px` (standard) or `min-height: 28px` (compact). Icon-only elements below 44px are not allowed except in clearly compact toolbar contexts.
- Where it lives: `CLAUDE.md § New Page Checklist`, `AGENTS.md`, `agents/design/charter.md § Must Never`
- Enforcement type: **prompt-only**

**A-12: Focus-visible outline rule on every new page**
- What it says: new pages must include `:focus-visible { outline: 2px solid rgba(0,232,200,0.35); outline-offset: 2px; }` globally.
- Where it lives: `CLAUDE.md § New Page Checklist`
- Enforcement type: **prompt-only**
- Note: The research-status.json already flags that `room-layout-editor.html` is missing this rule, confirming it was not caught automatically.

**A-13: No colored box shadows**
- What it says: box shadows must use only neutral `rgba(0,0,0,x)` values. Colored shadows are forbidden.
- Where it lives: `CLAUDE.md`, `AGENTS.md`, `agents/design/charter.md`
- Enforcement type: **prompt-only**

**A-14: Hover lift maximum translateY(-1px)**
- What it says: hover animations must not exceed `translateY(-1px)`. `translateY(-3px)` is a cited forbidden example.
- Where it lives: `CLAUDE.md`, `AGENTS.md`, `STYLE_GUIDE.md § 7`
- Enforcement type: **prompt-only**

**A-15: Color is not the only state differentiator (accessibility)**
- What it says: every state change must combine color with at least one of: shape, text, icon, or position change. Color-alone state indicators violate WCAG 1.4.1.
- Where it lives: `agents/design/charter.md § Must Never`
- Enforcement type: **prompt-only**

**A-16: No `transition: all` anywhere**
- What it says: duplicates A-4 but is specifically called out as a line-level prohibition to be applied codebase-wide.
- Where it lives: `AGENTS.md § Forbidden Patterns`, `agents/design/charter.md § Must Never`
- Enforcement type: **prompt-only**

---

### Group B — Agent Process and Output Rules (AGENTS.md, charter files, directive files)

**B-1: Standard output footer on every substantive agent output**
- What it says: every substantive agent output must end with Recommendation, Risks, Confidence, Founder approval needed, and Next actions fields.
- Where it lives: `AGENTS.md § Standard Output Format`, `agents/research/charter.md § Output footer`
- Enforcement type: **prompt-only**

**B-2: Research must check the library index before starting a complex task**
- What it says: all agents are directed to check `research/library/INDEX.md` before starting architecture changes, refactoring, new features, or non-trivial debugging.
- Where it lives: `AGENTS.md § Research Library — Mandatory Check Protocol`
- Enforcement type: **prompt-only**

**B-3: Agents must not re-open decisions already logged in /decisions/**
- What it says: agents must read the decisions log before proposing changes for active multi-pass features and must not re-litigate resolved choices.
- Where it lives: `AGENTS.md § Feature Decision Tracking`, `agents/research/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-4: Escalation trigger — must escalate for legal risk, security vulnerabilities, revenue impact > $500, external commitments, irreversible actions**
- What it says: any specialist agent encountering these five conditions must escalate to the founder before proceeding.
- Where it lives: `AGENTS.md § Authority Model — Escalation triggers`
- Enforcement type: **prompt-only**
- Note: `reporting/escalation-rules.yaml` exists as a structured YAML file defining trigger conditions and SLAs, but this file is metadata documentation only. No code reads it to enforce escalation at runtime. The triggers in the YAML (e.g. `api_key_in_client`) are not connected to any scanner.

**B-5: Orchestrator must not suppress minority specialist opinions**
- What it says: if specialists disagree, both positions go into the founder digest. The orchestrator cannot adjudicate or smooth over disagreements.
- Where it lives: `agents/orchestrator/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-6: Orchestrator must not act as fake legal or finance authority**
- What it says: the orchestrator cannot make statements like "it's probably fine from a legal standpoint." Route to Legal.
- Where it lives: `agents/orchestrator/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-7: QA must not approve a release with known P0 or P1 bugs without explicit founder override**
- What it says: a P0 or P1 bug blocks all releases unless the founder explicitly overrides in writing.
- Where it lives: `agents/qa/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-8: Cybersecurity must not log API keys or secrets in output**
- What it says: API keys, session tokens, and secrets must never appear in any log or output, even at debug level.
- Where it lives: `agents/cybersecurity/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-9: Cybersecurity must not approve features forwarding unvalidated user input to external AI APIs**
- What it says: any feature passing user input to an external AI API requires sanitization review before approval.
- Where it lives: `agents/cybersecurity/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-10: Finance must not approve spend over $500 without founder sign-off**
- What it says: any one-time or monthly recurring cost over $500 requires explicit founder approval.
- Where it lives: `agents/finance/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-11: Finance must present three-scenario modeling (bear, base, best case)**
- What it says: no revenue scenario may be presented without a corresponding base case and bear case.
- Where it lives: `agents/finance/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-12: Analytics must report sample size with every metric**
- What it says: every metric must include its denominator and sample size. Percentages without denominators are prohibited.
- Where it lives: `agents/analytics/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-13: Analytics must not track users without disclosed consent**
- What it says: user-level tracking requires lawful basis (GDPR Article 6) and disclosure. Coordinate with Legal before enabling.
- Where it lives: `agents/analytics/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-14: Legal must not provide actual legal advice or approve legal documents without real attorney review**
- What it says: the Legal agent may flag risks but cannot substitute for a qualified attorney on material decisions or document approvals.
- Where it lives: `agents/legal/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-15: Research must not duplicate findings already in the library index**
- What it says: before writing any finding, check INDEX.md to avoid redundant entries.
- Where it lives: `agents/research/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-16: Research must not ship fixes — hand off to owning agent**
- What it says: Research discovers and routes, but never implements fixes itself.
- Where it lives: `agents/research/charter.md § Must Never`
- Enforcement type: **prompt-only**

**B-17: Engineering must not approve export schema breaking changes without a versioning strategy**
- What it says: any change to the export schema that breaks downstream game runtime code requires an explicit versioning strategy before approval.
- Where it lives: `agents/engineering/charter.md § Must Never`
- Enforcement type: **prompt-only**

---

### Group C — Dashboard and Status File Rules (directive files, dashboard-standard.md)

**C-1: Dashboard status files must follow the 4-section maximum structure**
- What it says: every `*-status.json` file must map to a dashboard with at most 4 sections: Priorities, Risk Register, Health/Metrics, and one domain-specific section.
- Where it lives: `agents/directives/dashboard-standard.md`, `agents/design/dashboard-standard.md`
- Enforcement type: **prompt-only**

**C-2: Dashboard titles and notes must be plain English — no jargon or acronyms**
- What it says: all text in priority titles, notes, and founder decision fields must be readable by a non-technical person. No file paths, acronyms like XSS or API without explanation, technical shorthand.
- Where it lives: `agents/directives/plain-language-dashboards.md`, `agents/design/dashboard-standard.md`
- Enforcement type: **prompt-only**
- Note: The `os_dashboard_supervisor.py` `POST /api/status-update` endpoint accepts any well-formed JSON object. There is no language check, no field-presence validation beyond checking `data` is a dict.

**C-3: No run buttons on cards with permanent null/dash values**
- What it says: a card that will always show `—` as its value must not have a run button.
- Where it lives: `agents/design/dashboard-standard.md § Card rules`, `agents/directives/dashboard-standard.md`
- Enforcement type: **prompt-only**

**C-4: Priority items must always include id, title, status, risk, and note fields**
- What it says: `dashboard-standard.md` specifies the schema for priority objects. Required fields include `id`, `title`, `status` (valid values: queued, in-progress, needs-review, paused, done), `risk` (valid values: low, med, high), `note`.
- Where it lives: `agents/directives/dashboard-standard.md`
- Enforcement type: **partial**
- What exists: `tests/home_internal_snapshot.test.py` calls `build_home_internal_snapshot()` and asserts that the derived aggregate keys (`blocking_issue_count`, `tests_passing`, etc.) are present and of the right type. This test does NOT validate priority objects in individual status files — it only checks the derived summary.
- What is missing: no test or schema validates that each priority object has the required fields, that `status` is from the allowed enum, or that `risk` is from the allowed enum.

**C-5: Task-completion update — agent must update its status file after every task**
- What it says: at the end of every session, the agent must mark completed priorities as done, promote unblocked items, add new items, prune stale done items, and update the `updated` field.
- Where it lives: `agents/directives/task-completion-update.md`, standing directive in all agent charters
- Enforcement type: **prompt-only**

**C-6: actions[*].last_run and output_location must be updated after any action is run**
- What it says: when an agent runs a named action (e.g. `security-review`, `release-gate`), it must update `last_run` to today's date and `output_location` to the path of the output artifact.
- Where it lives: `agents/directives/task-completion-update.md`, all charter standing directives
- Enforcement type: **prompt-only**
- Evidence of violation: scanning all 19 status files shows that dozens of actions have `last_run: null, output_location: null` — including actions whose charters describe them as having been run (e.g. `cybersecurity: security-review` shows `last_run: 2026-03-28` with a real path, but `threat-model` and `prompt-injection-test` have both fields null). This is the expected pattern for unrun actions, but there is no way to distinguish "never run" from "run but not updated" without reading the output artifact.

**C-7: Maximum 5 priorities per status file**
- What it says: if an agent has more than 5 active priorities, the list is not a priorities list.
- Where it lives: `agents/design/dashboard-standard.md § Priorities`
- Enforcement type: **prompt-only**

**C-8: schema_version field must be present**
- What it says: the dashboard standard implies a `schema_version` field (observed as `"v1.0"` in most files).
- Where it lives: implicitly from `agents/design/dashboard-standard.md`
- Enforcement type: **prompt-only**
- Evidence: 3 of 19 status files (`design-status.json`, `research-status.json`, `strategy-status.json`) are missing `schema_version` entirely. The supervisor and snapshot test do not check for it.

---

### Group D — Truthfulness and Evidence (universal standing directive, 2026-04-02)

**D-1: Do not fabricate facts, sources, actions, results, or completion status**
- What it says: agents must ground factual, status, and completion claims in verifiable artifacts. Must not present inferences as facts. Must not claim work was completed without evidence.
- Where it lives: standing directive in every agent charter (orchestrator, research, qa, cybersecurity, design, engineering, and all others)
- Enforcement type: **prompt-only**

**D-2: Label speculative ideas as guesses in brainstorm mode**
- What it says: in explicitly creative or brainstorm contexts, agents may speculate but must label each speculation as a guess or hypothesis — not a verified fact.
- Where it lives: standing directive in every agent charter
- Enforcement type: **prompt-only**

---

### Group E — Security-Specific Technical Controls (cybersecurity/charter.md)

**E-1: Gemini API key must not appear in client-side code**
- What it says: the API key must live only in the Python server environment. It must never appear in HTML source, client JavaScript, server log output, or git-tracked files.
- Where it lives: `agents/cybersecurity/charter.md § Surface 2`
- Enforcement type: **prompt-only**
- Note: The charter recommends running `trufflehog` and `git log --all` to audit history, but no script or hook does this automatically. The `credential-audit` action in `cybersecurity-status.json` was last run 2026-03-28 manually.

**E-2: .env.local must be in .gitignore**
- What it says: `.env.local`, `.env`, `*.key`, `*.pem` and credential files must be in `.gitignore`.
- Where it lives: `agents/cybersecurity/charter.md § Surface 4`
- Enforcement type: **prompt-only**
- Note: No pre-commit hook enforces this. A hook could trivially catch it.

**E-3: Gemini Copilot outputs must pass JSON schema validation before reaching application state**
- What it says: all Copilot responses must be validated against a defined JSON schema. Entity types must be one of the 7 defined values. Coordinates must be finite numbers within canvas bounds.
- Where it lives: `agents/cybersecurity/charter.md § Surface 2 — Prompt Injection`
- Enforcement type: **partial**
- What exists: the Python test suite includes `room-wizard-environment-copilot.test.js` and Python room environment system tests. These test the validation logic in the backend code when invoked. However, whether schema validation actually runs before state mutation in production is a code audit question, not a test result — and the code audit has not been completed (it is listed as in-progress in both `research-status.json` and `cybersecurity-status.json`).

**E-4: Per-IP rate limiting on the Copilot endpoint**
- What it says: the Python server must limit requests to the Copilot endpoint (recommended: 20/minute per IP, 100/hour).
- Where it lives: `agents/cybersecurity/charter.md § Surface 2 — Rate Limiting`
- Enforcement type: **prompt-only**
- Note: No test verifies rate limiting exists. No CI check validates server configuration.

**E-5: Content Security Policy header on all HTML pages**
- What it says: all HTML pages must include a `Content-Security-Policy` meta tag. `unsafe-inline` must be avoided.
- Where it lives: `agents/cybersecurity/charter.md § Surface 1 — CSP`
- Enforcement type: **prompt-only**
- Evidence: cybersecurity-status.json explicitly flags this as "in-progress" P1 with no automated check detecting the absence.

**E-6: DOM writes must use textContent or DOMPurify — not innerHTML with user strings**
- What it says: entity names, room names, and any user-created string must not be inserted via `innerHTML`. Use `textContent` or sanitize with DOMPurify.
- Where it lives: `agents/cybersecurity/charter.md § Surface 1 — XSS`
- Enforcement type: **prompt-only**
- Evidence: research-status.json confirms a real XSS finding at `room-layout-editor.html:4513–4543` where `escapeHtml()` exists but is not called. No automated check caught this — it was found by manual code reading.

**E-7: AI entity IDs must be regenerated on application — never trust AI-generated IDs**
- What it says: when a Copilot suggestion is applied, new entity IDs must be generated for all incoming entities. AI-generated IDs must not be used as-is to prevent collisions.
- Where it lives: `agents/cybersecurity/charter.md § Surface 3`
- Enforcement type: **prompt-only**

---

### Group F — Reporting Cadence and Escalation Structure

**F-1: escalation-rules.yaml defines trigger conditions but is not enforced at runtime**
- What it says: the YAML defines 6 escalation rule types with triggers (e.g. `api_key_in_client`), severity levels, SLAs, and agent routing.
- Where it lives: `reporting/escalation-rules.yaml`
- Enforcement type: **prompt-only**
- Note: This YAML file is documentation. No code reads it or checks the trigger conditions. The triggers are not connected to any scanner, test, or automated monitor.

**F-2: Daily product report from Game Director**
- What it says: the Game Director sends a daily product report. Blockers and decisions in the report are escalated immediately — not held for Monday.
- Where it lives: `agents/orchestrator/charter.md § Reporting`
- Enforcement type: **prompt-only**

**F-3: Weekly Monday founder digest — readable in under 5 minutes**
- What it says: the orchestrator compiles a weekly digest every Monday. If it runs longer than 5 minutes of reading time, it has not been summarized enough.
- Where it lives: `agents/orchestrator/charter.md § Reporting`
- Enforcement type: **prompt-only**

**F-4: Quarterly security review with signed-off posture report**
- What it says: Cybersecurity produces a quarterly security review covering dependency scans, CSP audits, prompt injection results, and credential hygiene.
- Where it lives: `agents/cybersecurity/charter.md § Reporting`
- Enforcement type: **prompt-only**

---

## Section 2: Enforcement Gap Analysis

All guardrails classified as `prompt-only` or `partial` above are listed here with a concrete enforcement proposal. Proposals are grouped by implementation cost.

---

### Low cost — a schema change or single-file check, under 1 hour each

**Gap: C-4 partial — priority objects lack field and enum validation**

Proposal: Create `/schemas/status-file.schema.json` as a JSON Schema document. The `priorities` array item schema requires:
- `id`: string or integer, not null
- `title`: string, minLength 1
- `status`: enum ["queued", "in-progress", "needs-review", "paused", "done"]
- `risk`: enum ["low", "med", "high"]
- `note`: string

Add a 20-line Python script `scripts/validate_status_files.py` that runs `jsonschema.validate()` against every `*-status.json` in the repo root. Exit code 1 on failure. This can be run manually or wired to a pre-commit hook.

```
# pseudocode
for each *-status.json:
    validate against schema
    if invalid: print file + error message, exit 1
```

**Gap: C-8 prompt-only — schema_version field absence in 3 of 19 status files**

Proposal: Add `schema_version` as a required string field to the JSON Schema above. The validator in the proposal above will then catch the 3 files currently missing it (`design-status.json`, `research-status.json`, `strategy-status.json`).

**Gap: E-2 prompt-only — .env.local not guaranteed to be in .gitignore**

Proposal: Add a shell pre-commit hook (`.git/hooks/pre-commit`) with this check:

```sh
if git diff --cached --name-only | grep -E "^\.env" ; then
  echo "Blocked: .env file staged for commit. Remove it before committing."
  exit 1
fi
```

This is a 5-line addition to an existing sample hook. It catches the most dangerous class of credential exposure (committing the file itself) before it reaches git history.

**Gap: E-5 prompt-only — no Content Security Policy on HTML pages**

Proposal: Add a Python check `scripts/check_csp.py` that reads each `.html` file in the repo root and `tools/` and checks for a `Content-Security-Policy` meta tag. Report any file missing it. Exit 1 if any are found. This does not enforce a specific CSP policy, but it catches the absence of any policy, which is the current situation.

**Gap: C-2 prompt-only — jargon and acronyms in dashboard text**

Proposal: Add a regex check to `scripts/validate_status_files.py` that scans `title` and `note` fields for a list of forbidden terms (XSS, WCAG, P0, P1, API, telemetry, instrumentation, schema, serialisation, regression). Report matches with field path and value. This is imperfect (a note might correctly use "API" in context) but produces a reviewable list of potential violations rather than silent drift.

---

### Medium cost — a script plus hook, 1–4 hours each

**Gap: A-1 prompt-only — hardcoded hex colors in CSS**

Proposal: A Python script `scripts/lint_css_tokens.py` that:
1. Reads all `.css` files and `<style>` blocks in `.html` files
2. Uses a regex to find any hex color value (`#[0-9a-fA-F]{3,8}`) not inside a CSS variable declaration (`:root { --something: #abc; }`)
3. Reports file, line number, and the offending value
4. Exit 1 if any are found

This would have caught the known finding in `product-shell.css` (~15 hardcoded colors, logged in research-status.json) automatically. Wire as a pre-commit hook filtering on `*.css` and `*.html` changes.

**Gap: A-2 prompt-only — spacing not on 4px grid**

Proposal: Extend `scripts/lint_css_tokens.py` to check `padding`, `margin`, `gap`, and `column-gap` values that are pixel values not divisible by 4. Flag: 5px, 7px, 9px, 11px, 13px, 15px explicitly (the list in the style guide). Regex approach is viable for catching the most common violations. Edge cases (calc() expressions, shorthand with mixed values) can be flagged for manual review rather than blocking.

**Gap: A-4 / A-16 prompt-only — `transition: all` in CSS**

Proposal: Add to `scripts/lint_css_tokens.py` a check for `transition: all` anywhere in a CSS property value. This is a simple string match. Every occurrence is a violation; no exceptions are defined in the style guide. Exit 1 on any match. Wire to pre-commit hook.

**Gap: E-6 prompt-only — innerHTML with user strings (XSS risk)**

Proposal: A script `scripts/check_innerHTML_usage.py` that:
1. Scans all `.html` files and `.js` files for `.innerHTML` assignments
2. For each match, reports the file and line
3. Flags any `innerHTML` usage as a review-required finding

This cannot automatically determine whether a value is user-controlled, but it produces a complete inventory of innerHTML sites. Wire to a pre-commit hook that produces a warning (not a block) on new `.innerHTML` additions in changed files. Combine with requiring that any innerHTML site that handles user strings calls `escapeHtml()` first — the function already exists in the codebase.

**Gap: C-6 prompt-only — output_location null when action has been run**

Proposal: Extend `scripts/validate_status_files.py` to check: if `last_run` is non-null for an action, then `output_location` must also be non-null and the file at that path must exist. Exit 1 if an action claims to have been run but has no output artifact. This enforces the task-completion update directive mechanically. The inverse (last_run null with output_location null) is acceptable — it means the action has never been run.

**Gap: B-4 prompt-only — escalation-rules.yaml not connected to any runtime**

Proposal: Write a Python script `scripts/check_escalation_conditions.py` that implements the deterministic conditions from `escalation-rules.yaml` as actual code:
- Check for `.env*` files tracked by git (`git ls-files .env*`)
- Check for `GEMINI_API_KEY`, `OPENAI_API_KEY`, or similar patterns in `.js` and `.html` files
- Check that `.gitignore` contains `.env.local`

This covers the highest-severity triggers (`api_key_in_client`, `api_key_in_git`) with a real scanner. The behavioral triggers (e.g. `p0_bug_confirmed`) cannot be automated without a bug tracker integration, but the code-level triggers can. Wire to pre-commit hook.

**Gap: F-1 prompt-only — escalation-rules.yaml is documentation only**

This is the same gap as B-4 from a different angle. The YAML file defines rules that have no runtime enforcement. The proposal above addresses the automatable subset. For the behavioral rules (cost spike, legal document), the proposal is to add threshold checks to the scripts that produce finance and analytics reports — if the computed monthly API cost exceeds the threshold in the YAML, the script should print a clear escalation notice rather than relying on an agent to notice.

---

### High cost — requires significant new infrastructure, more than 4 hours

**Gap: C-1 prompt-only — dashboard 4-section maximum structure**

Proposal: A JSON Schema for the full dashboard structure (beyond just priority objects) that validates section count, presence of required sections, and absence of prohibited fields. This requires agreeing on a canonical JSON shape for each section type and encoding it as a schema. Medium-high effort because the current status files have heterogeneous structures across agents (not all follow the same section pattern). Recommend first making status files structurally consistent, then adding the schema.

**Gap: A-11, A-12, A-15 prompt-only — accessibility rules**

Proposal: Integrate `axe-core` into a Playwright-based test that loads each HTML tool page and runs an accessibility audit. This would catch missing focus-visible styles, color-only state indicators, and touch target sizes automatically. The Playwright test suite is already recommended in `agents/qa/charter.md`. Estimated 4+ hours to set up the test runner and initial test suite if it does not already exist.

**Gap: A-10 prompt-only — image-rendering: pixelated on canvas elements**

Proposal: Extend the CSS/HTML scanner to check that every `<canvas>` element has `image-rendering: pixelated` set in CSS. This is medium effort but requires handling both inline styles and stylesheet rules that target `canvas`. A simpler approximation: check that `image-rendering: pixelated` appears at least once in the CSS of each page that contains a canvas.

**Gap: E-3 partial — Copilot output schema validation in production**

Proposal: Add a test that calls the Copilot endpoint (or the validation function directly) with adversarial inputs and verifies rejection: a string instead of an object, an unknown entity type, coordinates at Infinity, coordinates outside canvas bounds. These are the specific cases called out in the Cybersecurity charter. The room environment test files already exist; adversarial cases need to be added. Estimated 2–4 hours to write comprehensive adversarial fixtures.

**Gap: E-4 prompt-only — rate limiting on Copilot endpoint**

Proposal: Add a test that sends rapid repeated requests to the Copilot endpoint and asserts that requests beyond the limit receive an HTTP 429 response. This test would also serve as documentation that rate limiting is configured. Without rate limiting in the server code, the test would fail — which is the goal. Estimated 2–4 hours including adding rate limiting to the server if not present.

**Gap: D-1 prompt-only — do not fabricate facts or claim work is complete without evidence**

This guardrail is inherently behavioral and cannot be enforced deterministically. The closest mechanical approximation: require that any priority with `status: "done"` or action with `last_run` non-null must have a corresponding `output_location` that points to an existing file. This is a subset of the proposal in C-6 above. Full enforcement of the truthfulness directive is not automatable — it requires human review of agent outputs.

---

## Summary Table

| ID | Guardrail | Enforcement | Proposal cost |
|----|-----------|-------------|---------------|
| A-1 | No hardcoded hex colors | prompt-only | medium |
| A-2 | 4px spacing grid | prompt-only | medium |
| A-3 | Defined border radius scale | prompt-only | medium |
| A-4/A-16 | Explicit transitions, no `all` | prompt-only | medium |
| A-5 | Correct fonts and scale | prompt-only | medium |
| A-6 | Dark theme only | prompt-only | medium |
| A-7 | No third-party frameworks | prompt-only | low |
| A-8 | No build tooling | prompt-only | low |
| A-9 | Semantic HTML | prompt-only | medium |
| A-10 | image-rendering: pixelated | prompt-only | high |
| A-11 | Touch target minimum sizes | prompt-only | high (Playwright) |
| A-12 | focus-visible on new pages | prompt-only | medium |
| A-13 | No colored box shadows | prompt-only | medium |
| A-14 | Hover lift max -1px | prompt-only | medium |
| A-15 | Color not sole state indicator | prompt-only | high (Playwright) |
| B-1 | Output footer on all outputs | prompt-only | not automatable |
| B-2 | Check library before task | prompt-only | not automatable |
| B-3 | Do not re-open decisions | prompt-only | not automatable |
| B-4/F-1 | Escalation triggers | prompt-only | medium |
| B-5 | No smoothing of disagreements | prompt-only | not automatable |
| B-6 | No fake legal/finance authority | prompt-only | not automatable |
| B-7 | QA release gate — no P0/P1 | prompt-only | partial CI possible |
| B-8 | No secrets in agent output | prompt-only | not automatable |
| B-9 | No unvalidated input to AI APIs | prompt-only | medium |
| B-10 | Finance: $500 spend threshold | prompt-only | not automatable |
| B-11 | Three-scenario finance models | prompt-only | not automatable |
| B-12 | Analytics: denominators required | prompt-only | not automatable |
| B-13 | No tracking without consent | prompt-only | not automatable |
| B-14 | Legal: no legal advice | prompt-only | not automatable |
| B-15 | No duplicate library findings | prompt-only | not automatable |
| B-16 | Research: no self-implementation | prompt-only | not automatable |
| B-17 | Schema versioning before breaks | prompt-only | medium |
| C-1 | 4-section max dashboards | prompt-only | high |
| C-2 | Plain English dashboard text | prompt-only | low (regex) |
| C-3 | No empty run buttons | prompt-only | not automatable |
| C-4 | Priority object required fields | partial | low (JSON Schema) |
| C-5 | Task-completion update | prompt-only | not automatable |
| C-6 | output_location set after run | prompt-only | low (script) |
| C-7 | Max 5 priorities | prompt-only | low (JSON Schema) |
| C-8 | schema_version field present | prompt-only | low (JSON Schema) |
| D-1 | No fabricated facts | prompt-only | not automatable |
| D-2 | Label speculation in brainstorm | prompt-only | not automatable |
| E-1 | API key not in client code | prompt-only | medium (scanner) |
| E-2 | .env.local in .gitignore | prompt-only | low (pre-commit hook) |
| E-3 | Copilot output schema validation | partial | medium (adversarial tests) |
| E-4 | Rate limiting on Copilot | prompt-only | high (code + test) |
| E-5 | CSP on all HTML pages | prompt-only | low (HTML scanner) |
| E-6 | innerHTML with user strings | prompt-only | medium (scanner) |
| E-7 | AI entity IDs regenerated | prompt-only | medium (unit test) |
| F-1 | escalation-rules.yaml connected | prompt-only | medium |
| F-2 | Daily product report cadence | prompt-only | not automatable |
| F-3 | Weekly digest under 5 minutes | prompt-only | not automatable |
| F-4 | Quarterly security review | prompt-only | not automatable |

---

## Key Findings

**There are no active git hooks.** All files in `.git/hooks/` are `.sample` files. Nothing runs at commit time to enforce any guardrail.

**There is no CI pipeline.** No `.github/` directory exists. No YAML CI configurations were found outside the `reporting/` subdirectory, which contains documentation files that are not connected to any automation.

**The single runtime enforcement point is the supervisor.** `scripts/os_dashboard_supervisor.py` enforces: (1) file writes must target allowed filenames, (2) path traversal is rejected, (3) the request body must be valid JSON with `data` as a dict. It does not validate the shape, field presence, enum values, or language quality of the JSON it writes.

**The only automated behavioral check is `tests/home_internal_snapshot.test.py`**, which validates the shape of an aggregate summary derived from status files — not the status files themselves. It does not check individual priority object fields, enum validity, or text quality.

**The highest-risk unenforced guardrails are in Group E (security).** Specifically: the absence of a Content Security Policy on any HTML page (E-5), innerHTML usage with user strings including a confirmed XSS finding (E-6), and the API key not being guaranteed absent from client code (E-1). These are not hypothetical — the current research and cybersecurity status files confirm all three are open findings with no automated detection.

**The quickest wins are the low-cost proposals** — particularly the JSON Schema for priority objects (C-4, C-7, C-8), the pre-commit hook blocking `.env` commits (E-2), the CSP absence scanner (E-5), and the CSS hex color linter (A-1). Together these six changes would convert the most consequential structural guardrails from prompt-only to at least partially deterministic, at under 4 hours of implementation time combined.

---

- **Recommendation:** Implement the six low-cost proposals first (JSON Schema for status files, pre-commit hook for `.env` files, CSP scanner, CSS hex color linter, `transition: all` detector, jargon regex check). Then schedule the medium-cost security scanner for the next development sprint.
- **Risks:** The CSS linter may produce false positives in the large inline `<style>` blocks in `room-layout-editor.html` — these will need triage on first run. The pre-commit hook approach only works if contributors use the local git repository; it does not help if files are modified by agents directly (e.g. via the supervisor API).
- **Confidence:** High — all findings are grounded in direct file reads. No enforcement mechanisms were assumed to exist that were not found.
- **Founder approval needed:** Yes — approving the decision to introduce pre-commit hooks and a validation script, and choosing which enforcement failures should block commits vs. warn only.
- **Next actions:** Development — implement `scripts/validate_status_files.py` with JSON Schema and the six low-cost checks. Cybersecurity — review the proposed pre-commit hook for credential scanning. Research — log this report in the library index.
