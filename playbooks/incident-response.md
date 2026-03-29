# Playbook: Incident Response

**Invoke:** orchestrator mode=incident
**Specialists involved:** Cybersecurity (if security), QA (if quality), Legal (if data), Support (if user-facing)
**Owner:** Orchestrator (coordinates), Founder (decides on response)

## Severity Levels

**P0 — Critical:** Data breach, security exploit, complete tool failure, AI feature producing harmful output.
**P1 — High:** Export corruption, major workflow broken, API key exposure, significant user data loss.
**P2 — Medium:** Feature regression, AI suggestions consistently wrong, performance degradation.

## Response Steps

### P0/P1
1. Orchestrator enters incident mode immediately
2. Loop in: Cybersecurity, QA, Legal within first 30 minutes
3. Assess blast radius: how many users affected?
4. Decide: take down vs. hotfix vs. disable specific feature
5. Communicate: draft user communication (Support drafts, Legal reviews, Founder approves)
6. Post-mortem within 48 hours

### P2
1. QA triages and prioritizes
2. Orchestrator adds to weekly review
3. Fix in next release cycle

## Post-Mortem Template
- What happened?
- Timeline of detection → resolution
- Root cause
- What would have caught this earlier?
- Changes to process/tooling/testing
