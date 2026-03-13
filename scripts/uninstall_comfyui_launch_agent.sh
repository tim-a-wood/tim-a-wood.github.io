#!/bin/zsh
set -euo pipefail

LABEL="com.timwood.mv.comfyui"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
UID_VALUE="$(id -u)"

launchctl bootout "gui/$UID_VALUE" "$PLIST_PATH" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"

echo "Removed LaunchAgent: $PLIST_PATH"
