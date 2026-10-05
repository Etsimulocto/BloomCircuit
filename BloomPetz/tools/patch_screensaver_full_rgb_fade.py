#!/usr/bin/env python3
"""Replace BloomPetz screensaver fixed-palette flashes with full-range RGB fades.

Requires the current proven HAPPY JARZ RMT screensaver layer.
Behavior:
- two APA106 bulbs on GPIO7
- each bulb independently crossfades through random 24-bit RGB targets
- 25% screensaver brightness cap remains unchanged
- no hard color pops/flashes
- uses the existing bloomSaverWriteFrame() proven RMT transport
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_SCREENSAVER_FULL_RGB_FADE_V1"
RMT_MARKER = "// BLOOMPETZ_SCREENSAVER_RMT_FIX_V1"
SERVICE_NAME = "static void serviceBloomSaverLights()"


def brace_block(text: str, start: int):
    op = text.find('{', start)
    if op < 0:
        raise SystemExit("opening brace not found")
    depth = 0
    in_string = False
    esc = False
    for i in range(op, len(text)):
        ch = text[i]
        if in_string:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit("unbalanced brace block")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_screensaver_full_rgb_fade.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Full-RGB screensaver fade already applied.")
        return
    if RMT_MARKER not in s:
        raise SystemExit("Proven RMT screensaver layer not found; refusing to guess")
    if "bloomSaverWriteFrame(" not in s:
        raise SystemExit("bloomSaverWriteFrame() not found")
    if "BLOOMPETZ_SAVER_LED_PERCENT" not in s:
        raise SystemExit("25% saver brightness constant not found")

    # Replace the old random-palette helper if present with fade-state helpers.
    random_fn = s.find("static BloomSaverRgb bloomSaverRandomColorRmt()")
    service_fn = s.find(SERVICE_NAME)
    if service_fn < 0:
        raise SystemExit("serviceBloomSaverLights() not found")

    if random_fn >= 0 and random_fn < service_fn:
        _, rand_end = brace_block(s, random_fn)
        s = s[:random_fn] + s[rand_end:]
        service_fn = s.find(SERVICE_NAME)

    # Replace the complete existing service function.
    _, service_end = brace_block(s, service_fn)

    block = r'''// BLOOMPETZ_SCREENSAVER_FULL_RGB_FADE_V1
static BloomSaverRgb bloomSaverFadeFrom[BLOOMPETZ_LED_COUNT] = {{0,0,0},{0,0,0}};
static BloomSaverRgb bloomSaverFadeTo[BLOOMPETZ_LED_COUNT] = {{0,0,0},{0,0,0}};
static BloomSaverRgb bloomSaverFadeNow[BLOOMPETZ_LED_COUNT] = {{0,0,0},{0,0,0}};
static unsigned long bloomSaverFadeStartMs = 0;
static unsigned long bloomSaverFadeDurationMs = 2200UL;
static unsigned long bloomSaverFadeLastFrameMs = 0;
static bool bloomSaverFadePrimed = false;

static BloomSaverRgb bloomSaverAnyRgb() {
  // Full 24-bit RGB space: 256^3 = 16,777,216 possible RGB triplets.
  // Reject only extremely dark targets so a 25% capped saver remains visible.
  BloomSaverRgb c;
  do {
    c = {(uint8_t)random(256), (uint8_t)random(256), (uint8_t)random(256)};
  } while ((uint16_t)c.r + c.g + c.b < 96U);
  return c;
}

static uint8_t bloomSaverLerp8(uint8_t a, uint8_t b, uint16_t step, uint16_t steps) {
  if (steps == 0 || step >= steps) return b;
  int16_t delta = (int16_t)b - (int16_t)a;
  return (uint8_t)((int16_t)a + (delta * (int32_t)step) / (int32_t)steps);
}

static void bloomSaverChooseFadeTargets(unsigned long now) {
  for (uint8_t i=0; i<BLOOMPETZ_LED_COUNT; ++i) {
    bloomSaverFadeFrom[i] = bloomSaverFadeNow[i];
    bloomSaverFadeTo[i] = bloomSaverAnyRgb();
  }
  bloomSaverFadeStartMs = now;
  bloomSaverFadeDurationMs = (unsigned long)random(1800, 5201);
}

static void serviceBloomSaverLights() {
  if (uiMode != SCREEN_SAVER || !bloomSaverRmtReady) return;

  unsigned long now = millis();
  if (!bloomSaverFadePrimed) {
    for (uint8_t i=0; i<BLOOMPETZ_LED_COUNT; ++i) {
      bloomSaverFadeNow[i] = bloomSaverAnyRgb();
      bloomSaverFadeFrom[i] = bloomSaverFadeNow[i];
      bloomSaverFadeTo[i] = bloomSaverAnyRgb();
    }
    bloomSaverFadeStartMs = now;
    bloomSaverFadeDurationMs = (unsigned long)random(1800, 5201);
    bloomSaverFadeLastFrameMs = 0;
    bloomSaverFadePrimed = true;
  }

  // Similar cadence to HAPPY JARZ FADE/RAINBOW engines; smooth without wasting cycles.
  if (now - bloomSaverFadeLastFrameMs < 28UL) return;
  bloomSaverFadeLastFrameMs = now;

  unsigned long elapsed = now - bloomSaverFadeStartMs;
  if (elapsed >= bloomSaverFadeDurationMs) {
    for (uint8_t i=0; i<BLOOMPETZ_LED_COUNT; ++i) bloomSaverFadeNow[i] = bloomSaverFadeTo[i];
    bloomSaverChooseFadeTargets(now);
    elapsed = 0;
  }

  const uint16_t steps = 1000U;
  uint16_t step = (uint16_t)min((unsigned long)steps,
      (elapsed * (unsigned long)steps) / max(1UL, bloomSaverFadeDurationMs));

  BloomSaverRgb frame[BLOOMPETZ_LED_COUNT];
  for (uint8_t i=0; i<BLOOMPETZ_LED_COUNT; ++i) {
    frame[i].r = bloomSaverLerp8(bloomSaverFadeFrom[i].r, bloomSaverFadeTo[i].r, step, steps);
    frame[i].g = bloomSaverLerp8(bloomSaverFadeFrom[i].g, bloomSaverFadeTo[i].g, step, steps);
    frame[i].b = bloomSaverLerp8(bloomSaverFadeFrom[i].b, bloomSaverFadeTo[i].b, step, steps);
    bloomSaverFadeNow[i] = frame[i];
  }

  bloomSaverWriteFrame(frame, BLOOMPETZ_SAVER_LED_PERCENT);
}
'''

    s = s[:service_fn] + block + s[service_end:]

    # Reset fade state whenever the saver lights are explicitly shut off.
    off_fn = s.find("static void bloomSaverLightsOff()")
    if off_fn < 0:
        raise SystemExit("bloomSaverLightsOff() not found")
    _, off_end = brace_block(s, off_fn)
    off_block = s[off_fn:off_end]
    if "bloomSaverFadePrimed = false;" not in off_block:
        close = off_block.rfind('}')
        off_block = off_block[:close] + "  bloomSaverFadePrimed = false;\n" + off_block[close:]
        s = s[:off_fn] + off_block + s[off_end:]

    p.write_text(s)
    print(f"Full-RGB screensaver fade applied to {p}")
    print("Two APA106 bulbs now independently crossfade through random 24-bit RGB targets.")
    print("Screensaver brightness cap remains 25%; proven HAPPY JARZ RMT transport unchanged.")


if __name__ == "__main__":
    main()
