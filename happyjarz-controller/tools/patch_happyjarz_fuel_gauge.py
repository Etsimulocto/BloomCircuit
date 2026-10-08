#!/usr/bin/env python3
"""Add HAPPY JARZ Fuel Gauge diagnostics/UI to the fully staged firmware.

BloomCore intent:
- run LAST in the standard flash pipeline
- do not alter the proven APA106, touch, OLED, saver, or protocol layers
- use the ESP32-S3 SuperMini GPIO3 ADC battery-divider path
- expose raw ADC millivolts, estimated battery voltage and estimated percent
- expose USB DATA link state only; do not falsely claim charger IC state
- show standalone power state on the OLED HOME screen
- charger CHARGING/FULL remains hardware-only unless a charger-status signal is
  explicitly wired to a GPIO in a future hardware revision

Calibration:
- default divider ratio is 2.0 (1:1 divider)
- BATTERY_CAL_FACTOR is centralized for bench calibration
- calibrated 2026-10-08 from live prototype reference:
  GPIO3 ADC ~2.184 V while battery terminals measured 3.50 V
- effective multiplier ~1.603, implemented as divider ratio 2.0 * cal factor 0.802
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
static constexpr float BATTERY_CAL_FACTOR = 0.802f;

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

static float batteryFilteredVoltage = 0.0f;
static bool batteryFilterReady = false;
static unsigned long batteryFilterLastMs = 0;
static constexpr unsigned long BATTERY_FILTER_INTERVAL_MS = 1000UL;

static float batteryVoltage() {
  unsigned long now = millis();
  if (batteryFilterReady && now - batteryFilterLastMs < BATTERY_FILTER_INTERVAL_MS) {
    return batteryFilteredVoltage;
  }

  float rawVolts = ((float)batteryAdcMillivolts() / 1000.0f) * BATTERY_DIVIDER_RATIO * BATTERY_CAL_FACTOR;
  batteryFilterLastMs = now;

  if (!batteryFilterReady) {
    batteryFilteredVoltage = rawVolts;
    batteryFilterReady = true;
  } else {
    // 1/4 new + 3/4 history. Smooth enough to stop percentage chatter while
    // still following real charging/discharge changes within a few seconds.
    batteryFilteredVoltage = batteryFilteredVoltage * 0.75f + rawVolts * 0.25f;
  }
  return batteryFilteredVoltage;
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

static String oledHomePowerText() {
  float volts = batteryVoltage();
  String text = "A MENU  ";
  if (batteryReadingPlausible(volts)) {
    text += String(batteryPercentFromVoltage(volts));
    text += "%";
  } else {
    text += "--%";
  }
  if (usbDataLinked()) text += " USB";
  return text;
}

static void printPowerStatus() {
  uint16_t adcMv = batteryAdcMillivolts();
  float volts = batteryVoltage();
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
  oledCentered(61, "CHARGE: HW ONLY");
}

'''
s = s.replace(render_marker, fuel_block + render_marker, 1)

# Put standalone power status on the HOME footer. The existing no-clock HOME
# footer is the stable A MENU line. Keep menu affordance, append battery/USB.
home_footer_old = '    oledCentered(61, "A MENU");'
home_footer_new = '    oledCentered(61, oledHomePowerText());'
if home_footer_old not in s:
    raise SystemExit("Fuel Gauge patch failed: HOME A MENU footer not found")
s = s.replace(home_footer_old, home_footer_new, 1)

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

# Add the renderer immediately before the final SYSTEM fallback. Later saver
# patches can add guards/branches around the switch, so do not depend on the
# exact preceding case layout here.
switch_fallback = '    default: oledRenderSystem(); break;'
if switch_fallback not in s:
    raise SystemExit("Fuel Gauge patch failed: OLED SYSTEM fallback not found")
s = s.replace(switch_fallback,
              '    case UI_POWER: oledRenderPower(); break;\n' + switch_fallback,
              1)

# Initialize ADC at the Arduino setup() boundary as it is actually written in
# the source: void setup(){  (no space before the opening brace).
setup_marker = 'void setup(){'
if setup_marker not in s:
    raise SystemExit("Fuel Gauge patch failed: setup() not found")
s = s.replace(setup_marker, setup_marker + '\n  fuelGaugeInit();', 1)

# Machine-readable diagnostic path.
proto_old = '''  if(line=="GET STATUS"){Serial.println(statusLine());return;}\n'''
proto_new = proto_old + '''  if(line=="GET POWER"){printPowerStatus();return;}\n'''
if proto_old not in s:
    raise SystemExit("Fuel Gauge patch failed: GET STATUS protocol point not found")
s = s.replace(proto_old, proto_new, 1)

p.write_text(s, encoding="utf-8")
print("Applied HAPPY JARZ Fuel Gauge patch: POWER menu + HOME battery/USB + GPIO3 ADC + GET POWER.")
