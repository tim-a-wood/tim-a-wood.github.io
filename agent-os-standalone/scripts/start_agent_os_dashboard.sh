#!/usr/bin/env bash
# Start the Agent OS supervisor (if needed) and open the dashboard in your browser.
# Safe to run repeatedly — skips launch when port is already listening.
#
# Issue chat: supervisor loads repo-root agent_os.env then .env.local (gitignored). See agent_os.env.example.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_APP_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE_DEFAULT_ROOT="${MV_WORKSPACE_ROOT:-${DEFAULT_APP_ROOT}}"
LAUNCH_ENV_FILE="${WORKSPACE_DEFAULT_ROOT}/.agent-os-launch.env"
if [ -f "${LAUNCH_ENV_FILE}" ]; then
  # shellcheck disable=SC1090
  source "${LAUNCH_ENV_FILE}"
fi
APP_ROOT_INPUT="${AGENT_OS_APP_ROOT:-${DEFAULT_APP_ROOT}}"
APP_ROOT="$(cd "${APP_ROOT_INPUT}" && pwd)"
WORKSPACE_ROOT_INPUT="${MV_WORKSPACE_ROOT:-${DEFAULT_APP_ROOT}}"
WORKSPACE_ROOT="$(cd "${WORKSPACE_ROOT_INPUT}" && pwd)"
cd "${APP_ROOT}"

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

if ! "${PYTHON}" -c "import markdown" >/dev/null 2>&1; then
  echo "Installing Markdown preview dependency (requirements-agent-os.txt)..." >&2
  "${PYTHON}" -m pip install -q -r "${APP_ROOT}/requirements-agent-os.txt" 2>/dev/null || {
    echo "Warning: could not install PyPI markdown; /view/markdown may show raw source until you run:" >&2
    echo "  ${PYTHON} -m pip install -r requirements-agent-os.txt" >&2
  }
fi

env MV_WORKSPACE_ROOT="${WORKSPACE_ROOT}" nohup "${PYTHON}" "${APP_ROOT}/scripts/os_dashboard_supervisor.py" --port "${SUP_PORT}" --workbench-port "${WB_PORT}" >>"${LOG}" 2>&1 &

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${SUP_PORT}/api/dashboard-data" >/dev/null 2>&1; then
    open "${URL}"
    exit 0
  fi
  sleep 0.25
done

echo "Agent OS supervisor did not become ready in time. See ${LOG}" >&2
exit 1
