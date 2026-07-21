#!/bin/zsh
set -euo pipefail

LABEL="com.local.watermarkautomation"
SOURCE_DIR="${0:A:h}"
APP_DIR="$HOME/WatermarkAutomation"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/$LABEL.plist"

echo
echo "Mac Watermark Automation Installer"
echo "=================================="
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required."
  echo
  if command -v brew >/dev/null 2>&1; then
    echo "Homebrew was found. Installing Python..."
    brew install python
  else
    echo "Install Python 3 first, then run this installer again."
    echo "Recommended: install Homebrew, then run: brew install python"
    echo
    read "?Press Return to close..."
    exit 1
  fi
fi

mkdir -p "$APP_DIR" "$PLIST_DIR"
mkdir -p "$APP_DIR/Incoming" "$APP_DIR/Watermarked"
mkdir -p "$APP_DIR/Originals" "$APP_DIR/Failed" "$APP_DIR/Logs"

cp "$SOURCE_DIR/watermark_watcher.py" "$APP_DIR/watermark_watcher.py"
cp "$SOURCE_DIR/config.json" "$APP_DIR/config.json"
cp "$SOURCE_DIR/README.md" "$APP_DIR/README.md"

if [[ ! -d "$APP_DIR/.venv" ]]; then
  echo "Creating the private Python environment..."
  python3 -m venv "$APP_DIR/.venv"
fi

echo "Installing image-processing libraries..."
"$APP_DIR/.venv/bin/python" -m pip install --quiet --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install --quiet \
  "Pillow>=11,<13" "pillow-heif>=0.20,<2"

chmod +x "$APP_DIR/watermark_watcher.py"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>$APP_DIR/.venv/bin/python</string>
    <string>$APP_DIR/watermark_watcher.py</string>
    <string>--config</string>
    <string>$APP_DIR/config.json</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$APP_DIR</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>ProcessType</key>
  <string>Background</string>

  <key>ThrottleInterval</key>
  <integer>10</integer>

  <key>StandardOutPath</key>
  <string>$APP_DIR/Logs/launchd-output.log</string>

  <key>StandardErrorPath</key>
  <string>$APP_DIR/Logs/launchd-error.log</string>
</dict>
</plist>
PLIST

plutil -lint "$PLIST_PATH" >/dev/null

launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST_PATH"
launchctl enable "gui/$UID/$LABEL" >/dev/null 2>&1 || true
launchctl kickstart -k "gui/$UID/$LABEL"

echo
echo "Installed successfully."
echo
echo "Folder: $APP_DIR"
echo "1. Edit config.json to change watermark text/settings."
echo "2. Or place a transparent PNG named watermark.png in that folder."
echo "3. Drop images into Incoming."
echo "4. Collect finished images from Watermarked."
echo
echo "In auto mode, watermark.png is used when present; otherwise text is used."
echo

open "$APP_DIR"
open -a TextEdit "$APP_DIR/config.json"

read "?Press Return to close..."
