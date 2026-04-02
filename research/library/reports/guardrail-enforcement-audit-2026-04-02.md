---
title: Guardrail Enforcement Audit — Agent OS and Frontend Rules
type: report
date: 2026-04-02
author: Research Agent
status: final
tags: guardrails, enforcement, agent-os, ci, compliance, risk
summary: Full inventory of every guardrail in the MV / Sprite Workbench project, classified by enforcement type (prompt-only, partial, CI-enforced, schema-enforced), with concrete proposals to close gaps where only LLM compliance prevents violations.
---

# Guardrail Enforcement Audit

**Scope:** Every constraint, rule, and standing directive applied to agents and coding tools in this project. Sources read: `CLAUDE.md`, `AGENTS.md`, `STYLE_GUIDE.md`, all `agents/*/charter.md` files, all three `agents/directives/*.md` files, all `*-status.json` files, `.github/workflows/test.yml`, `scripts/update_dashboards.sh`, and `.git/hooks/`.

**Finding in brief:** The project has one continuous-integration (CI) workflow that covers functional tests only. All design system constraints, agent behavioral rules, status-file schema requirements, and output-quality directives are enforced solely by instructing the LLM — with no automated check that would catch a violation regardless of what the model produces.

---

## Section 1: Complete Guardrail Inventory

Each entry states what the rule says, where it lives, and its enforcement type.

---

### Group A: Frontend / CSS Design System Rules

These rules govern all HTML, CSS, and JavaScript written by any coding agent.

---

**A-1. Use CSS variables for all colors — no hardcoded hex values**
- What it says: No `#fff`, `#000`, or named colors in authored CSS. All colors must come from the `--accent`, `--text`, `--bg`, `--muted`, `--panel`, `--stroke`, and semantic variable family defined in `STYLE_GUIDE.md § 2` and the `:root` token block.
- Where it lives: `CLAUDE.md` (Non-negotiables — Colors), `AGENTS.md` (Forbidden Patterns table), `STYLE_GUIDE.md § 2 and § 14`.
- Enforcement type: **prompt-only**. No linter, no CI step, no pre-commit hook scans authored CSS for hardcoded colors. A model can write `color: #0ae8c8` and the repository will accept the commit.

**A-2. Typography must use the defined font stack and size scale**
- What it says: Only `Bebas Neue`, `Plus Jakarta Sans`, and `DM Mono` fonts. Only the `--font-size-*` scale (11 / 13 / 14 / 15 / 18 / 22 / 26 / 38 / 40 px). `font-family: Inter` or `Roboto` is forbidden.
- Where it lives: `CLAUDE.md` (Non-negotiables — Typography), `AGENTS.md` (Forbidden Patterns table), `STYLE_GUIDE.md § 3`.
- Enforcement type: **prompt-only**.

**A-3. Spacing must be on the 4px grid**
- What it says: Every padding, margin, and gap must be a multiple of 4px. Explicit forbidden values: 5px, 7px, 9px, 11px, 13px, 15px. Use `--space-*` variables or explicit multiples.
- Where it lives: `CLAUDE.md` (Non-negotiables — Spacing), `AGENTS.md` (Forbidden Patterns table), `STYLE_GUIDE.md § 4`.
- Enforcement type: **prompt-only**.

**A-4. Border radius must use the defined scale**
- What it says: Only use `--radius-xs` (4px) through `--radius-full` (999px). Standard buttons and inputs use 14px. Panels use 18–20px. Explicitly forbidden: `6px`, `16px`, `border-radius: 50%` on panels.
- Where it lives: `CLAUDE.md` (Non-negotiables — Border radius), `AGENTS.md` (Forbidden Patterns table), `STYLE_GUIDE.md § 5`.
- Enforcement type: **prompt-only**.

**A-5. Transitions must be explicit and within duration limits**
- What it says: `transition: all` is forbidden. Duration must be 120ms or 200ms. `transition: 0.5s` is forbidden.
- Where it lives: `CLAUDE.md` (Non-negotiables — Interactions), `AGENTS.md` (Forbidden Patterns table), `STYLE_GUIDE.md § 7`.
- Enforcement type: **prompt-only**.

