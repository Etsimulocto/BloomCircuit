#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$HOME/BloomCircuit"
APP="$REPO_DIR/happyjarz-controller/tools/happyjarz_meter.py"
APPS_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$APPS_DIR/bloompulse.desktop"

mkdir -p "$APPS_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=BloomPulse
GenericName=Music Reactive Light Controller
Comment=HAPPY JARZ music-reactive EQ and 16-bulb light controller
Exec=/usr/bin/python3 $APP
Path=$REPO_DIR
Icon=audio-x-generic
Terminal=false
Categories=AudioVideo;Audio;
Keywords=HAPPY JARZ;BloomPulse;EQ;music;audio;lights;LED;
StartupNotify=true
EOF

chmod 644 "$DESKTOP_FILE"

# Refresh the desktop menu cache when available. Raspberry Pi OS variants do not
# all ship the same helper, so these are intentionally optional.
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
if command -v lxpanelctl >/dev/null 2>&1; then
  lxpanelctl restart >/dev/null 2>&1 || true
fi

echo "BloomPulse installed."
echo "Look under: Raspberry Pi menu -> Sound & Video -> BloomPulse"
echo "Launcher: $DESKTOP_FILE"
