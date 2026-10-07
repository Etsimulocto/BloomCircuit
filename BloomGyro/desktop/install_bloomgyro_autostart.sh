#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/bloomgyro-plug-watch.desktop"
LOG_DIR="$HOME/.local/share/bloomgyro"

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
Name=BloomGyro USB Watcher
Comment=Open BloomGyro Mini when BloomGyro is plugged in
Exec=python3 $HERE/bloomgyro_plug_watch.py
Path=$HERE
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

chmod +x "$DESKTOP_FILE"
chmod +x "$HERE/bloomgyro_plug_watch.py" "$HERE/bloomgyro_mini.py"

pkill -f '[b]loomgyro_plug_watch.py' 2>/dev/null || true
nohup python3 "$HERE/bloomgyro_plug_watch.py" \
  >> "$LOG_DIR/plug_watch.log" 2>&1 < /dev/null &

echo "Installed: $DESKTOP_FILE"
echo "BloomGyro watcher started."
echo "Plug BloomGyro in -> Mini opens."
echo "Unplug BloomGyro -> Mini closes after the USB disconnect grace."
