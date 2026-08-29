#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "Chưa có python3. Có thể cài bằng Homebrew: brew install python"
  exit 1
fi

SECRET_DIR="$HOME/.config/robot-ai-private"
TOKEN_FILE="$SECRET_DIR/mac_bridge_token"
mkdir -p "$SECRET_DIR"
chmod 700 "$SECRET_DIR"

if [ ! -s "$TOKEN_FILE" ]; then
  if [ -n "${ROBOT_MAC_BRIDGE_TOKEN:-}" ]; then
    printf '%s' "$ROBOT_MAC_BRIDGE_TOKEN" > "$TOKEN_FILE"
  else
    python3 - <<'PY' > "$TOKEN_FILE"
import secrets
print(secrets.token_urlsafe(48), end="")
PY
  fi
fi
chmod 600 "$TOKEN_FILE"

DEST="$HOME/Library/Application Support/RobotMacBridge"
mkdir -p "$DEST"
cp "$HERE/robot_mac_bridge.py" "$DEST/"
chmod +x "$DEST/robot_mac_bridge.py"

PLIST="$HOME/Library/LaunchAgents/com.robot.privatev1.macbridge.plist"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.robot.privatev1.macbridge</string>
<key>ProgramArguments</key><array>
<string>$PY</string>
<string>$DEST/robot_mac_bridge.py</string>
</array>
<key>EnvironmentVariables</key><dict>
<key>ROBOT_MAC_BRIDGE_TOKEN_FILE</key><string>$TOKEN_FILE</string>
</dict>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$HOME/Library/Logs/RobotMacBridge.log</string>
<key>StandardErrorPath</key><string>$HOME/Library/Logs/RobotMacBridge.err.log</string>
</dict></plist>
EOF

launchctl bootout gui/$(id -u) "$PLIST" 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$PLIST"
echo "Đã cài Robot Mac Bridge."
echo "Hãy cấp quyền Accessibility/Automation cho Terminal/Python khi macOS hỏi."
