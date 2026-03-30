#!/usr/bin/env bash
# Build a double-clickable .app (no Terminal window) in ~/Applications.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${ROOT}/macos/Agent-OS-Dashboard-MenuBar.applescript"
TMP="$(mktemp)"
mkdir -p "${HOME}/Applications"
OUT="${HOME}/Applications/Agent OS Dashboard.app"
sed "s|__MV_REPO_PATH__|${ROOT}|g" "${SRC}" >"${TMP}"
osacompile -o "${OUT}" "${TMP}"
rm -f "${TMP}"
echo "Installed: ${OUT}"
echo "Add to Dock: drag that app from Finder onto the Dock."
open -R "${OUT}"
