#!/usr/bin/env python3
"""Expand HAPPY JARZ into a sensory/fidget pattern library.

Runs after touch + OLED + menu/recovery patches.
Preserves the proven APA106 RMT writer and only replaces the high-level
pattern engine/control lists.

Safety/stability rule established on bench:
- 50% is bright enough for the product
- cap all normal light output at 50% so high-load white never enters the
  observed blue-collapse region
"""

from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_patterns.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

pattern_block = r'''// -----------------------------
// Pattern engine — sensory library
// -----------------------------
static constexpr uint8_t HJ_MAX_BRIGHTNESS = 50;
static unsigned long patternLastMs = 0;
static uint16_t patternStep = 0;

static uint8_t safeBrightness(uint8_t requested) {
  return requested > HJ_MAX_BRIGHTNESS ? HJ_MAX_BRIGHTNESS : requested;
}

static Rgb wheel(uint8_t pos) {
  pos = 255 - pos;
  if (pos < 85) return {(uint8_t)(255-pos*3),0,(uint8_t)(pos*3)};
  if (pos < 170) { pos -= 85; return {0,(uint8_t)(pos*3),(uint8_t)(255-pos*3)}; }
  pos -= 170; return {(uint8_t)(pos*3),(uint8_t)(255-pos*3),0};
}

static Rgb blendRgb(const Rgb &a, const Rgb &b, uint8_t amount) {
  uint16_t inv = 255U - amount;
  return {
    (uint8_t)(((uint16_t)a.r*inv + (uint16_t)b.r*amount)/255U),
    (uint8_t)(((uint16_t)a.g*inv + (uint16_t)b.g*amount)/255U),
    (uint8_t)(((uint16_t)a.b*inv + (uint16_t)b.b*amount)/255U)
  };
}

static uint8_t triangle8(uint16_t step, uint16_t period) {
  if (period < 2) return 255;
  uint16_t x = step % period;
  uint16_t half = period / 2U;
  if (x < half) return (uint8_t)((uint32_t)x * 255U / half);
  return (uint8_t)((uint32_t)(period - 1U - x) * 255U / half);
}

static void resetPatternEngine(){ patternStep=0; patternLastMs=0; }

static const char *PATTERN_NAMES[] = {
  "SOLID","FADE","PULSE","RAINBOW","RANDOM",
  "HUE_FADE","DUAL_HUE","BREATH","DRIFT","AURORA","OCEAN","LAVENDER","SUNSET",
  "CHRISTMAS","HALLOWEEN","VALENTINE","EASTER","FOURTH","THANKSGIVING",
  "CANDY","GALAXY","FIRE","ICE","FOREST","NEON","TWINKLE","SPARKLE","COLOR_SWAP",
  "COMET","FIREFLY","BUBBLEGUM","OFF"
};
static constexpr uint8_t PATTERN_COUNT = sizeof(PATTERN_NAMES)/sizeof(PATTERN_NAMES[0]);

static bool isPatternName(const String &name) {
  for (uint8_t i=0; i<PATTERN_COUNT; ++i) if (name == PATTERN_NAMES[i]) return true;
  return false;
}

static void showPair(const Rgb &a, const Rgb &b, uint8_t brightness) {
  Rgb frame[LED_COUNT] = {a,b};
  writeFrame(frame, safeBrightness(brightness));
}

static void servicePattern() {
  if (patternName == "SOLID") return;
  if (patternName == "OFF") { allOff(); return; }

  unsigned long now = millis();
  uint8_t bri = safeBrightness(brightnessPercent);

  if (patternName == "FADE" || patternName == "BREATH") {
    uint16_t interval = patternName == "BREATH" ? 35 : 22;
    if (now-patternLastMs < interval) return; patternLastMs=now;
    uint8_t level = triangle8(patternStep, patternName == "BREATH" ? 260 : 200);
    uint8_t floorPct = patternName == "BREATH" ? 5 : 8;
    uint8_t pct = floorPct + (uint8_t)((uint16_t)level*(100U-floorPct)/255U);
    writeFrame(ledColor,(uint8_t)((uint16_t)pct*bri/100U));
    patternStep++; return;
  }

  if (patternName == "PULSE") {
    if (now-patternLastMs < 16) return; patternLastMs=now;
    uint16_t phase=patternStep%150; uint8_t pct;
    if (phase<30) pct=10+(uint8_t)((uint16_t)phase*90U/29U);
    else if (phase<60) pct=100-(uint8_t)((uint16_t)(phase-30)*90U/29U);
    else pct=10;
    writeFrame(ledColor,(uint8_t)((uint16_t)pct*bri/100U));
    patternStep++; return;
  }

  if (patternName == "RAINBOW") {
    if (now-patternLastMs < 35) return; patternLastMs=now;
    showPair(wheel((uint8_t)patternStep), wheel((uint8_t)(patternStep+96)), bri);
    patternStep++; return;
  }

  if (patternName == "HUE_FADE") {
    if (now-patternLastMs < 45) return; patternLastMs=now;
    Rgb c=wheel((uint8_t)patternStep);
    showPair(c,c,bri); patternStep++; return;
  }

  if (patternName == "DUAL_HUE") {
    if (now-patternLastMs < 45) return; patternLastMs=now;
    showPair(wheel((uint8_t)patternStep),wheel((uint8_t)(patternStep+128)),bri);
    patternStep++; return;
  }

  if (patternName == "DRIFT") {
    if (now-patternLastMs < 70) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,220);
    Rgb a=blendRgb({20,0,90},{0,120,255},t);
    Rgb b=blendRgb({0,50,120},{130,0,190},(uint8_t)(255-t));
    showPair(a,b,bri); patternStep++; return;
  }

  if (patternName == "AURORA") {
    if (now-patternLastMs < 55) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,240);
    showPair(blendRgb({0,180,90},{100,0,220},t), blendRgb({0,80,255},{0,220,120},(uint8_t)(255-t)), bri);
    patternStep++; return;
  }

  if (patternName == "OCEAN") {
    if (now-patternLastMs < 65) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,180);
    showPair(blendRgb({0,20,100},{0,180,255},t),blendRgb({0,120,180},{0,30,130},t),bri);
    patternStep++; return;
  }

  if (patternName == "LAVENDER") {
    if (now-patternLastMs < 70) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,220);
    Rgb c=blendRgb({90,20,150},{230,120,255},t); showPair(c,c,bri);
    patternStep++; return;
  }

  if (patternName == "SUNSET") {
    if (now-patternLastMs < 60) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,200);
    showPair(blendRgb({255,30,0},{255,130,20},t),blendRgb({255,0,100},{100,0,180},t),bri);
    patternStep++; return;
  }

  if (patternName == "CHRISTMAS") {
    if (now-patternLastMs < 550) return; patternLastMs=now;
    bool flip=(patternStep++ & 1U); showPair(flip?Rgb{255,0,0}:Rgb{0,255,0},flip?Rgb{0,255,0}:Rgb{255,0,0},bri); return;
  }
  if (patternName == "HALLOWEEN") {
    if (now-patternLastMs < 500) return; patternLastMs=now;
    bool flip=(patternStep++ & 1U); showPair(flip?Rgb{255,70,0}:Rgb{120,0,255},flip?Rgb{120,0,255}:Rgb{255,70,0},bri); return;
  }
  if (patternName == "VALENTINE") {
    if (now-patternLastMs < 45) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,180); showPair(blendRgb({255,0,40},{255,20,160},t),blendRgb({255,40,100},{180,0,70},t),bri); patternStep++; return;
  }
  if (patternName == "EASTER") {
    if (now-patternLastMs < 650) return; patternLastMs=now;
    static const Rgb p[]={{255,120,200},{130,220,255},{180,130,255},{255,220,80},{120,255,170}};
    uint8_t i=patternStep++%5; showPair(p[i],p[(i+2)%5],bri); return;
  }
  if (patternName == "FOURTH") {
    if (now-patternLastMs < 420) return; patternLastMs=now;
    static const Rgb p[]={{255,0,0},{255,255,255},{0,60,255}};
    uint8_t i=patternStep++%3; showPair(p[i],p[(i+1)%3],bri); return;
  }
  if (patternName == "THANKSGIVING") {
    if (now-patternLastMs < 600) return; patternLastMs=now;
    static const Rgb p[]={{255,70,0},{180,30,0},{255,160,0},{100,20,0}};
    uint8_t i=patternStep++%4; showPair(p[i],p[(i+1)%4],bri); return;
  }

  if (patternName == "CANDY") {
    if (now-patternLastMs < 320) return; patternLastMs=now;
    static const Rgb p[]={{255,20,120},{0,220,255},{255,180,0},{120,255,80},{170,40,255}};
    uint8_t i=random(5),j=random(5); showPair(p[i],p[j],bri); return;
  }
  if (patternName == "GALAXY") {
    if (now-patternLastMs < 90) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,240);
    Rgb a=blendRgb({10,0,40},{100,0,220},t), b=blendRgb({0,20,70},{255,0,130},(uint8_t)(255-t));
    if ((patternStep%37)==0) a={180,180,255}; if ((patternStep%53)==0) b={255,255,255};
    showPair(a,b,bri); patternStep++; return;
  }
  if (patternName == "FIRE") {
    if (now-patternLastMs < 80) return; patternLastMs=now;
    Rgb a={(uint8_t)random(180,256),(uint8_t)random(20,100),0};
    Rgb b={(uint8_t)random(180,256),(uint8_t)random(10,80),0}; showPair(a,b,bri); return;
  }
  if (patternName == "ICE") {
    if (now-patternLastMs < 100) return; patternLastMs=now;
    Rgb a={(uint8_t)random(80,180),(uint8_t)random(170,256),255};
    Rgb b={(uint8_t)random(20,110),(uint8_t)random(100,220),255}; showPair(a,b,bri); return;
  }
  if (patternName == "FOREST") {
    if (now-patternLastMs < 90) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,210); showPair(blendRgb({0,45,5},{40,200,20},t),blendRgb({0,90,40},{100,255,50},(uint8_t)(255-t)),bri); patternStep++; return;
  }
  if (patternName == "NEON") {
    if (now-patternLastMs < 260) return; patternLastMs=now;
    static const Rgb p[]={{255,0,180},{0,255,220},{160,0,255},{255,80,0},{0,120,255}};
    uint8_t i=patternStep++%5; showPair(p[i],p[(i+2)%5],bri); return;
  }
  if (patternName == "TWINKLE") {
    if (now-patternLastMs < 180) return; patternLastMs=now;
    Rgb base0=blendRgb(ledColor[0],{255,255,255},(uint8_t)random(30,150));
    Rgb base1=blendRgb(ledColor[1],{255,255,255},(uint8_t)random(30,150));
    showPair(base0,base1,(uint8_t)random(max(8,(int)bri/3),(int)bri+1)); return;
  }
  if (patternName == "SPARKLE") {
    if (now-patternLastMs < 110) return; patternLastMs=now;
    Rgb a=ledColor[0],b=ledColor[1];
    if (random(3)==0) a={255,255,255}; if (random(3)==0) b={255,255,255}; showPair(a,b,bri); return;
  }
  if (patternName == "COLOR_SWAP") {
    if (now-patternLastMs < 700) return; patternLastMs=now;
    bool flip=(patternStep++&1U); showPair(flip?ledColor[1]:ledColor[0],flip?ledColor[0]:ledColor[1],bri); return;
  }
  if (patternName == "COMET") {
    if (now-patternLastMs < 120) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,64);
    Rgb dim0=blendRgb({0,0,0},ledColor[0],t),dim1=blendRgb({0,0,0},ledColor[1],(uint8_t)(255-t));
    showPair(dim0,dim1,bri); patternStep++; return;
  }
  if (patternName == "FIREFLY") {
    if (now-patternLastMs < 160) return; patternLastMs=now;
    Rgb dark={0,5,0}; Rgb glow={160,255,30};
    showPair(random(5)==0?glow:dark,random(5)==0?glow:dark,bri); return;
  }
  if (patternName == "BUBBLEGUM") {
    if (now-patternLastMs < 55) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,170); showPair(blendRgb({255,30,180},{80,180,255},t),blendRgb({120,40,255},{255,120,200},(uint8_t)(255-t)),bri); patternStep++; return;
  }

  if (patternName == "RANDOM") {
    if (now-patternLastMs < 300) return; patternLastMs=now;
    showPair({(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},
             {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},bri); return;
  }
}

static void hjSetLed(uint8_t led,uint8_t r,uint8_t g,uint8_t b){
  patternName="SOLID"; resetPatternEngine();
  if (led < 1 || led > LED_COUNT) return;
  ledColor[led-1]={r,g,b};
  showLeds();
}
static void hjSetBrightness(uint8_t p){
  brightnessPercent=constrain(p,0,HJ_MAX_BRIGHTNESS);
  if(patternName=="SOLID")showLeds();
}
static void hjSetPattern(const String &name){
  patternName=name; resetPatternEngine();
  if(name=="OFF")allOff(); else if(name=="SOLID")showLeds();
}
'''

