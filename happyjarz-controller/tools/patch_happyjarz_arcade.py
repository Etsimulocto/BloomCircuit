#!/usr/bin/env python3
"""Integrate the HAPPY JARZ board-native arcade into the staged firmware.

Requires the OLED and menu patches to have already run.
Uses the proven OLED layer:
- SSD1306 128x64
- U8g2
- SDA GPIO8
- SCL GPIO6
- I2C address 0x3C

Uses the proven six-touch edge layer rather than reading touch pins itself.
This patch deliberately avoids replacing the existing HOME/menu control block;
it gates that block while the arcade is active and inserts a separate arcade
input branch immediately before it.
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

# Insert U8g2 -> HjArcadeDisplay adapter beside the known-good OLED layer.
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

# Replace the placeholder GAMES detail screen with arcade entry instructions.
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

# Final staging adds screensaver ownership around the existing JAR controls.
# Do NOT replace that whole structure. Gate the normal JAR block only while the
# arcade owns controls, then insert an independent edge-event bridge before it.
jar_marker = '  if (inputMode == "JAR") {\n'
if jar_marker not in s:
    raise SystemExit("arcade patch failed: JAR input entry not found")

arcade_input = r'''  if (inputMode == "JAR" && hjArcadeActive()) {
    // ARCADE MODE: only consume edges already qualified by the proven touch
    // layer. Normal HOME/menu/light actions are gated below while active.
    if (q[IN_UP] && !latched[IN_UP]) hjArcadeButton(HJ_BTN_UP);
    if (q[IN_DOWN] && !latched[IN_DOWN]) hjArcadeButton(HJ_BTN_DOWN);
    if (q[IN_LEFT] && !latched[IN_LEFT]) hjArcadeButton(HJ_BTN_LEFT);
    if (q[IN_RIGHT] && !latched[IN_RIGHT]) hjArcadeButton(HJ_BTN_RIGHT);
    if (q[IN_A] && !latched[IN_A]) hjArcadeButton(HJ_BTN_A);
    if (q[IN_B] && !latched[IN_B]) hjArcadeButton(HJ_BTN_B);

    // Long B always escapes the arcade back to the GAMES page.
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
  }

'''
s = s.replace(jar_marker, arcade_input + '  if (inputMode == "JAR" && !hjArcadeActive()) {\n', 1)

# On the existing GAMES detail page A starts the arcade. This hook goes before
# the normal detail-page back handling and leaves every other detail page alone.
detail_marker = '''    } else {
      // DETAIL/STATUS MODE: still no light commands. B/LEFT return to menu.
'''
if detail_marker not in s:
    raise SystemExit("arcade patch failed: detail/status menu marker not found")
detail_repl = '''    } else {
      if (uiScreen == UI_GAMES && q[IN_A] && !latched[IN_A]) {
        hjArcadeEnter();
      }
      // DETAIL/STATUS MODE: still no light commands. B/LEFT return to menu.
'''
s = s.replace(detail_marker, detail_repl, 1)

# Initialize the arcade after the known-good OLED is initialized.
setup_marker = '''  oledInit();
  if(!initApa106Rmt())'''
setup_repl = '''  oledInit();
  hjArcadeBegin(ARCADE_DISPLAY);
  if(!initApa106Rmt())'''
if setup_marker not in s:
    raise SystemExit("arcade patch failed: oledInit setup marker not found")
s = s.replace(setup_marker, setup_repl, 1)

# When arcade is active it owns rendering. Otherwise the normal OLED service runs.
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
