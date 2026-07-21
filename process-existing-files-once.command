#!/bin/zsh
set -e
APP_DIR="$HOME/WatermarkAutomation"
LABEL="com.local.watermarkautomation"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
  echo "Install the automation first."
  read "?Press Return to close..."
  exit 1
fi

# Temporarily stop the background watcher to avoid a duplicate lock.
launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true

"$APP_DIR/.venv/bin/python" \
  "$APP_DIR/watermark_watcher.py" \
  --config "$APP_DIR/config.json" \
  --once

launchctl bootstrap "gui/$UID" "$PLIST_PATH"
launchctl kickstart -k "gui/$UID/$LABEL"

echo
echo "Existing Incoming files were processed."
read "?Press Return to close..."