# Replace the original high-level pattern engine, but preserve Wi-Fi and the
# proven low-level RMT writer above it.
engine_re = re.compile(
    r'// -----------------------------\n// Pattern engine\n// -----------------------------\n.*?\n// -----------------------------\n// Wi-Fi / NTP\n// -----------------------------',
    re.DOTALL,
)
m = engine_re.search(s)
if not m:
    raise SystemExit("pattern patch failed: pattern engine block not found")
s = s[:m.start()] + pattern_block + '\n// -----------------------------\n// Wi-Fi / NTP\n// -----------------------------' + s[m.end():]

# Clamp any saved legacy brightness above the newly selected product maximum.
load_needle = '  brightnessPercent = prefs.getUChar("bright", 75);\n'
if load_needle not in s:
    raise SystemExit("pattern patch failed: saved brightness load not found")
s = s.replace(load_needle, '  brightnessPercent = min((uint8_t)HJ_MAX_BRIGHTNESS, prefs.getUChar("bright", HJ_MAX_BRIGHTNESS));\n', 1)

# Replace the local physical-button pattern list with the full library.
local_re = re.compile(r'static const String patterns\[\] = \{.*?\};\nstatic int localPatternIndex=0;', re.DOTALL)
if not local_re.search(s):
    raise SystemExit("pattern patch failed: local pattern list not found")