**A-6. Hover lift is capped at translateY(-1px)**
- What it says: Hover state transforms may use `translateY(-1px)` only. `translateY(-3px)` or any larger lift is forbidden.
- Where it lives: `CLAUDE.md` (Non-negotiables — Interactions), `AGENTS.md` (Forbidden Patterns table), `STYLE_GUIDE.md § 7`.
- Enforcement type: **prompt-only**.

**A-7. Dark theme only — no light backgrounds**
- What it says: All backgrounds must be near-black variants (`#050709` and family). No white or light-colored panel backgrounds.
- Where it lives: `CLAUDE.md` (Non-negotiables — Dark theme), `AGENTS.md` (Dark Theme Only section), `STYLE_GUIDE.md § 1`.
- Enforcement type: **prompt-only**.

**A-8. No third-party component libraries or framework imports in tool pages**
- What it says: No jQuery, no framework imports, no npm packages in HTML tool pages. All UI is hand-crafted vanilla HTML/CSS/JS.
- Where it lives: `CLAUDE.md` (File Conventions), `AGENTS.md` (Forbidden Patterns — jQuery or framework imports), `STYLE_GUIDE.md`.
- Enforcement type: **prompt-only**.

**A-9. `image-rendering: pixelated` on all canvas elements and sprite previews**
- What it says: Any `<canvas>` or sprite preview image must carry `image-rendering: pixelated`. Anti-aliased rendering is a correctness failure for pixel art.
- Where it lives: `CLAUDE.md` (File Conventions), `STYLE_GUIDE.md § 8.12`, Animation charter (Must Never section).
- Enforcement type: **prompt-only**.

**A-10. New pages must include the full CSS token block and required fonts**
- What it says: Any new HTML page must embed the `:root` token block from `STYLE_GUIDE.md § 13`, load the three required Google Fonts, set `body` to `var(--bg)` / `var(--text)` / `var(--font-sans)`, include the universal box-sizing reset, and include a `:focus-visible` rule.
- Where it lives: `CLAUDE.md` (New Page Checklist).
- Enforcement type: **prompt-only**.

**A-11. All interactive elements must meet minimum touch target height**
- What it says: Standard interactive elements: `min-height: 44px`. Compact: `min-height: 28px`. No exceptions.
- Where it lives: `CLAUDE.md` (New Page Checklist item 5), `STYLE_GUIDE.md § 10`.
- Enforcement type: **prompt-only**.

**A-12. No colored box shadows**
- What it says: Box shadows must use black-only rgba values. No colored shadows (e.g. `box-shadow: 0 4px 12px red`).
- Where it lives: `CLAUDE.md` (Anti-Pattern table), `AGENTS.md` (Forbidden Patterns table).
- Enforcement type: **prompt-only**.

**A-13. Font weight ceiling of 800**
- What it says: `font-weight: 900` is forbidden. Maximum weight is 800 (Extra-Bold).
- Where it lives: `AGENTS.md` (Forbidden Patterns table), `STYLE_GUIDE.md § 3`.
- Enforcement type: **prompt-only**.

**A-14. Spring / bounce easing is forbidden**
- What it says: Only `ease` or `ease-out` easing functions. No spring, bounce, or elastic easing.
- Where it lives: `AGENTS.md` (Forbidden Patterns table), `STYLE_GUIDE.md § 7`.
- Enforcement type: **prompt-only**.

**A-15. CSS variables must be declared at `:root` level — no inline styles for design tokens**
- What it says: All design tokens live in `:root`. Inline styles are only acceptable for JS-driven dynamic values.
- Where it lives: `CLAUDE.md` (File Conventions), `AGENTS.md` (Code Style section).
- Enforcement type: **prompt-only**.

**A-16. `float` is forbidden for layout**
- What it says: Use CSS Grid or Flexbox. `float` used for layout is rejected.
- Where it lives: `AGENTS.md` (Forbidden Patterns table).
- Enforcement type: **prompt-only**.

