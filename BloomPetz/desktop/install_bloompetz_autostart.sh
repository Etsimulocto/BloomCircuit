#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/bloompetz-plug-watch.desktop"
LOG_DIR="$HOME/.bloompetz"

mkdir -p "$AUTOSTART_DIR" "$LOG_DIR"

if ! python3 - <<'PY' >/dev/null 2>&1
import tkinter
import serial
PY
then
  sudo apt-get update
  sudo apt-get install -y python3 python3-tk python3-serial
fi

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=BloomPetz USB Watcher
Comment=Open BloomPetz Mini when the controller is plugged in
Exec=python3 $HERE/bloompetz_plug_watch.py
Path=$HERE
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

chmod +x "$DESKTOP_FILE"
chmod +x "$HERE/bloompetz_plug_watch.py" "$HERE/bloompetz_mini.py"

pkill -f '[b]loompetz_plug_watch.py' 2>/dev/null || true
nohup python3 "$HERE/bloompetz_plug_watch.py" \
  >> "$LOG_DIR/plug_watch.log" 2>&1 &

echo "Installed: $DESKTOP_FILE"
echo "BloomPetz plug watcher started now and will start at desktop login."
