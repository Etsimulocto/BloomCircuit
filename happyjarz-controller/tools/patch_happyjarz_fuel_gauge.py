#!/usr/bin/env python3
"""Add HAPPY JARZ Fuel Gauge diagnostics/UI to the fully staged firmware.

BloomCore intent:
- run LAST in the standard flash pipeline
- do not alter the proven APA106, touch, OLED, saver, or protocol layers
- use the ESP32-S3 SuperMini GPIO3 ADC battery-divider path
- expose raw ADC millivolts, estimated battery voltage and estimated percent
- expose USB DATA link state only; do not falsely claim charger IC state
- charger CHARGING/FULL remains hardware-only unless a charger-status signal is
  explicitly wired to a GPIO in a future hardware revision

Calibration:
- default divider ratio is 2.0 (1:1 divider)
- BATTERY_CAL_FACTOR is intentionally centralized for multimeter calibration
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_fuel_gauge.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

if "FUEL_GAUGE_PATCH_V1" in s:
    print("Fuel Gauge patch already present; leaving staged sketch unchanged.")
    raise SystemExit(0)

# Add POWER screen without disturbing existing screen identities.
enum_old = '''  UI_SETTINGS,\n  UI_SYSTEM\n};'''
enum_new = '''  UI_SETTINGS,\n  UI_SYSTEM,\n  UI_POWER\n};'''
if enum_old not in s:
    raise SystemExit("Fuel Gauge patch failed: OLED UI enum not found")
s = s.replace(enum_old, enum_new, 1)

# Battery sensing/service block. Keep all calibration constants here.
render_marker = '''static void oledRenderSystem() {'''
if render_marker not in s:
    raise SystemExit("Fuel Gauge patch failed: oledRenderSystem not found")

fuel_block = r'''
// FUEL_GAUGE_PATCH_V1
// -----------------------------
// Fuel Gauge / battery diagnostics
// -----------------------------
static constexpr uint8_t BATTERY_ADC_PIN = 3;
static constexpr float BATTERY_DIVIDER_RATIO = 2.0f;
static constexpr float BATTERY_CAL_FACTOR = 1.000f;

static void fuelGaugeInit() {
  pinMode(BATTERY_ADC_PIN, INPUT);
  analogSetPinAttenuation(BATTERY_ADC_PIN, ADC_11db);
}

static uint16_t batteryAdcMillivolts() {
  uint32_t total = 0;
  static constexpr uint8_t samples = 12;
  for (uint8_t i=0; i<samples; ++i) {
    total += analogReadMilliVolts(BATTERY_ADC_PIN);
    delayMicroseconds(250);
  }
  return (uint16_t)(total / samples);
}

static float batteryVoltage() {
  return ((float)batteryAdcMillivolts() / 1000.0f) * BATTERY_DIVIDER_RATIO * BATTERY_CAL_FACTOR;
}

static bool batteryReadingPlausible(float v) {
  return v >= 2.8f && v <= 4.45f;
}

static uint8_t batteryPercentFromVoltage(float v) {
  struct Pt { float v; uint8_t pct; };
  static const Pt curve[] = {
    {4.20f,100}, {4.10f,90}, {4.00f,80}, {3.92f,70},
    {3.85f,60}, {3.79f,50}, {3.75f,40}, {3.70f,30},
    {3.65f,20}, {3.55f,10}, {3.40f,0}
  };
  if (v >= curve[0].v) return 100;
  const size_t n = sizeof(curve)/sizeof(curve[0]);
  if (v <= curve[n-1].v) return 0;
  for (size_t i=0; i<n-1; ++i) {
    if (v <= curve[i].v && v >= curve[i+1].v) {
      float span = curve[i].v - curve[i+1].v;
      float f = span > 0.0f ? (v - curve[i+1].v) / span : 0.0f;
      float pct = curve[i+1].pct + f * (float)(curve[i].pct - curve[i+1].pct);
      if (pct < 0.0f) pct = 0.0f;
      if (pct > 100.0f) pct = 100.0f;
      return (uint8_t)(pct + 0.5f);
    }
  }
  return 0;
}

static bool usbDataLinked() {
  // Native USB CDC can report a host/data link. A power-only charger may not.
  return (bool)Serial;
}

static void printPowerStatus() {
  uint16_t adcMv = batteryAdcMillivolts();
  float volts = ((float)adcMv / 1000.0f) * BATTERY_DIVIDER_RATIO * BATTERY_CAL_FACTOR;
  if (!batteryReadingPlausible(volts)) {
    Serial.printf("HJ|POWER|sensor=UNVERIFIED|adc_mv=%u|voltage=%.3f|percent=-1|usb_data=%d|charge=HW_ONLY\n",
                  adcMv, volts, usbDataLinked()?1:0);
    return;
  }
  Serial.printf("HJ|POWER|sensor=OK|adc_mv=%u|voltage=%.3f|percent=%u|usb_data=%d|charge=HW_ONLY\n",
                adcMv, volts, batteryPercentFromVoltage(volts), usbDataLinked()?1:0);
}

static void oledRenderPower() {
  float volts = batteryVoltage();
  oledCentered(13, "FUEL GAUGE");
  if (!batteryReadingPlausible(volts)) {
    oledCentered(29, "BAT SENSOR CHECK");
    oledCentered(45, "GPIO3 ADC");
  } else {
    char buf[24];
    snprintf(buf, sizeof(buf), "BAT %.2fV  %u%%", volts, batteryPercentFromVoltage(volts));
    oledCentered(29, String(buf));
    oledCentered(45, usbDataLinked() ? "USB DATA IN" : "USB DATA OUT");
  }
  oledCentered(61, "CHARGE: HW LED");
}

'''
s = s.replace(render_marker, fuel_block + render_marker, 1)

# Put POWER in the main menu. Six items still fit via the existing four-row scroll.
menu_old = '''static const char *items[] = {"CLOCK", "LIGHTS", "GAMES", "SETTINGS", "SYSTEM"};\n  static constexpr uint8_t count = 5;'''
menu_new = '''static const char *items[] = {"CLOCK", "LIGHTS", "GAMES", "SETTINGS", "POWER", "SYSTEM"};\n  static constexpr uint8_t count = 6;'''
if menu_old not in s:
    raise SystemExit("Fuel Gauge patch failed: main menu list not found")
s = s.replace(menu_old, menu_new, 1)

select_old = '''    case 2: uiScreen = UI_GAMES; break;\n    case 3: uiScreen = UI_SETTINGS; break;\n    default: uiScreen = UI_SYSTEM; break;'''
select_new = '''    case 2: uiScreen = UI_GAMES; break;\n    case 3: uiScreen = UI_SETTINGS; break;\n    case 4: uiScreen = UI_POWER; break;\n    default: uiScreen = UI_SYSTEM; break;'''
if select_old not in s:
    raise SystemExit("Fuel Gauge patch failed: menu selector not found")
s = s.replace(select_old, select_new, 1)

# Final menu-control patch currently hard-codes five entries; extend it to six.
up_old = 'uiCursor=(uiCursor+4)%5;'
down_old = 'uiCursor=(uiCursor+1)%5;'
if up_old not in s or down_old not in s:
    raise SystemExit("Fuel Gauge patch failed: final menu cursor math not found")
s = s.replace(up_old, 'uiCursor=(uiCursor+5)%6;', 1)
s = s.replace(down_old, 'uiCursor=(uiCursor+1)%6;', 1)

# Add the renderer to the existing OLED switch before the default SYSTEM case.
switch_old = '''    case UI_SETTINGS: oledRenderSettings(); break;\n    default: oledRenderSystem(); break;'''
switch_new = '''    case UI_SETTINGS: oledRenderSettings(); break;\n    case UI_POWER: oledRenderPower(); break;\n    default: oledRenderSystem(); break;'''
if switch_old not in s:
    raise SystemExit("Fuel Gauge patch failed: OLED render switch not found")
s = s.replace(switch_old, switch_new, 1)

# Initialize ADC before the OLED comes up.
setup_old = '''  loadSettings();\n  oledInit();'''
setup_new = '''  loadSettings();\n  fuelGaugeInit();\n  oledInit();'''
if setup_old not in s:
    raise SystemExit("Fuel Gauge patch failed: setup insertion point not found")
s = s.replace(setup_old, setup_new, 1)

# Machine-readable diagnostic path.
proto_old = '''  if(line=="GET STATUS"){Serial.println(statusLine());return;}\n'''
proto_new = proto_old + '''  if(line=="GET POWER"){printPowerStatus();return;}\n'''
if proto_old not in s:
    raise SystemExit("Fuel Gauge patch failed: GET STATUS protocol point not found")
s = s.replace(proto_old, proto_new, 1)

p.write_text(s, encoding="utf-8")
print("Applied HAPPY JARZ Fuel Gauge patch: POWER menu + GPIO3 ADC + GET POWER.")
