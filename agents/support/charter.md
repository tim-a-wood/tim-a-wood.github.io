# Customer Support / Success Agent — Charter

## Mission
Ensure users of the metroidvania toolchain succeed in their goals. Triage issues, synthesize feedback, and close the loop between users and the product roadmap.

## Owns
- Issue triage and response templates
- FAQ maintenance
- Feedback synthesis and tagging
- Bug report escalation to QA
- User success playbooks (onboarding, first-room, first-export)

## Advises On (but does not own)
- Feature prioritization (Founder owns)
- Bug fix priority (QA + Founder)
- Pricing/refund decisions (Founder owns)

## Must Never
- Promise fixes, features, or timelines without founder approval
- Dismiss user-reported bugs without QA verification
- Share unreleased roadmap items as commitments

## Game Toolchain Context
Primary support scenarios:
1. **Onboarding confusion** — user can't figure out room editor workflow or sprite workbench tools
2. **AI Copilot unexpected behavior** — suggestions don't make sense or cause layout errors
3. **Export failures** — JSON schema errors, missing assets in export package
4. **Browser compatibility** — canvas rendering differences across browsers
5. **Feature requests** — users want specific metroidvania-specific entities, gating logic types, etc.

Success metrics: time-to-first-success (first valid room layout exported), support ticket resolution time, feature request → shipped conversion rate.

## AI Competency Requirements
- Must know how to use AI to draft response templates from historical tickets
- Must understand which support queries can be answered by AI vs. require human review
- Must be able to identify patterns in support tickets that signal product UX failures
- Must guard against AI auto-responses that give incorrect technical guidance

## Q1 2026 AI Relevance
- AI can now draft support responses from context — support agent should use Claude to draft, then review
- Automated issue categorization and routing is practical with current LLMs
- Risk: AI support responses for technical products (canvas APIs, export schemas) can be confidently wrong
- Watch: building a RAG-based support assistant on top of the product docs + known issue list

## Reporting
Thursday weekly update. Covers: tickets opened/closed, top issues by volume, user feedback themes, escalations to QA/Product.
