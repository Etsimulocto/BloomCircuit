#!/usr/bin/env python3
"""Add animated vertical side-art lanes to the working BloomPetz OLED firmware.

Assumes the current local sketch already has the proven U8g2 OLED integration
using a global object named `oled` and `physicalOledRender(...)`.

Adds two narrow ~12 px decorative lanes at the extreme left/right edges.
Particles scroll vertically, respawn with randomized x/y/shape, and redraw on a
~120 ms timer without changing the mirrored text protocol.
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_SIDE_SCROLL_ART_V1"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_side_scroll_art.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Side-scroll art already applied.")
        return

    if "U8G2" not in s or "oled." not in s:
        raise SystemExit("Known-good U8g2 OLED layer not found in this local sketch. Refusing to guess.")

    anchor = 'static String screenLines[4] = {"", "", "", ""};\n'
    if anchor not in s:
        raise SystemExit("screenLines anchor not found")

    block = r'''

// BLOOMPETZ_SIDE_SCROLL_ART_V1
// Keep the center text region untouched. Decorative art lives only in the
// outer 12-pixel lanes: x=0..11 and x=116..127.
struct SideParticle {
  int8_t x;
  int8_t y;
  uint8_t speed;
  uint8_t shape;
};

static constexpr uint8_t SIDE_PARTICLE_COUNT = 8;
static SideParticle sideLeft[SIDE_PARTICLE_COUNT];
static SideParticle sideRight[SIDE_PARTICLE_COUNT];
static unsigned long lastSideArtMs = 0;
static bool sideArtReady = false;

static void randomizeSideParticle(SideParticle &p, bool rightSide, bool startAnywhere) {
  p.x = rightSide ? (int8_t)random(117, 127) : (int8_t)random(1, 11);
  p.y = startAnywhere ? (int8_t)random(0, 64) : (int8_t)random(-18, -1);
  p.speed = (uint8_t)random(1, 4);
  p.shape = (uint8_t)random(0, 5);
}

static void initSideArt() {
  for (uint8_t i=0; i<SIDE_PARTICLE_COUNT; ++i) {
    randomizeSideParticle(sideLeft[i], false, true);
    randomizeSideParticle(sideRight[i], true, true);
  }
  sideArtReady = true;
}

static void stepSideArt() {
  if (!sideArtReady) initSideArt();
  for (uint8_t i=0; i<SIDE_PARTICLE_COUNT; ++i) {
    sideLeft[i].y += sideLeft[i].speed;
    sideRight[i].y += sideRight[i].speed;
    if (sideLeft[i].y > 66) randomizeSideParticle(sideLeft[i], false, false);
    if (sideRight[i].y > 66) randomizeSideParticle(sideRight[i], true, false);
  }
}

static void drawOneSideParticle(const SideParticle &p) {
  int x = p.x;
  int y = p.y;
  if (y < -3 || y > 66) return;
  switch (p.shape) {
    case 0: oled.drawPixel(x, y); break;
    case 1:
      oled.drawPixel(x, y);
      oled.drawPixel(x-1, y);
      oled.drawPixel(x+1, y);
      oled.drawPixel(x, y-1);
      oled.drawPixel(x, y+1);
      break;
    case 2: oled.drawCircle(x, y, 1); break;
    case 3:
      oled.drawPixel(x, y);
      oled.drawPixel(x-1, y-1);
      oled.drawPixel(x+1, y+1);
      break;
    default:
      oled.drawPixel(x, y);
      oled.drawPixel(x+1, y);
      oled.drawPixel(x, y+1);
      oled.drawPixel(x+1, y+1);
      break;
  }
}

static void drawSideArt() {
  if (!sideArtReady) initSideArt();
  for (uint8_t i=0; i<SIDE_PARTICLE_COUNT; ++i) {
    drawOneSideParticle(sideLeft[i]);
    drawOneSideParticle(sideRight[i]);
  }
}
'''
    s = s.replace(anchor, anchor + block, 1)

    # Insert art after the text is drawn but before the framebuffer is sent.
    send_anchor = "  oled.sendBuffer();"
    if send_anchor not in s:
        raise SystemExit("oled.sendBuffer() not found in the known-good renderer")
    s = s.replace(send_anchor, "  drawSideArt();\n" + send_anchor, 1)

    # Refresh the physical display on a timer without emitting BP|SCREEN spam.
    loop_anchor = "void loop() {\n  serviceSerial();"
    if loop_anchor not in s:
        raise SystemExit("loop anchor not found")
    replacement = '''void loop() {
  serviceSerial();
  if (millis() - lastSideArtMs >= 120) {
    lastSideArtMs = millis();
    stepSideArt();
    physicalOledRender(screenLines[0], screenLines[1], screenLines[2], screenLines[3]);
  }'''
    s = s.replace(loop_anchor, replacement, 1)

    p.write_text(s)
    print(f"Side-scroll art applied to {p}")
    print("Two 12px side lanes, 8 particles per side, ~120ms vertical animation.")


if __name__ == "__main__":
    main()
