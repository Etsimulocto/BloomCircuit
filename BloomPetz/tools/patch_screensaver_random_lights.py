#!/usr/bin/env python3
"""Add random two-APA106 light twinkles to the existing BloomPetz screensaver.

Targets the current local firmware after patch_idle_kaomoji_screensaver.py.
Uses two APA106 LEDs on GPIO7 through Adafruit_NeoPixel. Lights animate only
while SCREEN_SAVER is active and are cleared immediately when any input wakes it.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_SCREENSAVER_RANDOM_LIGHTS_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_screensaver_random_lights.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Screensaver random lights already applied.")
        return

    required = [
        "BLOOMPETZ_IDLE_KAOMOJI_SCREENSAVER_V1",
        "SCREEN_SAVER",
        "static void serviceBloomSaver()",
        "static void handleInput(Input in)",
        "void setup()",
    ]
    missing = [x for x in required if x not in s]
    if missing:
        raise SystemExit("Required current screensaver anchors missing: " + ", ".join(missing))

    # Add NeoPixel include once.
    if "#include <Adafruit_NeoPixel.h>" not in s:
        inc = re.search(r"(?:#include[^\n]*\n)+", s)
        if not inc:
            raise SystemExit("Could not locate include block")
        s = s[:inc.end()] + "#include <Adafruit_NeoPixel.h>\n" + s[inc.end():]

    # Add light engine immediately before the existing screensaver constants.
    anchor = "static constexpr unsigned long BLOOMPETZ_SAVER_IDLE_MS = 30000UL;"
    if anchor not in s:
        raise SystemExit("Screensaver constant anchor missing")

    block = r'''// BLOOMPETZ_SCREENSAVER_RANDOM_LIGHTS_V1
static constexpr uint8_t BLOOMPETZ_SAVER_LED_PIN = 7;
static constexpr uint8_t BLOOMPETZ_SAVER_LED_COUNT = 2;
static Adafruit_NeoPixel bloomSaverPixels(
  BLOOMPETZ_SAVER_LED_COUNT,
  BLOOMPETZ_SAVER_LED_PIN,
  NEO_RGB + NEO_KHZ800
);
static unsigned long bloomSaverNextLightMs = 0;
static uint8_t bloomSaverLightBrightness = 42;

static uint32_t bloomSaverRandomColor() {
  // Favor colorful low-power twinkles instead of white flashes.
  uint8_t mode = random(0, 6);
  uint8_t hi = random(35, 120);
  uint8_t lo = random(0, 28);
  switch (mode) {
    case 0: return bloomSaverPixels.Color(hi, lo, lo);
    case 1: return bloomSaverPixels.Color(lo, hi, lo);
    case 2: return bloomSaverPixels.Color(lo, lo, hi);
    case 3: return bloomSaverPixels.Color(hi, hi/2, lo);
    case 4: return bloomSaverPixels.Color(lo, hi/2, hi);
    default:return bloomSaverPixels.Color(hi, lo, hi/2);
  }
}

static void bloomSaverLightsOff() {
  bloomSaverPixels.clear();
  bloomSaverPixels.show();
  bloomSaverNextLightMs = 0;
}

static void serviceBloomSaverLights() {
  if (uiMode != SCREEN_SAVER) return;
  unsigned long now = millis();
  if (bloomSaverNextLightMs != 0 && now < bloomSaverNextLightMs) return;

  // New random tableau every 180-850ms. Sometimes one LED, sometimes both,
  // sometimes a short dark beat so the pattern breathes.
  uint8_t scene = random(0, 8);
  bloomSaverPixels.clear();

  if (scene != 0) {
    if (scene == 1 || scene == 2) {
      uint8_t which = random(0, BLOOMPETZ_SAVER_LED_COUNT);
      bloomSaverPixels.setPixelColor(which, bloomSaverRandomColor());
    } else if (scene == 3) {
      uint32_t c = bloomSaverRandomColor();
      bloomSaverPixels.setPixelColor(0, c);
      bloomSaverPixels.setPixelColor(1, c);
    } else {
      bloomSaverPixels.setPixelColor(0, bloomSaverRandomColor());
      bloomSaverPixels.setPixelColor(1, bloomSaverRandomColor());
    }
  }

  bloomSaverPixels.setBrightness(bloomSaverLightBrightness);
  bloomSaverPixels.show();
  bloomSaverNextLightMs = now + (unsigned long)random(180, 851);
}

'''
    s = s.replace(anchor, block + anchor, 1)

    # Initialize the LED chain near the start of setup().
    setup_anchor = "void setup() {"
    setup_insert = "\n  bloomSaverPixels.begin();\n  bloomSaverPixels.setBrightness(bloomSaverLightBrightness);\n  bloomSaverLightsOff();"
    s = s.replace(setup_anchor, setup_anchor + setup_insert, 1)

    # When the saver starts, allow the first light scene immediately.
    enter_anchor = "    bloomSaverNextBlinkMs = now + random(1200, 3600);\n    drawBloomSaver();"
    if enter_anchor not in s:
        raise SystemExit("Screensaver entry block not found")
    s = s.replace(
        enter_anchor,
        "    bloomSaverNextBlinkMs = now + random(1200, 3600);\n"
        "    bloomSaverNextLightMs = 0;\n"
        "    drawBloomSaver();\n"
        "    serviceBloomSaverLights();",
        1,
    )

    # Keep light animation independent from OLED frame timing.
    saver_active_anchor = "  if (uiMode != SCREEN_SAVER) return;\n"
    if saver_active_anchor not in s:
        raise SystemExit("Active saver guard not found")
    s = s.replace(
        saver_active_anchor,
        saver_active_anchor + "\n  serviceBloomSaverLights();\n",
        1,
    )

    # Any input wakes the saver and immediately extinguishes its light scene.
    wake_old = "  if (uiMode == SCREEN_SAVER) { uiMode = HOME; drawHome(); return; }"
    if wake_old not in s:
        raise SystemExit("Screensaver wake handler not found")
    wake_new = "  if (uiMode == SCREEN_SAVER) { bloomSaverLightsOff(); uiMode = HOME; drawHome(); return; }"
    s = s.replace(wake_old, wake_new, 1)

    p.write_text(s)
    print(f"Random screensaver lights applied to {p}")
    print("Two APA106 LEDs on GPIO7 now twinkle in random colors only during SCREEN_SAVER.")
    print("Any wake input clears both LEDs immediately before returning HOME.")


if __name__ == "__main__":
    main()
