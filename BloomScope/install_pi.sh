#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sudo apt-get install -y python3-tk python3-serial
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
echo "Installed. Launch: python3 $HERE/bloomscope.py"
