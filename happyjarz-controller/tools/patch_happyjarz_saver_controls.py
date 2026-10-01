#!/usr/bin/env python3
"""Add simple fidget controls to HAPPY JARZ art screensavers.

While screensaver is active:
  LEFT/RIGHT -> previous/next screensaver (existing behavior)
  B          -> exit screensaver (existing behavior)
  UP         -> faster animation
  DOWN       -> slower animation
  A          -> next visual style

SAYINGS ignores A/UP/DOWN. SPIRAL and TRIPPY each remember their own speed/style.
Runs after screensaver/sayings/custom-sayings patches so it does not disturb
marquee message handling or the HOME/menu light-control isolation.
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
state_block = '''static uint8_t hjSpiralSpeed = 1;\nstatic uint8_t hjSpiralStyle = 0;\nstatic uint8_t hjTrippySpeed = 1;\nstatic uint8_t hjTrippyStyle = 0;\n'''
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
new_spiral = '''static void oledRenderSaverSpiral() {
  const int cx = 64, cy = 32;
  float angleScale = hjSpiralStyle == 0 ? 0.31f : (hjSpiralStyle == 1 ? -0.31f : 0.22f);
  float radiusScale = hjSpiralStyle == 2 ? 0.50f : 0.40f;
  float squash = hjSpiralStyle == 1 ? 1.00f : 0.72f;
  int points = hjSpiralStyle == 2 ? 92 : 72;
  for (int i=0; i<points; ++i) {
    float a = (float)(i + hjArtStep) * angleScale;
    float r = 2.0f + (float)i * radiusScale;
    int x = cx + (int)(cosf(a) * r);
    int y = cy + (int)(sinf(a) * r * squash);
    if (x>=0 && x<128 && y>=0 && y<64) oled->drawPixel(x,y);
    if (hjSpiralStyle == 2 && x+1<128 && y+1<64 && x>=0 && y>=0) oled->drawPixel(x+1,y+1);
  }
  if (hjSpiralStyle == 0) oled->drawCircle(cx,cy,2,U8G2_DRAW_ALL);
  else if (hjSpiralStyle == 1) oled->drawDisc(cx,cy,2,U8G2_DRAW_ALL);
  else oled->drawCircle(cx,cy,4,U8G2_DRAW_ALL);
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
new_trippy = '''static void oledRenderSaverTrippy() {
  if (hjTrippyStyle == 0) {
    for (int x=0; x<128; x+=8) {
      int y = (int)(32 + 20 * sinf((x + hjArtStep*3) * 0.09f));
      oled->drawLine(x,0,127-x,63);
      oled->drawCircle(x,y,(uint8_t)(2 + ((x/8 + hjArtStep/5)%5)),U8G2_DRAW_ALL);
    }
    oled->drawFrame((hjArtStep*3)%52,(hjArtStep*2)%20,76,44);
  } else if (hjTrippyStyle == 1) {
    for (int r=4; r<32; r+=5) {
      int wobble=(int)(5*sinf((hjArtStep+r)*0.12f));
      oled->drawCircle(64+wobble,32-wobble,r,U8G2_DRAW_ALL);
    }
    oled->drawLine(0,(hjArtStep*2)%64,127,63-((hjArtStep*2)%64));
  } else {
    for (int x=0; x<128; x+=12) {
      int y=(int)(31 + 25*sinf((x+hjArtStep*4)*0.07f));
      oled->drawBox(x,y<31?y:31,5,(uint8_t)(abs(31-y)+1));
    }
    for (int y=0; y<64; y+=8) oled->drawPixel((hjArtStep*5+y*3)%128,y);
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
      if (q[IN_UP] && !latched[IN_UP]) { if (hjSpiralSpeed < 6) hjSpiralSpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjSpiralSpeed > 1) hjSpiralSpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjSpiralStyle=(uint8_t)((hjSpiralStyle+1U)%3U); hjArtStep=0; }
    } else if (hjScreensaverMode == 2) {
      if (q[IN_UP] && !latched[IN_UP]) { if (hjTrippySpeed < 6) hjTrippySpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjTrippySpeed > 1) hjTrippySpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjTrippyStyle=(uint8_t)((hjTrippyStyle+1U)%3U); hjArtStep=0; }
    }

    // While the saver owns the screen, do not run HOME/menu actions.
'''
if old_input not in s:
    raise SystemExit("saver controls patch failed: screensaver input block not found")
s = s.replace(old_input, new_input, 1)

p.write_text(s, encoding="utf-8")
