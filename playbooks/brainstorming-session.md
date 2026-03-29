# Playbook: Brainstorming Session

**Invoke:** orchestrator mode=brainstorm
**Specialists involved:** varies by topic
**Owner:** Orchestrator (facilitates), Founder (decides)

## Format

1. **Topic statement** — one sentence. What decision or design challenge is being explored?
2. **Relevant specialists** — which agents have domain knowledge here?
3. **Round 1: options** — each specialist generates 2-3 options from their domain perspective
4. **Round 2: stress test** — each specialist identifies the weakest assumption in one other option
5. **Round 3: synthesis** — orchestrator synthesizes into a structured summary
6. **Output** → `/templates/brainstorming-summary.md`

## Game Toolchain Usage
Common brainstorm topics:
- New entity type design (Support + QA input on UX + testability)
- AI feature scope (Legal + Cybersecurity on risk, QA on validation)
- Pricing model change (Finance + Marketing)
- New tool concept (Marketing on positioning, QA on scope risk)

## Anti-Patterns
- Don't brainstorm if a decision is already made — use decision mode instead
- Don't invite all specialists to every session — keep to 2-3 for focused output
- Don't let brainstorm outputs substitute for decision briefs on high-stakes items
