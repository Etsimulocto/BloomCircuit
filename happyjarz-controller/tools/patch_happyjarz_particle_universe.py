#!/usr/bin/env python3
"""Add a fourth, board-seeded PARTICLES screensaver to HAPPY JARZ.

Runs after patch_happyjarz_saver_controls.py and before saver protocol.
The engine intentionally uses a tiny rule set (particles + attractors + optional
neighbor links) to generate a very large visual space without bitmap assets.

Controls while PARTICLES is active:
  A          reseed / NEW UNIVERSE
  UP/DOWN    simulation speed 1..8
  LEFT/RIGHT change saver family
  B          exit saver
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_particle_universe.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

count_old = 'static constexpr uint8_t HJ_SCREENSAVER_COUNT = 3;\n'
if count_old not in s:
    raise SystemExit("particle universe patch failed: saver count marker not found")
s = s.replace(count_old, 'static constexpr uint8_t HJ_SCREENSAVER_COUNT = 4;\n', 1)

state_marker = 'static uint32_t hjTrippySeed = 0x51A7C0DEUL;\n'
if state_marker not in s:
    raise SystemExit("particle universe patch failed: procedural state marker not found")

state_block = r'''static constexpr uint8_t HJ_PARTICLE_MAX = 18;
static constexpr uint8_t HJ_ATTRACTOR_MAX = 3;
struct HjParticle { float x,y,vx,vy; };
struct HjAttractor { float x,y,strength; };
static HjParticle hjParticles[HJ_PARTICLE_MAX];
static HjAttractor hjAttractors[HJ_ATTRACTOR_MAX];
static uint8_t hjParticleCount = 12;
static uint8_t hjAttractorCount = 1;
static uint8_t hjParticleSpeed = 1;
static uint32_t hjParticleSeed = 0xC05A1055UL;
static float hjParticleDamping = 0.985f;
static float hjParticleGravity = 0.055f;
static float hjParticleOrbit = 0.018f;
static float hjParticleLinkDistance = 18.0f;
static bool hjParticleLinks = true;
static bool hjParticleWrap = true;
static bool hjParticleRepel = false;

'''
s = s.replace(state_marker, state_marker + state_block, 1)

reseed_marker = '''static void hjReseedTrippy() {
  hjTrippySeed = hjBoardEntropy() ^ 0x54524950UL;
  hjArtStep = 0;
}
'''
if reseed_marker not in s:
    raise SystemExit("particle universe patch failed: trippy reseed marker not found")

particle_code = r'''

static void hjReseedParticles() {
  hjParticleSeed = hjBoardEntropy() ^ 0x50415254UL;
  uint32_t g = hjParticleSeed;

  hjParticleCount = (uint8_t)hjSeedInt(g, 7, HJ_PARTICLE_MAX);
  hjAttractorCount = (uint8_t)hjSeedInt(g, 1, HJ_ATTRACTOR_MAX);
  hjParticleDamping = hjSeedFloat(g, 0.965f, 0.997f);
  hjParticleGravity = hjSeedFloat(g, 0.018f, 0.105f);
  hjParticleOrbit = hjSeedFloat(g, -0.055f, 0.055f);
  hjParticleLinkDistance = hjSeedFloat(g, 9.0f, 29.0f);
  hjParticleLinks = hjSeedInt(g,0,3) != 0;
  hjParticleWrap = hjSeedInt(g,0,1) != 0;
  hjParticleRepel = hjSeedInt(g,0,4) == 0;

  for (uint8_t i=0; i<hjAttractorCount; ++i) {
    hjAttractors[i].x = hjSeedFloat(g, 24.0f, 104.0f);
    hjAttractors[i].y = hjSeedFloat(g, 13.0f, 51.0f);
    hjAttractors[i].strength = hjSeedFloat(g, 0.65f, 1.55f);
    if (hjSeedInt(g,0,5)==0) hjAttractors[i].strength *= -1.0f;
  }

  for (uint8_t i=0; i<hjParticleCount; ++i) {
    hjParticles[i].x = hjSeedFloat(g, 2.0f, 125.0f);
    hjParticles[i].y = hjSeedFloat(g, 2.0f, 61.0f);
    hjParticles[i].vx = hjSeedFloat(g, -0.72f, 0.72f);
    hjParticles[i].vy = hjSeedFloat(g, -0.54f, 0.54f);
  }
  hjArtStep = 0;
}

static void hjParticleStepOnce() {
  float t = (float)hjArtStep * 0.012f;

  // Let attractors breathe/orbit slightly so a generated universe evolves.
  for (uint8_t a=0; a<hjAttractorCount; ++a) {
    float phase = (float)(a+1) * 2.17f + (float)(hjParticleSeed & 255U) * 0.009f;
    float ax = hjAttractors[a].x + sinf(t*(0.33f + 0.08f*a) + phase) * (3.0f + 2.0f*a);
    float ay = hjAttractors[a].y + cosf(t*(0.27f + 0.06f*a) - phase) * (2.0f + 1.5f*a);

    for (uint8_t i=0; i<hjParticleCount; ++i) {
      float dx = ax - hjParticles[i].x;
      float dy = ay - hjParticles[i].y;
      float d2 = dx*dx + dy*dy + 10.0f;
      float inv = 1.0f / sqrtf(d2);
      float force = hjParticleGravity * hjAttractors[a].strength * inv;
      if (hjParticleRepel) force = -force;
      hjParticles[i].vx += dx * inv * force;
      hjParticles[i].vy += dy * inv * force;

      // Perpendicular component produces orbit/slingshot behavior.
      hjParticles[i].vx += -dy * inv * hjParticleOrbit * hjAttractors[a].strength;
      hjParticles[i].vy +=  dx * inv * hjParticleOrbit * hjAttractors[a].strength;
    }
  }

  for (uint8_t i=0; i<hjParticleCount; ++i) {
    hjParticles[i].vx *= hjParticleDamping;
    hjParticles[i].vy *= hjParticleDamping;
    hjParticles[i].x += hjParticles[i].vx;
    hjParticles[i].y += hjParticles[i].vy;

    // Keep the tiny universe numerically calm.
    if (hjParticles[i].vx > 2.2f) hjParticles[i].vx = 2.2f;
    if (hjParticles[i].vx < -2.2f) hjParticles[i].vx = -2.2f;
    if (hjParticles[i].vy > 1.7f) hjParticles[i].vy = 1.7f;
    if (hjParticles[i].vy < -1.7f) hjParticles[i].vy = -1.7f;

    if (hjParticleWrap) {
      if (hjParticles[i].x < 0) hjParticles[i].x += 128.0f;
      if (hjParticles[i].x >= 128) hjParticles[i].x -= 128.0f;
      if (hjParticles[i].y < 0) hjParticles[i].y += 64.0f;
      if (hjParticles[i].y >= 64) hjParticles[i].y -= 64.0f;
    } else {
      if (hjParticles[i].x < 1) { hjParticles[i].x=1; hjParticles[i].vx=fabsf(hjParticles[i].vx); }
      if (hjParticles[i].x > 126) { hjParticles[i].x=126; hjParticles[i].vx=-fabsf(hjParticles[i].vx); }
      if (hjParticles[i].y < 1) { hjParticles[i].y=1; hjParticles[i].vy=fabsf(hjParticles[i].vy); }
      if (hjParticles[i].y > 62) { hjParticles[i].y=62; hjParticles[i].vy=-fabsf(hjParticles[i].vy); }
    }
  }
}

static void oledRenderSaverParticles() {
  float link2 = hjParticleLinkDistance * hjParticleLinkDistance;

  if (hjParticleLinks) {
    for (uint8_t i=0; i<hjParticleCount; ++i) {
      for (uint8_t j=i+1; j<hjParticleCount; ++j) {
        float dx=hjParticles[j].x-hjParticles[i].x;
        float dy=hjParticles[j].y-hjParticles[i].y;
        float d2=dx*dx+dy*dy;
        if (d2 < link2) {
          oled->drawLine((int)hjParticles[i].x,(int)hjParticles[i].y,
                         (int)hjParticles[j].x,(int)hjParticles[j].y);
        }
      }
    }
  }

  for (uint8_t i=0; i<hjParticleCount; ++i) {
    int x=(int)hjParticles[i].x, y=(int)hjParticles[i].y;
    if ((i + hjArtStep/10U) % 5U == 0) oled->drawDisc(x,y,1,U8G2_DRAW_ALL);
    else oled->drawPixel(x,y);
  }

  // Tiny attractor markers make gravity wells visible without dominating art.
  for (uint8_t a=0; a<hjAttractorCount; ++a) {
    int x=(int)hjAttractors[a].x, y=(int)hjAttractors[a].y;
    if (hjAttractors[a].strength >= 0) oled->drawCircle(x,y,2,U8G2_DRAW_ALL);
    else { oled->drawPixel(x-1,y); oled->drawPixel(x+1,y); oled->drawPixel(x,y-1); oled->drawPixel(x,y+1); }
  }
}
'''
s = s.replace(reseed_marker, reseed_marker + particle_code, 1)

old_render = '''static void oledRenderScreensaver() {
  switch (hjScreensaverMode) {
    case 0: oledRenderSaverSayings(); break;
    case 1: oledRenderSaverSpiral(); break;
    default: oledRenderSaverTrippy(); break;
  }
}
'''
new_render = '''static void oledRenderScreensaver() {
  switch (hjScreensaverMode) {
    case 0: oledRenderSaverSayings(); break;
    case 1: oledRenderSaverSpiral(); break;
    case 2: oledRenderSaverTrippy(); break;
    default: oledRenderSaverParticles(); break;
  }
}
'''
if old_render not in s:
    raise SystemExit("particle universe patch failed: saver renderer switch not found")
s = s.replace(old_render, new_render, 1)

old_step = '''    if (hjScreensaverMode == 0) hjMarqueeX -= 2;
    else if (hjScreensaverMode == 1) hjArtStep += hjSpiralSpeed;
    else hjArtStep += hjTrippySpeed;
'''
new_step = '''    if (hjScreensaverMode == 0) hjMarqueeX -= 2;
    else if (hjScreensaverMode == 1) hjArtStep += hjSpiralSpeed;
    else if (hjScreensaverMode == 2) hjArtStep += hjTrippySpeed;
    else {
      for (uint8_t ps=0; ps<hjParticleSpeed; ++ps) hjParticleStepOnce();
      hjArtStep++;
    }
'''
if old_step not in s:
    raise SystemExit("particle universe patch failed: animation step block not found")
s = s.replace(old_step, new_step, 1)

old_input_tail = '''    } else if (hjScreensaverMode == 2) {
      if (q[IN_UP] && !latched[IN_UP]) { if (hjTrippySpeed < 8) hjTrippySpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjTrippySpeed > 1) hjTrippySpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjReseedTrippy(); }
    }

    // While the saver owns the screen, do not run HOME/menu actions.
'''
new_input_tail = '''    } else if (hjScreensaverMode == 2) {
      if (q[IN_UP] && !latched[IN_UP]) { if (hjTrippySpeed < 8) hjTrippySpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjTrippySpeed > 1) hjTrippySpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjReseedTrippy(); }
    } else if (hjScreensaverMode == 3) {
      if (q[IN_UP] && !latched[IN_UP]) { if (hjParticleSpeed < 8) hjParticleSpeed++; }
      else if (q[IN_DOWN] && !latched[IN_DOWN]) { if (hjParticleSpeed > 1) hjParticleSpeed--; }
      else if (q[IN_A] && !latched[IN_A]) { hjReseedParticles(); }
    }

    // While the saver owns the screen, do not run HOME/menu actions.
'''
if old_input_tail not in s:
    raise SystemExit("particle universe patch failed: saver input block not found")
s = s.replace(old_input_tail, new_input_tail, 1)

# Physical LEFT/RIGHT calls the base next/prev helpers. Make entering PARTICLES
# immediately create a fresh board-seeded universe rather than reusing boot state.
for fn in ('hjScreensaverNext', 'hjScreensaverPrev'):
    marker = f'''static void {fn}() {{\n'''
    pos = s.find(marker)
    if pos < 0:
        raise SystemExit(f"particle universe patch failed: {fn} not found")
    end = s.find('\n}', pos)
    if end < 0:
        raise SystemExit(f"particle universe patch failed: {fn} end not found")
    body = s[pos:end]
    target = '  hjArtStep = 0;'
    if target not in body:
        raise SystemExit(f"particle universe patch failed: {fn} reset point not found")
    body = body.replace(target, target + '\n  if (hjScreensaverMode == 3) hjReseedParticles();', 1)
    s = s[:pos] + body + s[end:]

p.write_text(s, encoding="utf-8")
