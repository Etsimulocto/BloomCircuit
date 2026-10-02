#!/usr/bin/env python3
"""Add a paged on-board INFO / manual to the HAPPY JARZ OLED menu.

Runs after Fuel Gauge staging, so the existing menu already contains:
CLOCK, LIGHTS, GAMES, SETTINGS, POWER, SYSTEM.

INFO becomes item 7.

INFO controls:
  RIGHT / DOWN / A = next page
  LEFT / UP        = previous page
  B                = back to main menu

The manual is intentionally board-local and requires no PC or Wi-Fi.
"""
from pathlib import Path
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_info_manual.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

# Fuel Gauge has already extended UiScreen through UI_POWER. Append INFO at the
# actual end of enum UiScreen rather than assuming any particular prior tail.
enum_re = re.compile(r'(enum UiScreen\s*:\s*uint8_t\s*\{)(.*?)(\n\};)', re.DOTALL)
m = enum_re.search(s)
if not m:
    raise SystemExit("info patch failed: UiScreen enum not found")
body = m.group(2)
if "UI_INFO" not in body:
    stripped = body.rstrip()
    if not stripped.endswith(','):
        stripped += ','
    body = stripped + "\n  UI_INFO"
    s = s[:m.start(2)] + body + s[m.end(2):]

# INFO page state lives beside the normal menu cursor state.
state_marker = "static uint8_t uiScroll = 0;\n"
if state_marker not in s:
    raise SystemExit("info patch failed: uiScroll marker not found")
if "static uint8_t infoPage = 0;" not in s:
    s = s.replace(state_marker, state_marker + "static uint8_t infoPage = 0;\n", 1)

# Fuel Gauge has already made this a six-item menu. Preserve POWER and SYSTEM,
# then add INFO as item seven.
old_items = 'static const char *items[] = {"CLOCK", "LIGHTS", "GAMES", "SETTINGS", "POWER", "SYSTEM"};'
new_items = 'static const char *items[] = {"CLOCK", "LIGHTS", "GAMES", "SETTINGS", "POWER", "SYSTEM", "INFO"};'
if old_items not in s:
    raise SystemExit("info patch failed: six-item POWER menu list not found")
s = s.replace(old_items, new_items, 1)

old_count = "static constexpr uint8_t count = 6;"
if old_count not in s:
    raise SystemExit("info patch failed: six-item menu count not found")
s = s.replace(old_count, "static constexpr uint8_t count = 7;", 1)

# Add the manual renderer before SYSTEM so all OLED render functions stay together.
system_marker = "static void oledRenderSystem() {\n"
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

# Fuel Gauge selector: 0 clock, 1 lights, 2 games, 3 settings, 4 power,
# default system. Split that default so 5=SYSTEM and 6=INFO.
old_select = "    case 2: uiScreen = UI_GAMES; break;\n    case 3: uiScreen = UI_SETTINGS; break;\n    case 4: uiScreen = UI_POWER; break;\n    default: uiScreen = UI_SYSTEM; break;\n"
new_select = "    case 2: uiScreen = UI_GAMES; break;\n    case 3: uiScreen = UI_SETTINGS; break;\n    case 4: uiScreen = UI_POWER; break;\n    case 5: uiScreen = UI_SYSTEM; break;\n    default: infoPage = 0; uiScreen = UI_INFO; break;\n"
if old_select not in s:
    raise SystemExit("info patch failed: Fuel Gauge uiSelectMain tail not found")
s = s.replace(old_select, new_select, 1)

# Fuel Gauge has an explicit POWER case followed by SYSTEM fallback. Add INFO
# explicitly before that fallback while preserving POWER.
switch_old = "    case UI_POWER: oledRenderPower(); break;\n    default: oledRenderSystem(); break;"
switch_new = "    case UI_POWER: oledRenderPower(); break;\n    case UI_INFO: oledRenderInfo(); break;\n    default: oledRenderSystem(); break;"
if switch_old not in s:
    raise SystemExit("info patch failed: POWER/SYSTEM render tail not found")
s = s.replace(switch_old, switch_new, 1)

# Fuel Gauge already changed the cursor math to six entries. Expand six -> seven.
if 'uiCursor=(uiCursor+5)%6;' not in s or 'uiCursor=(uiCursor+1)%6;' not in s:
    raise SystemExit("info patch failed: six-item menu navigation not found")
s = s.replace('uiCursor=(uiCursor+5)%6;', 'uiCursor=(uiCursor+6)%7;', 1)
s = s.replace('uiCursor=(uiCursor+1)%6;', 'uiCursor=(uiCursor+1)%7;', 1)

# INFO owns its buttons immediately after the six qualified touch reads.
service_re = re.compile(
    r'(static void serviceInputs\(\) \{\n'
    r'  bool q\[INPUT_COUNT\];\n'
    r'  for \(uint8_t i=0;i<INPUT_COUNT;\+\+i\) q\[i\]=updateInputState\(i\);\n)'
)
m = service_re.search(s)
if not m:
    raise SystemExit("info patch failed: serviceInputs touch-read entry not found")
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
s = s[:m.end()] + info_controls + s[m.end():]

p.write_text(s, encoding="utf-8")
print("Applied on-board INFO / manual pages after POWER menu.")
