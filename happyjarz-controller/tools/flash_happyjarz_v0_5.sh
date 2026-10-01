#!/usr/bin/env bash
set -euo pipefail

# HAPPY JARZ v0.5 safe Pi flash helper.
# Stops the USB controller/watcher so /dev/ttyACM* is free, stages the v0.5
# sketch, applies compatibility + Wi-Fi + USB clock + OLED dashboard patches,
# compiles, uploads, then restarts the watcher.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROLLER_DIR="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$CONTROLLER_DIR/.." && pwd)"
SRC="$CONTROLLER_DIR/firmware/happyjarz_integrated_v0_5.ino"
OLED_PATCH="$HERE/patch_happyjarz_oled.py"
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
if [[ ! -f "$OLED_PATCH" ]]; then
  echo "ERROR: OLED patch missing: $OLED_PATCH"
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

echo "HAPPY JARZ v0.5 flasher + centered OLED dashboard"
echo "Repo: $REPO"
echo "Port: $PORT"
echo

echo "Stopping controller/watcher so the USB port is free..."
pkill -f '[h]appyjarz_controller' 2>/dev/null || true
pkill -f '[h]appyjarz_plug_watch.py' 2>/dev/null || true
sleep 1

mkdir -p "$WORK"
cp "$SRC" "$SKETCH"

# Arduino's .ino preprocessor may synthesize function prototypes before the
# InputIndex enum is visible. Keep the staged compatibility fix.
sed -i \
  -e 's/static bool updateInputState(InputIndex idx)/static bool updateInputState(uint8_t idx)/' \
  -e 's/updateInputState((InputIndex)i)/updateInputState(i)/' \
  "$SKETCH"

python3 - "$SKETCH" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

if '#include <sys/time.h>' not in s:
    s = s.replace('#include <time.h>\n', '#include <time.h>\n#include <sys/time.h>\n', 1)

old = '''static void connectWifi() {
  if (!wifiSsid.length()) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
}
'''
new = '''static bool wifiConnecting = false;
static unsigned long wifiConnectStartedMs = 0;
static constexpr unsigned long WIFI_CONNECT_TIMEOUT_MS = 20000;

static String wifiSecurityName(wifi_auth_mode_t mode) {
  switch (mode) {
    case WIFI_AUTH_OPEN: return "OPEN";
    case WIFI_AUTH_WEP: return "WEP";
    case WIFI_AUTH_WPA_PSK: return "WPA";
    case WIFI_AUTH_WPA2_PSK: return "WPA2";
    case WIFI_AUTH_WPA_WPA2_PSK: return "WPA/WPA2";
    case WIFI_AUTH_WPA2_ENTERPRISE: return "WPA2-ENT";
    case WIFI_AUTH_WPA3_PSK: return "WPA3";
    case WIFI_AUTH_WPA2_WPA3_PSK: return "WPA2/WPA3";
    default: return String((int)mode);
  }
}

static void scanWifiNetworks() {
  if (wifiConnecting) {
    WiFi.disconnect(false, false);
    wifiConnecting = false;
    delay(100);
  }
  WiFi.mode(WIFI_STA);
  Serial.println("HJ|WIFI_SCAN|BEGIN");
  int count = WiFi.scanNetworks(false, true);
  if (count < 0) count = 0;
  for (int i = 0; i < count; ++i) {
    String ssid = WiFi.SSID(i);
    if (!ssid.length()) continue;
    Serial.print("HJ|WIFI_SCAN|NET|ssid="); Serial.print(ssid);
    Serial.print("|rssi="); Serial.print(WiFi.RSSI(i));
    Serial.print("|channel="); Serial.print(WiFi.channel(i));
    Serial.print("|security="); Serial.println(wifiSecurityName(WiFi.encryptionType(i)));
  }
  Serial.print("HJ|WIFI_SCAN|END|count="); Serial.println(count);
  WiFi.scanDelete();
}

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
        Serial.print("|security="); Serial.println(wifiSecurityName(WiFi.encryptionType(i)));
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

needle = '  if(line=="GET WIFI STATUS"){printWifiStatus();return;}\n'
replacement = needle + '  if(line=="SCAN WIFI"){scanWifiNetworks();return;}\n'
if needle not in s:
    raise SystemExit("Wi-Fi scan command patch failed: protocol insertion point not found")
s = s.replace(needle, replacement, 1)

time_needle = '  if(line=="GET TIME STATUS"){printTimeStatus();return;}\n'
time_replacement = time_needle + '''  if(line.startsWith("SET CLOCK UNIX ")){
    String raw=line.substring(15); raw.trim();
    unsigned long long epoch=strtoull(raw.c_str(), nullptr, 10);
    if(epoch < 1700000000ULL || epoch > 4102444800ULL){err("invalid unix time");return;}
    struct timeval tv; tv.tv_sec=(time_t)epoch; tv.tv_usec=0;
    if(settimeofday(&tv, nullptr)==0){ack("SET CLOCK UNIX");printTimeStatus();}
    else err("settimeofday failed");
    return;
  }\n'''
if time_needle not in s:
    raise SystemExit("Host-time patch failed: time protocol insertion point not found")
s = s.replace(time_needle, time_replacement, 1)

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

# Add the OLED UI to the staged sketch only. This keeps the known-good source
# recoverable while the screen layout is still being tuned.
python3 "$OLED_PATCH" "$SKETCH"

# U8g2 is the only new dependency for the OLED dashboard. Install if missing.
if ! arduino-cli lib list | grep -q '^U8g2[[:space:]]'; then
  echo "Installing U8g2 OLED library..."
  arduino-cli lib install U8g2
fi

echo "Compiling..."
arduino-cli compile --fqbn "$FQBN" "$WORK"

echo "Uploading..."
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$WORK"

echo
echo "Upload complete. Restarting HAPPY JARZ plug watcher..."
nohup python3 "$CONTROLLER_DIR/happyjarz_plug_watch.py" \
  >> "$HOME/.happyjarz/plug_watch_manual_start.log" 2>&1 &

echo "Done. OLED dashboard: four centered lines; LEFT/RIGHT changes pages."
