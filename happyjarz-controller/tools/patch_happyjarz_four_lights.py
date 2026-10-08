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
}

// Physical HAPPY JARZ stand topology.
// Bulb 1/2 light the jars; bulb 3/4 are the left/right box-side accents.
static constexpr uint8_t HJ_TOP_LEFT   = 0;
static constexpr uint8_t HJ_TOP_RIGHT  = 1;
static constexpr uint8_t HJ_SIDE_LEFT  = 2;
static constexpr uint8_t HJ_SIDE_RIGHT = 3;

static void hjBlankFrame(Rgb frame[LED_COUNT]) {
  for (uint8_t i=0; i<LED_COUNT; ++i) frame[i]={0,0,0};
}

static Rgb hjDim(const Rgb &c, uint8_t amount) {
  return blendRgb({0,0,0}, c, amount);
}''',
    s,
    count=1,
)

# Extend the shared pattern registry with stand-topology chase effects.
pattern_names_re = re.compile(
    r'static const char \*PATTERN_NAMES\[\] = \{.*?\n\};',
    re.DOTALL,
)
m = pattern_names_re.search(s)
if not m:
    raise SystemExit("four-light patch failed: PATTERN_NAMES registry not found")
registry = '''static const char *PATTERN_NAMES[] = {
  "SOLID","FADE","PULSE","RAINBOW","RANDOM",
  "HUE_FADE","DUAL_HUE","BREATH","DRIFT","AURORA","OCEAN","LAVENDER","SUNSET",
  "CHRISTMAS","HALLOWEEN","VALENTINE","EASTER","FOURTH","THANKSGIVING",
  "CANDY","GALAXY","FIRE","ICE","FOREST","NEON","TWINKLE","SPARKLE","COLOR_SWAP",
  "COMET","FIREFLY","BUBBLEGUM",
  "CHASE_CW","CHASE_CCW","JAR_CHASE","SIDE_CHASE",
  "SWEEP_LR","SWEEP_TS","DIAGONAL","PING_PONG",
  "DUAL_CHASE","OPP_CHASE","JAR_PULSE","SIDE_ACCENT",
  "OFF"
};'''
s = s[:m.start()] + registry + s[m.end():]

# Replace the entire staged pattern service with a true four-lamp engine.
# This is deliberately done after the shared pattern library is staged so no
# legacy two-lamp showPair() call can accidentally survive into the final build.
service_re = re.compile(
    r'static void servicePattern\(\) \{.*?\n\}\n\n(?=static void hjSetLed)',
    re.DOTALL,
)
if not service_re.search(s):
    raise SystemExit("four-light patch failed: servicePattern marker not found")

service_four = r'''static void servicePattern() {
  // HAPPYJARZ_FOUR_LAMP_PATTERN_ENGINE_V2
  if (patternName == "SOLID") return;
  if (patternName == "OFF") { allOff(); return; }

  unsigned long now = millis();
  uint8_t bri = safeBrightness(brightnessPercent);
  if (bri == 0) { allOff(); return; }

  // Base-color brightness effects already operate on all four saved lamp colors.
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

  // Four equally-spaced hues moving around the physical chain.
  if (patternName == "RAINBOW") {
    if (now-patternLastMs < 35) return; patternLastMs=now;
    showFour(
      wheel((uint8_t)patternStep),
      wheel((uint8_t)(patternStep+64)),
      wheel((uint8_t)(patternStep+128)),
      wheel((uint8_t)(patternStep+192)), bri);
    patternStep++; return;
  }

  // All four bulbs intentionally share one hue for a uniform color wash.
  if (patternName == "HUE_FADE") {
    if (now-patternLastMs < 45) return; patternLastMs=now;
    Rgb c=wheel((uint8_t)patternStep);
    showFour(c,c,c,c,bri);
    patternStep++; return;
  }

  // Two opposing hues alternate around the four-lamp ring/line.
  if (patternName == "DUAL_HUE") {
    if (now-patternLastMs < 45) return; patternLastMs=now;
    Rgb a=wheel((uint8_t)patternStep);
    Rgb b=wheel((uint8_t)(patternStep+128));
    showFour(a,b,a,b,bri);
    patternStep++; return;
  }

  if (patternName == "DRIFT") {
    if (now-patternLastMs < 70) return; patternLastMs=now;
    uint8_t t0=triangle8(patternStep,220);
    uint8_t t1=triangle8(patternStep+55,220);
    uint8_t t2=triangle8(patternStep+110,220);
    uint8_t t3=triangle8(patternStep+165,220);
    showFour(
      blendRgb({20,0,90},{0,120,255},t0),
      blendRgb({0,50,120},{130,0,190},t1),
      blendRgb({20,0,90},{0,120,255},t2),
      blendRgb({0,50,120},{130,0,190},t3), bri);
    patternStep++; return;
  }

  if (patternName == "AURORA") {
    if (now-patternLastMs < 55) return; patternLastMs=now;
    uint8_t t0=triangle8(patternStep,240);
    uint8_t t1=triangle8(patternStep+60,240);
    uint8_t t2=triangle8(patternStep+120,240);
    uint8_t t3=triangle8(patternStep+180,240);
    showFour(
      blendRgb({0,180,90},{100,0,220},t0),
      blendRgb({0,80,255},{0,220,120},t1),
      blendRgb({0,220,120},{90,20,230},t2),
      blendRgb({0,70,220},{20,255,140},t3), bri);
    patternStep++; return;
  }

  if (patternName == "OCEAN") {
    if (now-patternLastMs < 65) return; patternLastMs=now;
    uint8_t t0=triangle8(patternStep,180);
    uint8_t t1=triangle8(patternStep+45,180);
    uint8_t t2=triangle8(patternStep+90,180);
    uint8_t t3=triangle8(patternStep+135,180);
    showFour(
      blendRgb({0,20,100},{0,180,255},t0),
      blendRgb({0,120,180},{0,30,130},t1),
      blendRgb({0,35,120},{0,220,210},t2),
      blendRgb({0,100,200},{20,40,150},t3), bri);
    patternStep++; return;
  }

  // Uniform lavender remains intentionally uniform, but all four are explicit.
  if (patternName == "LAVENDER") {
    if (now-patternLastMs < 70) return; patternLastMs=now;
    uint8_t t=triangle8(patternStep,220);
    Rgb c=blendRgb({90,20,150},{230,120,255},t);
    showFour(c,c,c,c,bri);
    patternStep++; return;
  }

  if (patternName == "SUNSET") {
    if (now-patternLastMs < 60) return; patternLastMs=now;
    uint8_t t0=triangle8(patternStep,200);
    uint8_t t1=triangle8(patternStep+50,200);
    uint8_t t2=triangle8(patternStep+100,200);
    uint8_t t3=triangle8(patternStep+150,200);
    showFour(
      blendRgb({255,30,0},{255,130,20},t0),
      blendRgb({255,0,100},{100,0,180},t1),
      blendRgb({255,90,0},{255,20,120},t2),
      blendRgb({160,0,180},{255,100,20},t3), bri);
    patternStep++; return;
  }

  if (patternName == "CHRISTMAS") {
    if (now-patternLastMs < 550) return; patternLastMs=now;
    bool flip=(patternStep++ & 1U);
    Rgb red={255,0,0}, green={0,255,0};
    showFour(flip?red:green, flip?green:red, flip?red:green, flip?green:red, bri);
    return;
  }

  if (patternName == "HALLOWEEN") {
    if (now-patternLastMs < 500) return; patternLastMs=now;
    bool flip=(patternStep++ & 1U);
    Rgb orange={255,70,0}, purple={120,0,255};
    showFour(flip?orange:purple, flip?purple:orange,
             flip?orange:purple, flip?purple:orange, bri);
    return;
  }

  if (patternName == "VALENTINE") {
    if (now-patternLastMs < 45) return; patternLastMs=now;
    uint8_t t0=triangle8(patternStep,180);
    uint8_t t1=triangle8(patternStep+45,180);
    uint8_t t2=triangle8(patternStep+90,180);
    uint8_t t3=triangle8(patternStep+135,180);
    showFour(
      blendRgb({255,0,40},{255,20,160},t0),
      blendRgb({255,40,100},{180,0,70},t1),
      blendRgb({255,20,120},{255,100,160},t2),
      blendRgb({180,0,80},{255,40,60},t3), bri);
    patternStep++; return;
  }

  if (patternName == "EASTER") {
    if (now-patternLastMs < 650) return; patternLastMs=now;
    static const Rgb p[]={{255,120,200},{130,220,255},{180,130,255},{255,220,80},{120,255,170}};
    uint8_t i=patternStep++%5;
    showFour(p[i],p[(i+1)%5],p[(i+2)%5],p[(i+3)%5],bri);
    return;
  }

  if (patternName == "FOURTH") {
    if (now-patternLastMs < 420) return; patternLastMs=now;
    static const Rgb p[]={{255,0,0},{255,255,255},{0,60,255}};
    uint8_t i=patternStep++%3;
    showFour(p[i],p[(i+1)%3],p[(i+2)%3],p[i],bri);
    return;
  }

  if (patternName == "THANKSGIVING") {
    if (now-patternLastMs < 600) return; patternLastMs=now;
    static const Rgb p[]={{255,70,0},{180,30,0},{255,160,0},{100,20,0}};
    uint8_t i=patternStep++%4;
    showFour(p[i],p[(i+1)%4],p[(i+2)%4],p[(i+3)%4],bri);
    return;
  }

  if (patternName == "CANDY") {
    if (now-patternLastMs < 320) return; patternLastMs=now;
    static const Rgb p[]={{255,20,120},{0,220,255},{255,180,0},{120,255,80},{170,40,255}};
    showFour(p[random(5)],p[random(5)],p[random(5)],p[random(5)],bri);
    return;
  }

  if (patternName == "GALAXY") {
    if (now-patternLastMs < 90) return; patternLastMs=now;
    Rgb frame[LED_COUNT];
    for(uint8_t i=0;i<LED_COUNT;++i){
      uint8_t t=triangle8(patternStep + (uint16_t)i*60U,240);
      frame[i]=blendRgb(i&1 ? Rgb{0,20,70}:Rgb{10,0,40},
                        i&1 ? Rgb{255,0,130}:Rgb{100,0,220},t);
      uint16_t spark=(uint16_t)(37U + (uint16_t)i*7U);
      if(((patternStep + i*11U)%spark)==0) frame[i]=i&1 ? Rgb{255,255,255}:Rgb{180,180,255};
    }
    writeFrame(frame,bri);
    patternStep++; return;
  }

  if (patternName == "FIRE") {
    if (now-patternLastMs < 80) return; patternLastMs=now;
    Rgb frame[LED_COUNT];
    for(uint8_t i=0;i<LED_COUNT;++i)
      frame[i]={(uint8_t)random(180,256),(uint8_t)random(10,105),(uint8_t)random(0,8)};
    writeFrame(frame,bri); return;
  }

  if (patternName == "ICE") {
    if (now-patternLastMs < 100) return; patternLastMs=now;
    Rgb frame[LED_COUNT];
    for(uint8_t i=0;i<LED_COUNT;++i)
      frame[i]={(uint8_t)random(20,180),(uint8_t)random(120,256),255};
    writeFrame(frame,bri); return;
  }

  if (patternName == "FOREST") {
    if (now-patternLastMs < 90) return; patternLastMs=now;
    uint8_t t0=triangle8(patternStep,210);
    uint8_t t1=triangle8(patternStep+52,210);
    uint8_t t2=triangle8(patternStep+105,210);
    uint8_t t3=triangle8(patternStep+157,210);
    showFour(
      blendRgb({0,45,5},{40,200,20},t0),
      blendRgb({0,90,40},{100,255,50},t1),
      blendRgb({5,55,0},{80,180,25},t2),
      blendRgb({0,110,30},{130,240,60},t3), bri);
    patternStep++; return;
  }

  if (patternName == "NEON") {
    if (now-patternLastMs < 260) return; patternLastMs=now;
    static const Rgb p[]={{255,0,180},{0,255,220},{160,0,255},{255,80,0},{0,120,255}};
    uint8_t i=patternStep++%5;
    showFour(p[i],p[(i+1)%5],p[(i+2)%5],p[(i+3)%5],bri);
    return;
  }

  if (patternName == "TWINKLE") {
    if (now-patternLastMs < 180) return; patternLastMs=now;
    Rgb frame[LED_COUNT];
    for (uint8_t i=0; i<LED_COUNT; ++i)
      frame[i]=blendRgb(ledColor[i],{255,255,255},(uint8_t)random(30,150));
    uint8_t low=(uint8_t)max(1,(int)bri/3);
    writeFrame(frame,(uint8_t)random((long)low,(long)bri+1L)); return;
  }

  if (patternName == "SPARKLE") {
    if (now-patternLastMs < 110) return; patternLastMs=now;
    Rgb frame[LED_COUNT];
    for (uint8_t i=0; i<LED_COUNT; ++i) {
      frame[i]=ledColor[i];
      if (random(3)==0) frame[i]={255,255,255};
    }
    writeFrame(frame,bri); return;
  }

  if (patternName == "COLOR_SWAP") {
    if (now-patternLastMs < 700) return; patternLastMs=now;
    uint8_t shift=(uint8_t)(patternStep++ & 3U);
    Rgb frame[LED_COUNT];
    for (uint8_t i=0; i<LED_COUNT; ++i)
      frame[i]=ledColor[(i+shift)%LED_COUNT];
    writeFrame(frame,bri); return;
  }

  // One bright head moves through all four physical lamps with two fading tails.
  if (patternName == "COMET") {
    if (now-patternLastMs < 120) return; patternLastMs=now;
    uint8_t head=(uint8_t)(patternStep++ & 3U);
    Rgb frame[LED_COUNT]={{0,0,0},{0,0,0},{0,0,0},{0,0,0}};
    frame[head]=ledColor[head];
    uint8_t tail1=(uint8_t)((head+3U)&3U);
    uint8_t tail2=(uint8_t)((head+2U)&3U);
    frame[tail1]=blendRgb({0,0,0},ledColor[tail1],110);
    frame[tail2]=blendRgb({0,0,0},ledColor[tail2],40);
    writeFrame(frame,bri); return;
  }

  if (patternName == "FIREFLY") {
    if (now-patternLastMs < 160) return; patternLastMs=now;
    Rgb dark={0,5,0}, glow={160,255,30};
    showFour(random(5)==0?glow:dark,
             random(5)==0?glow:dark,
             random(5)==0?glow:dark,
             random(5)==0?glow:dark,bri);
    return;
  }

  if (patternName == "BUBBLEGUM") {
    if (now-patternLastMs < 55) return; patternLastMs=now;
    uint8_t t0=triangle8(patternStep,170);
    uint8_t t1=triangle8(patternStep+42,170);
    uint8_t t2=triangle8(patternStep+85,170);
    uint8_t t3=triangle8(patternStep+127,170);
    showFour(
      blendRgb({255,30,180},{80,180,255},t0),
      blendRgb({120,40,255},{255,120,200},t1),
      blendRgb({255,70,170},{50,210,255},t2),
      blendRgb({100,60,255},{255,160,210},t3), bri);
    patternStep++; return;
  }

  // Stand-topology chase family. Paths use physical geometry rather than
  // DIN order assumptions: 1=top-left, 2=top-right, 3=side-left, 4=side-right.
  if (patternName == "CHASE_CW") {
    if (now-patternLastMs < 180) return; patternLastMs=now;
    static const uint8_t path[] = {HJ_TOP_LEFT,HJ_TOP_RIGHT,HJ_SIDE_RIGHT,HJ_SIDE_LEFT};
    uint8_t head=path[patternStep++ & 3U];
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    frame[head]=ledColor[head];
    frame[path[(patternStep+2U)&3U]]=hjDim(ledColor[path[(patternStep+2U)&3U]],55);
    writeFrame(frame,bri); return;
  }

  if (patternName == "CHASE_CCW") {
    if (now-patternLastMs < 180) return; patternLastMs=now;
    static const uint8_t path[] = {HJ_TOP_LEFT,HJ_SIDE_LEFT,HJ_SIDE_RIGHT,HJ_TOP_RIGHT};
    uint8_t head=path[patternStep++ & 3U];
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    frame[head]=ledColor[head];
    frame[path[(patternStep+2U)&3U]]=hjDim(ledColor[path[(patternStep+2U)&3U]],55);
    writeFrame(frame,bri); return;
  }

  if (patternName == "JAR_CHASE") {
    if (now-patternLastMs < 260) return; patternLastMs=now;
    bool right=(patternStep++ & 1U);
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    frame[right?HJ_TOP_RIGHT:HJ_TOP_LEFT]=ledColor[right?HJ_TOP_RIGHT:HJ_TOP_LEFT];
    frame[HJ_SIDE_LEFT]=hjDim(ledColor[HJ_SIDE_LEFT],45);
    frame[HJ_SIDE_RIGHT]=hjDim(ledColor[HJ_SIDE_RIGHT],45);
    writeFrame(frame,bri); return;
  }

  if (patternName == "SIDE_CHASE") {
    if (now-patternLastMs < 260) return; patternLastMs=now;
    bool right=(patternStep++ & 1U);
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    frame[right?HJ_SIDE_RIGHT:HJ_SIDE_LEFT]=ledColor[right?HJ_SIDE_RIGHT:HJ_SIDE_LEFT];
    writeFrame(frame,bri); return;
  }

  if (patternName == "SWEEP_LR") {
    if (now-patternLastMs < 300) return; patternLastMs=now;
    bool right=(patternStep++ & 1U);
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    if(right){
      frame[HJ_TOP_RIGHT]=ledColor[HJ_TOP_RIGHT];
      frame[HJ_SIDE_RIGHT]=ledColor[HJ_SIDE_RIGHT];
    }else{
      frame[HJ_TOP_LEFT]=ledColor[HJ_TOP_LEFT];
      frame[HJ_SIDE_LEFT]=ledColor[HJ_SIDE_LEFT];
    }
    writeFrame(frame,bri); return;
  }

  if (patternName == "SWEEP_TS") {
    if (now-patternLastMs < 320) return; patternLastMs=now;
    bool sides=(patternStep++ & 1U);
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    if(sides){
      frame[HJ_SIDE_LEFT]=ledColor[HJ_SIDE_LEFT];
      frame[HJ_SIDE_RIGHT]=ledColor[HJ_SIDE_RIGHT];
    }else{
      frame[HJ_TOP_LEFT]=ledColor[HJ_TOP_LEFT];
      frame[HJ_TOP_RIGHT]=ledColor[HJ_TOP_RIGHT];
    }
    writeFrame(frame,bri); return;
  }

  if (patternName == "DIAGONAL") {
    if (now-patternLastMs < 320) return; patternLastMs=now;
    bool flip=(patternStep++ & 1U);
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    if(flip){
      frame[HJ_TOP_LEFT]=ledColor[HJ_TOP_LEFT];
      frame[HJ_SIDE_RIGHT]=ledColor[HJ_SIDE_RIGHT];
    }else{
      frame[HJ_TOP_RIGHT]=ledColor[HJ_TOP_RIGHT];
      frame[HJ_SIDE_LEFT]=ledColor[HJ_SIDE_LEFT];
    }
    writeFrame(frame,bri); return;
  }

  if (patternName == "PING_PONG") {
    if (now-patternLastMs < 170) return; patternLastMs=now;
    static const uint8_t path[] = {
      HJ_TOP_LEFT,HJ_TOP_RIGHT,HJ_SIDE_RIGHT,HJ_SIDE_LEFT,
      HJ_SIDE_RIGHT,HJ_TOP_RIGHT
    };
    uint8_t head=path[patternStep++ % 6U];
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    frame[head]=ledColor[head];
    writeFrame(frame,bri); return;
  }

  if (patternName == "DUAL_CHASE") {
    if (now-patternLastMs < 250) return; patternLastMs=now;
    bool right=(patternStep++ & 1U);
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    frame[right?HJ_TOP_RIGHT:HJ_TOP_LEFT]=ledColor[right?HJ_TOP_RIGHT:HJ_TOP_LEFT];
    frame[right?HJ_SIDE_RIGHT:HJ_SIDE_LEFT]=ledColor[right?HJ_SIDE_RIGHT:HJ_SIDE_LEFT];
    writeFrame(frame,bri); return;
  }

  if (patternName == "OPP_CHASE") {
    if (now-patternLastMs < 250) return; patternLastMs=now;
    bool phase=(patternStep++ & 1U);
    Rgb frame[LED_COUNT]; hjBlankFrame(frame);
    frame[phase?HJ_TOP_RIGHT:HJ_TOP_LEFT]=ledColor[phase?HJ_TOP_RIGHT:HJ_TOP_LEFT];
    frame[phase?HJ_SIDE_LEFT:HJ_SIDE_RIGHT]=ledColor[phase?HJ_SIDE_LEFT:HJ_SIDE_RIGHT];
    writeFrame(frame,bri); return;
  }

  if (patternName == "JAR_PULSE") {
    if (now-patternLastMs < 28) return; patternLastMs=now;
    uint8_t level=triangle8(patternStep++,180);
    uint8_t jarAmt=(uint8_t)(70U + (uint16_t)level*185U/255U);
    Rgb frame[LED_COUNT];
    frame[HJ_TOP_LEFT]=hjDim(ledColor[HJ_TOP_LEFT],jarAmt);
    frame[HJ_TOP_RIGHT]=hjDim(ledColor[HJ_TOP_RIGHT],jarAmt);
    frame[HJ_SIDE_LEFT]=hjDim(ledColor[HJ_SIDE_LEFT],55);
    frame[HJ_SIDE_RIGHT]=hjDim(ledColor[HJ_SIDE_RIGHT],55);
    writeFrame(frame,bri); return;
  }

  if (patternName == "SIDE_ACCENT") {
    if (now-patternLastMs < 240) return; patternLastMs=now;
    bool right=(patternStep++ & 1U);
    Rgb frame[LED_COUNT];
    frame[HJ_TOP_LEFT]=hjDim(ledColor[HJ_TOP_LEFT],150);
    frame[HJ_TOP_RIGHT]=hjDim(ledColor[HJ_TOP_RIGHT],150);
    frame[HJ_SIDE_LEFT]=right ? hjDim(ledColor[HJ_SIDE_LEFT],25) : ledColor[HJ_SIDE_LEFT];
    frame[HJ_SIDE_RIGHT]=right ? ledColor[HJ_SIDE_RIGHT] : hjDim(ledColor[HJ_SIDE_RIGHT],25);
    writeFrame(frame,bri); return;
  }

  if (patternName == "RANDOM") {
    if (now-patternLastMs < 300) return; patternLastMs=now;
    showFour(
      {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},
      {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},
      {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},
      {(uint8_t)random(256),(uint8_t)random(256),(uint8_t)random(256)},bri);
    return;
  }
}

'''
s = service_re.sub(service_four, s, count=1)

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
        r'(?m)^\s*if\(line\.startsWith\("SET BRIGHTNESS "\)\).*?$',
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
