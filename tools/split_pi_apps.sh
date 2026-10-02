#!/usr/bin/env bash
set -euo pipefail

# Split the Pi tools into independent folders so switching Git branches never
# makes an app disappear again.
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

echo "Updating remote refs..."
git fetch origin main happyjarz-controller-v0.1

extract_dir() {
  local ref="$1"
  local source_dir="$2"
  local dest="$3"
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN
  git archive "$ref" "$source_dir" | tar -x -C "$tmp"
  mkdir -p "$dest"
  rsync -a --delete "$tmp/$source_dir/" "$dest/"
  rm -rf "$tmp"
  trap - RETURN
}

extract_dir origin/main BloomSaver "$HOME/BloomSaver"
extract_dir origin/happyjarz-controller-v0.1 BloomTunes "$HOME/BloomTunes"
extract_dir origin/happyjarz-controller-v0.1 happyjarz-controller "$HOME/HappyJarzController"

# Keep Pi login autostart tied to the stable split-app folder, not whichever
# Git branch/path happened to be checked out when the watcher was first installed.
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/happyjarz-plug-watch.desktop"
HJ_DIR="$HOME/HappyJarzController"
mkdir -p "$AUTOSTART_DIR" "$HOME/.happyjarz"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=HAPPY JARZ USB Watcher
Comment=Open the HAPPY JARZ controller when a Jar is plugged in
Exec=python3 $HJ_DIR/happyjarz_plug_watch.py
Path=$HJ_DIR
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
chmod +x "$DESKTOP_FILE"

# Activate the refreshed watcher immediately so logout/login is not required.
pkill -f '[h]appyjarz_plug_watch.py' 2>/dev/null || true
nohup python3 "$HJ_DIR/happyjarz_plug_watch.py" \
  >> "$HOME/.happyjarz/plug_watch_manual_start.log" 2>&1 &

cat <<EOF

Pi app folders are now independent:

  BloomCircuit editor : $HOME/BloomCircuit
  Happy Jarz control  : $HOME/HappyJarzController
  BloomTunes          : $HOME/BloomTunes
  BloomSaver          : $HOME/BloomSaver

Launch BloomSaver:
  cd $HOME/BloomSaver && python3 bloomsaver_pi.py

Launch BloomTunes:
  cd $HOME/BloomTunes && python3 bloomtunes_studio_v0_6.py

HAPPY JARZ watcher refreshed and running from:
  $HOME/HappyJarzController/happyjarz_plug_watch.py

Flash the current HAPPY JARZ firmware from the same refreshed controller copy:
  bash $HOME/HappyJarzController/tools/flash_happyjarz_v0_5.sh

EOF
