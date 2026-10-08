#!/usr/bin/env python3
"""Add HAPPY JARZ low-battery warning overlay.

Requires the fully staged Fuel Gauge + four-light + host-sync layers.

Behavior:
- only trusts a plausible calibrated battery reading
- enter warning at <=10%
- clear at >=15% (hysteresis)
- bulb 4 / HJ_SIDE_RIGHT flashes red while bulbs 1-3 keep their pattern
- every OLED present is replaced with a large CHARGE ME warning while active
- invalid/unverified battery readings NEVER trigger the warning
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_low_battery_warning.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

def fail(msg):
    raise SystemExit("low-battery patch failed: " + msg)

if "HAPPYJARZ_LOW_BATTERY_WARNING_V1" in s:
    print("Low-battery warning already present; leaving staged sketch unchanged.")
    raise SystemExit(0)

required = (
    "static float batteryVoltage()",
    "static uint8_t batteryPercentFromVoltage(float v)",
    "static bool batteryReadingPlausible(float v)",
    "HJ_SIDE_RIGHT",
    "static void hjOledPresent()",
)
for marker in required:
    if marker not in s:
        fail("required marker not found: " + marker)

# Add cached warning state after Fuel Gauge helpers are available.
anchor = "static bool usbDataLinked() {\n"
if anchor not in s:
    fail("Fuel Gauge usbDataLinked marker not found")

block = r'''
// HAPPYJARZ_LOW_BATTERY_WARNING_V1
static constexpr uint8_t HJ_LOW_BATTERY_ENTER_PCT = 10;
static constexpr uint8_t HJ_LOW_BATTERY_CLEAR_PCT = 15;
static bool hjLowBatteryWarning = false;
static int16_t hjLowBatteryPercent = -1;
static unsigned long hjLowBatteryLastCheckMs = 0;
static constexpr unsigned long HJ_LOW_BATTERY_CHECK_MS = 5000UL;

static void hjServiceLowBattery() {
  unsigned long now = millis();
  if (hjLowBatteryLastCheckMs && now - hjLowBatteryLastCheckMs < HJ_LOW_BATTERY_CHECK_MS) return;
  hjLowBatteryLastCheckMs = now;

  float volts = batteryVoltage();
  if (!batteryReadingPlausible(volts)) {
    // Sensor is still unverified/calibrating. Never raise a false alarm.
    hjLowBatteryPercent = -1;
    hjLowBatteryWarning = false;
    return;
  }

  uint8_t pct = batteryPercentFromVoltage(volts);
  hjLowBatteryPercent = (int16_t)pct;

  if (!hjLowBatteryWarning && pct <= HJ_LOW_BATTERY_ENTER_PCT) {
    hjLowBatteryWarning = true;
    oledDirty = true;
    if (Serial) {
      Serial.print("HJ|BATTERY_WARNING|state=LOW|percent=");
      Serial.println(pct);
    }
  } else if (hjLowBatteryWarning && pct >= HJ_LOW_BATTERY_CLEAR_PCT) {
    hjLowBatteryWarning = false;
    oledDirty = true;
    if (Serial) {
      Serial.print("HJ|BATTERY_WARNING|state=CLEAR|percent=");
      Serial.println(pct);
    }
  }
}

static bool hjLowBatteryFlashOn() {
  // Calm, obvious 1 Hz beacon: half second red / half second normal.
  return ((millis() / 500UL) & 1UL) == 0UL;
}

static void hjRenderLowBatteryWarning() {
  if (!oled) return;
  oled->clearBuffer();
  oled->setFont(u8g2_font_6x12_tr);
  oledCentered(13, "LOW BATTERY");
  oled->setFont(u8g2_font_9x15B_tr);
  oledCentered(39, "CHARGE ME!!!");
  oled->setFont(u8g2_font_6x12_tr);
  if (hjLowBatteryPercent >= 0) {
    oledCentered(61, String(hjLowBatteryPercent) + "%   USB ->");
  } else {
    oledCentered(61, "USB ->");
  }
}

'''
s = s.replace(anchor, block + anchor, 1)

# Service the battery state from the main loop.
loop_candidates = ("void loop(){\n", "void loop() {\n")
loop_sig = next((x for x in loop_candidates if x in s), None)
if not loop_sig:
    fail("loop marker not found")
s = s.replace(loop_sig, loop_sig + "  hjServiceLowBattery();\n", 1)

# Overlay bulb 4 at the byte-generation point. The physical pattern frame
# remains untouched, so the normal right-side color returns on each off phase
# and immediately after warning clear.
bytes_old = '''    uint8_t bytes[3] = {
      (uint8_t)((uint16_t)frame[led].r * brightness / 100U),
      (uint8_t)((uint16_t)frame[led].g * brightness / 100U),
      (uint8_t)((uint16_t)frame[led].b * brightness / 100U)
    };'''
if bytes_old not in s:
    fail("writeFrame byte block not found")

bytes_new = '''    Rgb txColor = frame[led];
    if (hjLowBatteryWarning && led == HJ_SIDE_RIGHT && hjLowBatteryFlashOn()) {
      txColor = {255,0,0};
    }
    uint8_t bytes[3] = {
      (uint8_t)((uint16_t)txColor.r * brightness / 100U),
      (uint8_t)((uint16_t)txColor.g * brightness / 100U),
      (uint8_t)((uint16_t)txColor.b * brightness / 100U)
    };'''
s = s.replace(bytes_old, bytes_new, 1)

# Force the actual OLED framebuffer to the warning screen at the common
# presentation choke point. Arcade, menu, saver and HOME all go through here.
present_old = '''static void hjOledPresent() {
  if (!oled) return;
  oled->sendBuffer();
  hjEmitOledFrame(false);
}'''
if present_old not in s:
    fail("hjOledPresent block not found")

present_new = '''static void hjOledPresent() {
  if (!oled) return;
  if (hjLowBatteryWarning) hjRenderLowBatteryWarning();
  oled->sendBuffer();
  hjEmitOledFrame(false);
}'''
s = s.replace(present_old, present_new, 1)

p.write_text(s, encoding="utf-8")
print("Applied HAPPY JARZ low-battery warning: bulb 4 red beacon + CHARGE ME OLED override.")
