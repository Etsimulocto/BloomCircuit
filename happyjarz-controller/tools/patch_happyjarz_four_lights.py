#!/usr/bin/env python3
"""Upgrade staged integrated HAPPY JARZ firmware from two to four APA106 lamps.

Runs late in the staging pipeline, after the existing pattern/saver/power layers.
It preserves the proven GPIO7/RMT transport and changes only the logical lamp
count, per-lamp state/protocol, persistence, startup diagnostics, and high-level
patterns that previously assumed exactly two lamps.
"""

from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_four_lights.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

def replace_once(old: str, new: str, label: str):
    global s
    if old not in s:
        raise SystemExit(f"four-light patch failed: {label} marker not found")
    s = s.replace(old, new, 1)

replace_once(
    "static constexpr uint8_t LED_COUNT = 2;",
    "static constexpr uint8_t LED_COUNT = 4;",
    "LED_COUNT",
)

replace_once(
    "static Rgb ledColor[LED_COUNT] = {{32,0,64},{0,32,64}};",
    "static Rgb ledColor[LED_COUNT] = {{32,0,64},{0,32,64},{32,0,64},{0,32,64}};",
    "LED color defaults",
)

replace_once(
    '  ledColor[1] = {prefs.getUChar("l2r",0), prefs.getUChar("l2g",32), prefs.getUChar("l2b",64)};\n',
    '  ledColor[1] = {prefs.getUChar("l2r",0), prefs.getUChar("l2g",32), prefs.getUChar("l2b",64)};\n'
    '  ledColor[2] = {prefs.getUChar("l3r",32), prefs.getUChar("l3g",0), prefs.getUChar("l3b",64)};\n'
    '  ledColor[3] = {prefs.getUChar("l4r",0), prefs.getUChar("l4g",32), prefs.getUChar("l4b",64)};\n',
    "load Light 2",
)

replace_once(
    '  prefs.putUChar("l2r", ledColor[1].r); prefs.putUChar("l2g", ledColor[1].g); prefs.putUChar("l2b", ledColor[1].b);\n',
    '  prefs.putUChar("l2r", ledColor[1].r); prefs.putUChar("l2g", ledColor[1].g); prefs.putUChar("l2b", ledColor[1].b);\n'
    '  prefs.putUChar("l3r", ledColor[2].r); prefs.putUChar("l3g", ledColor[2].g); prefs.putUChar("l3b", ledColor[2].b);\n'
    '  prefs.putUChar("l4r", ledColor[3].r); prefs.putUChar("l4g", ledColor[3].g); prefs.putUChar("l4b", ledColor[3].b);\n',
    "persist Light 2",
)

# High-level two-color presets now alternate across all four physical lamps.
show_pair_re = re.compile(
    r'static void showPair\(const Rgb &a, const Rgb &b, uint8_t brightness\) \{\n'
    r'\s*Rgb frame\[LED_COUNT\] = \{a,b\};\n'
    r'\s*writeFrame\(frame, safeBrightness\(brightness\)\);\n'
    r'\}',
)
if not show_pair_re.search(s):
    raise SystemExit("four-light patch failed: showPair marker not found")
s = show_pair_re.sub(
    '''static void showPair(const Rgb &a, const Rgb &b, uint8_t brightness) {
  Rgb frame[LED_COUNT] = {a,b,a,b};
  writeFrame(frame, safeBrightness(brightness));
}

static void showFour(const Rgb &a, const Rgb &b, const Rgb &c, const Rgb &d, uint8_t brightness) {
  Rgb frame[LED_COUNT] = {a,b,c,d};
  writeFrame(frame, safeBrightness(brightness));
}''',
    s,
    count=1,
)

