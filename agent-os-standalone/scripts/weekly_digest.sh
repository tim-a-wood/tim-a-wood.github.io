#!/bin/bash
# Weekly Founder Digest — generates via Claude CLI and emails via Resend
# Runs every Monday at 9:07am via crontab
# Install: crontab -e → add: 7 9 * * 1 /Users/timwood/Desktop/projects/PWA/MV/scripts/weekly_digest.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_INPUT="${MV_WORKSPACE_ROOT:-${APP_ROOT}}"
REPO="$(cd "${REPO_INPUT}" && pwd)"
CLAUDE="/opt/homebrew/bin/claude"
PYTHON="/usr/bin/python3"
LOG="$REPO/artifacts/weekly-digest-cron.log"

cd "$REPO"
source "$REPO/.env.local" 2>/dev/null || true

TODAY=$(date +%Y-%m-%d)
ARTIFACT="$REPO/artifacts/weekly-digest-$TODAY.md"

echo "[$(date)] Starting weekly digest" >> "$LOG"

# ── Build context ──────────────────────────────────────────────────────────

GIT_LOG=$(git log --oneline --since="7 days ago" 2>/dev/null || echo "(no commits this week)")
GIT_STATUS=$(git status --short 2>/dev/null | head -30 || echo "(clean)")

CHARTER=$(cat "$REPO/agents/orchestrator/charter.md" 2>/dev/null)
PLAYBOOK=$(cat "$REPO/playbooks/weekly-founder-review.md" 2>/dev/null)
TEMPLATE=$(cat "$REPO/templates/weekly-founder-digest.md" 2>/dev/null)

# ── Generate digest ────────────────────────────────────────────────────────

PROMPT=$(cat <<PROMPT
You are the Orchestrator agent for the MV metroidvania toolchain business.

## Your Charter
$CHARTER

## Playbook
$PLAYBOOK

## Output Template
$TEMPLATE

## This Week's Git Activity
Commits (last 7 days):
$GIT_LOG

Uncommitted changes:
$GIT_STATUS

## Task
Today is $TODAY. Compile the weekly founder digest using the template above.
Base it entirely on the git activity shown — do not invent items.
Suppress low-signal status updates. Surface only decisions the founder must make and risks that changed this week.
Write the output as clean markdown ready to be emailed.

End with:
- Recommendation:
- Risks:
- Confidence:
- Founder approval needed:
- Next actions:
PROMPT
)

echo "[$(date)] Calling Claude..." >> "$LOG"

DIGEST=$("$CLAUDE" -p "$PROMPT" --output-format text 2>>"$LOG")

if [ -z "$DIGEST" ]; then
  echo "[$(date)] ERROR: Empty digest from Claude" >> "$LOG"
  exit 1
fi

# ── Save artifact ──────────────────────────────────────────────────────────

echo "$DIGEST" > "$ARTIFACT"
echo "[$(date)] Saved to $ARTIFACT" >> "$LOG"

# ── Send email ─────────────────────────────────────────────────────────────

"$PYTHON" "$APP_ROOT/scripts/send_weekly_digest.py" --file "$ARTIFACT" >> "$LOG" 2>&1

echo "[$(date)] Done" >> "$LOG"
