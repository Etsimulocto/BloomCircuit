#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
HOME_DESKTOP="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
if [ -z "$HOME_DESKTOP" ]; then
  HOME_DESKTOP="$HOME/Desktop"
fi

mkdir -p "$DESKTOP_DIR" "$BIN_DIR" "$ICON_DIR" "$HOME_DESKTOP"

chmod +x "$APP_DIR/bloomcircuit_pi.py"

cat > "$BIN_DIR/bloomcircuit" <<EOF
#!/usr/bin/env bash
exec python3 "$APP_DIR/bloomcircuit_pi.py"
EOF
chmod +x "$BIN_DIR/bloomcircuit"

cp "$APP_DIR/bloomcircuit.svg" "$ICON_DIR/bloomcircuit.svg"

cat > "$DESKTOP_DIR/bloomcircuit.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=BloomCircuit
Comment=Offline circuit and breadboard layout editor
Exec=$BIN_DIR/bloomcircuit
Icon=bloomcircuit
Terminal=false
Categories=Development;Electronics;Education;
StartupNotify=true
EOF

chmod +x "$DESKTOP_DIR/bloomcircuit.desktop"

cp "$DESKTOP_DIR/bloomcircuit.desktop" "$HOME_DESKTOP/BloomCircuit.desktop"
chmod +x "$HOME_DESKTOP/BloomCircuit.desktop"

# Raspberry Pi OS / PCManFM may require desktop launchers to be marked trusted.
if command -v gio >/dev/null 2>&1; then
  gio set "$HOME_DESKTOP/BloomCircuit.desktop" metadata::trusted true >/dev/null 2>&1 || true
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo
echo "BloomCircuit installed."
echo "A BloomCircuit icon was added to your desktop:"
echo "  $HOME_DESKTOP/BloomCircuit.desktop"
echo
echo "You can also open it from the Raspberry Pi application menu, or run:"
echo "  bloomcircuit"
echo
echo "It runs entirely from: $APP_DIR"
echo "No internet connection is required."
