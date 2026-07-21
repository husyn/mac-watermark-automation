#!/bin/zsh
LABEL="com.local.watermarkautomation"
APP_DIR="$HOME/WatermarkAutomation"

echo
echo "Watermark Automation Status"
echo "==========================="
echo

if launchctl print "gui/$UID/$LABEL" >/dev/null 2>&1; then
  echo "Status: RUNNING"
else
  echo "Status: NOT RUNNING"
fi

echo "Incoming:    $APP_DIR/Incoming"
echo "Watermarked: $APP_DIR/Watermarked"
echo "Originals:   $APP_DIR/Originals"
echo "Log:         $APP_DIR/Logs/watermark.log"
echo

if [[ -f "$APP_DIR/Logs/watermark.log" ]]; then
  echo "Latest activity:"
  tail -n 12 "$APP_DIR/Logs/watermark.log"
fi

echo
read "?Press Return to close..."
