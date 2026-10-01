#!/usr/bin/env bash
set -euo pipefail

# HAPPY JARZ v0.5 safe Pi flash helper.
# Stops the USB controller/watcher so /dev/ttyACM* is free, stages the v0.5
# sketch, applies the Arduino .ino enum-prototype compatibility patch, compiles,
# uploads, then restarts the plug watcher.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROLLER_DIR="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$CONTROLLER_DIR/.." && pwd)"
SRC="$CONTROLLER_DIR/firmware/happyjarz_integrated_v0_5.ino"
WORK="$HOME/hjflash/happyjarz_integrated_v0_5"
SKETCH="$WORK/happyjarz_integrated_v0_5.ino"
FQBN="esp32:esp32:esp32s3:CDCOnBoot=cdc"

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "ERROR: arduino-cli not found."
  exit 1
fi

if [[ ! -f "$SRC" ]]; then
  echo "ERROR: firmware source missing: $SRC"
  exit 1
fi

PORT="${1:-}"
if [[ -z "$PORT" ]]; then
  for p in /dev/ttyACM* /dev/ttyUSB*; do
    [[ -e "$p" ]] || continue
    PORT="$p"
    break
  done
fi

if [[ -z "$PORT" ]]; then
  echo "ERROR: no ESP32 serial port found. Plug the jar in and retry."
  exit 1
fi

echo "HAPPY JARZ v0.5 flasher"
echo "Repo: $REPO"
echo "Port: $PORT"
echo

echo "Stopping controller/watcher so the USB port is free..."
pkill -f '[h]appyjarz_controller.py' 2>/dev/null || true
pkill -f '[h]appyjarz_plug_watch.py' 2>/dev/null || true
sleep 1

mkdir -p "$WORK"
cp "$SRC" "$SKETCH"

# Arduino's .ino preprocessor may synthesize function prototypes before the
# InputIndex enum is visible. Use uint8_t at that one function boundary in the
# staged copy; behavior is identical because InputIndex is uint8_t-backed.
sed -i \
  -e 's/static bool updateInputState(InputIndex idx)/static bool updateInputState(uint8_t idx)/' \
  -e 's/updateInputState((InputIndex)i)/updateInputState(i)/' \
  "$SKETCH"

echo "Compiling..."
arduino-cli compile --fqbn "$FQBN" "$WORK"

echo "Uploading..."
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$WORK"

echo
echo "Upload complete. Restarting HAPPY JARZ plug watcher..."
nohup python3 "$CONTROLLER_DIR/happyjarz_plug_watch.py" \
  >> "$HOME/.happyjarz/plug_watch_manual_start.log" 2>&1 &

echo "Done. The controller should reopen after the watcher identifies HJ-001."
