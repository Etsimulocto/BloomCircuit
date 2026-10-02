#!/usr/bin/env python3
"""Stage HAPPY JARZ touch diagnostics without changing the proven touch behavior.

BloomCore rule: the original touch state machine worked before OLED/menu work.
Do not stack extra cooldown/hysteresis/release logic on it.

This patch therefore preserves:
- direct touchRead()
- baseline +20% threshold
- 60 ms qualification
- original slow baseline drift
- original per-loop qualified/latch behavior

It only adds:
- startup settle before calibration
- calibration diagnostics
- ESP32 reset-reason diagnostics
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_touch.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

if '#include "esp_system.h"' not in s:
    s = s.replace('#include <Arduino.h>\n', '#include <Arduino.h>\n#include "esp_system.h"\n', 1)

# Leave the proven readTouchPin(), threshold, and updateInputState() untouched.
# Only add calibration diagnostics.
cal_end = '''  bHomeSent = false;\n}\n\nstatic bool updateInputState'''
cal_diag = '''  bHomeSent = false;\n}\n\nstatic void printTouchCalibration() {\n  Serial.print("HJ|TOUCH_CAL");\n  for (uint8_t i=0; i<INPUT_COUNT; ++i) {\n    Serial.print("|"); Serial.print(inputs[i].name); Serial.print("_base="); Serial.print(inputs[i].baseline);\n    Serial.print("|"); Serial.print(inputs[i].name); Serial.print("_thr="); Serial.print(inputs[i].threshold);\n  }\n  Serial.println();\n}\n\nstatic bool updateInputState'''
if cal_end not in s:
    raise SystemExit("Touch diagnostics patch failed: calibration insertion point not found")
s = s.replace(cal_end, cal_diag, 1)

old_test = 'if(line=="TEST INPUT"||line=="TEST TOUCH"){calibrateInputs();Serial.println("HJ|TEST|input=PASS");return;}'
new_test = 'if(line=="TEST INPUT"||line=="TEST TOUCH"){calibrateInputs();printTouchCalibration();Serial.println("HJ|TEST|input=PASS");return;}'
if old_test not in s:
    raise SystemExit("Touch diagnostics patch failed: TEST INPUT handler not found")
s = s.replace(old_test, new_test, 1)

# Let rails/OLED settle before taking the otherwise-original calibration.
old_start = '''    uint8_t savedBrightness=brightnessPercent;\n    brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();\n    calibrateInputs();'''
new_start = '''    uint8_t savedBrightness=brightnessPercent;\n    brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();\n    delay(350);\n    calibrateInputs();\n    printTouchCalibration();'''
if old_start not in s:
    raise SystemExit("Touch diagnostics patch failed: startup calibration block not found")
s = s.replace(old_start, new_start, 1)

boot_needle = '  Serial.begin(115200); delay(250); rxLine.reserve(128); randomSeed((uint32_t)micros());\n'
boot_repl = '''  Serial.begin(115200); delay(250); rxLine.reserve(128); randomSeed((uint32_t)micros());\n  Serial.print("HJ|BOOT|reset_reason="); Serial.println((int)esp_reset_reason());\n'''
if boot_needle not in s:
    raise SystemExit("Touch diagnostics patch failed: setup diagnostic insertion point not found")
s = s.replace(boot_needle, boot_repl, 1)

p.write_text(s, encoding="utf-8")
