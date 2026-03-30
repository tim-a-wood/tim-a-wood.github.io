#!/usr/bin/env bash
# Send the MV Company Brand Charter PDF via Resend — same stack as update_dashboards.sh
#
# Requires in .env.local (or environment):
#   RESEND_API_KEY
#   DIGEST_EMAIL_TO      (optional; default in send_weekly_digest.py)
#   DIGEST_EMAIL_FROM    (optional)
#
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
# shellcheck source=/dev/null
source "$REPO/.env.local" 2>/dev/null || true

TODAY=$(date +%Y-%m-%d)
PDF="$REPO/docs/MV-Brand-Charter-v1.pdf"
BODY="$REPO/artifacts/brand-charter-email.md"

if [[ ! -f "$PDF" ]]; then
  echo "ERROR: Missing $PDF — generate from docs/brand-charter.html or restore from git." >&2
  exit 1
fi
if [[ ! -f "$BODY" ]]; then
  echo "ERROR: Missing $BODY" >&2
  exit 1
fi

exec python3 "$REPO/scripts/send_weekly_digest.py" \
  --file "$BODY" \
  --subject "[MV Agent OS] Company Brand Charter v1.0 — PDF attached — $TODAY" \
  --subtitle "Marketing · Strategy · Design" \
  --attach "$PDF"
