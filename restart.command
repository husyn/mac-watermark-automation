#!/bin/zsh
set -e
LABEL="com.local.watermarkautomation"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ ! -f "$PLIST_PATH" ]]; then
  echo "The automation is not installed."
  read "?Press Return to close..."
  exit 1
fi

launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST_PATH"
launchctl kickstart -k "gui/$UID/$LABEL"

echo "Watermark automation restarted."
read "?Press Return to close..."
