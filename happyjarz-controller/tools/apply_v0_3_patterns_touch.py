#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FW = ROOT / "happyjarz-controller" / "firmware" / "happyjarz_integrated_v0_1.ino"
APP = ROOT / "happyjarz-controller" / "happyjarz_controller.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"PATCH FAILED: could not find {label}")
    return text.replace(old, new, 1)


# ---- Firmware ---------------------------------------------------------------
s = FW.read_text()

s = replace_once(s,
    'static const char *HJ_FW_VERSION = "0.2";',
    'static const char *HJ_FW_VERSION = "0.3";',
    "firmware version")

old_random_anchor = '''  if (patternName == "RAINBOW") {
    if (now - patternLastMs < 35) return;
'''
new_random_anchor = '''  if (patternName == "RANDOM") {
    // Independent lively flashes: random lamp, random saturated-ish color,
    // random short pause. Non-blocking so touch + serial remain responsive.
    static unsigned long nextRandomMs = 0;
    static Rgb randomFrame[LED_COUNT] = {{0,0,0},{0,0,0}};

    if (now < nextRandomMs) return;

    uint8_t lamp = (uint8_t)random(0, LED_COUNT);
    uint8_t action = (uint8_t)random(0, 5);

    if (action == 0) {
      randomFrame[lamp] = {0, 0, 0};
    } else {
      Rgb c = wheel((uint8_t)random(0, 256));
      randomFrame[lamp] = c;
    }

    // Occasionally let the other lamp fall dark too; keeps it irregular.
    if (random(0, 7) == 0) {
      uint8_t other = (lamp + 1) % LED_COUNT;
      randomFrame[other] = {0, 0, 0};
    }

    writeFrame(randomFrame, brightnessPercent);
    nextRandomMs = now + (unsigned long)random(70, 360);
    return;
  }

  if (patternName == "RAINBOW") {
    if (now - patternLastMs < 35) return;
'''
s = replace_once(s, old_random_anchor, new_random_anchor, "RAINBOW pattern anchor")

s = replace_once(s,
    'if (!(name == "OFF" || name == "SOLID" || name == "FADE" || name == "RAINBOW" || name == "PULSE")) {',
    'if (!(name == "OFF" || name == "SOLID" || name == "FADE" || name == "RAINBOW" || name == "PULSE" || name == "RANDOM")) {',
    "pattern command validator")

old_touch = '''static int paletteIndex1 = 6;
static int paletteIndex2 = 4;
static uint8_t selectedLed = 1;
static bool latchC1 = false, latchC2 = false, latchUp = false, latchDown = false;

static void serviceLocalTouch() {
  bool c1 = qualifiedTouch(0);
  bool c2 = qualifiedTouch(1);
  bool up = qualifiedTouch(2);
  bool down = qualifiedTouch(3);

  if (c1 && !latchC1) selectedLed = 1;
  if (c2 && !latchC2) selectedLed = 2;

  if (up && !latchUp) {
    if (selectedLed == 1) {
      paletteIndex1 = (paletteIndex1 + 1) % (int)(sizeof(palette) / sizeof(palette[0]));
      Rgb c = palette[paletteIndex1];
      hjSetLed(1, c.r, c.g, c.b);
    } else {
      paletteIndex2 = (paletteIndex2 + 1) % (int)(sizeof(palette) / sizeof(palette[0]));
      Rgb c = palette[paletteIndex2];
      hjSetLed(2, c.r, c.g, c.b);
    }
  }

  if (down && !latchDown) {
    const int n = (int)(sizeof(palette) / sizeof(palette[0]));
    if (selectedLed == 1) {
      paletteIndex1 = (paletteIndex1 - 1 + n) % n;
      Rgb c = palette[paletteIndex1];
      hjSetLed(1, c.r, c.g, c.b);
    } else {
      paletteIndex2 = (paletteIndex2 - 1 + n) % n;
      Rgb c = palette[paletteIndex2];
      hjSetLed(2, c.r, c.g, c.b);
    }
  }

  latchC1 = c1;
  latchC2 = c2;
  latchUp = up;
  latchDown = down;
}
'''

new_touch = '''static int paletteIndex1 = 6;
static int paletteIndex2 = 4;
static bool latchC1 = false, latchC2 = false, latchUp = false, latchDown = false;

static const char *touchPatterns[] = {
  "SOLID", "FADE", "PULSE", "RAINBOW", "RANDOM", "OFF"
};
static const int touchPatternCount = sizeof(touchPatterns) / sizeof(touchPatterns[0]);

static int currentPatternIndex() {
  for (int i = 0; i < touchPatternCount; ++i) {
    if (patternName == touchPatterns[i]) return i;
  }
  return 0;
}

static void serviceLocalTouch() {
  bool c1 = qualifiedTouch(0);
  bool c2 = qualifiedTouch(1);
  bool up = qualifiedTouch(2);
  bool down = qualifiedTouch(3);

  // COLOR 1: Light 1 next color.
  if (c1 && !latchC1) {
    paletteIndex1 = (paletteIndex1 + 1) % (int)(sizeof(palette) / sizeof(palette[0]));
    Rgb c = palette[paletteIndex1];
    hjSetLed(1, c.r, c.g, c.b);
  }

  // COLOR 2: Light 2 next color.
  if (c2 && !latchC2) {
    paletteIndex2 = (paletteIndex2 + 1) % (int)(sizeof(palette) / sizeof(palette[0]));
    Rgb c = palette[paletteIndex2];
    hjSetLed(2, c.r, c.g, c.b);
  }

  // CYCLE UP/DOWN: move through scene patterns.
  if (up && !latchUp) {
    int i = (currentPatternIndex() + 1) % touchPatternCount;
    hjSetPattern(touchPatterns[i]);
  }

  if (down && !latchDown) {
    int i = (currentPatternIndex() - 1 + touchPatternCount) % touchPatternCount;
    hjSetPattern(touchPatterns[i]);
  }

  latchC1 = c1;
  latchC2 = c2;
  latchUp = up;
  latchDown = down;
}
'''

s = replace_once(s, old_touch, new_touch, "standalone touch control block")
FW.write_text(s)

# ---- Desktop/Pi controller --------------------------------------------------
a = APP.read_text()
a = a.replace('APP_VERSION = "0.2.1"', 'APP_VERSION = "0.2.2"', 1)
a = replace_once(a,
    'values=("OFF", "SOLID", "FADE", "RAINBOW", "PULSE"))',
    'values=("OFF", "SOLID", "FADE", "PULSE", "RAINBOW", "RANDOM"))',
    "controller pattern list")
APP.write_text(a)

print("HAPPY JARZ v0.3 patch applied")
print("Firmware:", FW)
print("Controller:", APP)
print("Touch map: COLOR1->Light1 color, COLOR2->Light2 color, UP/DOWN->patterns")
print("Patterns: SOLID, FADE, PULSE, RAINBOW, RANDOM, OFF")
