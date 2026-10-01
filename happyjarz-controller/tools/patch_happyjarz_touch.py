#!/usr/bin/env python3
"""Stage a more tolerant/diagnostic HAPPY JARZ touch layer into v0.5 firmware.

Goals:
- keep the existing six GPIO assignments unchanged
- reduce missed touches after OLED/menu activity changes the runtime environment
- average several touch samples to reject spikes
- lower the qualification threshold from +20% to +12.5%
- keep slow baseline tracking
- print baseline/threshold diagnostics after TEST INPUT recalibration
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_touch.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

old_read = 'static uint32_t readTouchPin(uint8_t pin) { return touchRead(pin); }'
new_read = '''static uint32_t readTouchPin(uint8_t pin) {
  // Average three readings. OLED/I2C and USB activity can inject short spikes;
  // a tiny average makes the capacitive layer much less brittle.
  uint64_t sum = 0;
  sum += touchRead(pin);
  sum += touchRead(pin);
  sum += touchRead(pin);
  return (uint32_t)(sum / 3ULL);
}'''
if old_read not in s:
    raise SystemExit("Touch patch failed: readTouchPin block not found")
s = s.replace(old_read, new_read, 1)

# +12.5% instead of +20%. This preserves the same polarity/algorithm while
# giving weaker pads (notably LEFT/DOWN on the current prototype) more margin.
s = s.replace('pad.threshold = pad.baseline + (pad.baseline / 5U);',
              'pad.threshold = pad.baseline + (pad.baseline / 8U);')
s = s.replace('pad.threshold = pad.baseline + (pad.baseline / 5U);',
              'pad.threshold = pad.baseline + (pad.baseline / 8U);')

# Slightly faster qualification and slower baseline drift. A real touch still
# has to remain present for multiple loop passes before it becomes an event.
s = s.replace('now - pad.enteredMs >= 60', 'now - pad.enteredMs >= 45')
s = s.replace('(pad.baseline * 127U + value) / 128U',
              '(pad.baseline * 255U + value) / 256U')

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

old_test = 'if(line=="TEST INPUT"||line=="TEST TOUCH"){calibrateInputs();Serial.println("HJ|TEST|input=PASS");return;}'
new_test = 'if(line=="TEST INPUT"||line=="TEST TOUCH"){calibrateInputs();printTouchCalibration();Serial.println("HJ|TEST|input=PASS");return;}'
if old_test not in s:
    raise SystemExit("Touch patch failed: TEST INPUT handler not found")
s = s.replace(old_test, new_test, 1)

# Let power/OLED rails settle before startup calibration samples are captured.
old_start = '''    uint8_t savedBrightness=brightnessPercent;
    brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();
    calibrateInputs();'''
new_start = '''    uint8_t savedBrightness=brightnessPercent;
    brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();
    delay(250);
    calibrateInputs();
    printTouchCalibration();'''
if old_start not in s:
    raise SystemExit("Touch patch failed: startup calibration block not found")
s = s.replace(old_start, new_start, 1)

p.write_text(s, encoding="utf-8")
