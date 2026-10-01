#!/usr/bin/env python3
"""Keep OLED/menu work from clobbering the proven HAPPY JARZ light controls.

Applied to the staged v0.5 sketch after touch + OLED patches.
- remove blue/green boot-test colors from normal startup
- preserve saved LED RGB/pattern state across USB reconnect/reset
- desktop LED/pattern commands always return OLED UI to HOME so local A/B/UP/DOWN work
- expand TEST RGB to identify whether combined RGB channels fail
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_led_recovery.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

# Touch patch runs before this patch, so match the CURRENT staged startup
# block rather than the pre-touch version.
old_boot = '''    uint8_t savedBrightness=brightnessPercent;
    brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();
    delay(350);
    calibrateInputs();
    printTouchCalibration();
    ledColor[0]={0,255,0};ledColor[1]={0,255,0};showLeds();delay(180);
    loadSettings();brightnessPercent=savedBrightness;if(patternName=="SOLID")showLeds();
'''
new_boot = '''    // Quiet boot/reconnect: never overwrite user LED colors just because USB
    // power wobbled. Let rails settle, calibrate touch, then restore settings.
    delay(350);
    calibrateInputs();
    printTouchCalibration();
    loadSettings();
    if(patternName=="OFF") allOff();
    else if(patternName=="SOLID") showLeds();
    else resetPatternEngine();
'''
if old_boot not in s:
    raise SystemExit("LED recovery patch failed: current staged startup block not found")
s = s.replace(old_boot, new_boot, 1)

old_led1 = 'if(line.startsWith("SET LED1 COLOR ")){if(parseRgb(line,1))ack("SET LED1 COLOR");else err("invalid LED1 RGB values");return;}'
new_led1 = 'if(line.startsWith("SET LED1 COLOR ")){uiGoHome();if(parseRgb(line,1)){oledDirty=true;ack("SET LED1 COLOR");}else err("invalid LED1 RGB values");return;}'
old_led2 = 'if(line.startsWith("SET LED2 COLOR ")){if(parseRgb(line,2))ack("SET LED2 COLOR");else err("invalid LED2 RGB values");return;}'
new_led2 = 'if(line.startsWith("SET LED2 COLOR ")){uiGoHome();if(parseRgb(line,2)){oledDirty=true;ack("SET LED2 COLOR");}else err("invalid LED2 RGB values");return;}'
old_pattern = 'if(line.startsWith("SET PATTERN ")){String v=line.substring(12);v.trim();if(v=="OFF"||v=="SOLID"||v=="FADE"||v=="PULSE"||v=="RAINBOW"||v=="RANDOM"){hjSetPattern(v);ack("SET PATTERN");}else err("unknown pattern");return;}'
new_pattern = 'if(line.startsWith("SET PATTERN ")){String v=line.substring(12);v.trim();if(v=="OFF"||v=="SOLID"||v=="FADE"||v=="PULSE"||v=="RAINBOW"||v=="RANDOM"){uiGoHome();hjSetPattern(v);oledDirty=true;ack("SET PATTERN");}else err("unknown pattern");return;}'

for old, new, label in ((old_led1,new_led1,"LED1"),(old_led2,new_led2,"LED2"),(old_pattern,new_pattern,"pattern")):
    if old not in s:
        raise SystemExit(f"LED recovery patch failed: {label} command block not found")
    s = s.replace(old, new, 1)

# Diagnostic only: single-channel colors work, but WHITE was observed as BLUE.
# Add two-channel combinations at low brightness so one TEST RGB run tells us
# whether the fault is generic to combined-channel frames or specific to white.
old_test = '''    Rgb s0=ledColor[0],s1=ledColor[1];uint8_t sb=brightnessPercent;String sp=patternName;patternName="SOLID";brightnessPercent=35;
    const Rgb tests[]={{255,0,0},{0,255,0},{0,0,255},{255,255,255}};
    for(const auto &c:tests){ledColor[0]=c;ledColor[1]=c;showLeds();delay(350);} ledColor[0]=s0;ledColor[1]=s1;brightnessPercent=sb;patternName=sp;resetPatternEngine();if(sp=="SOLID")showLeds();
'''
new_test = '''    Rgb s0=ledColor[0],s1=ledColor[1];uint8_t sb=brightnessPercent;String sp=patternName;patternName="SOLID";brightnessPercent=12;
    const Rgb tests[]={
      {255,0,0},      // red
      {0,255,0},      // green
      {0,0,255},      // blue
      {255,255,0},    // yellow = R+G
      {255,0,255},    // magenta = R+B
      {0,255,255},    // cyan = G+B
      {255,255,255}   // white = R+G+B
    };
    for(const auto &c:tests){ledColor[0]=c;ledColor[1]=c;showLeds();delay(500);} ledColor[0]=s0;ledColor[1]=s1;brightnessPercent=sb;patternName=sp;resetPatternEngine();if(sp=="SOLID")showLeds();
'''
if old_test not in s:
    raise SystemExit("LED recovery patch failed: TEST RGB body not found")
s = s.replace(old_test, new_test, 1)

p.write_text(s, encoding="utf-8")
