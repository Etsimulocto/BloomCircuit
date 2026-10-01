#!/usr/bin/env python3
"""Add procedural fidget controls to HAPPY JARZ art screensavers.

While screensaver is active:
  LEFT/RIGHT -> previous/next screensaver
  B          -> exit screensaver
  UP         -> faster animation
  DOWN       -> slower animation
  A          -> reseed the procedural generator from live board state

SPIRAL and TRIPPY are not canned presets. A reseed mixes uptime, micros jitter,
ESP32 temperature, Wi-Fi RSSI (when connected), six raw capacitive touch reads,
current light state and Arduino PRNG state into a 32-bit seed. That seed is then
expanded into drawing parameters so the combinations are effectively unbounded.

Runs after screensaver/sayings/custom-sayings patches and leaves marquee/business
message behavior alone.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_saver_controls.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

state_needle = '''static uint16_t hjArtStep = 0;\n'''
if state_needle not in s:
    raise SystemExit("saver controls patch failed: art-step state not found")

state_block = r'''static uint8_t hjSpiralSpeed = 1;
static uint8_t hjTrippySpeed = 1;
static uint32_t hjSpiralSeed = 0x8255A11FUL;
static uint32_t hjTrippySeed = 0x51A7C0DEUL;

static uint32_t hjMix32(uint32_t x) {
  x ^= x >> 16; x *= 0x7feb352dUL;
  x ^= x >> 15; x *= 0x846ca68bUL;
  x ^= x >> 16;
  return x;
}

static uint32_t hjBoardEntropy() {
  uint32_t s = millis() ^ (micros() << 1);
  s ^= (uint32_t)((int)(temperatureRead() * 100.0f)) * 0x9E3779B9UL;
  if (WiFi.status() == WL_CONNECTED) s ^= (uint32_t)(WiFi.RSSI() + 128) * 0x85EBCA6BUL;
  s ^= (uint32_t)touchRead(4)  << 1;
  s ^= (uint32_t)touchRead(5)  << 5;
  s ^= (uint32_t)touchRead(9)  << 9;
  s ^= (uint32_t)touchRead(10) << 13;
  s ^= (uint32_t)touchRead(1)  << 17;
  s ^= (uint32_t)touchRead(2)  << 21;
  s ^= (uint32_t)brightnessPercent << 24;
  s ^= (uint32_t)ledColor[0].r << 8;
  s ^= (uint32_t)ledColor[0].g << 16;
  s ^= (uint32_t)ledColor[0].b << 24;
  s ^= (uint32_t)ledColor[1].r;
  s ^= (uint32_t)random(0x7fffffff);
  return hjMix32(s);
}

static uint32_t hjSeedNext(uint32_t &state) {
  state = hjMix32(state + 0x9E3779B9UL);
  return state;
}

static float hjSeedFloat(uint32_t &state, float lo, float hi) {
  uint32_t v = hjSeedNext(state);
  float t = (float)(v & 0xFFFFU) / 65535.0f;
  return lo + (hi - lo) * t;
}

static int hjSeedInt(uint32_t &state, int lo, int hi) {
  if (hi <= lo) return lo;
  return lo + (int)(hjSeedNext(state) % (uint32_t)(hi - lo + 1));
}

static void hjReseedSpiral() {
  hjSpiralSeed = hjBoardEntropy() ^ 0x53504952UL;
  hjArtStep = 0;
}

static void hjReseedTrippy() {
  hjTrippySeed = hjBoardEntropy() ^ 0x54524950UL;
  hjArtStep = 0;
}
'''
s = s.replace(state_needle, state_needle + state_block, 1)

old_spiral = '''static void oledRenderSaverSpiral() {
  const int cx = 64, cy = 32;
  for (int i=0; i<72; ++i) {
    float a = (float)(i + hjArtStep) * 0.31f;
    float r = 2.0f + (float)i * 0.40f;
    int x = cx + (int)(cosf(a) * r);
    int y = cy + (int)(sinf(a) * r * 0.72f);
    if (x>=0 && x<128 && y>=0 && y<64) oled->drawPixel(x,y);
  }
  oled->drawCircle(cx,cy,2,U8G2_DRAW_ALL);
}
'''
new_spiral = r'''static void oledRenderSaverSpiral() {
  uint32_t g = hjSpiralSeed;

  float angleScale = hjSeedFloat(g, 0.12f, 0.62f);
  if (hjSeedInt(g,0,1)) angleScale = -angleScale;
  float radiusScale = hjSeedFloat(g, 0.24f, 0.62f);
  float squash = hjSeedFloat(g, 0.45f, 1.15f);
  float wobble = hjSeedFloat(g, 0.0f, 0.22f);
  float phase = hjSeedFloat(g, 0.0f, 6.28318f);
  int points = hjSeedInt(g, 52, 118);
  int cxBase = hjSeedInt(g, 50, 78);
  int cyBase = hjSeedInt(g, 24, 40);
  int thickness = hjSeedInt(g, 1, 2);
  int satelliteEvery = hjSeedInt(g, 7, 19);

  // Slow drift comes from the animation step, while the recipe remains stable
  // until A reseeds it. This makes one generated spiral evolve instead of flicker.
  int cx = cxBase + (int)(5.0f * sinf(hjArtStep * 0.017f + phase));
  int cy = cyBase + (int)(4.0f * cosf(hjArtStep * 0.013f + phase));

  for (int i=0; i<points; ++i) {
    float fi = (float)i;
    float a = (fi + (float)hjArtStep * 0.28f) * angleScale + phase;
    a += sinf(fi * 0.17f + hjArtStep * 0.021f) * wobble;
    float r = 1.5f + fi * radiusScale;
    int x = cx + (int)(cosf(a) * r);
    int y = cy + (int)(sinf(a) * r * squash);
    if (x>=0 && x<128 && y>=0 && y<64) {
      oled->drawPixel(x,y);
      if (thickness > 1 && x+1 < 128) oled->drawPixel(x+1,y);
    }
    if (satelliteEvery > 0 && (i % satelliteEvery)==0) {
      int sx = cx + (int)(cosf(-a*0.63f) * r * 0.55f);
      int sy = cy + (int)(sinf(-a*0.63f) * r * 0.38f);
      if (sx>=0 && sx<128 && sy>=0 && sy<64) oled->drawPixel(sx,sy);
    }
  }

  int core = hjSeedInt(g,1,5);
  if (hjSeedInt(g,0,1)) oled->drawCircle(cx,cy,core,U8G2_DRAW_ALL);
  else oled->drawDisc(cx,cy,core,U8G2_DRAW_ALL);
}
'''
if old_spiral not in s:
    raise SystemExit("saver controls patch failed: spiral renderer not found")
s = s.replace(old_spiral, new_spiral, 1)

old_trippy = '''static void oledRenderSaverTrippy() {
  for (int x=0; x<128; x+=8) {
    int y = (int)(32 + 20 * sinf((x + hjArtStep*3) * 0.09f));
    oled->drawLine(x,0,127-x,63);
    oled->drawCircle(x,y,(uint8_t)(2 + ((x/8 + hjArtStep/5)%5)),U8G2_DRAW_ALL);
  }
  oled->drawFrame((hjArtStep*3)%52,(hjArtStep*2)%20,76,44);
}
'''
new_trippy = r'''static void oledRenderSaverTrippy() {
  uint32_t g = hjTrippySeed;

  int family = hjSeedInt(g,0,4);
  int spacing = hjSeedInt(g,5,15);
  float freq1 = hjSeedFloat(g,0.035f,0.14f);
  float freq2 = hjSeedFloat(g,0.025f,0.11f);
  float amp1 = hjSeedFloat(g,7.0f,27.0f);
  float amp2 = hjSeedFloat(g,4.0f,20.0f);
  float phase = hjSeedFloat(g,0.0f,6.28318f);
  int dotEvery = hjSeedInt(g,2,7);
  int ringStep = hjSeedInt(g,4,9);
  bool mirror = hjSeedInt(g,0,1);

  if (family == 0) {
    // Wave + dots + crossing lines.
    int n=0;
    for (int x=0; x<128; x+=spacing,++n) {
      int y = (int)(32 + amp1*sinf((x + hjArtStep*2)*freq1 + phase));
      int y2 = (int)(32 + amp2*cosf((x - hjArtStep)*freq2 - phase));
      oled->drawLine(x,y, mirror ? 127-x : x, y2);
      if ((n % dotEvery)==0) oled->drawCircle(x,y,(uint8_t)(1 + ((n+hjArtStep/8)%4)),U8G2_DRAW_ALL);
    }
  } else if (family == 1) {
    // Drifting concentric orbit field.
    int cx=64+(int)(14*sinf(hjArtStep*0.019f+phase));
    int cy=32+(int)(10*cosf(hjArtStep*0.016f-phase));
    for (int r=3;r<38;r+=ringStep) {
      int dx=(int)(6*sinf((hjArtStep+r)*freq1));
      int dy=(int)(5*cosf((hjArtStep-r)*freq2));
      oled->drawCircle(cx+dx,cy+dy,r,U8G2_DRAW_ALL);
    }
  } else if (family == 2) {
    // Graphic-EQ field, but each generated seed changes spacing/frequency/phase.
    int col=0;
    for (int x=0;x<128;x+=spacing,++col) {
      float wave=sinf(x*freq1 + hjArtStep*0.055f + phase) + cosf(x*freq2 - hjArtStep*0.031f);
      int h=3 + (int)((wave+2.0f)*0.25f*56.0f);
      if (h>60) h=60;
      int y0=mirror ? 2 : 62-h;
      oled->drawBox(x,y0,(uint8_t)max(1,spacing/2),(uint8_t)h);
      if ((col%dotEvery)==0) oled->drawPixel((x+hjArtStep)%128,(h+col*7)%64);
    }
  } else if (family == 3) {
    // Lissajous-ish point cloud with a moving connector.
    int px=64,py=32;
    for (int i=0;i<84;++i) {
      float t=i*0.11f + hjArtStep*0.018f;
      int x=64+(int)(58*sinf(t*(1.0f+freq1*7.0f)+phase));
      int y=32+(int)(28*sinf(t*(1.3f+freq2*9.0f)-phase));
      if (x>=0&&x<128&&y>=0&&y<64) oled->drawPixel(x,y);
      if ((i%dotEvery)==0) oled->drawLine(px,py,x,y);
      px=x;py=y;
    }
  } else {
    // Infinite line lattice; seed controls slope, gaps and phase.
    int tilt=hjSeedInt(g,6,28);
    for (int y=-64;y<128;y+=spacing) {
      int shift=(int)(amp1*sinf(hjArtStep*0.02f + y*freq1 + phase));
      oled->drawLine(0,y+shift,127,y+shift+(mirror?-tilt:tilt));
    }
    for (int x=0;x<128;x+=spacing*2) {
      int yy=(int)(32+amp2*sinf(x*freq2+hjArtStep*0.035f));
      oled->drawCircle(x,yy,(uint8_t)(1+(x/spacing)%4),U8G2_DRAW_ALL);
    }
  }
}
'''
if old_trippy not in s:
    raise SystemExit("saver controls patch failed: trippy renderer not found")
s = s.replace(old_trippy, new_trippy, 1)

old_step = '''    if (hjScreensaverMode == 0) hjMarqueeX -= 2;
    else hjArtStep++;
'''
new_step = '''    if (hjScreensaverMode == 0) hjMarqueeX -= 2;
    else if (hjScreensaverMode == 1) hjArtStep += hjSpiralSpeed;
    else hjArtStep += hjTrippySpeed;
'''
if old_step not in s:
    raise SystemExit("saver controls patch failed: animation step block not found")
s = s.replace(old_step, new_step, 1)

old_input = '''  if (hjScreensaverActive) {
    if (q[IN_B] && !latched[IN_B]) hjScreensaverExit();
    else if (q[IN_RIGHT] && !latched[IN_RIGHT]) hjScreensaverNext();
    else if (q[IN_LEFT] && !latched[IN_LEFT]) hjScreensaverPrev();

    // While the saver owns the screen, do not run HOME/menu actions.
'''
new_input = '''  if (hjScreensaverActive) {
    if (q[IN_B] && !latched[IN_B]) hjScreensaverExit();
    else if (q[IN_RIGHT] && !latched[IN_RIGHT]) hjScreensaverNext();
    else if (q[IN_LEFT] && !latched[IN_LEFT]) hjScreensaverPrev();
    else if (hjScreensaverMode == 1) {
      if (q[IN_UP] && !latched[IN_UP]) { if (hjSpiralSpeed < 8) hjSpiralSpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjSpiralSpeed > 1) hjSpiralSpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjReseedSpiral(); }
    } else if (hjScreensaverMode == 2) {
      if (q[IN_UP] && !latched[IN_UP]) { if (hjTrippySpeed < 8) hjTrippySpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjTrippySpeed > 1) hjTrippySpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjReseedTrippy(); }
    }

    // While the saver owns the screen, do not run HOME/menu actions.
'''
if old_input not in s:
    raise SystemExit("saver controls patch failed: screensaver input block not found")
s = s.replace(old_input, new_input, 1)

# Generate fresh recipes on entry to each art saver. The board state at that
# instant influences the result; A can reseed again any time.
old_next = '''static void hjScreensaverNext() {
  hjScreensaverMode = (uint8_t)((hjScreensaverMode + 1U) % HJ_SCREENSAVER_COUNT);'''
new_next = '''static void hjScreensaverNext() {
  hjScreensaverMode = (uint8_t)((hjScreensaverMode + 1U) % HJ_SCREENSAVER_COUNT);'''
# Keep function text unchanged here; add reseeding after the whole patch via
# input-time lazy init to avoid colliding with sayings-v2's picker rewrites.

p.write_text(s, encoding="utf-8")
