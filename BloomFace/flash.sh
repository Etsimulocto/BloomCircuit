#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FQBN='esp32:esp32:esp32s3:CDCOnBoot=cdc'
command -v arduino-cli >/dev/null || { echo 'arduino-cli is required.'; exit 1; }
if [[ "${1:-}" == '--compile-only' ]]; then
  arduino-cli compile --fqbn "$FQBN" "$HERE/firmware/BloomFace"
  exit
fi
[[ $# == 1 ]] || { echo 'Usage: bash BloomFace/flash.sh /dev/ttyACM0'; exit 1; }
echo "Replacing the bench board firmware with BloomFace on $1."
echo 'Close all serial apps first; disconnect all measurement leads and external supplies.'
# Pause known desktop watchers to keep the flashing port free. Login restores them.
pkill -f '[p]ython3 .*BloomScope/plug_watch.py' 2>/dev/null || true
pkill -f '[p]ython3 .*BloomFace/plug_watch.py' 2>/dev/null || true
arduino-cli compile --fqbn "$FQBN" "$HERE/firmware/BloomFace"
arduino-cli upload --fqbn "$FQBN" --port "$1" "$HERE/firmware/BloomFace"
