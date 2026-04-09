#!/bin/bash
# Double-click or Dock this file to open Agent OS (Engineering dashboard + workbench controls).
cd "$(dirname "$0")" || exit 1
exec bash scripts/start_agent_os_dashboard.sh
