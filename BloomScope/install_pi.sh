#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo apt-get install -y python3-tk python3-serial pulseaudio-utils alsa-utils
mkdir -p "$HOME/.local/share/applications"
DESKTOP="$HOME/.local/share/applications/bloomscope.desktop"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=BloomScope
Comment=ESP32 USB bench doctor
Exec=python3 "$HERE/bloomscope.py"
Path=$HERE
Icon=utilities-system-monitor
Terminal=false
Categories=Development;Electronics;
EOF
if [[ -d "$HOME/Desktop" ]]; then
  cp "$DESKTOP" "$HOME/Desktop/BloomScope.desktop"
  chmod +x "$HOME/Desktop/BloomScope.desktop"
fi
mkdir -p "$HOME/.config/autostart" "$HOME/.cache/bloomscope"
cat > "$HOME/.config/autostart/bloomscope-plug-watch.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=BloomScope USB Watcher
Comment=Open BloomScope when its ESP32 is plugged in
Exec=python3 "$HERE/plug_watch.py"
Path=$HERE
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
# Refresh the watcher now; login autostart handles subsequent desktop sessions.
pkill -f '[p]ython3 .*BloomScope/plug_watch.py' 2>/dev/null || true
nohup python3 "$HERE/plug_watch.py" >> "$HOME/.cache/bloomscope/watcher.log" 2>&1 < /dev/null &
echo 'USB auto-open watcher installed and started. Replug the BloomScope board.'
echo "Installed. Launch: python3 $HERE/bloomscope.py"
