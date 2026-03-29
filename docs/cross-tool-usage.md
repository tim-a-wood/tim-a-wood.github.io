# Cross-Tool Usage Notes

The business operating system in this repo is designed to work from Claude Code, Codex, and Cursor without maintaining separate logic.

## Shared Source of Truth

| File | Purpose | Used by |
|---|---|---|
| `AGENTS.md` | OS authority model + coding agent rules | All tools |
| `CLAUDE.md` | Claude Code-specific rules | Claude Code |
| `.cursor/rules/frontend-design.mdc` | Cursor-specific rules | Cursor |
| `agents/*/charter.md` | Specialist agent definitions | All tools |
| `playbooks/` | Recurring workflow procedures | All tools |
| `templates/` | Standard output formats | All tools |
| `knowledge/` | Domain knowledge base | All tools |

## Claude Code

Primary tool for: feature implementation, debugging, agent operations, orchestrator sessions.

**Invoking the orchestrator:**
```
Run orchestrator in [mode] mode: [topic]
Context: [brief]
Relevant playbook: playbooks/[relevant].md
```

**Invoking a specialist:**
```
You are the [specialist] agent for this metroidvania toolchain business.
Read: agents/[specialist]/charter.md
Task: [specific task]
Output format: templates/[relevant].md
```

**Scheduled reports:** Use Claude Code with the schedule skill to set up recurring digests.

## Codex (OpenAI)

Primary tool for: code generation, automated test creation, PR review.

Codex reads `AGENTS.md` as its primary instruction set. The coding agent rules (below the divider in AGENTS.md) are specifically formatted for Codex.

When using Codex for business OS tasks, prefix with:
```
Read AGENTS.md section "AI-Native Business Operating System" before proceeding.
You are acting as [specialist] agent.
```

## Cursor

Primary tool for: IDE-native editing, inline refactoring, context-aware code changes.

Cursor reads `.cursor/rules/frontend-design.mdc` for frontend work. For OS tasks, reference `AGENTS.md` directly.

## Anti-Patterns
- Don't create separate agent definitions for each tool — one charter.md per agent, used by all
- Don't store business decisions in tool-specific config files — use `/decisions/` directory
- Don't put sensitive data (API keys, user info) in any agent context file
