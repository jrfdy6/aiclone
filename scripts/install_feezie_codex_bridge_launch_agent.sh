#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CANONICAL_ROOT="${OPENCLAW_WORKSPACE_ROOT:-/Users/neo/.openclaw/workspace}"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
LABEL="com.neo.feezie_codex_bridge"
PLIST_NAME="$LABEL.plist"

SOURCE_BRIDGE="$ROOT/scripts/local_codex_bridge.py"
SOURCE_WRAPPER="$ROOT/scripts/run_local_codex_bridge.sh"
SOURCE_PLIST="$ROOT/automations/launchd/$PLIST_NAME"

TARGET_SCRIPT_DIR="$CANONICAL_ROOT/scripts"
TARGET_AUTOMATION_DIR="$CANONICAL_ROOT/automations/launchd"
TARGET_BRIDGE="$TARGET_SCRIPT_DIR/local_codex_bridge.py"
TARGET_WRAPPER="$TARGET_SCRIPT_DIR/run_local_codex_bridge.sh"
TARGET_PLIST="$TARGET_AUTOMATION_DIR/$PLIST_NAME"
LIVE_PLIST="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

mkdir -p "$TARGET_SCRIPT_DIR" "$TARGET_AUTOMATION_DIR" "$LAUNCH_AGENTS_DIR" /Users/neo/.openclaw/logs

install -m 755 "$SOURCE_BRIDGE" "$TARGET_BRIDGE"
install -m 755 "$SOURCE_WRAPPER" "$TARGET_WRAPPER"
install -m 644 "$SOURCE_PLIST" "$TARGET_PLIST"
install -m 644 "$SOURCE_PLIST" "$LIVE_PLIST"

launchctl bootout "gui/$UID" "$LIVE_PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$LIVE_PLIST"

echo "Installed $LABEL"
echo "  bridge:  $TARGET_BRIDGE"
echo "  wrapper: $TARGET_WRAPPER"
echo "  plist:   $LIVE_PLIST"
echo "  log:     /Users/neo/.openclaw/logs/feezie_codex_bridge.log"
