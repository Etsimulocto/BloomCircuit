#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFERRED="$HOME/HappyJarzController"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/happyjarz-plug-watch.desktop"
LOG_DIR="$HOME/.happyjarz"

# The Pi split workflow copies the controller to ~/HappyJarzController. Prefer
# that stable path so a .desktop file created from an older repo checkout cannot
# keep launching a stale watcher after branch changes.
if [[ -f "$PREFERRED/happyjarz_plug_watch.py" ]]; then
  TARGET="$PREFERRED"
else
  TARGET="$HERE"
fi

mkdir -p "$AUTOSTART_DIR" "$LOG_DIR"

# Only touch packages when the runtime dependencies are actually missing.
if ! python3 - <<'PY' >/dev/null 2>&1
import tkinter
import serial
PY
then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-tk python3-serial
  else
    python3 -m pip install --user -r "$TARGET/requirements.txt"
  fi
fi

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=HAPPY JARZ USB Watcher
Comment=Open the HAPPY JARZ controller when a Jar is plugged in
Exec=python3 $TARGET/happyjarz_plug_watch.py
Path=$TARGET
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

chmod +x "$DESKTOP_FILE"

# Replace any watcher launched from an older checkout immediately; no logout is
# required to activate the repaired autostart path.
pkill -f '[h]appyjarz_plug_watch.py' 2>/dev/null || true
nohup python3 "$TARGET/happyjarz_plug_watch.py" \
  >> "$LOG_DIR/plug_watch_manual_start.log" 2>&1 &

echo "Installed: $DESKTOP_FILE"
echo "Watcher path: $TARGET/happyjarz_plug_watch.py"
echo "Watcher restarted now and will also start at desktop login."
