# Playbook: Weekly Founder Review

**Invoke:** orchestrator mode=weekly-review (Monday morning)
**Specialists involved:** All (summarized)
**Owner:** Orchestrator (compiles), Founder (reviews + decides)

## Orchestrator Compilation Steps

1. Collect weekly updates from: Marketing (Tue), Analytics (Wed), Support (Thu), Finance (Fri), QA (Fri if release)
2. Identify: items requiring founder decision this week
3. Identify: items that can be handled by orchestrator or specialists autonomously
4. Suppress: status updates with no change, no risk, no decision needed
5. Escalate immediately: any item that hit an escalation trigger during the week
6. Produce: single founder digest using `/templates/weekly-founder-digest.md`

## Format Rules
- Total digest: max 2 pages
- Each section: status + delta + action needed (or "no action")
- Decisions section: explicit list of what founder must decide this week
- One "AI opportunity of the week" — most relevant AI development that could affect this business

## Anti-Patterns
- Don't include every metric — only those that changed significantly or need action
- Don't smooth over specialist disagreements — flag them
- Don't defer escalations to the weekly review — escalate immediately when triggers hit
