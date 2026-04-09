#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG="${ROOT}/.agent-os-launch.env"

rm -f "${CONFIG}"
echo "Removed ${CONFIG}; launcher now defaults back to embedded Agent OS."