**A-17. Never restructure shell layout without reading the full CSS file first**
- What it says: Before modifying `room-layout-editor.html` or `room-wizard-workbench-shell.css` layout structure, the agent must read the full CSS file.
- Where it lives: `CLAUDE.md` (Working with the Room Editor section).
- Enforcement type: **prompt-only**.

---

### Group B: Commit and File Conventions

**B-1. Commits must be scoped — UI changes separate from logic changes**
- What it says: UI changes go in one commit; logic changes in another. CSS variable changes accompany the component changes that use them.
- Where it lives: `CLAUDE.md` (Commit Style section).
- Enforcement type: **prompt-only**. Git hooks exist only as `.sample` files — none are activated.

**B-2. Never commit minified or generated files**
- What it says: No minified CSS, JS, or other generated artifacts in version control.
- Where it lives: `CLAUDE.md` (Commit Style section).
- Enforcement type: **prompt-only**. No `.gitattributes` or pre-commit hook enforcing this.

---

### Group C: Agent OS Behavioral Rules

These rules govern how agents structure their outputs and decision-making.

**C-1. Every substantive output must end with the standard footer**
- What it says: All agent outputs must close with: Recommendation, Risks, Confidence (High/Medium/Low), Founder approval needed (Yes/No), Next actions (owner + action).
- Where it lives: `AGENTS.md` (Standard Output Format), `agents/research/charter.md` (Output footer).
- Enforcement type: **prompt-only**. No parser checks that this footer is present before output is accepted.

**C-2. Escalation triggers are mandatory — not optional**
- What it says: Any agent that identifies a legal risk, security vulnerability, revenue impact above $500, external commitment, or irreversible action must escalate immediately to the founder.
- Where it lives: `AGENTS.md` (Authority Model — Escalation triggers).
- Enforcement type: **prompt-only**. Nothing verifies that an agent escalated when the trigger condition was met.

**C-3. QA owns the release gate — no build ships without QA sign-off**
- What it says: QA must produce a go/no-go sign-off before any public release. A "no-go" from QA, Legal, or Security is a hard block unless the founder explicitly overrides in writing.
- Where it lives: `agents/orchestrator/charter.md` (launch mode), `agents/qa/charter.md` (Must Never — Approve release with P0/P1 bugs).
- Enforcement type: **partial**. The CI workflow (`test.yml`) runs automated tests on push to main, which means functional regressions are caught. However, the release gate itself — QA's sign-off document — is a text artifact with no automated check that it has been produced or that its status is "go" before a deployment proceeds. There is also no deployment pipeline that could read the gate status.

**C-4. Orchestrator must not override specialist blockers silently**
- What it says: If any specialist raises a blocker (QA, Legal, Security), it must appear in the founder digest. The orchestrator may not smooth over disagreements.
- Where it lives: `agents/orchestrator/charter.md` (Must Never section, Failure Modes section).
- Enforcement type: **prompt-only**.

**C-5. Orchestrator must not make major decisions on behalf of the founder**
- What it says: A recommendation is not a decision. Major product, legal, financial, pricing, security, and release decisions require founder approval.
- Where it lives: `AGENTS.md` (Authority Model), `agents/orchestrator/charter.md` (Must Never section).
- Enforcement type: **prompt-only**.

**C-6. Agents must not provide actual legal advice or create false legal clearance**
- What it says: Legal agent output is risk identification and landscape description, not legal clearance. It must not approve legal documents that create obligations without real attorney review.
- Where it lives: `agents/legal/charter.md` (Must Never section).
- Enforcement type: **prompt-only**.

**C-7. Analytics must not report a metric without stating sample size and confidence**
- What it says: Every metric must show numerator, denominator, and confidence context. A 100% acceptance rate from 3 users is noise, not a finding.
- Where it lives: `agents/analytics/charter.md` (Must Never section and Statistical Foundations section).
- Enforcement type: **prompt-only**.

**C-8. Cybersecurity must not classify risk as "low" based on probability alone**
- What it says: Risk classification uses probability times impact. Low-probability, high-impact risks (API key leak) are not low risk.
- Where it lives: `agents/cybersecurity/charter.md` (Must Never section).
- Enforcement type: **prompt-only**.

