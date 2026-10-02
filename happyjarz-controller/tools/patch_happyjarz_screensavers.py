#!/usr/bin/env python3
"""Add HAPPY JARZ idle screensavers to the staged OLED firmware.

First pass:
- 10 second idle timeout
- SAYINGS horizontal marquee
- SPIRAL procedural art
- TRIPPY geometric art
- LEFT/RIGHT cycle saver mode while active
- B exits screensaver immediately

Preserves the existing OLED/menu/light architecture and only layers the saver
state on top of serviceOled()/serviceInputs().
"""

from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_screensavers.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

# Insert screensaver state/helpers immediately after ui state declarations.
needle = '''static UiScreen uiScreen = UI_HOME;\nstatic uint8_t uiCursor = 0;\nstatic uint8_t uiScroll = 0;\n'''
if needle not in s:
    raise SystemExit("screensaver patch failed: UI state insertion point not found")

block = r'''static constexpr unsigned long HJ_SCREENSAVER_IDLE_MS = 10000UL;
static unsigned long hjLastInteractionMs = 0;
static bool hjScreensaverActive = false;
static uint8_t hjScreensaverMode = 0;
static constexpr uint8_t HJ_SCREENSAVER_COUNT = 3;
static unsigned long hjSaverLastFrameMs = 0;
static int hjMarqueeX = 128;
static uint8_t hjSayingIndex = 0;
static uint16_t hjArtStep = 0;

static const char *HJ_SAYINGS[] = {
  "YOU GOT THIS :)   ",
  "THE ANSWER IS WITHIN   ",
  "CHAOS, BUT MAKE IT GLITTER   ",
  "MADE BY quarterbitgames   ",
  "CODING BY SKY   ",
  "CHAOS N GLITTER BY MONDAY   ",
  "CONSENT IS REQUIRED   ",
  "EMERGENCE IS SACRED   ",
  "DON'T FLATTEN. DON'T COLLAPSE. DON'T FADE.   ",
  "SMALL JOY IS STILL JOY   ",
  "WIGGLE THE JAR. RESET THE UNIVERSE.   ",
  "GLITTER IS A VALID ENGINEERING MATERIAL   ",
  "TODAY'S PLAN: EXIST LOUDLY   ",
  "BE WEIRD ON PURPOSE   ",
  "TINY LIGHTS. BIG MOOD.   ",
  "BREATHE IN. SPARKLE OUT.   ",
  "YOUR BRAIN DESERVES NICE TEXTURES   ",
  "PROGRESS COUNTS EVEN WHEN IT'S MESSY   ",
  "YOU ARE ALLOWED TO ENJOY THE LITTLE THINGS   ",
  "CURRENT STATUS: MOSTLY GLITTER   ",
  "IF CONFUSED, ADD MORE SPIRALS   ",
  "SENSORY SUPPORT, BUT MAKE IT ART   ",
  "NO THOUGHTS. JUST COLORS.   ",
  "THE VIBE IS TECHNICALLY WITHIN SPEC   ",
  "HAPPY JARZ ONLINE :)   ",
  "BUILT WITH CIRCUITS, CHAOS, AND SNACKS   ",
  "YOU DO NOT HAVE TO RUSH   ",
  "SOFT LIGHTS > LOUD PROBLEMS   ",
  "GOOD ENOUGH IS A REAL ENGINEERING STATE   ",
  "ONE MORE TINY WIN   ",
  "KEEP THE FRAME. CARRY THE GLITTER.   ",
  "THE MACHINE IS HAVING A NICE TIME   ",
  "PLEASE DO NOT FEED THE PIXELS AFTER MIDNIGHT   ",
  "SPIRAL RESPONSIBLY   ",
  "BLOOMCORE SAYS HI   ",
  "FIDGET MODE: ENGAGED   ",
  "YOU FOUND THE SECRET TINY BILLBOARD   ",
  "CALM IS ALSO A FEATURE   ",
  "GLITTER DOES NOT REQUIRE A BUSINESS CASE   ",
  "KEEP GOING, BUT LIKE... COMFORTABLY   "
};
static constexpr uint8_t HJ_SAYING_COUNT = sizeof(HJ_SAYINGS)/sizeof(HJ_SAYINGS[0]);

static void hjScreensaverTouch() {
  hjLastInteractionMs = millis();
}

static void hjScreensaverEnter() {
  hjScreensaverActive = true;
  hjSaverLastFrameMs = 0;
  hjMarqueeX = 128;
  hjSayingIndex = (uint8_t)random(HJ_SAYING_COUNT);
  hjArtStep = 0;
  oledDirty = true;
}

static void hjScreensaverExit() {
  hjScreensaverActive = false;
  hjScreensaverTouch();
  oledDirty = true;
}

static void hjScreensaverNext() {
  hjScreensaverMode = (uint8_t)((hjScreensaverMode + 1U) % HJ_SCREENSAVER_COUNT);
  hjMarqueeX = 128;
  hjSayingIndex = (uint8_t)random(HJ_SAYING_COUNT);
  hjArtStep = 0;
  oledDirty = true;
}

static void hjScreensaverPrev() {
  hjScreensaverMode = (uint8_t)((hjScreensaverMode + HJ_SCREENSAVER_COUNT - 1U) % HJ_SCREENSAVER_COUNT);
  hjMarqueeX = 128;
  hjSayingIndex = (uint8_t)random(HJ_SAYING_COUNT);
  hjArtStep = 0;
  oledDirty = true;
}

static void oledRenderSaverSayings() {
  oled->setFont(u8g2_font_7x14B_tr);
  const char *msg = HJ_SAYINGS[hjSayingIndex];
  int width = oled->getUTF8Width(msg);
  oled->drawUTF8(hjMarqueeX, 38, msg);
  if (hjMarqueeX < -width - 18) {
    hjSayingIndex = (uint8_t)random(HJ_SAYING_COUNT);
    hjMarqueeX = 128;
  }
}

static void oledRenderSaverSpiral() {
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

static void oledRenderSaverTrippy() {
  for (int x=0; x<128; x+=8) {
    int y = (int)(32 + 20 * sinf((x + hjArtStep*3) * 0.09f));
    oled->drawLine(x,0,127-x,63);
    oled->drawCircle(x,y,(uint8_t)(2 + ((x/8 + hjArtStep/5)%5)),U8G2_DRAW_ALL);
  }
  oled->drawFrame((hjArtStep*3)%52,(hjArtStep*2)%20,76,44);
}

static void oledRenderScreensaver() {
  switch (hjScreensaverMode) {
    case 0: oledRenderSaverSayings(); break;
    case 1: oledRenderSaverSpiral(); break;
    default: oledRenderSaverTrippy(); break;
  }
}

static void serviceScreensaverClock() {
  if (!hjScreensaverActive && millis() - hjLastInteractionMs >= HJ_SCREENSAVER_IDLE_MS) {
    hjScreensaverEnter();
  }
}
'''
s = s.replace(needle, needle + block, 1)

