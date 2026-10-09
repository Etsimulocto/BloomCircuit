#!/usr/bin/env python3
"""Add automatic HAPPY JARZ accessory-rail pause using OLED presence as the sensor.

Hardware assumption:
- ESP32 remains powered.
- OLED + four APA106 lamps share a switched 3.3 V accessory rail.
- OLED stays at I2C address 0x3C on SDA GPIO8 / SCL GPIO6.

Behavior:
- OLED ACK present  -> accessory rail ACTIVE
- OLED ACK absent   -> accessory rail PAUSED
- PAUSED freezes the pattern engine, blocks LED writes, and holds GPIO7 LOW.
- ACTIVE reinitializes the OLED, redraws, and resumes the current pattern.
- ESP32 time/Wi-Fi/USB/input services continue running.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_accessory_pause.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

def fail(msg):
    raise SystemExit("accessory-pause patch failed: " + msg)

# State must exist before writeFrame() so the central LED output choke point can
# refuse writes while the accessory rail is dead.
marker = 'static String patternName = "SOLID";\n'
if marker not in s:
    fail("patternName marker not found")

state = r'''
// HAPPYJARZ_ACCESSORY_PAUSE_V1
// OLED presence doubles as the switched 3.3 V accessory-rail sensor.
static bool hjAccessoryPaused = false;
static bool hjAccessoryKnown = false;
static unsigned long hjAccessoryLastProbeMs = 0;
static constexpr unsigned long HJ_ACCESSORY_PROBE_MS = 100UL;
'''
s = s.replace(marker, marker + state, 1)

# Never drive the APA106 chain while its rail is off.
write_sig = 'static void writeFrame(const Rgb frame[LED_COUNT], uint8_t brightness) {\n'
if write_sig not in s:
    fail("writeFrame marker not found")
s = s.replace(
    write_sig,
    write_sig +
    '  if (hjAccessoryPaused) { pinMode(LED_DATA_PIN, OUTPUT); digitalWrite(LED_DATA_PIN, LOW); return; }\n',
    1,
)

# Freeze pattern progression itself, not merely the output.
service_sig = 'static void servicePattern() {\n'
if service_sig not in s:
    fail("servicePattern marker not found")
s = s.replace(service_sig, service_sig + '  if (hjAccessoryPaused) return;\n', 1)

# oledInit() must tolerate booting with the accessory switch already OFF.
oled_init_old = '''static void oledInit() {
  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  Wire.setClock(400000);
  oled = HJ_OLED_SH1106 ? static_cast<U8G2*>(&oledSh1106) : static_cast<U8G2*>(&oledSsd1306);
'''
if oled_init_old not in s:
    fail("oledInit marker not found")

oled_init_new = '''static void oledInit() {
  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  Wire.setClock(400000);

  Wire.beginTransmission(OLED_I2C_ADDR);
  bool present = (Wire.endTransmission() == 0);
  if (!present) {
    oledReady = false;
    hjAccessoryPaused = true;
    hjAccessoryKnown = true;
    pinMode(LED_DATA_PIN, OUTPUT);
    digitalWrite(LED_DATA_PIN, LOW);
    return;
  }

  oled = HJ_OLED_SH1106 ? static_cast<U8G2*>(&oledSh1106) : static_cast<U8G2*>(&oledSsd1306);
'''
s = s.replace(oled_init_old, oled_init_new, 1)

# Add the periodic rail service after OLED init is defined so all OLED symbols
# are available. It probes only at 10 Hz and emits events only on state changes.
anchor = 'static void oledRenderHome() {\n'
if anchor not in s:
    fail("OLED render anchor not found")

service = r'''
static bool hjAccessoryRailPresent() {
  Wire.beginTransmission(OLED_I2C_ADDR);
  return Wire.endTransmission() == 0;
}

static void hjAccessoryPauseEnter() {
  if (hjAccessoryPaused && hjAccessoryKnown) return;
  hjAccessoryPaused = true;
  hjAccessoryKnown = true;
  oledReady = false;
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  if (Serial) Serial.println("HJ|ACCESSORY|state=PAUSED|sensor=OLED");
}

static void hjAccessoryPauseExit() {
  if (!hjAccessoryPaused && hjAccessoryKnown) return;
  hjAccessoryPaused = false;
  hjAccessoryKnown = true;

  // The OLED lost power, so initialize the controller again from scratch.
  oledInit();
  if (!oledReady) {
    hjAccessoryPaused = true;
    return;
  }

  oledDirty = true;

  // The APA106 chain lost VCC with the OLED. Treat rail return like a lamp
  // cold-start, not just a pattern-engine resume. Give the shared rail a short
  // settling window, re-establish a long LOW latch/reset, then push a fresh
  // frame immediately so the lamps cannot remain stuck on power-up data.
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  delay(8);
  resetPatternEngine();

  if (patternName == "OFF") {
    allOff();
  } else {
    // Send a known valid four-lamp frame immediately. Animated patterns will
    // overwrite this on their next service tick.
    showLeds();
    delayMicroseconds(200);
    showLeds();
  }

  if (Serial) Serial.println("HJ|ACCESSORY|state=ACTIVE|sensor=OLED|lamps=RESTARTED");
}

static void serviceAccessoryPause() {
  unsigned long now = millis();
  if (hjAccessoryKnown && now - hjAccessoryLastProbeMs < HJ_ACCESSORY_PROBE_MS) return;
  hjAccessoryLastProbeMs = now;

  bool present = hjAccessoryRailPresent();
  if (!hjAccessoryKnown) {
    hjAccessoryKnown = true;
    hjAccessoryPaused = !present;
    if (hjAccessoryPaused) {
      oledReady = false;
      pinMode(LED_DATA_PIN, OUTPUT);
      digitalWrite(LED_DATA_PIN, LOW);
      if (Serial) Serial.println("HJ|ACCESSORY|state=PAUSED|sensor=OLED");
    }
    return;
  }

  if (!present && !hjAccessoryPaused) hjAccessoryPauseEnter();
  else if (present && hjAccessoryPaused) hjAccessoryPauseExit();
}

'''
s = s.replace(anchor, service + anchor, 1)

# Guard all OLED rendering/present work while paused. The late host-sync patch
# may have replaced oled->sendBuffer() with hjOledPresent(), but serviceOled's
# leading readiness check remains stable.
oled_service_sig = 'static void serviceOled() {\n'
if oled_service_sig not in s:
    fail("serviceOled marker not found")
s = s.replace(
    oled_service_sig,
    oled_service_sig + '  if (hjAccessoryPaused) return;\n',
    1,
)

# Probe before the rest of the main loop each pass. The 100 ms internal cadence
# makes this cheap while ensuring GPIO7 gets clamped quickly after switch-off.
loop_sig = 'void loop(){\n'
if loop_sig not in s:
    loop_sig = 'void loop() {\n'
if loop_sig not in s:
    fail("loop marker not found")
s = s.replace(loop_sig, loop_sig + '  serviceAccessoryPause();\n', 1)

p.write_text(s, encoding="utf-8")
print("Applied HAPPY JARZ accessory-rail pause: OLED sensing + LED clamp + automatic resume.")
