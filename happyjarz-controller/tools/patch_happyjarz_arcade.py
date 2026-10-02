#!/usr/bin/env python3
"""Integrate the HAPPY JARZ board-native arcade into final staged firmware.

Runs after the OLED/menu/saver patch stack. It deliberately anchors only to
stable symbols/function calls instead of neighboring formatting from earlier
patches.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_arcade.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

# Arcade header beside the already-proven U8g2 include.
if '#include "happyjarz_arcade.h"' not in s:
    marker = '#include <U8g2lib.h>\n'
    if marker not in s:
        raise SystemExit("arcade patch failed: U8g2 include not found")
    s = s.replace(marker, marker + '#include "happyjarz_arcade.h"\n', 1)

# U8g2 -> arcade drawing adapter.
marker = '''static bool oledDirty = true;
static unsigned long oledLastDrawMs = 0;
'''
if marker not in s:
    raise SystemExit("arcade patch failed: OLED state marker not found")

adapter = r'''

// HAPPY JARZ Arcade -> known-good U8g2 OLED adapter
static void arcadeClear() {
  if (oled) oled->clearBuffer();
}

static void arcadePixel(int16_t x, int16_t y, bool on) {
  if (!oled) return;
  if (!on) oled->setDrawColor(0);
  oled->drawPixel(x, y);
  if (!on) oled->setDrawColor(1);
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

# Turn the existing GAMES detail page into the arcade entry page.
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

# Own input at the stable top of serviceInputs(), before downstream menu/saver
# routing can consume the same touch edge.
service_marker = '''static void serviceInputs() {
  bool q[INPUT_COUNT];
  for (uint8_t i=0;i<INPUT_COUNT;++i) q[i]=updateInputState(i);
'''
if service_marker not in s:
    raise SystemExit("arcade patch failed: serviceInputs scan marker not found")

arcade_input = r'''

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

    for (uint8_t i=0;i<INPUT_COUNT;++i) latched[i]=q[i];
    if (inputStream && Serial && millis()-lastInputStreamMs>=100) {
      lastInputStreamMs=millis();
      printInputTelemetry();
    }
    return;
  }
'''
s = s.replace(service_marker, service_marker + arcade_input, 1)

# Initialize arcade immediately after the actual OLED init call. Do not depend
# on which subsystem initialization happens on the following line.
setup_call = '  oledInit();\n'
if setup_call not in s:
    raise SystemExit("arcade patch failed: oledInit() call not found")
s = s.replace(setup_call, setup_call + '  hjArcadeBegin(ARCADE_DISPLAY);\n', 1)

# Let the arcade own OLED refresh while active. Again, match only the stable
# service call rather than its neighboring loop lines.
service_call = '  serviceOled();\n'
if service_call not in s:
    raise SystemExit("arcade patch failed: serviceOled() loop call not found")
s = s.replace(service_call,
              '  if (hjArcadeActive()) hjArcadeService(millis());\n'
              '  else serviceOled();\n',
              1)

p.write_text(s, encoding="utf-8")
print("HAPPY JARZ arcade integration patch: PASS")
