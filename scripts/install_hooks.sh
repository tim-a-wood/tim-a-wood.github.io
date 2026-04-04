#!/usr/bin/env bash
# Install the MV / Sprite Workbench git pre-commit hook.
#
# This script symlinks scripts/pre-commit → .git/hooks/pre-commit so that
# the hook is version-controlled (in scripts/) and always current.
#
# Usage:
#   bash scripts/install_hooks.sh
#
# To uninstall:
#   rm .git/hooks/pre-commit

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOK_SOURCE="$REPO_ROOT/scripts/pre-commit"
HOOK_TARGET="$REPO_ROOT/.git/hooks/pre-commit"

if [ ! -f "$HOOK_SOURCE" ]; then
  echo "Error: $HOOK_SOURCE not found. Run from the repo root." >&2
  exit 1
fi

chmod +x "$HOOK_SOURCE"

if [ -L "$HOOK_TARGET" ]; then
  echo "Removing existing symlink at .git/hooks/pre-commit"
  rm "$HOOK_TARGET"
elif [ -f "$HOOK_TARGET" ]; then
  echo "Backing up existing .git/hooks/pre-commit → .git/hooks/pre-commit.bak"
  mv "$HOOK_TARGET" "$HOOK_TARGET.bak"
fi

ln -s "$HOOK_SOURCE" "$HOOK_TARGET"
echo "Installed: .git/hooks/pre-commit → scripts/pre-commit"
echo ""
echo "To test the hook without committing:"
echo "  bash scripts/pre-commit"
echo ""
echo "To run individual checks:"
echo "  python3 scripts/validate_status_files.py"
echo "  python3 scripts/lint_css_tokens.py"
echo "  python3 scripts/check_html_structure.py"
echo "  python3 scripts/check_escalation_conditions.py"
