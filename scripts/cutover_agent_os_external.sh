#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET="${1:-${ROOT}/agent-os-standalone}"
CONFIG="${ROOT}/.agent-os-launch.env"

if [ ! -d "${TARGET}" ]; then
  echo "Missing Agent OS standalone checkout: ${TARGET}" >&2
  exit 1
fi

cat > "${CONFIG}" <<EOF
AGENT_OS_APP_ROOT=${TARGET}
MV_WORKSPACE_ROOT=${ROOT}
EOF

echo "Agent OS cutover config written to ${CONFIG}"
echo "AGENT_OS_APP_ROOT=${TARGET}"
