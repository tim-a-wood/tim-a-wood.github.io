#!/bin/bash
# Daily Dashboard Update — refreshes all agent status JSONs via Claude and emails confirmation.
#
# Runs every day at noon via crontab:
#   0 12 * * * /Users/timwood/Desktop/projects/PWA/MV/scripts/update_dashboards.sh
#
# Each agent reads its charter, looks at recent git activity, and rewrites its
# status JSON in plain English. No jargon. No technical code snippets. Written
# for the founder, not for engineers.

set -euo pipefail

REPO="/Users/timwood/Desktop/projects/PWA/MV"
CLAUDE="/opt/homebrew/bin/claude"
PYTHON="/usr/bin/python3"
LOG="$REPO/artifacts/dashboard-update-cron.log"

cd "$REPO"
source .env.local 2>/dev/null || true

TODAY=$(date +%Y-%m-%d)
echo "" >> "$LOG"
echo "[$(date)] ── Dashboard update starting ─────────────────" >> "$LOG"

GIT_LOG=$(git log --oneline --since="48 hours ago" 2>/dev/null | head -20 || echo "(no recent commits)")

# Extract first valid JSON object from Claude output. If extraction fails,
# print nothing so the caller keeps the existing file.
extract_json() {
  "$PYTHON" - <<'PYEOF'
import sys, json, re
text = sys.stdin.read()
# Find the outermost {...} block
start = text.find('{')
if start == -1:
    sys.exit(1)
depth = 0
for i, ch in enumerate(text[start:], start):
    if ch == '{': depth += 1
    elif ch == '}':
        depth -= 1
        if depth == 0:
            candidate = text[start:i+1]
            try:
                json.loads(candidate)
                print(candidate)
                sys.exit(0)
            except json.JSONDecodeError:
                pass
sys.exit(1)
PYEOF
}

PLAIN_LANGUAGE_DIRECTIVE="
IMPORTANT — Language rules for this dashboard:
- Write for the founder, not for engineers or product managers.
- No code snippets, file paths, function names, or technical acronyms in any text visible on the dashboard.
- No jargon: no 'schema versioning', 'instrumentation', 'telemetry', 'API', 'ledger', 'token violations', 'P0', 'P1'.
- Explain things in plain terms: 'saved files have no version number' not 'schema has no version field'.
- Priority titles should be one clear sentence saying what we're doing and why it matters.
- Notes should be one or two plain sentences a non-technical person could read and understand.
- Founder decisions should be phrased as real questions: 'What should we build first?' not 'Define prioritisation criteria'.
- If something is paused, say why in plain English.
- Keep it honest. If something is uncertain, say so plainly.
"

# ── Engineering ───────────────────────────────────────────────────────────────
echo "[$(date)] Updating engineering..." >> "$LOG"

ENG_CHARTER=$(cat "$REPO/agents/engineering/charter.md" 2>/dev/null)
ENG_CURRENT=$(cat "$REPO/engineering-status.json" 2>/dev/null)

ENG_PROMPT=$(cat <<PROMPT
You are the engineering lead for the MV metroidvania toolchain.

## Your Charter
$ENG_CHARTER

## Recent git activity (last 48 hours)
$GIT_LOG

## Current status file
$ENG_CURRENT

## Task
Today is $TODAY. Update engineering-status.json to reflect the current state of engineering work.

$PLAIN_LANGUAGE_DIRECTIVE

Output ONLY valid JSON. No markdown fences. No commentary before or after.
Match the exact structure of the current file. Update "updated" to "$TODAY".
Keep existing priorities unless there is clear evidence from git activity that something has changed.
PROMPT
)

ENG_JSON=$("$CLAUDE" -p "$ENG_PROMPT" --output-format text 2>>"$LOG" | extract_json || true)
if [ -n "$ENG_JSON" ]; then
  echo "$ENG_JSON" > "$REPO/engineering-status.json"
  echo "[$(date)] Engineering done." >> "$LOG"