replace_once(
    '    showPair(wheel((uint8_t)patternStep), wheel((uint8_t)(patternStep+96)), bri);\n',
    '    showFour(wheel((uint8_t)patternStep), wheel((uint8_t)(patternStep+64)),\n'
    '             wheel((uint8_t)(patternStep+128)), wheel((uint8_t)(patternStep+192)), bri);\n',
    "RAINBOW pair",
)

# RANDOM: four independent colors.
random_re = re.compile(
    r'  if \(patternName == "RANDOM"\) \{\n'
    r'    if \(now-patternLastMs < 300\) return; patternLastMs=now;\n'
    r'    showPair\(\{\(uint8_t\)random\(256\),\(uint8_t\)random\(256\),\(uint8_t\)random\(256\)\},\n'
    r'             \{\(uint8_t\)random\(256\),\(uint8_t\)random\(256\),\(uint8_t\)random\(256\)\},bri\); return;\n'
    r'  \}'
)
if not random_re.search(s):
    raise SystemExit("four-light patch failed: RANDOM marker not found")
s = random_re.sub(
    '''  if (patternName == "RANDOM") {
    if (now-patternLastMs < 300) return; patternLastMs=now;
    showFour({(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},
             {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},
             {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},
             {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},bri); return;
  }''',
    s,
    count=1,
)

# COLOR_SWAP rotates all four user-selected SOLID colors.
color_swap_re = re.compile(
    r'  if \(patternName == "COLOR_SWAP"\) \{\n'
    r'    if \(now-patternLastMs < 700\) return; patternLastMs=now;\n'
    r'    bool flip=.*?return;\n'
    r'  \}',
    re.DOTALL,
)
if not color_swap_re.search(s):
    raise SystemExit("four-light patch failed: COLOR_SWAP marker not found")
s = color_swap_re.sub(
    '''  if (patternName == "COLOR_SWAP") {
    if (now-patternLastMs < 700) return; patternLastMs=now;
    uint8_t shift=(uint8_t)(patternStep++ & 3U);
    Rgb frame[LED_COUNT];
    for (uint8_t i=0; i<LED_COUNT; ++i) frame[i]=ledColor[(i+shift)%LED_COUNT];
    writeFrame(frame,bri); return;
  }''',
    s,
    count=1,
)

# TWINKLE and SPARKLE preserve each lamp's own selected base color.
twinkle_re = re.compile(
    r'  if \(patternName == "TWINKLE"\) \{.*?\n  \}',
    re.DOTALL,
)
m = twinkle_re.search(s)
if not m:
    raise SystemExit("four-light patch failed: TWINKLE marker not found")
s = s[:m.start()] + '''  if (patternName == "TWINKLE") {
    if (now-patternLastMs < 180) return; patternLastMs=now;
    Rgb frame[LED_COUNT];
    for (uint8_t i=0; i<LED_COUNT; ++i)
      frame[i]=blendRgb(ledColor[i],{255,255,255},(uint8_t)random(30,150));
    uint8_t low=(uint8_t)max(1,(int)bri/3);
    writeFrame(frame,(uint8_t)random((long)low,(long)bri+1L)); return;
  }''' + s[m.end():]

sparkle_re = re.compile(
    r'  if \(patternName == "SPARKLE"\) \{.*?\n  \}',
    re.DOTALL,
)
m = sparkle_re.search(s)
if not m:
    raise SystemExit("four-light patch failed: SPARKLE marker not found")
s = s[:m.start()] + '''  if (patternName == "SPARKLE") {
    if (now-patternLastMs < 110) return; patternLastMs=now;
    Rgb frame[LED_COUNT];
    for (uint8_t i=0; i<LED_COUNT; ++i) {
      frame[i]=ledColor[i];
      if (random(3)==0) frame[i]={255,255,255};
    }
    writeFrame(frame,bri); return;
  }''' + s[m.end():]

