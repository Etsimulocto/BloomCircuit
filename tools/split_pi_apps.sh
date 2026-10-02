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

The controller autostart files are now under:
  $HOME/HappyJarzController

EOF
