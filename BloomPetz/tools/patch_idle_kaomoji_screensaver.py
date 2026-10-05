#!/usr/bin/env python3
"""Add 30s idle kaomoji screensaver to the current BloomPetz local sketch.

Behavior:
- activates after 30 seconds of no input while in HOME
- no pet name; only pet art/kaomoji is centered
- random ASCII drift fills all four OLED lines around the pet
- the pet art briefly mutates/blinks by swapping eye-like characters
- any input exits immediately to HOME and resets idle timer
- no pet stats/actions are changed

This patch targets the current post-startup-slot-picker/post-flat-stats sketch.
"""
from pathlib import Path
import re
import sys

MARKER = "// BLOOMPETZ_IDLE_KAOMOJI_SCREENSAVER_V1"


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_idle_kaomoji_screensaver.py <bloompetz_v0_1.ino>")
    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()
    if MARKER in s:
        print("Idle kaomoji screensaver already applied.")
        return

    if "static void handleInput(Input in)" not in s:
        raise SystemExit("handleInput() not found")
    if "static void drawHome()" not in s:
        raise SystemExit("drawHome() not found")
    if "void loop()" not in s:
        raise SystemExit("loop() not found")

    # Extend UiMode with SCREEN_SAVER if needed.
    m = re.search(r'enum\s+UiMode\s*:\s*uint8_t\s*\{([^}]*)\};', s)
    if not m:
        raise SystemExit("UiMode enum not found")
    items = [x.strip() for x in m.group(1).split(',') if x.strip()]
    if "SCREEN_SAVER" not in items:
        items.append("SCREEN_SAVER")
        enum_new = "enum UiMode : uint8_t { " + ", ".join(items) + " };"
        s = s[:m.start()] + enum_new + s[m.end():]

    anchor = "static void handleInput(Input in) {"
    helpers = r'''// BLOOMPETZ_IDLE_KAOMOJI_SCREENSAVER_V1
static constexpr unsigned long BLOOMPETZ_SAVER_IDLE_MS = 30000UL;
static unsigned long bloomSaverLastInputMs = 0;
static unsigned long bloomSaverLastFrameMs = 0;
static unsigned long bloomSaverBlinkUntilMs = 0;
static unsigned long bloomSaverNextBlinkMs = 0;
static uint8_t bloomSaverPhase = 0;

static const char BLOOMPETZ_SAVER_SYMBOLS[] = ".*+xo@#~^:;=<>[]{}()/\\|!";

static String bloomSaverMutatedArt(const String &src) {
  if (millis() >= bloomSaverBlinkUntilMs) return src;
  String out = src;
  bool changed = false;
  for (uint16_t i=0; i<out.length(); ++i) {
    char c = out[i];
    if (c=='^' || c=='o' || c=='O' || c=='0' || c=='=' || c=='.') {
      const char repl[] = {'-', '_', 'x', '*', '~'};
      out.setCharAt(i, repl[random(0, 5)]);
      changed = true;
      if (changed && random(0, 3) != 0) break;
    }
  }
  if (!changed && out.length()) {
    uint16_t i = random(0, out.length());
    out.setCharAt(i, BLOOMPETZ_SAVER_SYMBOLS[random(0, sizeof(BLOOMPETZ_SAVER_SYMBOLS)-1)]);
  }
  return out;
}

static String bloomSaverNoiseLine(uint8_t row, const String &petArt, bool placePet) {
  char buf[17];
  for (uint8_t i=0;i<16;++i) buf[i]=' ';
  buf[16]='\\0';

  // sparse drifting symbols; phase changes their apparent horizontal position
  uint8_t count = 3 + random(0, 4);
  for (uint8_t n=0;n<count;++n) {
    uint8_t x = (uint8_t)((random(0,16) + bloomSaverPhase + row*3) % 16);
    buf[x] = BLOOMPETZ_SAVER_SYMBOLS[random(0, sizeof(BLOOMPETZ_SAVER_SYMBOLS)-1)];
  }

  String line(buf);
  if (placePet) {
    String art = bloomSaverMutatedArt(petArt);
    if (art.length() > 16) art = art.substring(0,16);
    int start = (16 - (int)art.length()) / 2;
    for (uint16_t i=0;i<art.length() && start+(int)i<16;++i)
      line.setCharAt(start+i, art[i]);
  }
  return line;
}

static void drawBloomSaver() {
  PetSave &pet = pets[activeSlot];
  String art = pet.occupied ? String(pet.art) : String("[=^.^=]");
  // Put the pet between lines 2 and 3 by alternating which center line owns it.
  bool onLine2 = ((bloomSaverPhase / 3) & 1U) == 0;
  String l1 = bloomSaverNoiseLine(0, art, false);
  String l2 = bloomSaverNoiseLine(1, art, onLine2);
  String l3 = bloomSaverNoiseLine(2, art, !onLine2);
  String l4 = bloomSaverNoiseLine(3, art, false);
  renderDisplay(l1,l2,l3,l4);
}

static void serviceBloomSaver() {
  unsigned long now = millis();
  if (bloomSaverLastInputMs == 0) bloomSaverLastInputMs = now;

  if (uiMode == HOME && now - bloomSaverLastInputMs >= BLOOMPETZ_SAVER_IDLE_MS) {
    uiMode = SCREEN_SAVER;
    bloomSaverPhase = 0;
    bloomSaverLastFrameMs = 0;
    bloomSaverNextBlinkMs = now + random(1200, 3600);
    drawBloomSaver();
    return;
  }

  if (uiMode != SCREEN_SAVER) return;

  if (bloomSaverNextBlinkMs == 0 || now >= bloomSaverNextBlinkMs) {
    bloomSaverBlinkUntilMs = now + random(140, 360);
    bloomSaverNextBlinkMs = now + random(1200, 4200);
  }
  if (now - bloomSaverLastFrameMs >= 220) {
    bloomSaverLastFrameMs = now;
    ++bloomSaverPhase;
    drawBloomSaver();
  }
}

'''
    s = s.replace(anchor, helpers + anchor, 1)

    # Wake saver on any input before other handling.
    old = "static void handleInput(Input in) {\n  if (in == NONE) return;"
    if old not in s:
        raise SystemExit("handleInput NONE guard shape not found")
    new = "static void handleInput(Input in) {\n  if (in == NONE) return;\n  bloomSaverLastInputMs = millis();\n  if (uiMode == SCREEN_SAVER) { uiMode = HOME; drawHome(); return; }"
    s = s.replace(old, new, 1)

    # Service in loop. Prefer just before loop closing brace by inserting after input handling call.
    # Known current sketch has `if(in != NONE) handleInput(in);`
    marker = "if(in != NONE) handleInput(in);"
    if marker in s:
        s = s.replace(marker, marker + "\n  serviceBloomSaver();", 1)
    else:
        # Fallback: insert immediately after loop opening.
        loop_anchor = "void loop() {"
        if loop_anchor not in s:
            raise SystemExit("loop anchor missing")
        s = s.replace(loop_anchor, loop_anchor + "\n  serviceBloomSaver();", 1)

    # Ensure idle timer starts after setup has finished boot/slot flow. We do not force a redraw.
    setup_end = re.search(r'void\s+setup\s*\(\s*\)\s*\{', s)
    if setup_end:
        # add a safe initialization near first occurrence of delay/calibration end is too brittle;
        # zero means serviceBloomSaver initializes itself on first loop pass.
        pass

    p.write_text(s)
    print(f"Idle kaomoji screensaver applied to {p}")
    print("30s HOME idle -> screensaver; any input wakes HOME immediately.")
    print("No pet name; pet kaomoji floats between center lines with random ASCII drift/blinks.")


if __name__ == "__main__":
    main()