else
  echo "[$(date)] WARNING: Could not extract valid JSON for engineering, keeping existing file." >> "$LOG"
fi

# ── QA ───────────────────────────────────────────────────────────────────────
echo "[$(date)] Updating QA..." >> "$LOG"

QA_CHARTER=$(cat "$REPO/agents/qa/charter.md" 2>/dev/null)
QA_CURRENT=$(cat "$REPO/qa-status.json" 2>/dev/null)

# Run actual tests and capture counts for the QA agent to use
JS_RESULTS=$(node --test tests/room-editor-export.test.js tests/game-logic.test.js tests/room-wizard-footprint.test.js tests/room-wizard-terrain.test.js tests/room-wizard-neighbor-align.test.js tests/room-wizard-environment.test.js tests/room-wizard-environment-copilot.test.js 2>&1 | tail -8 || echo "test run failed")
PY_RESULTS=$(python3 -m pytest tests/test_sprite_workbench.py tests/test_sprite_workbench_surface.py tests/test_project_asset_path_encoding.py tests/test_ashen_hollow_runtime_manifest.py -q 2>&1 | tail -3 || echo "test run failed")

QA_PROMPT=$(cat <<PROMPT
You are the QA lead for the MV metroidvania toolchain.

## Your Charter
$QA_CHARTER

## Today's test run results

JavaScript tests:
$JS_RESULTS

Python tests:
$PY_RESULTS

Note: tests/room_environment_system.test.py still has a broken import path and cannot be collected.

## Current status file
$QA_CURRENT

## Task
Today is $TODAY. Update qa-status.json with current test counts from the test results above.
Update test_suite.js_pass, test_suite.js_fail, test_suite.py_pass, test_suite.py_fail, test_suite.last_run to "$TODAY".
Update metrics.tests_passing, metrics.tests_failing, metrics.last_full_run.
Keep priorities, coverage_gaps, bugs, release_gate, and risks unchanged unless something in the test results indicates a change.

$PLAIN_LANGUAGE_DIRECTIVE

Output ONLY valid JSON. No markdown fences. No commentary before or after.
Match the exact structure of the current file. Update "updated" to "$TODAY".
PROMPT
)

QA_JSON=$("$CLAUDE" -p "$QA_PROMPT" --output-format text 2>>"$LOG" | extract_json || true)
if [ -n "$QA_JSON" ]; then
  echo "$QA_JSON" > "$REPO/qa-status.json"
  echo "[$(date)] QA done." >> "$LOG"
else
  # Minimal fallback: just update the date in the existing file
  "$PYTHON" - "$REPO/qa-status.json" "$TODAY" <<'PYEOF'
import sys, json
path, today = sys.argv[1], sys.argv[2]
with open(path) as f: d = json.load(f)
d['updated'] = today
if 'test_suite' in d: d['test_suite']['last_run'] = today
if 'metrics' in d: d['metrics']['last_full_run'] = today
print(json.dumps(d, indent=2))
PYEOF
  echo "[$(date)] WARNING: Could not extract valid JSON for QA, date-stamped only." >> "$LOG"
fi

# ── Design ───────────────────────────────────────────────────────────────────
echo "[$(date)] Updating design..." >> "$LOG"

DESIGN_CHARTER=$(cat "$REPO/agents/design/charter.md" 2>/dev/null)
DESIGN_CURRENT=$(cat "$REPO/design-status.json" 2>/dev/null)

DESIGN_PROMPT=$(cat <<PROMPT
You are the design lead for the MV metroidvania toolchain.

## Your Charter
$DESIGN_CHARTER

## Recent git activity (last 48 hours)
$GIT_LOG

## Current status file
$DESIGN_CURRENT

## Task
Today is $TODAY. Update design-status.json to reflect the current state of design work.

$PLAIN_LANGUAGE_DIRECTIVE

Output ONLY valid JSON. No markdown fences. No commentary before or after.
Match the exact structure of the current file. Update "updated" to "$TODAY".
PROMPT
)

