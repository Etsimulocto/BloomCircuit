#!/usr/bin/env python3
"""Add BLOOM, BREATHE and GLITTER OLED screensavers.

Runs after the existing PARTICLES layer and before saver protocol helpers.
Modes:
  4 BLOOM   - procedural lotus opening/closing
  5 BREATHE - slow breathing geometry with dither-like density changes
  6 GLITTER - mixed-shape falling glitter with independent drift/speed
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_saver_visual_pack.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

count_old = 'static constexpr uint8_t HJ_SCREENSAVER_COUNT = 4;\n'
if count_old not in s:
    raise SystemExit("visual saver pack failed: 4-mode saver count marker not found")
s = s.replace(count_old, 'static constexpr uint8_t HJ_SCREENSAVER_COUNT = 7;\n', 1)

marker = '''static void oledRenderSaverParticles() {
'''
pos = s.find(marker)
if pos < 0:
    raise SystemExit("visual saver pack failed: particle renderer marker not found")
end = s.find("\n}", pos)
if end < 0:
    raise SystemExit("visual saver pack failed: particle renderer end not found")
end += 2

visual_code = r'''

// HAPPYJARZ_VISUAL_SAVER_PACK_V1
static uint8_t hjVisualSpeed = 1;
static uint32_t hjVisualSeed = 0xB1008255UL;

static constexpr uint8_t HJ_GLITTER_COUNT = 18;
struct HjGlitterBit {
  int16_t x;
  int16_t y8;
  int8_t drift;
  uint8_t fall;
  uint8_t shape;
  uint8_t phase;
};
static HjGlitterBit hjGlitter[HJ_GLITTER_COUNT];
static bool hjGlitterReady = false;

static void hjGlitterRespawn(uint8_t i, bool fromTop) {
  hjGlitter[i].x = (int16_t)random(2,126);
  hjGlitter[i].y8 = fromTop ? (int16_t)random(-160,0) : (int16_t)random(0,64*8);
  hjGlitter[i].drift = (int8_t)random(-2,3);
  hjGlitter[i].fall = (uint8_t)random(2,8);
  hjGlitter[i].shape = (uint8_t)random(0,6);
  hjGlitter[i].phase = (uint8_t)random(0,255);
}

static void hjReseedVisualSaver() {
  hjVisualSeed = hjBoardEntropy() ^ 0xB1006D5AUL;
  randomSeed(hjVisualSeed);
  hjArtStep = 0;
  for(uint8_t i=0;i<HJ_GLITTER_COUNT;++i) hjGlitterRespawn(i,false);
  hjGlitterReady = true;
}

static void oledDrawGlitterShape(int x, int y, uint8_t shape, uint8_t phase) {
  if(x<1 || x>126 || y<1 || y>62) return;
  switch(shape % 6U) {
    case 0:
      oled->drawPixel(x,y);
      break;
    case 1:
      oled->drawPixel(x,y);
      oled->drawPixel(x-1,y); oled->drawPixel(x+1,y);
      oled->drawPixel(x,y-1); oled->drawPixel(x,y+1);
      break;
    case 2:
      oled->drawPixel(x,y-1);
      oled->drawPixel(x-1,y);
      oled->drawPixel(x+1,y);
      oled->drawPixel(x,y+1);
      break;
    case 3:
      oled->drawFrame(x-1,y-1,3,3);
      break;
    case 4:
      oled->drawLine(x-2,y,x+2,y);
      oled->drawLine(x,y-2,x,y+2);
      if(phase & 0x20U) {
        oled->drawPixel(x-1,y-1); oled->drawPixel(x+1,y+1);
        oled->drawPixel(x+1,y-1); oled->drawPixel(x-1,y+1);
      }
      break;
    default:
      oled->drawDisc(x,y,1,U8G2_DRAW_ALL);
      break;
  }
}

static void oledRenderSaverBloom() {
  // Eight symmetric petals open and close around a small lotus core.
  float breath = (sinf((float)hjArtStep * 0.035f) + 1.0f) * 0.5f;
  float twist = (float)hjArtStep * 0.010f;
  int cx=64, cy=34;
  int outerR = 10 + (int)(breath * 18.0f);
  int innerR = 5 + (int)((1.0f-breath) * 8.0f);

  for(int petal=0; petal<8; ++petal) {
    float a = twist + (float)petal * 0.785398f;
    int x1 = cx + (int)(cosf(a) * innerR);
    int y1 = cy + (int)(sinf(a) * innerR * 0.58f);
    int x2 = cx + (int)(cosf(a) * outerR);
    int y2 = cy + (int)(sinf(a) * outerR * 0.58f);
    int px = cx + (int)(cosf(a+0.33f) * (outerR-3));
    int py = cy + (int)(sinf(a+0.33f) * (outerR-3) * 0.58f);
    int mx = cx + (int)(cosf(a-0.33f) * (outerR-3));
    int my = cy + (int)(sinf(a-0.33f) * (outerR-3) * 0.58f);
    oled->drawTriangle(x1,y1,px,py,x2,y2);
    oled->drawTriangle(x1,y1,mx,my,x2,y2);
  }

  // Lower lotus bowl / leaves.
  oled->drawArc(cx,47,24,18,20,160);
  oled->drawArc(cx,47,17,12,20,160);
  oled->drawCircle(cx,cy,2,U8G2_DRAW_ALL);

  // Occasional tiny pollen pixels.
  for(uint8_t i=0;i<5;++i) {
    uint16_t v=(uint16_t)(hjArtStep*13U + i*97U);
    int x=48 + (v % 33U);
    int y=9 + ((v/7U + i*11U) % 15U);
    if(((hjArtStep+i*5U)%17U)<9U) oled->drawPixel(x,y);
  }
}

static void oledRenderSaverBreathe() {
  // Monochrome OLED cannot truly dim, so density + radius create a perceived
  // fade. Each breath cycle slowly changes the geometry recipe.
  uint16_t cycle = hjArtStep / 180U;
  float t = (sinf((float)hjArtStep * 0.0349f - 1.5708f) + 1.0f) * 0.5f;
  int cx = 64 + (int)(6.0f*sinf(cycle*0.73f));
  int cy = 32 + (int)(4.0f*cosf(cycle*0.61f));
  int radius = 5 + (int)(t*25.0f);
  uint8_t recipe=(uint8_t)(cycle % 4U);

  if(recipe==0) {
    for(int r=radius; r>2; r-=5) oled->drawCircle(cx,cy,r,U8G2_DRAW_ALL);
  } else if(recipe==1) {
    int w=12+(int)(t*76.0f), h=8+(int)(t*38.0f);
    for(int inset=0; inset<4; ++inset) {
      int ww=w-inset*9, hh=h-inset*5;
      if(ww>3 && hh>3) oled->drawFrame(cx-ww/2,cy-hh/2,ww,hh);
    }
  } else if(recipe==2) {
    for(int i=0;i<12;++i) {
      float a=(float)i*0.523599f + hjArtStep*0.005f;
      int x=cx+(int)(cosf(a)*radius);
      int y=cy+(int)(sinf(a)*radius*0.65f);
      if((i + (hjArtStep/8U))%3U) oled->drawDisc(x,y,1,U8G2_DRAW_ALL);
      else oled->drawCircle(x,y,2,U8G2_DRAW_ALL);
    }
  } else {
    int spacing=3 + (int)((1.0f-t)*5.0f);
    for(int y=4;y<62;y+=spacing) {
      int xoff=((y/spacing)&1)?spacing/2:0;
      for(int x=4+xoff;x<126;x+=spacing) {
        int dx=x-cx, dy=y-cy;
        if(dx*dx + dy*dy < radius*radius) oled->drawPixel(x,y);
      }
    }
  }

  // A calm center cue.
  oled->drawDisc(cx,cy,1,U8G2_DRAW_ALL);
}

static void oledRenderSaverGlitter() {
  if(!hjGlitterReady) hjReseedVisualSaver();

  for(uint8_t i=0;i<HJ_GLITTER_COUNT;++i) {
    HjGlitterBit &g=hjGlitter[i];

    // Different fall rates plus a gentle pseudo-wobble.
    g.y8 += (int16_t)g.fall * hjVisualSpeed;
    int wobble = (((int)g.phase + (int)hjArtStep + i*9) & 31) < 16 ? -1 : 1;
    if((hjArtStep + i) % (uint16_t)(7U + (i%5U)) == 0U) g.x += g.drift + wobble;

    int y=g.y8/8;
    if(y>66 || g.x<-3 || g.x>130) {
      hjGlitterRespawn(i,true);
      continue;
    }

    oledDrawGlitterShape(g.x,y,g.shape,(uint8_t)(g.phase+hjArtStep));

    // Some flakes leave one tiny trailing sparkle.
    if((g.phase & 3U)==0U && y>2 && y<63) oled->drawPixel(g.x,y-2);
  }

  // Random flash-stars make the field occasionally go a little feral.
  if((hjArtStep % 11U)==0U) {
    int x=(int)random(4,124), y=(int)random(4,60);
    oled->drawLine(x-2,y,x+2,y);
    oled->drawLine(x,y-2,x,y+2);
  }
}
'''
s = s[:end] + visual_code + s[end:]

old_render = '''static void oledRenderScreensaver() {
  switch (hjScreensaverMode) {
    case 0: oledRenderSaverSayings(); break;
    case 1: oledRenderSaverSpiral(); break;
    case 2: oledRenderSaverTrippy(); break;
    default: oledRenderSaverParticles(); break;
  }
}
'''
new_render = '''static void oledRenderScreensaver() {
  switch (hjScreensaverMode) {
    case 0: oledRenderSaverSayings(); break;
    case 1: oledRenderSaverSpiral(); break;
    case 2: oledRenderSaverTrippy(); break;
    case 3: oledRenderSaverParticles(); break;
    case 4: oledRenderSaverBloom(); break;
    case 5: oledRenderSaverBreathe(); break;
    default: oledRenderSaverGlitter(); break;
  }
}
'''
if old_render not in s:
    raise SystemExit("visual saver pack failed: 4-mode renderer switch not found")
s = s.replace(old_render,new_render,1)

old_step = '''    if (hjScreensaverMode == 0) hjMarqueeX -= 2;
    else if (hjScreensaverMode == 1) hjArtStep += hjSpiralSpeed;
    else if (hjScreensaverMode == 2) hjArtStep += hjTrippySpeed;
    else {
      for (uint8_t ps=0; ps<hjParticleSpeed; ++ps) hjParticleStepOnce();
      hjArtStep++;
    }
'''
new_step = '''    if (hjScreensaverMode == 0) hjMarqueeX -= 2;
    else if (hjScreensaverMode == 1) hjArtStep += hjSpiralSpeed;
    else if (hjScreensaverMode == 2) hjArtStep += hjTrippySpeed;
    else if (hjScreensaverMode == 3) {
      for (uint8_t ps=0; ps<hjParticleSpeed; ++ps) hjParticleStepOnce();
      hjArtStep++;
    } else {
      hjArtStep += hjVisualSpeed;
    }
'''
if old_step not in s:
    raise SystemExit("visual saver pack failed: 4-mode animation step block not found")
s = s.replace(old_step,new_step,1)

# New visual modes share speed/reseed controls.
old_input = '''    } else if (hjScreensaverMode == 3) {
      if (q[IN_UP] && !latched[IN_UP]) { if (hjParticleSpeed < 8) hjParticleSpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjParticleSpeed > 1) hjParticleSpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjReseedParticles(); }
    }

    // While the saver owns the screen, do not run HOME/menu actions.
'''
new_input = '''    } else if (hjScreensaverMode == 3) {
      if (q[IN_UP] && !latched[IN_UP]) { if (hjParticleSpeed < 8) hjParticleSpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjParticleSpeed > 1) hjParticleSpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjReseedParticles(); }
    } else if (hjScreensaverMode >= 4) {
      if (q[IN_UP] && !latched[IN_UP]) { if (hjVisualSpeed < 8) hjVisualSpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjVisualSpeed > 1) hjVisualSpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjReseedVisualSaver(); }
    }

    // While the saver owns the screen, do not run HOME/menu actions.
'''
if old_input not in s:
    raise SystemExit("visual saver pack failed: input tail not found")
s = s.replace(old_input,new_input,1)

# Reset/reseed when entering new visual modes using physical LEFT/RIGHT.
for fn in ('hjScreensaverNext','hjScreensaverPrev'):
    marker=f'static void {fn}() {{\n'
    pos=s.find(marker)
    if pos<0:
        raise SystemExit(f"visual saver pack failed: {fn} not found")
    end=s.find('\n}',pos)
    body=s[pos:end]
    target='  if (hjScreensaverMode == 3) hjReseedParticles();'
    if target not in body:
        raise SystemExit(f"visual saver pack failed: {fn} particle reset marker not found")
    body=body.replace(target,target+'\n  if (hjScreensaverMode >= 4) hjReseedVisualSaver();',1)
    s=s[:pos]+body+s[end:]

p.write_text(s,encoding="utf-8")
print("Applied HAPPY JARZ visual saver pack: BLOOM + BREATHE + GLITTER.")
