#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/happyjarz-plug-watch.desktop"

mkdir -p "$AUTOSTART_DIR"

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-tk python3-serial
else
  python3 -m pip install --user -r "$HERE/requirements.txt"
fi

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=HAPPY JARZ USB Watcher
Comment=Open the HAPPY JARZ controller when a Jar is plugged in
Exec=python3 $HERE/happyjarz_plug_watch.py
Path=$HERE
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

chmod +x "$DESKTOP_FILE"

echo "Installed: $DESKTOP_FILE"
echo "The watcher will start at desktop login and open the controller when a HAPPY JARZ is plugged in."