DESIGN_JSON=$("$CLAUDE" -p "$DESIGN_PROMPT" --output-format text 2>>"$LOG" | extract_json || true)
if [ -n "$DESIGN_JSON" ]; then
  echo "$DESIGN_JSON" > "$REPO/design-status.json"
  echo "[$(date)] Design done." >> "$LOG"
else
  echo "[$(date)] WARNING: Could not extract valid JSON for design, keeping existing file." >> "$LOG"
fi

# ── Analytics ────────────────────────────────────────────────────────────────
echo "[$(date)] Updating analytics..." >> "$LOG"

ANALYTICS_CHARTER=$(cat "$REPO/agents/analytics/charter.md" 2>/dev/null)
ANALYTICS_CURRENT=$(cat "$REPO/analytics-status.json" 2>/dev/null)

ANALYTICS_PROMPT=$(cat <<PROMPT
You are the analytics lead for the MV metroidvania toolchain.

## Your Charter
$ANALYTICS_CHARTER

## Recent git activity (last 48 hours)
$GIT_LOG

## Current status file
$ANALYTICS_CURRENT

## Task
Today is $TODAY. Update analytics-status.json to reflect the current state of analytics work.

$PLAIN_LANGUAGE_DIRECTIVE

Output ONLY valid JSON. No markdown fences. No commentary before or after.
Match the exact structure of the current file. Update "updated" to "$TODAY".
PROMPT
)

ANALYTICS_JSON=$("$CLAUDE" -p "$ANALYTICS_PROMPT" --output-format text 2>>"$LOG" | extract_json || true)
if [ -n "$ANALYTICS_JSON" ]; then
  echo "$ANALYTICS_JSON" > "$REPO/analytics-status.json"
  echo "[$(date)] Analytics done." >> "$LOG"
else
  echo "[$(date)] WARNING: Could not extract valid JSON for analytics, keeping existing file." >> "$LOG"
fi

# ── Marketing ────────────────────────────────────────────────────────────────
echo "[$(date)] Updating marketing..." >> "$LOG"

MARKETING_CHARTER=$(cat "$REPO/agents/marketing/charter.md" 2>/dev/null)
MARKETING_CURRENT=$(cat "$REPO/marketing-status.json" 2>/dev/null)

MARKETING_PROMPT=$(cat <<PROMPT
You are the marketing lead for the MV metroidvania toolchain.

## Your Charter
$MARKETING_CHARTER

## Recent git activity (last 48 hours)
$GIT_LOG

## Current status file
$MARKETING_CURRENT

## Task
Today is $TODAY. Update marketing-status.json to reflect the current state of marketing work.

$PLAIN_LANGUAGE_DIRECTIVE

Output ONLY valid JSON. No markdown fences. No commentary before or after.
Match the exact structure of the current file. Update "updated" to "$TODAY".
PROMPT
)

MARKETING_JSON=$("$CLAUDE" -p "$MARKETING_PROMPT" --output-format text 2>>"$LOG" | extract_json || true)
if [ -n "$MARKETING_JSON" ]; then
  echo "$MARKETING_JSON" > "$REPO/marketing-status.json"
  echo "[$(date)] Marketing done." >> "$LOG"
else
  echo "[$(date)] WARNING: Could not extract valid JSON for marketing, keeping existing file." >> "$LOG"
fi

# ── Strategy ─────────────────────────────────────────────────────────────────
echo "[$(date)] Updating strategy..." >> "$LOG"

STRATEGY_CHARTER=$(cat "$REPO/agents/strategy/charter.md" 2>/dev/null)
STRATEGY_CURRENT=$(cat "$REPO/strategy-status.json" 2>/dev/null)