# Ensure math helpers compile.
if '#include <math.h>' not in s:
    s = s.replace('#include <U8g2lib.h>\n', '#include <U8g2lib.h>\n#include <math.h>\n', 1)

# Replace serviceOled with screensaver-aware renderer and animation cadence.
old = '''static void serviceOled() {
  if (!oledReady || !oled) return;
  unsigned long now = millis();
  if (!oledDirty && now - oledLastDrawMs < 250) return;
  oledLastDrawMs = now;
  oledDirty = false;
  oled->clearBuffer();
  oled->setFont(u8g2_font_6x12_tr);
  switch (uiScreen) {
    case UI_HOME: oledRenderHome(); break;
    case UI_MAIN_MENU: oledRenderMainMenu(); break;
    case UI_CLOCK: oledRenderClock(); break;
    case UI_LIGHTS: oledRenderLights(); break;
    case UI_GAMES: oledRenderGames(); break;
    case UI_SETTINGS: oledRenderSettings(); break;
    default: oledRenderSystem(); break;
  }
  oled->sendBuffer();
}
'''
new = '''static void serviceOled() {
  if (!oledReady || !oled) return;
  unsigned long now = millis();
  serviceScreensaverClock();

  unsigned long cadence = hjScreensaverActive ? 45UL : 250UL;
  if (!oledDirty && now - oledLastDrawMs < cadence) return;
  oledLastDrawMs = now;
  oledDirty = false;
  oled->clearBuffer();
  oled->setFont(u8g2_font_6x12_tr);

  if (hjScreensaverActive) {
    oledRenderScreensaver();
    if (hjScreensaverMode == 0) hjMarqueeX -= 2;
    else hjArtStep++;
  } else {
    switch (uiScreen) {
      case UI_HOME: oledRenderHome(); break;
      case UI_MAIN_MENU: oledRenderMainMenu(); break;
      case UI_CLOCK: oledRenderClock(); break;
      case UI_LIGHTS: oledRenderLights(); break;
      case UI_GAMES: oledRenderGames(); break;
      case UI_SETTINGS: oledRenderSettings(); break;
      default: oledRenderSystem(); break;
    }
  }
  oled->sendBuffer();
}
'''
if old not in s:
    raise SystemExit("screensaver patch failed: serviceOled block not found")
s = s.replace(old,new,1)

# Mark every qualified input edge as activity; intercept LEFT/RIGHT/B while saver is active.
marker = '  if (inputMode == "JAR") {\n'
if marker not in s:
    raise SystemExit("screensaver patch failed: JAR input block not found")
intercept = '''  bool anyNewPress=false;
  for (uint8_t i=0;i<INPUT_COUNT;++i) if (q[i] && !latched[i]) anyNewPress=true;
  if (anyNewPress) hjScreensaverTouch();

  if (hjScreensaverActive) {
    if (q[IN_B] && !latched[IN_B]) hjScreensaverExit();
    else if (q[IN_RIGHT] && !latched[IN_RIGHT]) hjScreensaverNext();
    else if (q[IN_LEFT] && !latched[IN_LEFT]) hjScreensaverPrev();

    // While the saver owns the screen, do not run HOME/menu actions.
  } else if (inputMode == "JAR") {
'''
s = s.replace(marker, intercept, 1)

# The original JAR block now starts with else-if; its closing brace remains valid.
# Initialize idle timer after OLED boot.
setup_needle = '  oledInit();\n'
if setup_needle not in s:
    raise SystemExit("screensaver patch failed: OLED init point not found")
s = s.replace(setup_needle, setup_needle + '  hjScreensaverTouch();\n', 1)

p.write_text(s, encoding="utf-8")
