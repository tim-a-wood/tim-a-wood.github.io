#!/usr/bin/env bash
# Start the Agent OS supervisor (if needed) and open the dashboard in your browser.
# Safe to run repeatedly — skips launch when port is already listening.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

SUP_PORT="${OS_AGENT_OS_PORT:-${OS_DASHBOARD_SUPERVISOR_PORT:-8769}}"
WB_PORT="${OS_DASHBOARD_WORKBENCH_PORT:-8766}"
PYTHON="${PYTHON:-python3}"
URL="http://127.0.0.1:${SUP_PORT}/os-dashboard.html"
LOG="${TMPDIR:-/tmp}/os_dashboard_supervisor.log"

if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  echo "Error: ${PYTHON} not found." >&2
  exit 1
fi

if lsof -nP -iTCP:"${SUP_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  open "${URL}"
  exit 0
fi

nohup "${PYTHON}" scripts/os_dashboard_supervisor.py --port "${SUP_PORT}" --workbench-port "${WB_PORT}" >>"${LOG}" 2>&1 &

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${SUP_PORT}/api/dashboard-data" >/dev/null 2>&1; then
    open "${URL}"
    exit 0
  fi
  sleep 0.25
done

echo "Agent OS supervisor did not become ready in time. See ${LOG}" >&2
exit 1
