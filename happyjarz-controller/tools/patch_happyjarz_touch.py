#!/usr/bin/env python3
"""Stage the HAPPY JARZ stabilized/diagnostic touch layer into v0.5 firmware.

Goals:
- keep the existing six GPIO assignments unchanged
- keep OLED/menu work from changing the physical control map
- average several touch samples to reject short spikes
- use a saner +16.7% touch threshold after startup rails settle
- add hysteresis so a held finger does not chatter on/off near threshold
- add a short release lockout so one touch produces one clean event
- keep slow baseline tracking while untouched
- print baseline/threshold diagnostics after calibration
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_touch.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

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

# Add service diagnostics so TEST INPUT tells us exactly what every pad is using.
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
new_update = '''static unsigned long touchReleasedMs[INPUT_COUNT] = {0,0,0,0,0,0};

static bool updateInputState(uint8_t idx) {
  TouchPadState &pad = inputs[idx];
  uint32_t value = readTouchPin(pad.pin);
  unsigned long now = millis();

  // Enter at the full threshold, but release at roughly +7.7% above baseline.
  // This hysteresis prevents a held finger from rapidly toggling around one edge.
  uint32_t releaseThreshold = pad.baseline + (pad.baseline / 13U);
  bool enterAbove = value >= pad.threshold;
  bool stayAbove = value >= releaseThreshold;

  if (!pad.touching) {
    // A short refractory period prevents one physical touch/release from becoming
    // several menu/light events if the capacitive value rings near threshold.
    if (now - touchReleasedMs[idx] < 180UL) return false;

    if (enterAbove) {
      pad.touching = true;
      pad.enteredMs = now;
    } else {
      // Track ambient drift only while unquestionably untouched.
      pad.baseline = (pad.baseline * 255U + value) / 256U;
      pad.threshold = pad.baseline + (pad.baseline / 6U);
    }
  } else if (!stayAbove) {
    pad.touching = false;
    pad.qualified = false;
    pad.enteredMs = 0;
    pad.qualifiedMs = 0;
    touchReleasedMs[idx] = now;
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

# Let OLED/current draw settle before measuring the idle capacitance.
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

p.write_text(s, encoding="utf-8")
