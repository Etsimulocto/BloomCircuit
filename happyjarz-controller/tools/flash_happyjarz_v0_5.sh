#!/usr/bin/env bash
set -euo pipefail

# HAPPY JARZ v0.5 safe Pi flash helper.
# Stops the USB controller/watcher so /dev/ttyACM* is free, stages the v0.5
# sketch, applies Arduino .ino compatibility + Wi-Fi state-machine patches,
# compiles, uploads, then restarts the plug watcher.

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

# v0.5 Wi-Fi hardening: repeated WIFI CONNECT commands used to call WiFi.begin()
# again while the station was already associating, which ESP-IDF rejects with
# "sta is connecting, cannot set config". Patch the staged copy into a small
# non-blocking connection state machine. Repeated clicks become harmless and NTP
# still starts automatically after association succeeds.
python3 - "$SKETCH" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

old = '''static void connectWifi() {
  if (!wifiSsid.length()) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
}
'''
new = '''static bool wifiConnecting = false;
static unsigned long wifiConnectStartedMs = 0;
static constexpr unsigned long WIFI_CONNECT_TIMEOUT_MS = 20000;

static void connectWifi() {
  if (!wifiSsid.length()) {
    Serial.println("HJ|ERR|message=wifi ssid is empty");
    return;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("HJ|EVENT|wifi=CONNECTED");
    return;
  }

  // Do not reconfigure the STA while ESP-IDF is already associating.
  if (wifiConnecting && millis() - wifiConnectStartedMs < WIFI_CONNECT_TIMEOUT_MS) {
    Serial.println("HJ|EVENT|wifi=CONNECTING");
    return;
  }

  wifiConnecting = false;
  WiFi.mode(WIFI_STA);
  WiFi.disconnect(false, false);
  delay(75);
  WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
  wifiConnecting = true;
  wifiConnectStartedMs = millis();
  Serial.println("HJ|EVENT|wifi=CONNECTING");
}
'''
if old not in s:
    raise SystemExit("Wi-Fi patch failed: connectWifi block not found")
s = s.replace(old, new, 1)

old_loop = '''  static bool timeStarted=false;
  if(!timeStarted && WiFi.status()==WL_CONNECTED){startTimeSync();timeStarted=true;Serial.println("HJ|EVENT|wifi=CONNECTED");}
  if(timeStarted && WiFi.status()!=WL_CONNECTED) timeStarted=false;
  delay(5);
}'''
new_loop = '''  static bool timeStarted=false;
  if (WiFi.status()==WL_CONNECTED) {
    wifiConnecting=false;
    if(!timeStarted){startTimeSync();timeStarted=true;Serial.println("HJ|EVENT|wifi=CONNECTED");}
  } else {
    if(timeStarted) timeStarted=false;
    if(wifiConnecting && millis()-wifiConnectStartedMs>=WIFI_CONNECT_TIMEOUT_MS){
      wifiConnecting=false;
      WiFi.disconnect(false, false);
      Serial.println("HJ|EVENT|wifi=FAILED");
    }
  }
  delay(5);
}'''
if old_loop not in s:
    raise SystemExit("Wi-Fi patch failed: loop block not found")
s = s.replace(old_loop, new_loop, 1)

p.write_text(s, encoding="utf-8")
PY

echo "Compiling..."
arduino-cli compile --fqbn "$FQBN" "$WORK"

echo "Uploading..."
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$WORK"

echo
echo "Upload complete. Restarting HAPPY JARZ plug watcher..."
nohup python3 "$CONTROLLER_DIR/happyjarz_plug_watch.py" \
  >> "$HOME/.happyjarz/plug_watch_manual_start.log" 2>&1 &

echo "Done. The controller should reopen after the watcher identifies HJ-001."
