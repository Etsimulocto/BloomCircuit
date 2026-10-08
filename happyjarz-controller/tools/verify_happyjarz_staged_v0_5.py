#!/usr/bin/env python3
"""Refuse to flash an incomplete or wrongly-versioned HAPPY JARZ staged firmware build."""

from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: verify_happyjarz_staged_v0_5.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
controller_dir = Path(__file__).resolve().parent.parent
version_file = controller_dir / "firmware" / "VERSION"
expected_version = version_file.read_text(encoding="utf-8").strip()

if not re.fullmatch(r"\d+\.\d+\.\d+", expected_version):
    print(f"ERROR: invalid firmware VERSION file: {expected_version!r}", file=sys.stderr)
    raise SystemExit(4)

version_marker = f'static const char *HJ_FW_VERSION = "{expected_version}";'
if version_marker not in s:
    print(
        f"ERROR: staged firmware version does not match firmware/VERSION ({expected_version}); refusing to flash.",
        file=sys.stderr,
    )
    print(f"Staged file left for inspection: {p}", file=sys.stderr)
    raise SystemExit(5)

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
    "USB touch stream fix": "USB_TOUCH_STREAM_FIX_V1",
    "5 Hz touch telemetry": "millis()-lastInputStreamMs>=200",
    "four APA106 lamps": "LED_COUNT = 4",
    "Light 3 protocol": "SET LED3 COLOR",
    "Light 4 protocol": "SET LED4 COLOR",
    "Light 3 status": "|led3=",
    "Light 4 status": "|led4=",
    "host KEY input": 'line.startsWith("KEY ")',
    "host capability protocol": "HJ|CAPS|profile=SIMPLE",
    "OLED mirror protocol": "HJ|OLED|seq=",
    "OLED mirror stream": 'line=="STREAM OLED ON"',
    "OLED actual framebuffer source": "oled->getBufferPtr()",
    "arcade uses mirrored OLED present": "if (oled) hjOledPresent();",
    "unified virtual input queue": "hjHostKeyPending",
    "true four-lamp pattern engine": "HAPPYJARZ_FOUR_LAMP_PATTERN_ENGINE_V2",
    "stand topology constants": "HJ_TOP_LEFT",
    "clockwise chase": '"CHASE_CW"',
    "side accent chase": '"SIDE_ACCENT"',
    "100-pattern bank marker": "HAPPYJARZ_PATTERN_BANK_100",
    "100-pattern terminal entry": '"MOONLIGHT"',
}

missing = [name for name, marker in required.items() if marker not in s]
if missing:
    print("ERROR: staged HAPPY JARZ firmware is incomplete; refusing to flash.", file=sys.stderr)
    for name in missing:
        print(f"  MISSING: {name}", file=sys.stderr)
    print(f"Staged file left for inspection: {p}", file=sys.stderr)
    raise SystemExit(2)

old_home = 'String bottom = timerEnabled ? timerText() : String(alarmBuf);\n  oledCentered(61, bottom);'
if old_home in s:
    print("ERROR: old ALARM OFF HOME footer survived staging; refusing to flash.", file=sys.stderr)
    print(f"Staged file left for inspection: {p}", file=sys.stderr)
    raise SystemExit(3)

if 'touchStreamCompat && millis()-lastTouchCompatMs' in s:
    print("ERROR: duplicate USB touch telemetry emitter survived staging; refusing to flash.", file=sys.stderr)
    print(f"Staged file left for inspection: {p}", file=sys.stderr)
    raise SystemExit(6)

print("HAPPY JARZ staged firmware verification: PASS")
print(f"  firmware version {expected_version}")
print("  Fuel Gauge + HOME battery/power cycle present")
print("  GET POWER protocol present")
print("  30-second OLED screensaver present")
print("  expanded four-lamp patterns + particle saver present")
print("  USB touch telemetry single-stream fix present (5 Hz)")
print("  four-lamp protocol/status/persistence present")
print("  host KEY/CAPS protocol present")
print("  actual U8g2 OLED framebuffer mirror present")
print("  arcade/game OLED frames use mirrored present path")
print("  true four-lamp pattern engine present")
print("  stand-topology chase family present")
print("  100-pattern descriptor bank present")