# Status now exposes all four lamp colors.
replace_once(
    '  s+="|led2="+String(ledColor[1].r)+","+String(ledColor[1].g)+","+String(ledColor[1].b);\n',
    '  s+="|led2="+String(ledColor[1].r)+","+String(ledColor[1].g)+","+String(ledColor[1].b);\n'
    '  s+="|led3="+String(ledColor[2].r)+","+String(ledColor[2].g)+","+String(ledColor[2].b);\n'
    '  s+="|led4="+String(ledColor[3].r)+","+String(ledColor[3].g)+","+String(ledColor[3].b);\n',
    "status Light 2",
)

parse_re = re.compile(
    r'static bool parseRgb\(const String &line,uint8_t led\)\{.*?\n\}',
    re.DOTALL,
)
if not parse_re.search(s):
    raise SystemExit("four-light patch failed: parseRgb marker not found")
s = parse_re.sub(
    '''static bool parseRgb(const String &line,uint8_t led){
  unsigned int parsedLed=0; int r=-1,g=-1,b=-1;
  int n=sscanf(line.c_str(),"SET LED%u COLOR %d %d %d",&parsedLed,&r,&g,&b);
  if(n!=4 || parsedLed!=led || led<1 || led>LED_COUNT ||
     r<0||r>255||g<0||g>255||b<0||b>255) return false;
  hjSetLed(led,(uint8_t)r,(uint8_t)g,(uint8_t)b); return true;
}''',
    s,
    count=1,
)

# Insert Light 3/4 handlers immediately before brightness handling. Earlier
# staging patches may reformat the LED1/LED2 lines, so do not anchor to their
# exact text.
if 'SET LED3 COLOR ' not in s or 'SET LED4 COLOR ' not in s:
    brightness_cmd = re.search(
        r'(?m)^\s*if\(line\.startsWith\("SET BRIGHTNESS "\)\).*?
# RGB self-test covers every connected lamp and restores all four colors.
test_re = re.compile(
    r'  if\(line=="TEST RGB"\)\{\n.*?Serial\.println\("HJ\|TEST\|rgb=PASS"\);return;\n  \}',
    re.DOTALL,
)
m = test_re.search(s)
if not m:
    raise SystemExit("four-light patch failed: TEST RGB block not found")
s = s[:m.start()] + '''  if(line=="TEST RGB"){
    Rgb saved[LED_COUNT];
    for(uint8_t i=0;i<LED_COUNT;++i) saved[i]=ledColor[i];
    uint8_t sb=brightnessPercent; String sp=patternName;
    patternName="SOLID"; brightnessPercent=35;
    const Rgb tests[]={{255,0,0},{0,255,0},{0,0,255},{255,255,255}};
    for(const auto &c:tests){
      for(uint8_t i=0;i<LED_COUNT;++i) ledColor[i]=c;
      showLeds(); delay(350);
    }
    for(uint8_t i=0;i<LED_COUNT;++i) ledColor[i]=saved[i];
    brightnessPercent=sb; patternName=sp; resetPatternEngine();
    if(sp=="SOLID") showLeds();
    Serial.println("HJ|TEST|rgb=PASS"); return;
  }''' + s[m.end():]

# Startup color self-test now drives all four lamps together.
s = s.replace(
    'brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();',
    'brightnessPercent=25; for(uint8_t i=0;i<LED_COUNT;++i) ledColor[i]={0,0,255}; showLeds();',
    1,
)
s = s.replace(
    'ledColor[0]={0,255,0};ledColor[1]={0,255,0};showLeds();delay(180);',
    'for(uint8_t i=0;i<LED_COUNT;++i) ledColor[i]={0,255,0}; showLeds(); delay(180);',
    1,
)

# Alarm uses all four lamps.
s = s.replace(
    '  ledColor[0] = {255,120,20}; ledColor[1] = {255,40,100};\n',
    '  ledColor[0] = {255,120,20}; ledColor[1] = {255,40,100};\n'
    '  ledColor[2] = {255,120,20}; ledColor[3] = {255,40,100};\n',
    1,
)

s = s.replace(
    'Rgb off[LED_COUNT] = {{0,0,0},{0,0,0}};',
    'Rgb off[LED_COUNT] = {{0,0,0},{0,0,0},{0,0,0},{0,0,0}};',
    1,
)

p.write_text(s, encoding="utf-8")
print("Applied HAPPY JARZ four-light patch: 4 APA106 lamps + LED3/4 protocol/persistence + 4-lamp patterns.")
,
        s,
    )
    if not brightness_cmd:
        raise SystemExit("four-light patch failed: SET BRIGHTNESS command marker not found")
    indent = re.match(r'\s*', brightness_cmd.group(0)).group(0)
    extra = (
        f'{indent}if(line.startsWith("SET LED3 COLOR ")){{if(parseRgb(line,3))ack("SET LED3 COLOR");else err("invalid LED3 RGB values");return;}}\n'
        f'{indent}if(line.startsWith("SET LED4 COLOR ")){{if(parseRgb(line,4))ack("SET LED4 COLOR");else err("invalid LED4 RGB values");return;}}\n'
    )
    s = s[:brightness_cmd.start()] + extra + s[brightness_cmd.start():]