s = local_re.sub('static int localPatternIndex=0;', s, count=1)

# Menu isolation patch currently hardcodes the old six-pattern count.
s = s.replace('localPatternIndex=(localPatternIndex+1)%6; hjSetPattern(patterns[localPatternIndex]);',
              'localPatternIndex=(localPatternIndex+1)%PATTERN_COUNT; hjSetPattern(PATTERN_NAMES[localPatternIndex]);')
s = s.replace('localPatternIndex=(localPatternIndex+5)%6; hjSetPattern(patterns[localPatternIndex]);',
              'localPatternIndex=(localPatternIndex+PATTERN_COUNT-1)%PATTERN_COUNT; hjSetPattern(PATTERN_NAMES[localPatternIndex]);')

# Recovery patch has already wrapped SET PATTERN with uiGoHome(); retain that
# behavior while accepting every library entry through one validator.
handler_re = re.compile(
    r'if\(line\.startsWith\("SET PATTERN "\)\)\{String v=line\.substring\(12\);v\.trim\(\);if\(.*?\)\{uiGoHome\(\);hjSetPattern\(v\);oledDirty=true;ack\("SET PATTERN"\);\}else err\("unknown pattern"\);return;\}',
    re.DOTALL,
)
if not handler_re.search(s):
    raise SystemExit("pattern patch failed: recovered SET PATTERN handler not found")
s = handler_re.sub('if(line.startsWith("SET PATTERN ")){String v=line.substring(12);v.trim();if(isPatternName(v)){uiGoHome();hjSetPattern(v);oledDirty=true;ack("SET PATTERN");}else err("unknown pattern");return;}', s, count=1)

# Old parser allows 0-100; accept it for protocol compatibility but clamp in
# hjSetBrightness(). Also report the actual applied value through status.

p.write_text(s, encoding="utf-8")
