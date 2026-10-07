#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FQBN="esp32:esp32:esp32s3:CDCOnBoot=cdc"
SKETCH="$HERE/firmware/BloomGyro"

command -v arduino-cli >/dev/null || {
  echo "arduino-cli is required."
  exit 1
}

if [[ "${1:-}" == "--compile-only" ]]; then
  arduino-cli compile --fqbn "$FQBN" "$SKETCH"
  exit
fi

if [[ $# -gt 1 ]]; then
  echo "Usage:"
  echo "  bash flash.sh --compile-only"
  echo "  bash flash.sh [PORT]"
  echo
  echo "If PORT is omitted, the script uses the first /dev/ttyACM* device."
  exit 1
fi

PORT="${1:-}"
if [[ -z "$PORT" ]]; then
  PORT="$(ls /dev/ttyACM* 2>/dev/null | head -n1 || true)"
fi

if [[ -z "$PORT" ]]; then
  cat <<'EOF'
No /dev/ttyACM* port found.

Put the ESP32-S3 SuperMini into ROM bootloader mode:
  1. Hold BOOT.
  2. While holding BOOT, tap RESET once.
  3. Release BOOT.
  4. Run: ls /dev/ttyACM*

Then rerun this script with the detected port.
EOF
  exit 2
fi

echo "BloomGyro v0.1.0"
echo "Target: $PORT"
echo "Compiling..."
arduino-cli compile --fqbn "$FQBN" "$SKETCH"

echo
echo "Uploading to $PORT..."
if ! arduino-cli upload --fqbn "$FQBN" --port "$PORT" "$SKETCH"; then
  cat <<EOF

Upload failed.

Force ROM bootloader mode and retry:
  1. Hold BOOT.
  2. Tap RESET while still holding BOOT.
  3. Release BOOT after about one second.
  4. Verify the port:
       ls /dev/ttyACM*
  5. Retry:
       bash "$HERE/flash.sh" "$PORT"

If the port changed after entering boot mode, use the new /dev/ttyACM* path.
EOF
  exit 3
fi

echo
echo "Upload complete."
echo "If BloomGyro does not start automatically, tap RESET once (do not hold BOOT)."
echo "Serial diagnostics: arduino-cli monitor -p $PORT -c baudrate=115200"
