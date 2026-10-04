#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$HOME/BloomCircuit"
WATCHER="$REPO_DIR/happyjarz-controller/tools/happyjarz_autolaunch.py"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/happyjarz-autolaunch.desktop"

mkdir -p "$AUTOSTART_DIR"
chmod +x "$WATCHER"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=HAPPY JARZ Controller Auto-Launch
Comment=Open the HAPPY JARZ EQ tuner when the ESP32 controller is plugged in
Exec=python3 $WATCHER
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

# Replace any older watcher process so updates take effect immediately.
pkill -f "python3 .*happyjarz_autolaunch.py" >/dev/null 2>&1 || true
sleep 0.25
nohup python3 "$WATCHER" >/tmp/happyjarz-autolaunch.log 2>&1 &

echo "HAPPY JARZ auto-launch installed."
echo "The watcher now waits for a stable serial port and stays out of the way while arduino-cli/esptool is flashing."
echo "Plugging /dev/ttyACM0 in will open the tuner. Unplugging closes the tuner cleanly."
echo "If you manually close the tuner while it is still plugged in, it will stay closed until the next unplug/replug."
