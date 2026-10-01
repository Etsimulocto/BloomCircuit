#!/usr/bin/env bash
set -euo pipefail

# HAPPY JARZ v0.5 safe Pi flash helper.
# Stops the USB controller/watcher so /dev/ttyACM* is free, stages the v0.5
# sketch, applies Arduino .ino compatibility + Wi-Fi state-machine/diagnostic
# patches, compiles, uploads, then restarts the plug watcher.

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

# v0.5 Wi-Fi hardening + diagnostics. Repeated WIFI CONNECT commands no longer
# reconfigure the STA while association is in progress. If a 20-second attempt
# fails, the firmware scans for the configured SSID and prints visibility,
# signal, channel, and encryption type so the next failure is actionable.
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

static void diagnoseWifiFailure() {
  int count = WiFi.scanNetworks(false, true);
  bool found = false;
  if (count > 0) {
    for (int i = 0; i < count; ++i) {
      if (WiFi.SSID(i) == wifiSsid) {
        found = true;
        Serial.print("HJ|WIFI_DIAG|found=1|ssid="); Serial.print(wifiSsid);
        Serial.print("|rssi="); Serial.print(WiFi.RSSI(i));
        Serial.print("|channel="); Serial.print(WiFi.channel(i));
        Serial.print("|enc="); Serial.println((int)WiFi.encryptionType(i));
        break;
      }
    }
  }
  if (!found) {
    Serial.print("HJ|WIFI_DIAG|found=0|ssid="); Serial.println(wifiSsid);
  }
  WiFi.scanDelete();
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
      diagnoseWifiFailure();
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
