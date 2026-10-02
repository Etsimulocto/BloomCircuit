#!/usr/bin/env python3
"""Final HAPPY JARZ HOME power-status polish.

Runs after the Fuel Gauge patch so it can safely adjust only the already-staged
HOME power helper and screensaver timeout without disturbing LED/touch/menu
architecture.

HOME footer cycles every 2.5 seconds:
  BAT <percent>   (or --% when the voltage model is not yet calibrated)
  V <voltage>
  PWR USB/BAT
  CHG HW          (charger IC state is not yet observable by firmware)

Also extends the idle screensaver timeout from 10 seconds to 30 seconds so the
OLED menus/status pages are actually readable during standalone use.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_home_power_cycle.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

old_timeout = "static constexpr unsigned long HJ_SCREENSAVER_IDLE_MS = 10000UL;"
new_timeout = "static constexpr unsigned long HJ_SCREENSAVER_IDLE_MS = 30000UL;"
if old_timeout not in s:
    raise SystemExit("HOME power-cycle patch failed: 10-second saver timeout not found")
s = s.replace(old_timeout, new_timeout, 1)

old_helper = r'''static String oledHomePowerText() {
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
'''

new_helper = r'''static String oledHomePowerText() {
  uint16_t adcMv = batteryAdcMillivolts();
  float volts = ((float)adcMv / 1000.0f) * BATTERY_DIVIDER_RATIO * BATTERY_CAL_FACTOR;
  bool usbPower = volts > 4.45f;
  uint8_t page = (uint8_t)((millis() / 2500UL) % 4UL);

  String text = "A MENU  ";
  if (page == 0) {
    text += "BAT ";
    if (batteryReadingPlausible(volts)) {
      text += String(batteryPercentFromVoltage(volts));
      text += "%";
    } else {
      text += "--%";
    }
  } else if (page == 1) {
    text += "V ";
    text += String(volts, 2);
  } else if (page == 2) {
    text += usbPower ? "PWR USB" : "PWR BAT";
  } else {
    // Charging/full is a charger-IC hardware state that is not wired to an
    // ESP32 GPIO yet. Keep this explicit rather than inventing a status.
    text += "CHG HW";
  }
  return text;
}
'''

if old_helper not in s:
    raise SystemExit("HOME power-cycle patch failed: existing HOME power helper not found")
s = s.replace(old_helper, new_helper, 1)

p.write_text(s, encoding="utf-8")
print("Applied HOME power cycle + 30-second screensaver timeout.")
