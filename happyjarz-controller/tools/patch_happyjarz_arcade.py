#!/usr/bin/env python3
"""Integrate the HAPPY JARZ board-native arcade into the final staged firmware.

Requires the OLED/menu/saver patch stack to have already run.
Uses the proven OLED layer:
- SSD1306 128x64
- U8g2
- SDA GPIO8
- SCL GPIO6
- I2C address 0x3C

Uses the proven six-touch edge layer rather than reading touch pins itself.

IMPORTANT: this patch intentionally does NOT search for or rewrite the later
HOME/menu JAR-control block. That block is reshaped by several staging patches.
Instead, arcade ownership is injected immediately after the six qualified input
states are computed at the top of serviceInputs(). Arcade-owned input returns
early, so no downstream HOME/menu/light/saver action can leak through.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_arcade.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

if '#include "happyjarz_arcade.h"' not in s:
    marker = '#include <U8g2lib.h>\n'
    if marker not in s:
        raise SystemExit("arcade patch failed: U8g2 include not found; OLED patch must run first")
    s = s.replace(marker, marker + '#include "happyjarz_arcade.h"\n', 1)

# ---------------------------------------------------------------------------
# U8g2 -> board-native arcade display adapter
# ---------------------------------------------------------------------------
marker = '''static bool oledDirty = true;
static unsigned long oledLastDrawMs = 0;
'''
if marker not in s:
    raise SystemExit("arcade patch failed: OLED state marker not found")

adapter = r'''

// -----------------------------
// HAPPY JARZ Arcade -> known-good U8g2 OLED adapter
// -----------------------------
static void arcadeClear() {
  if (oled) oled->clearBuffer();
}

static void arcadePixel(int16_t x, int16_t y, bool on) {
  if (!oled) return;
  if (on) oled->drawPixel(x, y);
  else {
    oled->setDrawColor(0);
    oled->drawPixel(x, y);
    oled->setDrawColor(1);
  }
}

static void arcadeLine(int16_t x0, int16_t y0, int16_t x1, int16_t y1, bool on) {
  if (!oled) return;
  if (!on) oled->setDrawColor(0);
  oled->drawLine(x0, y0, x1, y1);
  if (!on) oled->setDrawColor(1);
}

static void arcadeRect(int16_t x, int16_t y, int16_t w, int16_t h, bool fill, bool on) {
  if (!oled) return;
  if (!on) oled->setDrawColor(0);
  if (fill) oled->drawBox(x, y, w, h);
  else oled->drawFrame(x, y, w, h);
  if (!on) oled->setDrawColor(1);
}

static void arcadeText(int16_t x, int16_t y, const char *text, uint8_t size) {
  if (!oled || !text) return;
  oled->setFont(size > 1 ? u8g2_font_7x14_tf : u8g2_font_5x8_tf);
  oled->drawStr(x, y + (size > 1 ? 13 : 7), text);
}

static void arcadePresent() {
  if (oled) oled->sendBuffer();
}

static const HjArcadeDisplay ARCADE_DISPLAY = {
  arcadeClear,
  arcadePixel,
  arcadeLine,
  arcadeRect,
  arcadeText,
  arcadePresent
};
'''
s = s.replace(marker, marker + adapter, 1)

# ---------------------------------------------------------------------------
# Replace only the known OLED GAMES placeholder. This marker is supplied by
# patch_happyjarz_oled.py and is intentionally independent of serviceInputs().
# ---------------------------------------------------------------------------
old_games = '''static void oledRenderGames() {
  oledCentered(13, "GAMES");
  oledCentered(29, "COMING SOON");
  oledCentered(45, "TINY CONSOLE");
  oledCentered(61, "B BACK");
}
'''
new_games = '''static void oledRenderGames() {
  oledCentered(13, "HAPPY ARCADE");
  oledCentered(29, "7 MINI GAMES");
  oledCentered(45, "A PLAY");
  oledCentered(61, "B BACK");
}
'''
if old_games not in s:
    raise SystemExit("arcade patch failed: GAMES placeholder screen not found")
s = s.replace(old_games, new_games, 1)

# ---------------------------------------------------------------------------
# Arcade input ownership.
# Anchor only to the stable top of serviceInputs(): the six qualified readings.
# Do NOT depend on the shape or wording of any later JAR/menu/saver block.
# ---------------------------------------------------------------------------
service_marker = '''static void serviceInputs() {
  bool q[INPUT_COUNT];
  for (uint8_t i=0;i<INPUT_COUNT;++i) q[i]=updateInputState(i);
'''
if service_marker not in s:
    raise SystemExit("arcade patch failed: stable serviceInputs input-scan marker not found")

arcade_input = r'''

  // HAPPY ARCADE owns controls before any downstream HOME/menu/saver routing.
  // Enter only from the visible GAMES page, and never steal the first touch
  // from an active screensaver.
  if (!hjArcadeActive() && !hjScreensaverActive && uiScreen == UI_GAMES &&
      q[IN_A] && !latched[IN_A]) {
    hjArcadeEnter();
    for (uint8_t i=0;i<INPUT_COUNT;++i) latched[i]=q[i];
    oledDirty = true;
    return;
  }

  if (hjArcadeActive()) {
    if (q[IN_UP] && !latched[IN_UP]) hjArcadeButton(HJ_BTN_UP);
    if (q[IN_DOWN] && !latched[IN_DOWN]) hjArcadeButton(HJ_BTN_DOWN);
    if (q[IN_LEFT] && !latched[IN_LEFT]) hjArcadeButton(HJ_BTN_LEFT);
    if (q[IN_RIGHT] && !latched[IN_RIGHT]) hjArcadeButton(HJ_BTN_RIGHT);
    if (q[IN_A] && !latched[IN_A]) hjArcadeButton(HJ_BTN_A);
    if (q[IN_B] && !latched[IN_B]) hjArcadeButton(HJ_BTN_B);

    // Long B is the hard escape back to the normal GAMES detail page.
    if (q[IN_B] && !bHomeSent && inputs[IN_B].qualifiedMs &&
        millis() - inputs[IN_B].qualifiedMs >= 1000) {
      bHomeSent = true;
      hjArcadeButton(HJ_BTN_HOME);
      hjArcadeExit();
      uiScreen = UI_GAMES;
      uiCursor = 0;
      uiScroll = 0;
      oledDirty = true;
    }

    // Preserve the proven one-action-per-touch/release edge state even though
    // downstream HOME/menu handling is intentionally skipped this cycle.
    for (uint8_t i=0;i<INPUT_COUNT;++i) latched[i]=q[i];

    // Keep optional raw-input telemetry usable while playing.
    if (inputStream && Serial && millis()-lastInputStreamMs>=100) {
      lastInputStreamMs=millis();
      printInputTelemetry();
    }
    return;
  }
'''
s = s.replace(service_marker, service_marker + arcade_input, 1)

# ---------------------------------------------------------------------------
# Initialize after known-good OLED init.
# ---------------------------------------------------------------------------
setup_marker = '''  oledInit();
  if(!initApa106Rmt())'''
setup_repl = '''  oledInit();
  hjArcadeBegin(ARCADE_DISPLAY);
  if(!initApa106Rmt())'''
if setup_marker not in s:
    raise SystemExit("arcade patch failed: oledInit setup marker not found")
s = s.replace(setup_marker, setup_repl, 1)

# ---------------------------------------------------------------------------
# Arcade owns display refresh while active; normal OLED service resumes on exit.
# ---------------------------------------------------------------------------
loop_marker = '''  serviceTimer();
  serviceOled();
  static bool timeStarted=false;'''
loop_repl = '''  serviceTimer();
  if (hjArcadeActive()) hjArcadeService(millis());
  else serviceOled();
  static bool timeStarted=false;'''
if loop_marker not in s:
    raise SystemExit("arcade patch failed: OLED loop marker not found")
s = s.replace(loop_marker, loop_repl, 1)

p.write_text(s, encoding="utf-8")
print("HAPPY JARZ arcade integration patch: PASS")
