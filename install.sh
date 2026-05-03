#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_LABEL="com.adb-interaction-mcp"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
LOG_DIR="$HOME/Library/Logs/adb-interaction-mcp"

mkdir -p "$LOG_DIR"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/uv</string>
        <string>--directory</string>
        <string>$REPO_DIR</string>
        <string>run</string>
        <string>adb-mcp</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/server.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/server.log</string>
</dict>
</plist>
EOF

# Unload first in case it was already loaded (e.g. re-running install)
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load -w "$PLIST_PATH"

echo "✓ adb-interaction-mcp installed and started on port 8755"
echo "  Logs: $LOG_DIR/server.log"
echo "  Stop:    launchctl unload $PLIST_PATH"
echo "  Start:   launchctl load $PLIST_PATH"
