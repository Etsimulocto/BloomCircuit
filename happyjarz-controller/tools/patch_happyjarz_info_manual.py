#!/usr/bin/env python3
"""Add a paged on-board INFO / manual to the HAPPY JARZ OLED menu.

MAIN MENU gains INFO as item 6.

INFO controls:
  RIGHT / DOWN / A = next page
  LEFT / UP        = previous page
  B                = back to main menu

The manual is intentionally board-local and requires no PC or Wi-Fi.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_info_manual.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

# Add UI_INFO to the existing screen enum.
old_enum = '''  UI_GAMES,\n  UI_SETTINGS,\n  UI_SYSTEM\n};\n'''
new_enum = '''  UI_GAMES,\n  UI_SETTINGS,\n  UI_SYSTEM,\n  UI_INFO\n};\n'''
if old_enum not in s:
    raise SystemExit("info patch failed: UiScreen enum marker not found")
s = s.replace(old_enum, new_enum, 1)

# INFO page state lives beside the normal menu cursor state.
state_marker = '''static uint8_t uiScroll = 0;\n'''
if state_marker not in s:
    raise SystemExit("info patch failed: uiScroll marker not found")
s = s.replace(state_marker, state_marker + 'static uint8_t infoPage = 0;\n', 1)

old_main = '''static void oledRenderMainMenu() {\n  static const char *items[] = {"CLOCK", "LIGHTS", "GAMES", "SETTINGS", "SYSTEM"};\n  static constexpr uint8_t count = 5;\n'''
new_main = '''static void oledRenderMainMenu() {\n  static const char *items[] = {"CLOCK", "LIGHTS", "GAMES", "SETTINGS", "SYSTEM", "INFO"};\n  static constexpr uint8_t count = 6;\n'''
if old_main not in s:
    raise SystemExit("info patch failed: main-menu renderer marker not found")
s = s.replace(old_main, new_main, 1)

# Add the manual renderer before SYSTEM so all OLED render functions remain together.
system_marker = '''static void oledRenderSystem() {\n'''
if system_marker not in s:
    raise SystemExit("info patch failed: SYSTEM renderer marker not found")
manual = r'''static constexpr uint8_t INFO_PAGE_COUNT = 12;

static void oledRenderInfo() {
  oledCentered(10, "INFO / MANUAL");
  switch (infoPage % INFO_PAGE_COUNT) {
    case 0:
      oledCentered(25, "HAPPY JARZ");
      oledCentered(39, "STANDALONE CONSOLE");
      oledCentered(53, "A/RIGHT NEXT");
      break;
    case 1:
      oledCentered(25, "HOME CONTROLS");
      oledCentered(39, "UP/DN PATTERN");
      oledCentered(53, "A MENU  B FREE");
      break;
    case 2:
      oledCentered(25, "HOME COLORS");
      oledCentered(39, "LEFT = LIGHT 1");
      oledCentered(53, "RIGHT = LIGHT 2");
      break;
    case 3:
      oledCentered(25, "LIGHTS / SOLID");
      oledCentered(39, "UP/DN +/-5%");
      oledCentered(53, "LT/RT +/-1%");
      break;
    case 4:
      oledCentered(25, "BRIGHTNESS");
      oledCentered(39, "0 - 100% RANGE");
      oledCentered(53, "A SAVE  B BACK");
      break;
    case 5:
      oledCentered(25, "CLOCK / DATE");
      oledCentered(39, "A = SET CLOCK");
      oledCentered(53, "NO PC REQUIRED");
      break;
    case 6:
      oledCentered(25, "SETTINGS");
      oledCentered(39, "ALARM + TIMER");
      oledCentered(53, "BOARD LOCAL");
      break;
    case 7:
      oledCentered(25, "HAPPY ARCADE");
      oledCentered(39, "7 MINI GAMES");
      oledCentered(53, "LONG B = EXIT");
      break;
    case 8:
      oledCentered(25, "SCREENSAVERS");
      oledCentered(39, "SAYINGS + ART");
      oledCentered(53, "30 SEC IDLE");
      break;
    case 9:
      oledCentered(25, "POWER / BATTERY");
      oledCentered(39, "HOME SHOWS STATUS");
      oledCentered(53, "GPIO3 FUEL GAUGE");
      break;
    case 10:
      oledCentered(25, "USB + WIFI");
      oledCentered(39, "PC OPTIONAL");
      oledCentered(53, "LOCAL MODE FALLBACK");
      break;
    default:
      oledCentered(25, "SYSTEM");
      oledCentered(39, String("FW ") + HJ_FW_VERSION);
      oledCentered(53, "B = MAIN MENU");
      break;
  }
  char pageBuf[16];
  snprintf(pageBuf, sizeof(pageBuf), "%u/%u", (unsigned)(infoPage + 1), (unsigned)INFO_PAGE_COUNT);
  oled->setFont(u8g2_font_5x8_tf);
  oled->drawStr(108, 63, pageBuf);
  oled->setFont(u8g2_font_6x12_tr);
}

'''
s = s.replace(system_marker, manual + system_marker, 1)

old_select = '''    case 2: uiScreen = UI_GAMES; break;\n    case 3: uiScreen = UI_SETTINGS; break;\n    default: uiScreen = UI_SYSTEM; break;\n'''
new_select = '''    case 2: uiScreen = UI_GAMES; break;\n    case 3: uiScreen = UI_SETTINGS; break;\n    case 4: uiScreen = UI_SYSTEM; break;\n    default: infoPage = 0; uiScreen = UI_INFO; break;\n'''
if old_select not in s:
    raise SystemExit("info patch failed: uiSelectMain marker not found")
s = s.replace(old_select, new_select, 1)

# Make INFO an explicit render target instead of falling into SYSTEM default.
old_switch = '''    case UI_GAMES: oledRenderGames(); break;\n    case UI_SETTINGS: oledRenderSettings(); break;\n    default: oledRenderSystem(); break;\n'''
new_switch = '''    case UI_GAMES: oledRenderGames(); break;\n    case UI_SETTINGS: oledRenderSettings(); break;\n    case UI_SYSTEM: oledRenderSystem(); break;\n    default: oledRenderInfo(); break;\n'''
if old_switch not in s:
    raise SystemExit("info patch failed: OLED service switch marker not found")
s = s.replace(old_switch, new_switch, 1)

# Main-menu navigation now wraps across six items.
s = s.replace('uiCursor=(uiCursor+4)%5;', 'uiCursor=(uiCursor+5)%6;', 1)
s = s.replace('uiCursor=(uiCursor+1)%5;', 'uiCursor=(uiCursor+1)%6;', 1)

# INFO owns its buttons before the downstream generic detail router.
service_marker = '''static void serviceInputs() {\n  bool q[INPUT_COUNT];\n  for (uint8_t i=0;i<INPUT_COUNT;++i) q[i]=updateInputState(i);\n'''
if service_marker not in s:
    raise SystemExit("info patch failed: serviceInputs marker not found")
info_controls = r'''

  if (inputMode == "JAR" && uiScreen == UI_INFO) {
    bool next = (q[IN_RIGHT] && !latched[IN_RIGHT]) ||
                (q[IN_DOWN] && !latched[IN_DOWN]) ||
                (q[IN_A] && !latched[IN_A]);
    bool prev = (q[IN_LEFT] && !latched[IN_LEFT]) ||
                (q[IN_UP] && !latched[IN_UP]);
    if (next) {
      infoPage = (infoPage + 1) % INFO_PAGE_COUNT;
      oledDirty = true;
    } else if (prev) {
      infoPage = (infoPage + INFO_PAGE_COUNT - 1) % INFO_PAGE_COUNT;
      oledDirty = true;
    } else if (q[IN_B] && !latched[IN_B]) {
      uiOpenMainMenu();
    }
    for (uint8_t i=0;i<INPUT_COUNT;++i) latched[i]=q[i];
    return;
  }
'''
s = s.replace(service_marker, service_marker + info_controls, 1)

p.write_text(s, encoding="utf-8")
print("Applied on-board INFO / manual pages.")
