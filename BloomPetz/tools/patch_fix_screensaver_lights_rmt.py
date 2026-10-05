#!/usr/bin/env python3
"""Replace the BloomPetz screensaver NeoPixel driver with the known-good HAPPY JARZ APA106 RMT layer.

Why:
- the previous screensaver-light patch used Adafruit_NeoPixel
- the HAPPY JARZ bench firmware explicitly preserves a proven low-level APA106 transport:
  GPIO7, ESP32 HAL RMT at 10 MHz, RGB byte order, 0=4/14 ticks, 1=14/4 ticks,
  100 us LOW latch/reset

This patch keeps the existing screensaver calls/function names so the current UI flow
stays intact, but swaps the hardware transport underneath them.

Brightness policy:
- normal BloomPetz light ceiling: 50%
- screensaver light brightness: 25%
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_SCREENSAVER_RMT_FIX_V1"
OLD_MARKER = "// BLOOMPETZ_SCREENSAVER_RANDOM_LIGHTS_V1"
SAVER_ANCHOR = "static constexpr unsigned long BLOOMPETZ_SAVER_IDLE_MS = 30000UL;"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_fix_screensaver_lights_rmt.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Screensaver RMT light fix already applied.")
        return

    if OLD_MARKER not in s:
        raise SystemExit("Old NeoPixel screensaver-light patch not found; refusing to guess")
    if SAVER_ANCHOR not in s:
        raise SystemExit("Screensaver anchor not found")

    # Remove the generic NeoPixel include; the proven HAPPY JARZ path uses ESP32 HAL RMT.
    s = s.replace("#include <Adafruit_NeoPixel.h>\n", "")
    if '#include "esp32-hal-rmt.h"' not in s:
        inc = re.search(r"(?:#include[^\n]*\n)+", s)
        if not inc:
            raise SystemExit("Include block not found")
        s = s[:inc.end()] + '#include "esp32-hal-rmt.h"\n' + s[inc.end():]

    # Replace the entire old light-engine block, preserving the function names
    # already called by the screensaver entry/service/wake code.
    start = s.find(OLD_MARKER)
    end = s.find(SAVER_ANCHOR, start)
    if start < 0 or end < 0:
        raise SystemExit("Could not locate old screensaver light block")

    block = r'''// BLOOMPETZ_SCREENSAVER_RMT_FIX_V1
// Proven HAPPY JARZ APA106 transport. Preserve this hardware layer.
static constexpr uint8_t BLOOMPETZ_LED_DATA_PIN = 7;
static constexpr uint8_t BLOOMPETZ_LED_COUNT = 2;
static constexpr uint8_t BLOOMPETZ_LED_NORMAL_MAX_PERCENT = 50;
static constexpr uint8_t BLOOMPETZ_SAVER_LED_PERCENT = 25;

struct BloomSaverRgb { uint8_t r, g, b; };
static unsigned long bloomSaverNextLightMs = 0;
static bool bloomSaverRmtReady = false;

static bool bloomSaverInitApa106Rmt() {
  pinMode(BLOOMPETZ_LED_DATA_PIN, OUTPUT);
  digitalWrite(BLOOMPETZ_LED_DATA_PIN, LOW);
  if (!rmtInit(BLOOMPETZ_LED_DATA_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) return false;
  rmtSetEOT(BLOOMPETZ_LED_DATA_PIN, 0);
  return true;
}

static void bloomSaverWriteFrame(const BloomSaverRgb frame[BLOOMPETZ_LED_COUNT], uint8_t brightnessPercent) {
  if (!bloomSaverRmtReady) return;
  brightnessPercent = constrain(brightnessPercent, (uint8_t)0, (uint8_t)100);

  rmt_data_t symbols[BLOOMPETZ_LED_COUNT * 24];
  size_t n = 0;

  for (uint8_t led = 0; led < BLOOMPETZ_LED_COUNT; ++led) {
    // Proven physical APA106 byte order is RGB.
    uint8_t bytes[3] = {
      (uint8_t)((uint16_t)frame[led].r * brightnessPercent / 100U),
      (uint8_t)((uint16_t)frame[led].g * brightnessPercent / 100U),
      (uint8_t)((uint16_t)frame[led].b * brightnessPercent / 100U)
    };

    for (uint8_t c = 0; c < 3; ++c) {
      for (int bit = 7; bit >= 0; --bit) {
        bool one = bytes[c] & (1U << bit);
        symbols[n].level0 = 1;
        symbols[n].duration0 = one ? 14 : 4;
        symbols[n].level1 = 0;
        symbols[n].duration1 = one ? 4 : 14;
        ++n;
      }
    }
  }

  rmtWrite(BLOOMPETZ_LED_DATA_PIN, symbols, n, RMT_WAIT_FOR_EVER);
  digitalWrite(BLOOMPETZ_LED_DATA_PIN, LOW);
  delayMicroseconds(100);
}

static BloomSaverRgb bloomSaverRandomColorRmt() {
  // Saturated colors at full logical RGB; writeFrame applies the 25% saver cap.
  switch (random(0, 8)) {
    case 0: return {255, 0, 0};
    case 1: return {255, 70, 0};
    case 2: return {255, 180, 0};
    case 3: return {80, 255, 0};
    case 4: return {0, 255, 90};
    case 5: return {0, 180, 255};
    case 6: return {40, 40, 255};
    default:return {180, 0, 255};
  }
}

static void bloomSaverLightsOff() {
  BloomSaverRgb off[BLOOMPETZ_LED_COUNT] = {{0,0,0},{0,0,0}};
  bloomSaverWriteFrame(off, 100);
  bloomSaverNextLightMs = 0;
}

static void serviceBloomSaverLights() {
  if (uiMode != SCREEN_SAVER || !bloomSaverRmtReady) return;

  unsigned long now = millis();
  if (bloomSaverNextLightMs != 0 && now < bloomSaverNextLightMs) return;

  BloomSaverRgb frame[BLOOMPETZ_LED_COUNT] = {{0,0,0},{0,0,0}};
  uint8_t scene = random(0, 9);

  // A little breathing room: scene 0 is dark.
  if (scene != 0) {
    if (scene <= 2) {
      frame[random(0, BLOOMPETZ_LED_COUNT)] = bloomSaverRandomColorRmt();
    } else if (scene == 3 || scene == 4) {
      BloomSaverRgb c = bloomSaverRandomColorRmt();
      frame[0] = c;
      frame[1] = c;
    } else {
      frame[0] = bloomSaverRandomColorRmt();
      frame[1] = bloomSaverRandomColorRmt();
    }
  }

  bloomSaverWriteFrame(frame, BLOOMPETZ_SAVER_LED_PERCENT);
  bloomSaverNextLightMs = now + (unsigned long)random(260, 951);
}

'''
    s = s[:start] + block + s[end:]

    # Remove the previous NeoPixel setup calls and initialize the proven RMT layer instead.
    old_setup = (
        "  bloomSaverPixels.begin();\n"
        "  bloomSaverPixels.setBrightness(bloomSaverLightBrightness);\n"
        "  bloomSaverLightsOff();\n"
    )
    if old_setup in s:
        s = s.replace(old_setup, "", 1)
    else:
        # tolerate the exact same statements without the trailing newline
        s = s.replace("  bloomSaverPixels.begin();\n", "", 1)
        s = s.replace("  bloomSaverPixels.setBrightness(bloomSaverLightBrightness);\n", "", 1)
        s = s.replace("  bloomSaverLightsOff();\n", "", 1)

    setup_anchor = "void setup() {\n"
    if setup_anchor not in s:
        raise SystemExit("setup() anchor not found")
    setup_code = (
        "  bloomSaverRmtReady = bloomSaverInitApa106Rmt();\n"
        "  if (bloomSaverRmtReady) bloomSaverLightsOff();\n"
    )
    s = s.replace(setup_anchor, setup_anchor + setup_code, 1)

    # Make sure no NeoPixel object/API remains in the local sketch.
    leftovers = [
        "Adafruit_NeoPixel", "bloomSaverPixels.", "NEO_RGB", "NEO_KHZ800",
        "bloomSaverLightBrightness"
    ]
    bad = [x for x in leftovers if x in s]
    if bad:
        raise SystemExit("NeoPixel leftovers remain after repair: " + ", ".join(bad))

    p.write_text(s)
    print(f"Replaced screensaver LED driver with proven HAPPY JARZ RMT layer in {p}")
    print("APA106: GPIO7, RGB order, 10 MHz RMT, 4/14 + 14/4 timing, 100 us latch.")
    print("Screensaver brightness = 25%. Normal BloomPetz light ceiling = 50%.")
    print("The Adafruit_NeoPixel path has been removed from this sketch.")


if __name__ == "__main__":
    main()
