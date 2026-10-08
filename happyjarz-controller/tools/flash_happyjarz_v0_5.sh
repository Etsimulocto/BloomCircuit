#!/usr/bin/env bash
set -euo pipefail

# HAPPY JARZ safe Pi flash helper.
# Legacy filename retained for compatibility; release version comes from firmware/VERSION.
# Stops the USB controller/watcher so /dev/ttyACM* is free, stages the current
# firmware patch chain, injects the release version, verifies the FINAL staged
# sketch, compiles, uploads, then restarts the watcher.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROLLER_DIR="$(cd "$HERE/.." && pwd)"
REPO="$(cd "$CONTROLLER_DIR/.." && pwd)"
SRC="$CONTROLLER_DIR/firmware/happyjarz_integrated_v0_5.ino"
FW_VERSION_FILE="$CONTROLLER_DIR/firmware/VERSION"
VERSION_PATCH="$HERE/patch_happyjarz_release_version.py"
TOUCH_PATCH="$HERE/patch_happyjarz_touch.py"
OLED_PATCH="$HERE/patch_happyjarz_oled.py"
MENU_PATCH="$HERE/patch_happyjarz_menu_controls.py"
PATTERN_PATCH="$HERE/patch_happyjarz_patterns.py"
FOUR_LIGHT_PATCH="$HERE/patch_happyjarz_four_lights.py"
HOST_SYNC_PATCH="$HERE/patch_happyjarz_host_sync.py"
SCREENSAVER_PATCH="$HERE/patch_happyjarz_screensavers.py"
SAYINGS_PATCH="$HERE/patch_happyjarz_sayings_v2.py"
CUSTOM_SAYINGS_PATCH="$HERE/patch_happyjarz_custom_sayings.py"
SAVER_CONTROLS_PATCH="$HERE/patch_happyjarz_saver_controls.py"
SAVER_PROTOCOL_PATCH="$HERE/patch_happyjarz_saver_protocol.py"
VERIFY_STAGE="$HERE/verify_happyjarz_staged_v0_5.py"
WORK="$HOME/hjflash/happyjarz_integrated_v0_5"
SKETCH="$WORK/happyjarz_integrated_v0_5.ino"
FQBN="esp32:esp32:esp32s3:CDCOnBoot=cdc"

if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "ERROR: arduino-cli not found."
  exit 1
fi

for required in "$SRC" "$FW_VERSION_FILE" "$VERSION_PATCH" "$TOUCH_PATCH" "$OLED_PATCH" "$MENU_PATCH" "$PATTERN_PATCH" "$FOUR_LIGHT_PATCH" "$HOST_SYNC_PATCH" "$SCREENSAVER_PATCH" "$SAYINGS_PATCH" "$CUSTOM_SAYINGS_PATCH" "$SAVER_CONTROLS_PATCH" "$SAVER_PROTOCOL_PATCH" "$VERIFY_STAGE"; do
  if [[ ! -f "$required" ]]; then
    echo "ERROR: required file missing: $required"
    exit 1
  fi
done

FW_VERSION="$(tr -d '[:space:]' < "$FW_VERSION_FILE")"
if [[ ! "$FW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "ERROR: invalid firmware version in $FW_VERSION_FILE: $FW_VERSION"
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

echo "HAPPY JARZ firmware v$FW_VERSION CURRENT flasher"
echo "Repo: $REPO"
echo "Controller source: $CONTROLLER_DIR"
echo "Port: $PORT"
echo

echo "Stopping controller/watcher so the USB port is free..."
pkill -f '[h]appyjarz_controller' 2>/dev/null || true
pkill -f '[h]appyjarz_plug_watch.py' 2>/dev/null || true
sleep 1

mkdir -p "$WORK"
rm -f "$SKETCH"
cp "$SRC" "$SKETCH"

echo "Staging compatibility + Wi-Fi/clock support..."
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

echo "Applying current HAPPY JARZ patch chain..."
python3 "$TOUCH_PATCH" "$SKETCH"
python3 "$OLED_PATCH" "$SKETCH"
python3 "$MENU_PATCH" "$SKETCH"
python3 "$PATTERN_PATCH" "$SKETCH"
python3 "$SCREENSAVER_PATCH" "$SKETCH"
python3 "$SAYINGS_PATCH" "$SKETCH"
python3 "$CUSTOM_SAYINGS_PATCH" "$SKETCH"
python3 "$SAVER_CONTROLS_PATCH" "$SKETCH"
# SAVER_PROTOCOL intentionally applies the later smooth-drift, PARTICLES,
# Fuel Gauge, expanded happy sayings, HOME power-cycle and 30-second saver
# layers. Do not duplicate those patches here.
python3 "$SAVER_PROTOCOL_PATCH" "$SKETCH"
python3 "$FOUR_LIGHT_PATCH" "$SKETCH"
python3 "$HOST_SYNC_PATCH" "$SKETCH"

# Release version is injected LAST so the binary identity always matches the
# firmware/VERSION source of truth for this build.
python3 "$VERSION_PATCH" "$SKETCH"

sed -i \
  -e 's/if (inputStream && millis()-lastInputStreamMs>=100)/if (inputStream \&\& Serial \&\& millis()-lastInputStreamMs>=100)/' \
  -e 's/if(touchStreamCompat && millis()-lastTouchCompatMs>=100)/if(touchStreamCompat \&\& Serial \&\& millis()-lastTouchCompatMs>=100)/' \
  "$SKETCH"

echo
echo "Verifying FINAL staged firmware before compile/upload..."
python3 "$VERIFY_STAGE" "$SKETCH"
echo

if ! arduino-cli lib list | grep -q '^U8g2[[:space:]]'; then
  echo "Installing U8g2 OLED library..."
  arduino-cli lib install U8g2
fi

echo "Compiling VERIFIED firmware v$FW_VERSION..."
arduino-cli compile --fqbn "$FQBN" "$WORK"

echo "Uploading VERIFIED firmware v$FW_VERSION..."
arduino-cli upload -p "$PORT" --fqbn "$FQBN" "$WORK"

echo
echo "Upload complete. Restarting HAPPY JARZ plug watcher..."
nohup python3 "$CONTROLLER_DIR/happyjarz_plug_watch.py" \
  >> "$HOME/.happyjarz/plug_watch_manual_start.log" 2>&1 &
echo "Done. Firmware v$FW_VERSION verified: four APA106 lamps + host KEY input + OLED mirror + Fuel Gauge + 30s saver + expanded patterns/particles present."