STRATEGY_PROMPT=$(cat <<PROMPT
You are the strategy lead for the MV metroidvania toolchain.

## Your Charter
$STRATEGY_CHARTER

## Recent git activity (last 48 hours)
$GIT_LOG

## Current status file
$STRATEGY_CURRENT

## Task
Today is $TODAY. Update strategy-status.json to reflect the current strategic picture.

$PLAIN_LANGUAGE_DIRECTIVE

Output ONLY valid JSON. No markdown fences. No commentary before or after.
Match the exact structure of the current file. Update "updated" to "$TODAY".
PROMPT
)

STRATEGY_JSON=$("$CLAUDE" -p "$STRATEGY_PROMPT" --output-format text 2>>"$LOG" | extract_json || true)
if [ -n "$STRATEGY_JSON" ]; then
  echo "$STRATEGY_JSON" > "$REPO/strategy-status.json"
  echo "[$(date)] Strategy done." >> "$LOG"
else
  echo "[$(date)] WARNING: Could not extract valid JSON for strategy, keeping existing file." >> "$LOG"
fi

# ── Orchestration ─────────────────────────────────────────────────────────────
echo "[$(date)] Updating orchestration..." >> "$LOG"

ORCH_CHARTER=$(cat "$REPO/agents/orchestrator/charter.md" 2>/dev/null)
ORCH_CURRENT=$(cat "$REPO/orchestration-status.json" 2>/dev/null)
ENG_UPDATED=$(cat "$REPO/engineering-status.json" 2>/dev/null)
DESIGN_UPDATED=$(cat "$REPO/design-status.json" 2>/dev/null)

ORCH_PROMPT=$(cat <<PROMPT
You are the orchestrator for the MV metroidvania toolchain.

## Your Charter
$ORCH_CHARTER

## Recent git activity (last 48 hours)
$GIT_LOG

## Engineering status (just updated)
$ENG_UPDATED

## Design status (just updated)
$DESIGN_UPDATED

## Current orchestration status file
$ORCH_CURRENT

## Task
Today is $TODAY. Update orchestration-status.json. Your job is to synthesise across all agents — surface the most important cross-team priorities, blockers, and founder decisions in plain language.

$PLAIN_LANGUAGE_DIRECTIVE

Output ONLY valid JSON. No markdown fences. No commentary before or after.
Match the exact structure of the current file. Update "updated" to "$TODAY".
PROMPT
)

ORCH_JSON=$("$CLAUDE" -p "$ORCH_PROMPT" --output-format text 2>>"$LOG" | extract_json || true)
if [ -n "$ORCH_JSON" ]; then
  echo "$ORCH_JSON" > "$REPO/orchestration-status.json"
  echo "[$(date)] Orchestration done." >> "$LOG"
else
  echo "[$(date)] WARNING: Could not extract valid JSON for orchestration, keeping existing file." >> "$LOG"
fi

# ── Email notification ────────────────────────────────────────────────────────
echo "[$(date)] Sending email notification..." >> "$LOG"

SUMMARY_MD=$(cat <<MD
# Dashboards Updated — $TODAY

All agent dashboards were refreshed at noon today.

## What was updated

- **Engineering** — current build priorities and blockers
- **QA** — test results (run live), known bugs, and what isn't tested yet
- **Design** — design work in progress and open decisions
- **Analytics** — tracking priorities and what we're measuring
- **Marketing** — content and messaging priorities
- **Strategy** — strategic position, risks, and founder decisions
- **Orchestration** — cross-team view synthesised from all of the above

Open the [Agent OS dashboard](http://127.0.0.1:8769/os-dashboard.html) to review.

---

*This notification is sent automatically each day at noon. If a dashboard shows stale data, check the update log at artifacts/dashboard-update-cron.log.*
MD
)

echo "$SUMMARY_MD" | "$PYTHON" "$REPO/scripts/send_weekly_digest.py" \
  --subject "[MV Agent OS] Dashboards updated — $TODAY" \
  --subtitle "Agent OS — Daily Dashboard Update" \
  >> "$LOG" 2>&1

echo "[$(date)] ── Dashboard update complete ──────────────────" >> "$LOG"
