#!/usr/bin/env python3
"""Refuse to flash an incomplete HAPPY JARZ staged firmware build.

This guard runs after all staging patches and before compile/upload.
It checks for features that distinguish the current bench-proven build from the
older OLED-only v0.5 stage that still showed ALARM OFF on HOME.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: verify_happyjarz_staged_v0_5.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

required = {
    "Fuel Gauge layer": "FUEL_GAUGE_PATCH_V1",
    "battery ADC": "BATTERY_ADC_PIN = 3",
    "GET POWER protocol": 'if(line=="GET POWER")',
    "POWER OLED screen": "UI_POWER",
    "HOME power helper": "oledHomePowerText",
    "battery-only HOME status": '"PWR BAT"',
    "USB HOME status": '"PWR USB"',
    "charger unknown status": '"CHG ?"',
    "30 second OLED screensaver": "HJ_SCREENSAVER_IDLE_MS = 30000UL",
    "expanded pattern library": "PATTERN_COUNT",
    "particle screensaver": "hjParticleCount",
}

missing = [name for name, marker in required.items() if marker not in s]
if missing:
    print("ERROR: staged HAPPY JARZ firmware is incomplete; refusing to flash.", file=sys.stderr)
    for name in missing:
        print(f"  MISSING: {name}", file=sys.stderr)
    print(f"Staged file left for inspection: {p}", file=sys.stderr)
    raise SystemExit(2)

# The early OLED HOME implementation ends with ALARM OFF/TIMER text. That text
# may still legitimately exist on the SETTINGS page, so only reject the exact
# old HOME-bottom assignment if it survived staging.
old_home = 'String bottom = timerEnabled ? timerText() : String(alarmBuf);\n  oledCentered(61, bottom);'
if old_home in s:
    print("ERROR: old ALARM OFF HOME footer survived staging; refusing to flash.", file=sys.stderr)
    print(f"Staged file left for inspection: {p}", file=sys.stderr)
    raise SystemExit(3)

print("HAPPY JARZ staged firmware verification: PASS")
print("  Fuel Gauge + HOME battery/power cycle present")
print("  GET POWER protocol present")
print("  30-second OLED screensaver present")
print("  expanded patterns + particle saver present")