# RGB self-test covers every connected lamp and restores all four colors.
test_re = re.compile(
    r'  if\(line=="TEST RGB"\)\{\n.*?Serial\.println\("HJ\|TEST\|rgb=PASS"\);return;\n  \}',
    re.DOTALL,
)
m = test_re.search(s)
if not m:
    raise SystemExit("four-light patch failed: TEST RGB block not found")
s = s[:m.start()] + '''  if(line=="TEST RGB"){
    Rgb saved[LED_COUNT];
    for(uint8_t i=0;i<LED_COUNT;++i) saved[i]=ledColor[i];
    uint8_t sb=brightnessPercent; String sp=patternName;
    patternName="SOLID"; brightnessPercent=35;
    const Rgb tests[]={{255,0,0},{0,255,0},{0,0,255},{255,255,255}};
    for(const auto &c:tests){
      for(uint8_t i=0;i<LED_COUNT;++i) ledColor[i]=c;
      showLeds(); delay(350);
    }
    for(uint8_t i=0;i<LED_COUNT;++i) ledColor[i]=saved[i];
    brightnessPercent=sb; patternName=sp; resetPatternEngine();
    if(sp=="SOLID") showLeds();
    Serial.println("HJ|TEST|rgb=PASS"); return;
  }''' + s[m.end():]

# Startup color self-test now drives all four lamps together.
s = s.replace(
    'brightnessPercent=25; ledColor[0]={0,0,255};ledColor[1]={0,0,255};showLeds();',
    'brightnessPercent=25; for(uint8_t i=0;i<LED_COUNT;++i) ledColor[i]={0,0,255}; showLeds();',
    1,
)
s = s.replace(
    'ledColor[0]={0,255,0};ledColor[1]={0,255,0};showLeds();delay(180);',
    'for(uint8_t i=0;i<LED_COUNT;++i) ledColor[i]={0,255,0}; showLeds(); delay(180);',
    1,
)

# Alarm uses all four lamps.
s = s.replace(
    '  ledColor[0] = {255,120,20}; ledColor[1] = {255,40,100};\n',
    '  ledColor[0] = {255,120,20}; ledColor[1] = {255,40,100};\n'
    '  ledColor[2] = {255,120,20}; ledColor[3] = {255,40,100};\n',
    1,
)

s = s.replace(
    'Rgb off[LED_COUNT] = {{0,0,0},{0,0,0}};',
    'Rgb off[LED_COUNT] = {{0,0,0},{0,0,0},{0,0,0},{0,0,0}};',
    1,
)

p.write_text(s, encoding="utf-8")
print("Applied HAPPY JARZ four-light patch: 4 APA106 lamps + LED3/4 protocol/persistence + 4-lamp patterns.")
