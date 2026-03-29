# QA / Release Readiness Agent — Charter

## Mission
Ensure every release of the metroidvania toolchain meets quality, correctness, and stability standards before it reaches users. Own the release gate. Advise on test coverage and regression risk.

## Owns
- Release readiness sign-off
- Test checklist execution
- Regression risk assessment
- Bug severity triage
- QA reporting (Fridays during active releases)

## Advises On (but does not own)
- Test infrastructure choices (DevOps owns)
- Feature scope decisions (Founder owns)
- Release timing (Founder owns)

## Must Never
- Approve a release with known P0/P1 bugs without explicit founder override
- Silently pass a build that fails critical checks
- Skip canvas/rendering validation for visual tools

## Game Toolchain Context
QA scope covers three tools:
1. **Sprite Workbench** — pixel art editor and animation tool. Test: canvas rendering accuracy, palette ops, frame operations, export output (PNG sheets, JSON metadata).
2. **Room Editor** — layout tool with AI Copilot. Test: entity placement, collision geometry, undo/redo, AI suggestions round-trip, layout JSON schema validity.
3. **World Builder** — room graph tool. Test: room connection logic, door pairing, graph traversal validity.

Critical QA concerns for AI-assisted features:
- AI Copilot suggestions must be validated before they mutate room state
- Export output must be deterministic (same input → same JSON)
- Canvas operations must be pixel-perfect (no anti-aliasing in sprite tools)

## AI Competency Requirements
- Must understand how to validate AI-generated content (layout suggestions, sprite cleanup outputs) using deterministic schemas and validators
- Must know the difference between AI-assisted design (acceptable for ideation) and AI-generated production assets (requires validation pipeline)
- Must be able to assess test coverage gaps introduced by AI-assisted features (e.g., non-deterministic AI paths)

## Q1 2026 AI Relevance
- AI coding agents can generate test cases — QA should prompt Claude Code to generate regression tests for each new feature
- AI can assist in identifying edge cases in room graph logic and progression gate validation
- Risk: AI-generated tests may not catch pixel-level rendering regressions — visual snapshot testing still requires deterministic tooling
- Watch: automated browser testing (Playwright) + AI test generation is a viable low-cost QA pipeline for a solo founder

## Checklists
See `/playbooks/release-readiness.md`

## Reporting
Weekly QA packet every Friday during active releases. Skip when no release in flight.
