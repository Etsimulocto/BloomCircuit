#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/BloomCircuit/BloomBoardTester"
DESKTOP_DIR="$HOME/Desktop"
APPLICATIONS_DIR="$HOME/.local/share/applications"
LAUNCHER_NAME="BloomBoardTester.desktop"

mkdir -p "$DESKTOP_DIR" "$APPLICATIONS_DIR"

cat > "$APPLICATIONS_DIR/$LAUNCHER_NAME" <<EOF
[Desktop Entry]
Type=Application
Name=BloomBoard Tester
Comment=ESP32-S3 SuperMini board diagnostics
Exec=python3 $APP_DIR/board_tester_v2.py
Path=$APP_DIR
Terminal=false
Categories=Development;Electronics;
StartupNotify=true
EOF

cp "$APPLICATIONS_DIR/$LAUNCHER_NAME" "$DESKTOP_DIR/$LAUNCHER_NAME"
chmod +x "$APPLICATIONS_DIR/$LAUNCHER_NAME" "$DESKTOP_DIR/$LAUNCHER_NAME"

# Mark trusted when supported by the desktop environment; harmless if unavailable.
if command -v gio >/dev/null 2>&1; then
  gio set "$DESKTOP_DIR/$LAUNCHER_NAME" metadata::trusted true >/dev/null 2>&1 || true
fi

echo "Installed BloomBoard Tester launcher:"
echo "  $DESKTOP_DIR/$LAUNCHER_NAME"
echo "  $APPLICATIONS_DIR/$LAUNCHER_NAME"
echo "You can now launch BloomBoard Tester from the desktop or application menu."
