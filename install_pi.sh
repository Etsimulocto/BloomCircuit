#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

mkdir -p "$DESKTOP_DIR" "$BIN_DIR" "$ICON_DIR"

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

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo
echo "BloomCircuit installed."
echo "Open it from the Raspberry Pi application menu, or run:"
echo "  bloomcircuit"
echo
echo "It runs entirely from: $APP_DIR"
echo "No internet connection is required."
