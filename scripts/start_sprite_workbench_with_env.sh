#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env.local"
HOST="127.0.0.1"
PORT="8766"
HEALTH_URL="http://${HOST}:${PORT}/api/health"
APP_URL="http://${HOST}:${PORT}/tools/2d-sprite-and-animation/index.html"
LOG_FILE="/tmp/sprite_workbench_server.log"
PID_FILE="/tmp/sprite_workbench_server.pid"
SERVER_CMD=(python3 "${REPO_ROOT}/scripts/sprite_workbench_server.py" --host "${HOST}" --port "${PORT}")

cleanup() {
    if [[ -n "${SERVER_PID:-}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
        kill "${SERVER_PID}" >/dev/null 2>&1 || true
    fi
    rm -f "${PID_FILE}"
}

fail() {
    printf 'Error: %s\n' "$1" >&2
    exit 1
}

if [[ ! -f "${ENV_FILE}" ]]; then
    fail "Missing ${ENV_FILE}. Copy .env.local.example to .env.local and paste your Gemini API key."
fi

# Export sourced vars even if the file uses plain KEY=value entries.
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    fail "GEMINI_API_KEY is missing or empty in ${ENV_FILE}."
fi

printf 'Loaded GEMINI_API_KEY from .env.local\n'

if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 is not installed or not on PATH."
fi

if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    LISTENER="$(lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN | tail -n +2)"
    fail "Port ${PORT} is already in use. Stop the existing listener first.\n${LISTENER}"
fi

trap cleanup EXIT

SERVER_PID="$(python3 - "${LOG_FILE}" "${PID_FILE}" "${SERVER_CMD[@]}" <<'PY'
import os
import subprocess
import sys

log_file = sys.argv[1]
pid_file = sys.argv[2]
cmd = sys.argv[3:]

with open(log_file, "ab") as log:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        start_new_session=True,
        close_fds=True,
        env=os.environ.copy(),
    )

with open(pid_file, "w", encoding="utf-8") as handle:
    handle.write(str(proc.pid))

print(proc.pid)
PY
)"

for _ in $(seq 1 30); do
    if curl -fsS "${HEALTH_URL}" >/dev/null 2>&1; then
        trap - EXIT
        printf 'Sprite workbench server is healthy\n'
        printf 'PID %s\n' "${SERVER_PID}"
        printf 'Open %s\n' "${APP_URL}"
        exit 0
    fi
    if ! kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
        fail "Server exited before passing health check. See ${LOG_FILE}."
    fi
    sleep 1
done

fail "Server failed health check at ${HEALTH_URL}. See ${LOG_FILE}."
