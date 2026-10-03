#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FQBN="esp32:esp32:esp32s3:CDCOnBoot=cdc"
command -v arduino-cli >/dev/null || { echo 'arduino-cli is required (use the existing HAPPY JARZ setup).'; exit 1; }
if [[ "${1:-}" == '--compile-only' ]]; then
  arduino-cli compile --fqbn "$FQBN" "$HERE/firmware/BloomScope"
  exit
fi
[[ $# == 1 ]] || { echo 'Usage: bash flash.sh /dev/ttyACM0  (or --compile-only)'; echo 'Choose the damaged bench board explicitly; do not flash a working Jar.'; exit 1; }
echo "Flashing BloomScope 0.1.0 to $1 — replaces firmware on this board."
echo 'Close BloomScope, serial monitors, and any HAPPY JARZ USB watcher first.'
arduino-cli compile --fqbn "$FQBN" "$HERE/firmware/BloomScope"
arduino-cli upload --fqbn "$FQBN" --port "$1" "$HERE/firmware/BloomScope"
