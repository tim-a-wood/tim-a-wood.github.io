#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMFY_DIR="$ROOT_DIR/tools/ComfyUI"
PYTHON_BIN="$COMFY_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ComfyUI virtualenv is missing at $PYTHON_BIN" >&2
  exit 1
fi

exec "$PYTHON_BIN" "$COMFY_DIR/main.py" \
  --listen 127.0.0.1 \
  --port 8188 \
  --disable-auto-launch