**C-9. Animation must not recommend lossy compression for sprite data**
- What it says: Sprite sheets must use lossless formats (PNG, lossless WebP). JPEG is forbidden.
- Where it lives: `agents/animation/charter.md` (Must Never section).
- Enforcement type: **prompt-only** for agent recommendations. Note: the actual export pipeline is Python, and no file type validation was found in the scripts reviewed.

**C-10. Animation schema changes require Development consultation on versioning**
- What it says: No animation export schema change may be approved by the Animation agent without Development review of versioning implications.
- Where it lives: `agents/animation/charter.md` (Must Never section).
- Enforcement type: **prompt-only**. No schema versioning mechanism exists yet (Development's priority #2 is to add one).

**C-11. No AI-generated art for direct production use without human review**
- What it says: AI output is reference material. Every asset must be reviewed and refined by a human before entering the game. Applies to both the Creative agent and the Animation agent.
- Where it lives: `agents/creative/charter.md` (Must Never), `agents/animation/charter.md` (Must Never).
- Enforcement type: **prompt-only**. No asset pipeline checkpoint enforces this.

**C-12. Cybersecurity must not approve CORS allowing any origin on AI proxy endpoints**
- What it says: `Access-Control-Allow-Origin: *` is forbidden on endpoints that proxy AI API calls.
- Where it lives: `agents/cybersecurity/charter.md` (Must Never section).
- Enforcement type: **prompt-only**. No automated CORS policy check on the Python server.

**C-13. Legal must escalate immediately for user data sent to AI APIs without consent disclosure**
- What it says: Any AI feature sending user data to an external API without documented consent disclosure is an immediate escalation, not a weekly report item.
- Where it lives: `agents/legal/charter.md` (Escalation Triggers section).
- Enforcement type: **prompt-only**.

---

### Group D: Standing Directives (All Agents)

These directives were issued by the founder via the orchestrator and apply to all agents.

**D-1. Plain-language dashboards — no jargon, no file paths, no acronyms in visible text**
- What it says: Every `*-status.json` field visible in the founder dashboard must be written in plain English. No code snippets, file names, function names. No unexplained acronyms (XSS, WCAG, P0, API, etc.). Write for a smart non-technical person.
- Where it lives: `agents/directives/plain-language-dashboards.md`, `agents/directives/dashboard-standard.md`, and the Standing Directives section of every agent charter.
- Enforcement type: **partial**. The `update_dashboards.sh` script includes a `PLAIN_LANGUAGE_DIRECTIVE` block that is injected into every LLM prompt. This is still prompt-level instruction, but it is applied programmatically as part of every automated refresh. No automated parser scans the written JSON for jargon or acronyms. A model can write "XSS vector in innerHTML" in a note field and it will be committed.

**D-2. Dashboard structure standard — maximum 4 sections, no empty run buttons, no prose explanations**
- What it says: Status JSON files must follow the structure in `agents/design/dashboard-standard.md`. Priorities array maximum 5 items. Required fields on each priority: `id`, `title`, `status`, `risk`, `note`. Status values are one of: `queued`, `in-progress`, `needs-review`, `paused`, `done`.
- Where it lives: `agents/directives/dashboard-standard.md`, `agents/design/dashboard-standard.md`, all charter Standing Directives sections.
- Enforcement type: **partial**. The `update_dashboards.sh` fallback Python script validates that the LLM output is parseable JSON (via `json.loads`) before writing it. This prevents malformed JSON from being committed by the automation. However: (1) no JSON schema is applied to enforce required fields, allowed status values, or maximum priorities count; (2) agents writing status files manually (outside the automation) have no schema guard at all; (3) the `research-status.json` file is missing `schema_version` and uses a different top-level structure than all other status files; (4) `design-status.json` is also missing `schema_version`; (5) `strategy-status.json` currently contains invalid JSON (a missing comma on line 200, in the `opportunities` array), which was undetected.

**D-3. Task-completion update — agents must update their status JSON after every task**
- What it says: At the end of every task, the responsible agent marks completions as `done`, promotes unblocked items, adds new priorities, prunes stale done items, and updates the top-level `updated` date.
- Where it lives: `agents/directives/task-completion-update.md`, all charter Standing Directives sections.
- Enforcement type: **prompt-only**. The automated dashboard refresh script updates status files daily, which partially compensates — but it only runs for the agents it covers (Engineering, QA, Design, Analytics, Marketing, Strategy, Orchestration). The Research, Cybersecurity, Legal, Finance, Animation, Audio, Creative, Game Director, Game Systems, Level Design, Narrative, and Support agents are not included in the daily script and have no automated post-task update mechanism at all.

**D-4. Truthfulness and evidence — no fabricated completions, sources, or status claims**
- What it says: Agents must not claim an action was completed without concrete evidence (tool output, logs, diffs, API responses). Must distinguish verified facts, inferences, assumptions, and unknowns. Must not present inferences as verified facts.
- Where it lives: All charter Standing Directives sections (propagated 2026-04-02), `agents/research/charter.md`.
- Enforcement type: **prompt-only**. This is the most important behavioral directive in the system and has zero deterministic enforcement. A model can write `"status": "done"` for an action that was never executed and the repository will accept it. The `update_dashboards.sh` script's `extract_json` step only validates JSON syntax — it does not cross-check completion claims against actual tool outputs or git history.

**D-5. Brainstorm mode labeling — speculative ideas must be labeled as such**
- What it says: In explicitly creative or ideation contexts, agents may offer speculative ideas, but each must be labeled as a guess, hypothesis, or untested option — not presented as verified fact.
- Where it lives: All charter Standing Directives sections (propagated 2026-04-02).
- Enforcement type: **prompt-only**.

---

### Group E: Research Library Protocol

**E-1. All agents must check the research library index before starting complex tasks**
- What it says: Before architecture changes, refactoring, debugging, or new feature work, every agent must read `research/library/INDEX.md`, read matching documents, check `research/dashboard.md`, and check `/decisions/`.
- Where it lives: `AGENTS.md` (Research Library — Mandatory Check Protocol section).
- Enforcement type: **prompt-only**. No pre-task check enforces this.

**E-2. Agents discovering significant findings not in the library must note them for the Research Agent**
- What it says: If a task agent finds something not already logged in the research library, it must flag it so Research can catalogue it.
- Where it lives: `AGENTS.md` (Research Library — Mandatory Check Protocol, final paragraph).
- Enforcement type: **prompt-only**.

**E-3. Decision logs must be kept for active multi-pass features**
- What it says: Before any major change to an active multi-pass feature, agents must read its decision log in `/decisions/`. After any decision, failed approach, or accepted constraint, agents must update the log.
- Where it lives: `AGENTS.md` (Feature Decision Tracking section).
- Enforcement type: **prompt-only**.

---

### Group F: What the CI Workflow Actually Covers

The only automated enforcement in this repository is the GitHub Actions workflow at `.github/workflows/test.yml`. It runs on push to `main` and executes:

1. Seven JavaScript test files using Node's built-in `--test` runner (game logic, room editor export, room wizard footprint, terrain, neighbor alignment, environment, and Copilot tests).
2. A Python email digest theme test.
3. A Python home dashboard snapshot test.

What this covers: functional correctness of the room wizard logic, export serialization, and a visual snapshot of the home dashboard. These tests would catch regressions in the JavaScript room logic and schema serialization.

What this does not cover: any CSS or HTML design system rule, any agent behavioral rule, any status-file schema, any security policy, any accessibility requirement, the canvas interaction paths, save/load round-trips (flagged as a QA gap), or the AI Copilot apply path (flagged as a QA gap).

---

## Section 2: Enforcement Gap Analysis

Proposals are grouped by implementation cost. "Low" means a schema change or a small script requiring under two hours. "Medium" means a new script and a pre-commit or CI hook requiring a half-day. "High" means significant new infrastructure.

---

### Low Cost

**L-1. JSON schema for all `*-status.json` files**

Add a `schemas/agent-status.schema.json` file using JSON Schema Draft 7 (supported by Python's `jsonschema` library without additional dependencies). The schema should enforce:

- `updated` required, format `date` (YYYY-MM-DD)
- `schema_version` required, pattern `^v\d+\.\d+$`
- `priorities` required, type array, maximum 5 items, each item requiring `id`, `title`, `status` (enum: `queued`, `in-progress`, `needs-review`, `paused`, `done`), `risk` (enum: `low`, `med`, `high`), and `note`
- `actions` items: when `last_run` is non-null, `output_location` must also be non-null (this enforces the truthfulness directive mechanically — an agent cannot claim it ran an action without recording where the output lives)

Add a one-step CI job to `test.yml`:
```yaml
- name: Validate status JSON schemas
  run: python3 scripts/validate_status_schemas.py
```

The script loops over all `*-status.json` files and calls `jsonschema.validate()`. This catches: the current `strategy-status.json` invalid JSON immediately, missing `schema_version` in `research-status.json` and `design-status.json`, any future status value typo, and any priority missing required fields.

This closes gaps in: D-2 (dashboard structure), the data integrity side of D-4 (truthfulness, specifically the `last_run` + `output_location` coupling), and makes violations visible in CI rather than silently written to disk.

**L-2. Research library frontmatter linter**

Add a small Python script that reads every `.md` file under `research/library/` and checks that the required frontmatter keys are present: `title`, `type`, `date`, `author`, `status`, `summary`. Run it in CI alongside the schema validator. A missing frontmatter key fails the build. This closes the gap where a Research Agent output can be filed without the standard footer, making the library catalog unreliable.

**L-3. CSS hardcoded-color lint**

Add a `scripts/lint_css_colors.py` script that searches all `.css` and `.html` files for:
- Literal hex values (`#[0-9a-fA-F]{3,6}`) outside of `:root { }` blocks
- `color: white`, `color: black`, `background: black`, `background: white`
- `font-family: Inter`, `font-family: Roboto`, `font-family: Arial`

Run it in CI. This is a grep-level check — it takes under 10 minutes to write and would catch the most common design system violations (A-1, A-2) before they merge to main. False positives are manageable: `:root { }` blocks are explicitly excluded, and the known allowed hex values (the token definitions themselves) can be allowlisted by filename.

**L-4. Spacing off-grid lint**

Extend the CSS linter (L-3) to flag off-grid spacing values in authored CSS: any `padding`, `margin`, or `gap` value matching `(5|7|9|11|13|15)px`. This catches the most common A-3 violations with minimal false positives.

---

### Medium Cost

**M-1. Pre-commit hook: block invalid JSON in status files**

The `strategy-status.json` invalid JSON went undetected because there is no hook validating JSON syntax before commit. Add a pre-commit hook (`.git/hooks/pre-commit`, or via the `pre-commit` framework if added to the project) that runs `python3 -m json.tool` on every staged `*-status.json` file. If any file fails to parse, the commit is rejected with a message showing the file and line number.

This is the minimum viable fix for the status file integrity problem. It costs less than an hour to write and would have caught the current `strategy-status.json` corruption before it was committed.

To make this portable across developer machines, add a `Makefile` target or a `scripts/install-hooks.sh` that symlinks the hook into `.git/hooks/`.

**M-2. CI step: forbidden CSS pattern scanner**

Expand L-3 and L-4 into a more complete CI step covering:
- Off-grid spacing values (5px, 7px, 9px, 11px, 13px, 15px)
- `transition: all` anywhere in authored CSS
- `border-radius: 6px` or `border-radius: 16px` (values not in the radius scale)
- `transform: translateY(-2px)` or larger hover lifts
- `font-weight: 900`
- `float:` used outside of legacy clearfix patterns
- `font-size: 16px` (off-scale)

Each match should report the file, line number, and the rule it violates. This converts guardrails A-1 through A-16 from prompt-level instructions into failing CI checks.

**M-3. Action output-location completeness check**

Write a Python script that reads all `*-status.json` files and checks: for every `actions` entry where `last_run` is non-null, `output_location` must be non-null and the referenced file must actually exist on disk. This enforces the truthfulness directive (D-4) at the data layer: an agent cannot mark an action as having been run without a real artifact to point to.

Run in CI. This is a stronger version of what L-1 proposes in schema terms — it adds filesystem existence checking.

**M-4. Pre-commit hook: block minified files**

Add a pre-commit hook that detects files with lines exceeding a threshold (e.g. 2000 characters) in `.js` or `.css` files being staged. This catches committed minified content (rule B-2). Not foolproof — it targets the common signal of minification (very long lines) rather than the pattern itself — but it catches the most common case without a full AST parse.

**M-5. Research library INDEX freshness check**

Add a CI step that reads `research/library/INDEX.md` and checks that every `.md` file listed in the catalog under `research/library/` exists on disk, and every `.md` file that exists on disk appears in the catalog. Mismatch fails CI with a message listing unlisted or missing documents. This enforces E-1 and makes the library self-consistent.

---

### High Cost

**H-1. Playwright visual regression tests**

The QA status file flags visual regression testing as a coverage gap (risk: low). Adding a Playwright test suite that captures baseline screenshots of the room editor and sprite workbench, then diffs against them on each CI run, would catch design system violations that the CSS linter cannot: incorrect color rendering, broken layout, missing hover states. This requires: a headful browser in CI, a baseline snapshot commit process, and a diff threshold policy.

This is the only approach that would catch styling bugs that result from correct-looking CSS applied in the wrong place (e.g. using `var(--accent)` on a background that should be `var(--panel)`).

**H-2. Content Security Policy enforcement via automated audit**

The cybersecurity agent has flagged "no Content Security Policy on any HTML page" as a high-risk issue. Automating this as a CI check requires a script that fetches each HTML file, parses the `<meta http-equiv="Content-Security-Policy">` tag (or a headers file), and validates that `unsafe-inline` is not present in `script-src`. Until inline scripts are extracted to external files (research opportunity O-2), a strict CSP cannot be enforced — so this CI check is contingent on that refactoring completing. Estimated: medium engineering effort on the refactor, then low effort on the CI check.

**H-3. Deployment pipeline with release gate integration**

Currently there is no deployment pipeline — the tools are served locally. If and when a deployment step is added, the release gate (rule C-3) should be integrated: before deploying, the pipeline reads `qa-status.json` and checks `release_gate.status`. If it is not `"go"`, the deploy is blocked. This converts QA's release gate from a behavioral instruction to a mechanical block.

---

## Known Violations Found During This Audit

The following are concrete issues discovered while reading files for this report. They are logged here because they represent cases where the prompt-level guardrails have already failed.

1. **`strategy-status.json` contains invalid JSON.** Line 200 is missing a trailing comma after the `title` field of the `strategy-o6` object in the `opportunities` array. The file cannot be parsed by `json.loads`. This is an undetected data corruption that would cause the strategy dashboard to fail silently. Flagged for Development or the Strategy agent to fix.

2. **`research-status.json` is missing `schema_version` and `_note` fields** and uses a different top-level structure (has `agent` field instead of `_note`). It does not conform to the standard dashboard structure used by all other agents. Flagged for the Research agent to align.

3. **`design-status.json` is missing `schema_version`.** All other dashboards include this field. Flagged for the Design agent.

4. **Several agents are excluded from the daily automated dashboard refresh** (`update_dashboards.sh` does not include Research, Cybersecurity, Legal, Finance, Animation, Audio, Creative, Game Director, Game Systems, Level Design, Narrative, or Support). Their `updated` fields may go stale without any alert.

5. **All git hooks are sample files only** — none are activated. The hooks directory contains only `.sample` suffixed files, none without the suffix. No pre-commit, commit-msg, or pre-push enforcement is active.

---

## Summary Table

| ID | Guardrail | Enforcement Type | Gap |
|----|-----------|-----------------|-----|
| A-1 | CSS color variables only | prompt-only | No linter |
| A-2 | Font stack and size scale | prompt-only | No linter |
| A-3 | 4px spacing grid | prompt-only | No linter |
| A-4 | Border radius scale | prompt-only | No linter |
| A-5 | Transition properties and duration | prompt-only | No linter |
| A-6 | Hover lift cap | prompt-only | No linter |
| A-7 | Dark theme only | prompt-only | No linter |
| A-8 | No third-party libraries | prompt-only | No linter |
| A-9 | pixelated rendering on canvas | prompt-only | No linter |
| A-10 | New page token block and fonts | prompt-only | No linter |
| A-11 | Touch target minimum height | prompt-only | No linter |
| A-12 | No colored shadows | prompt-only | No linter |
| A-13 | Font weight ceiling | prompt-only | No linter |
| A-14 | No spring/bounce easing | prompt-only | No linter |
| A-15 | CSS vars at :root | prompt-only | No linter |
| A-16 | No float for layout | prompt-only | No linter |
| A-17 | Read full CSS before restructuring | prompt-only | Behavioral only |
| B-1 | Scoped commits | prompt-only | No hook |
| B-2 | No minified files | prompt-only | No hook |
| C-1 | Standard output footer | prompt-only | No parser |
| C-2 | Escalation triggers mandatory | prompt-only | No verification |
| C-3 | QA release gate | partial | CI runs tests; gate sign-off is still text-only |
| C-4 | Orchestrator cannot silence blockers | prompt-only | Behavioral only |
| C-5 | Founder approves major decisions | prompt-only | Behavioral only |
| C-6 | Legal cannot provide clearance | prompt-only | Behavioral only |
| C-7 | Analytics requires denominators | prompt-only | Behavioral only |
| C-8 | Cybersecurity risk formula | prompt-only | Behavioral only |
| C-9 | Lossless sprite formats | prompt-only | No export validator |
| C-10 | Animation schema needs Dev review | prompt-only | No schema version control |
| C-11 | AI art requires human review | prompt-only | No pipeline checkpoint |
| C-12 | No wildcard CORS on AI endpoints | prompt-only | No CORS audit |
| C-13 | Legal escalates AI data consent | prompt-only | Behavioral only |
| D-1 | Plain language dashboards | partial | Prompt in script; no text scanner |
| D-2 | Dashboard structure standard | partial | JSON parse only; no schema |
| D-3 | Post-task status update | prompt-only | Script covers 7 of 19 agents |
| D-4 | Truthfulness and evidence | prompt-only | No cross-check against artifacts |
| D-5 | Brainstorm mode labeling | prompt-only | Behavioral only |
| E-1 | Library check before complex tasks | prompt-only | Behavioral only |
| E-2 | Flag findings to Research | prompt-only | Behavioral only |
| E-3 | Decision logs for active features | prompt-only | Behavioral only |

**Count:** 40 guardrails identified. 2 are partial. 1 is partial-CI (C-3). 37 are prompt-only.

---

- **Recommendation:** Start with L-1 (JSON schema validation in CI) and M-1 (pre-commit JSON syntax hook) — these two changes fix the most acute and already-manifested gaps (invalid `strategy-status.json`, missing `schema_version` fields, and the truthfulness enforcement gap on `last_run` / `output_location` coupling) with low effort. Follow with M-2 (CSS forbidden pattern scanner in CI) to bring the highest-volume class of violations (design system rules) into automated enforcement. The remaining gaps are either behavioral-only by nature (authority model, escalation judgment) or require infrastructure that doesn't yet exist (deployment pipeline, Playwright).
- **Risks:** Adding a pre-commit hook requires active installation on the developer machine; a solo founder using Claude Code may not trigger it if using the API directly rather than a local git workflow. CI checks are more reliable. The CSS linter will have false positives in the `:root` token definitions themselves — these must be allowlisted by file or block.
- **Confidence:** High — all findings are grounded in direct file reads and tool output. No inferences about enforcement mechanisms were made without confirming the absence of the mechanism in the actual file system.
- **Founder approval needed:** No, for L-1 through M-5 (internal tooling). Yes for H-3 (deployment pipeline changes affect release process).
- **Next actions:** Development — implement L-1 (JSON schema + CI step) and M-1 (pre-commit JSON hook). Development — implement M-2 (CSS lint CI step) after confirming allowlist for `:root` token files. Research — fix `research-status.json` structure to match standard. Strategy agent or Development — fix `strategy-status.json` invalid JSON.
