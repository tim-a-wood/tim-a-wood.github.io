#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.timwood.mv.comfyui"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/$LABEL.plist"
LOG_DIR="$ROOT_DIR/tools/ComfyUI/logs"
PYTHON_BIN="$ROOT_DIR/tools/ComfyUI/.venv/bin/python"
COMFY_MAIN="$ROOT_DIR/tools/ComfyUI/main.py"
UID_VALUE="$(id -u)"

mkdir -p "$PLIST_DIR" "$LOG_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing ComfyUI python runtime: $PYTHON_BIN" >&2
  exit 1
fi

if [[ ! -f "$COMFY_MAIN" ]]; then
  echo "Missing ComfyUI entrypoint: $COMFY_MAIN" >&2
  exit 1
fi

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$COMFY_MAIN</string>
    <string>--listen</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>8188</string>
    <string>--disable-auto-launch</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key>
    <string>$HOME</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ProcessType</key>
  <string>Background</string>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/launchd.stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/launchd.stderr.log</string>
</dict>
</plist>
EOF

chmod 644 "$PLIST_PATH"

# Stop any existing foreground or background ComfyUI process using this workspace checkout.
pkill -f "$ROOT_DIR/tools/ComfyUI/main.py" >/dev/null 2>&1 || true

# Reload the agent cleanly if it already exists.
launchctl bootout "gui/$UID_VALUE" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID_VALUE" "$PLIST_PATH"
launchctl enable "gui/$UID_VALUE/$LABEL" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$UID_VALUE/$LABEL"

echo "Installed LaunchAgent: $PLIST_PATH"
echo "Label: $LABEL"
