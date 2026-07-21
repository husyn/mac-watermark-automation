#!/bin/zsh
set -e
LABEL="com.local.watermarkautomation"
APP_DIR="$HOME/WatermarkAutomation"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

echo
echo "This removes the background service."
echo "Your WatermarkAutomation folder and images will NOT be deleted."
echo
read "reply?Continue? Type YES: "

if [[ "$reply" != "YES" ]]; then
  echo "Cancelled."
  exit 0
fi

launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"

echo
echo "Background service removed."
echo "Your files remain at: $APP_DIR"
echo
read "?Press Return to close..."
