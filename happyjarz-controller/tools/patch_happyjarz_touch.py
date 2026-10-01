#!/usr/bin/env python3
"""Stage the HAPPY JARZ stabilized/diagnostic touch layer into v0.5 firmware.

Goals:
- keep the existing six GPIO assignments unchanged
- keep OLED/menu work from changing the physical control map
- average several touch samples to reject short spikes
- use a saner +16.7% touch threshold after startup rails settle
- add hysteresis so a held finger does not chatter on/off near threshold
- one physical touch produces exactly one logical press
- require a sustained real release before a pad can fire again
- keep slow baseline tracking while untouched
- print baseline/threshold diagnostics after calibration
- print ESP32 reset reason on boot so unexpected USB drops are diagnosable
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_touch.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

if '#include "esp_system.h"' not in s:
    s = s.replace('#include <Arduino.h>\n', '#include <Arduino.h>\n#include "esp_system.h"\n', 1)

old_read = 'static uint32_t readTouchPin(uint8_t pin) { return touchRead(pin); }'
new_read = '''static uint32_t readTouchPin(uint8_t pin) {
  uint64_t sum = 0;
  sum += touchRead(pin);
  sum += touchRead(pin);
  sum += touchRead(pin);
  return (uint32_t)(sum / 3ULL);
}'''
if old_read not in s:
    raise SystemExit("Touch patch failed: readTouchPin block not found")
s = s.replace(old_read, new_read, 1)

# Startup/idle threshold: baseline + 1/6 ~= +16.7%.
# The earlier +12.5% experiment made neighboring pads cross-trigger.
s = s.replace('pad.threshold = pad.baseline + (pad.baseline / 5U);',
              'pad.threshold = pad.baseline + (pad.baseline / 6U);')

cal_end = '''  bHomeSent = false;
}

static bool updateInputState'''
cal_diag = '''  bHomeSent = false;
}

static void printTouchCalibration() {
  Serial.print("HJ|TOUCH_CAL");
  for (uint8_t i=0; i<INPUT_COUNT; ++i) {
    Serial.print("|"); Serial.print(inputs[i].name); Serial.print("_base="); Serial.print(inputs[i].baseline);
    Serial.print("|"); Serial.print(inputs[i].name); Serial.print("_thr="); Serial.print(inputs[i].threshold);
  }
  Serial.println();
}

static bool updateInputState'''
if cal_end not in s:
    raise SystemExit("Touch patch failed: calibration insertion point not found")
s = s.replace(cal_end, cal_diag, 1)

old_update = '''static bool updateInputState(uint8_t idx) {
  TouchPadState &pad = inputs[idx];
  uint32_t value = readTouchPin(pad.pin);
  bool above = value >= pad.threshold;
  unsigned long now = millis();
  if (above && !pad.touching) {
    pad.touching = true;
    pad.enteredMs = now;
  } else if (!above) {
    pad.touching = false;
    pad.qualified = false;
    pad.enteredMs = 0;
    pad.qualifiedMs = 0;
    pad.baseline = (pad.baseline * 127U + value) / 128U;
    pad.threshold = pad.baseline + (pad.baseline / 6U);
    if (idx == IN_B) bHomeSent = false;
  }
  bool q = pad.touching && (now - pad.enteredMs >= 60);
  if (q && !pad.qualified) pad.qualifiedMs = now;
  pad.qualified = q;
  return q;
}'''
new_update = '''static bool touchNeedsRelease[INPUT_COUNT] = {false,false,false,false,false,false};
static unsigned long touchReleaseStableMs[INPUT_COUNT] = {0,0,0,0,0,0};

static bool updateInputState(uint8_t idx) {
  TouchPadState &pad = inputs[idx];
  uint32_t value = readTouchPin(pad.pin);
  unsigned long now = millis();

  // Enter at the full threshold, release at a lower threshold. This hysteresis
  // keeps OLED/I2C noise from toggling a held finger around one edge.
  uint32_t releaseThreshold = pad.baseline + (pad.baseline / 13U);
  bool enterAbove = value >= pad.threshold;
  bool stayAbove = value >= releaseThreshold;

  // Once a press has ended, do not arm this pad again merely because some time
  // passed. Require a genuine, continuous release for 250 ms. That makes one
  // physical touch exactly one logical event, even if the signal chatters.
  if (touchNeedsRelease[idx]) {
    if (!stayAbove) {
      if (touchReleaseStableMs[idx] == 0) touchReleaseStableMs[idx] = now;
      if (now - touchReleaseStableMs[idx] >= 250UL) {
        touchNeedsRelease[idx] = false;
        touchReleaseStableMs[idx] = 0;
        pad.baseline = (pad.baseline * 255U + value) / 256U;
        pad.threshold = pad.baseline + (pad.baseline / 6U);
        if (idx == IN_B) bHomeSent = false;
      }
    } else {
      touchReleaseStableMs[idx] = 0;
    }
    return false;
  }

  if (!pad.touching) {
    if (enterAbove) {
      pad.touching = true;
      pad.enteredMs = now;
    } else {
      pad.baseline = (pad.baseline * 255U + value) / 256U;
      pad.threshold = pad.baseline + (pad.baseline / 6U);
    }
  } else if (!stayAbove) {
    bool hadQualified = pad.qualified;
    pad.touching = false;
    pad.qualified = false;
    pad.enteredMs = 0;
    pad.qualifiedMs = 0;
    touchReleaseStableMs[idx] = now;
    touchNeedsRelease[idx] = hadQualified;
    if (idx == IN_B) bHomeSent = false;
    return false;
  }

  bool q = pad.touching && (now - pad.enteredMs >= 65UL);
  if (q && !pad.qualified) pad.qualifiedMs = now;
  pad.qualified = q;
  return q;
}'''
if old_update not in s:
    raise SystemExit("Touch patch failed: updateInputState block not found")
s = s.replace(old_update, new_update, 1)

old_test = 'if(line=="TEST INPUT"||line=="TEST TOUCH"){calibrateInputs();Serial.println("HJ|TEST|input=PASS");return;}'
new_test = 'if(line=="TEST INPUT"||line=="TEST TOUCH"){calibrateInputs();printTouchCalibration();Serial.println("HJ|TEST|input=PASS");return;}'
if old_test not in s:
    raise SystemExit("Touch patch failed: TEST INPUT handler not found")
s = s.replace(old_test, new_test, 1)

old_start = '''    uint8_t savedBrightness=brightnessPercent;
    brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();
    calibrateInputs();'''
new_start = '''    uint8_t savedBrightness=brightnessPercent;
    brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();
    delay(350);
    calibrateInputs();
    printTouchCalibration();'''
if old_start not in s:
    raise SystemExit("Touch patch failed: startup calibration block not found")
s = s.replace(old_start, new_start, 1)

boot_needle = '  Serial.begin(115200); delay(250); rxLine.reserve(128); randomSeed((uint32_t)micros());\n'
boot_repl = '''  Serial.begin(115200); delay(250); rxLine.reserve(128); randomSeed((uint32_t)micros());
  Serial.print("HJ|BOOT|reset_reason="); Serial.println((int)esp_reset_reason());
'''
if boot_needle not in s:
    raise SystemExit("Touch patch failed: setup boot diagnostic insertion point not found")
s = s.replace(boot_needle, boot_repl, 1)

p.write_text(s, encoding="utf-8")
