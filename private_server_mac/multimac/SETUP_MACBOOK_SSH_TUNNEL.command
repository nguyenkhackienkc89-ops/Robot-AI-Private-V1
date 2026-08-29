#!/bin/bash
set -euo pipefail
PORT=11436
LABEL="com.robotai.qwen35-tunnel"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
KEY="${ROBOTAI_QWEN35_SSH_KEY:-$HOME/.ssh/robotai_qwen35_ed25519}"

if [ ! -f "$KEY" ]; then
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh"
  ssh-keygen -t ed25519 -f "$KEY" -N "" -C "robotai-qwen35-macbook-tunnel"
fi

REMOTE_USER="${REMOTE_USER:-}"
REMOTE_HOST="${REMOTE_HOST:-}"
if [ -z "$REMOTE_USER" ]; then
  read -r -p "Tên user trên MacBook: " REMOTE_USER
fi
if [ -z "$REMOTE_HOST" ]; then
  read -r -p "IP hoặc hostname MacBook: " REMOTE_HOST
fi
TARGET="${REMOTE_USER}@${REMOTE_HOST}"

echo "Kiểm tra passwordless SSH..."
if ! ssh -i "$KEY" -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=5 "$TARGET" 'echo ROBOT_AI_SSH_OK' 2>/dev/null | grep -q ROBOT_AI_SSH_OK; then
  echo "Chưa có passwordless SSH."
  echo "Bật Remote Login trên MacBook, sau đó cấu hình SSH key từ Mac mini."
  echo "Public key cần thêm vào MacBook ~/.ssh/authorized_keys:"
  cat "$KEY.pub"
  exit 2
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/ssh</string>
    <string>-N</string><string>-T</string>
    <string>-o</string><string>ExitOnForwardFailure=yes</string>
    <string>-o</string><string>ServerAliveInterval=30</string>
    <string>-o</string><string>ServerAliveCountMax=3</string>
    <string>-o</string><string>ConnectTimeout=5</string>
    <string>-o</string><string>BatchMode=yes</string>
    <string>-o</string><string>IdentitiesOnly=yes</string>
    <string>-i</string><string>$KEY</string>
    <string>-L</string><string>127.0.0.1:${PORT}:127.0.0.1:11434</string>
    <string>$TARGET</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/robotai-qwen35-tunnel.out.log</string>
  <key>StandardErrorPath</key><string>/tmp/robotai-qwen35-tunnel.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/$LABEL"
sleep 2

curl -fsS http://127.0.0.1:${PORT}/api/tags | python3 -m json.tool >/tmp/robotai-qwen35-tags.json
grep -Ei 'qwen3\.5.*35b' /tmp/robotai-qwen35-tags.json || true

cat > "$(dirname "$0")/.macbook_node" <<EOF
REMOTE_USER=$REMOTE_USER
REMOTE_HOST=$REMOTE_HOST
LOCAL_PORT=$PORT
SSH_KEY=$KEY
EOF
echo "PASS: localhost:$PORT -> MacBook Ollama."
