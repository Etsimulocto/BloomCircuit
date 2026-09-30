#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/happyjarz-controller.desktop"

mkdir -p "$AUTOSTART_DIR"

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-pip python3-tk
fi

python3 -m pip install --user -r "$HERE/requirements.txt"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=HAPPY JARZ Controller
Comment=USB service and configuration controller for HAPPY JARZ
Exec=python3 $HERE/happyjarz_controller.py
Path=$HERE
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

chmod +x "$DESKTOP_FILE"

echo "Installed: $DESKTOP_FILE"
echo "HAPPY JARZ Controller will start at desktop login and wait for a Jar to be plugged in."
