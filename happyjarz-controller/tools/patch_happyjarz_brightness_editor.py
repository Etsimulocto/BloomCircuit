#!/usr/bin/env python3
"""Enable the on-board SOLID brightness tuner across the full 0..100 range.

Runs late in staging after the sensory pattern patch so it can deliberately
replace the original 50% bench safety ceiling without disturbing the proven
APA106 RMT writer or pattern implementations.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_brightness_editor.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

old_cap = "static constexpr uint8_t HJ_MAX_BRIGHTNESS = 50;"
if old_cap not in s:
    raise SystemExit("brightness editor patch failed: 50% brightness cap not found")
s = s.replace(old_cap, "static constexpr uint8_t HJ_MAX_BRIGHTNESS = 100;", 1)

old_load = '  brightnessPercent = min((uint8_t)50, prefs.getUChar("bright", (uint8_t)50));'
if old_load not in s:
    raise SystemExit("brightness editor patch failed: capped saved-brightness load not found")
s = s.replace(
    old_load,
    '  brightnessPercent = min((uint8_t)100, prefs.getUChar("bright", (uint8_t)50));',
    1,
)

old_lights = '''static void oledRenderLights() {
  oledCentered(13, "LIGHTS");
  oledCentered(29, "L1  " + compactRgb(ledColor[0]));
  oledCentered(45, "L2  " + compactRgb(ledColor[1]));
  oledCentered(61, patternName + "  " + String(brightnessPercent) + "%");
}
'''
new_lights = '''static void oledRenderLights() {
  oledCentered(13, "LIGHTS / SOLID");
  oledCentered(31, String(brightnessPercent) + "%");
  oledCentered(47, "UP/DN 5   LT/RT 1");
  oledCentered(61, "A SAVE   B BACK");
}
'''
if old_lights not in s:
    raise SystemExit("brightness editor patch failed: LIGHTS renderer not found")
s = s.replace(old_lights, new_lights, 1)

p.write_text(s, encoding="utf-8")
print("HAPPY JARZ brightness editor: 0..100 enabled")
