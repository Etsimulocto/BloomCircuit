#!/usr/bin/env python3
"""Stage the HAPPY JARZ centered OLED dashboard + menu UI into v0.5 firmware.

BloomCore intent:
- preserve proven APA106/touch/time/USB layers
- OLED: I2C 0x3C, SDA GPIO8, SCL GPIO6
- SSD1306 128x64 via U8g2 by default
- four centered visible rows
- HOME is live clock/status
- A opens menu; UP/DOWN navigate; A selects; B backs out/home
- while menus are open, local jar controls are temporarily captured by UI
- when HOME is visible, normal jar controls remain active
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_oled.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

if '#include <Wire.h>' not in s:
    s = s.replace('#include <WiFi.h>\n', '#include <WiFi.h>\n#include <Wire.h>\n#include <U8g2lib.h>\n', 1)

marker = '''static uint32_t timerRemainingSeconds() {
  if (!timerEnabled) return 0;
  uint64_t target=(uint64_t)timerMinutes*60000ULL;
  uint64_t elapsed=(uint64_t)(millis()-timerStartedMs);
  return elapsed>=target?0:(uint32_t)((target-elapsed)/1000ULL);
}
'''
if marker not in s:
    raise SystemExit("OLED patch failed: timerRemainingSeconds block not found")

block = r'''

// -----------------------------
// OLED dashboard + menu UI
// -----------------------------
static constexpr uint8_t OLED_SDA_PIN = 8;
static constexpr uint8_t OLED_SCL_PIN = 6;
static constexpr uint8_t OLED_I2C_ADDR = 0x3C;
static constexpr bool HJ_OLED_SH1106 = false;

static U8G2_SSD1306_128X64_NONAME_F_HW_I2C oledSsd1306(U8G2_R0, U8X8_PIN_NONE);
static U8G2_SH1106_128X64_NONAME_F_HW_I2C oledSh1106(U8G2_R0, U8X8_PIN_NONE);
static U8G2 *oled = nullptr;
static bool oledReady = false;
static bool oledDirty = true;
static unsigned long oledLastDrawMs = 0;

enum UiScreen : uint8_t {
  UI_HOME=0,
  UI_MAIN_MENU,
  UI_CLOCK,
  UI_LIGHTS,
  UI_GAMES,
  UI_SETTINGS,
  UI_SYSTEM
};
static UiScreen uiScreen = UI_HOME;
static uint8_t uiCursor = 0;
static uint8_t uiScroll = 0;

static void oledCentered(uint8_t y, const String &text) {
  if (!oled) return;
  int width = oled->getUTF8Width(text.c_str());
  int x = (128 - width) / 2;
  if (x < 0) x = 0;
  oled->drawUTF8(x, y, text.c_str());
}

static String compactRgb(const Rgb &c) {
  return String(c.r) + "," + String(c.g) + "," + String(c.b);
}

static String timerText() {
  if (!timerEnabled) return "TIMER OFF";
  uint32_t sec = timerRemainingSeconds();
  char buf[22];
  snprintf(buf, sizeof(buf), "TIMER %lu:%02lu", (unsigned long)(sec/60UL), (unsigned long)(sec%60UL));
  return String(buf);
}

static void oledApplyBrightness() {
  if (!oledReady || !oled) return;
  uint8_t contrast = (uint8_t)map(displayBrightness, 0, 100, 0, 255);
  oled->setContrast(contrast);
}

static void oledInit() {
  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  Wire.setClock(400000);
  oled = HJ_OLED_SH1106 ? static_cast<U8G2*>(&oledSh1106) : static_cast<U8G2*>(&oledSsd1306);
  oled->setI2CAddress(OLED_I2C_ADDR << 1);
  oled->begin();
  oled->setFont(u8g2_font_6x12_tr);
  oledReady = true;
  oledApplyBrightness();
  oled->clearBuffer();
  oledCentered(13, "HAPPY JARZ");
  oledCentered(29, "BOOTING");
  oledCentered(45, "HJ-001");
  oledCentered(61, "BLOOMCORE");
  oled->sendBuffer();
}

static void oledRenderHome() {
  if (!clockSynced()) {
    oledCentered(13, "HAPPY JARZ");
    oledCentered(29, "CLOCK NOT SET");
    oledCentered(45, patternName + "  " + String(brightnessPercent) + "%");
    oledCentered(61, "A MENU");
    return;
  }
  struct tm t;
  if (!getLocalTime(&t, 10)) return;
  char timeBuf[22], dateBuf[22], alarmBuf[22];
  strftime(timeBuf, sizeof(timeBuf), "%I:%M:%S %p", &t);
  strftime(dateBuf, sizeof(dateBuf), "%a  %b %d  %Y", &t);
  snprintf(alarmBuf, sizeof(alarmBuf), alarmEnabled ? "ALARM %02u:%02u" : "ALARM OFF", alarmHour, alarmMinute);
  oledCentered(13, String(timeBuf));
  oledCentered(29, String(dateBuf));
  oledCentered(45, patternName + "  " + String(brightnessPercent) + "%");
  String bottom = timerEnabled ? timerText() : String(alarmBuf);
  oledCentered(61, bottom);
}

static void oledRenderMainMenu() {
  static const char *items[] = {"CLOCK", "LIGHTS", "GAMES", "SETTINGS", "SYSTEM"};
  static constexpr uint8_t count = 5;
  if (uiCursor >= count) uiCursor = 0;
  if (uiCursor < uiScroll) uiScroll = uiCursor;
  if (uiCursor > uiScroll + 3) uiScroll = uiCursor - 3;
  for (uint8_t row=0; row<4; ++row) {
    uint8_t idx = uiScroll + row;
    if (idx >= count) break;
    String text = String(idx == uiCursor ? "> " : "  ") + items[idx];
    oledCentered(13 + row*16, text);
  }
}

static void oledRenderClock() {
  struct tm t;
  oledCentered(13, "CLOCK");
  if (!clockSynced() || !getLocalTime(&t, 10)) {
    oledCentered(29, "NOT SET");
    oledCentered(45, timezoneName);
    oledCentered(61, "B BACK");
    return;
  }
  char timeBuf[22], dateBuf[22];
  strftime(timeBuf, sizeof(timeBuf), "%I:%M:%S %p", &t);
  strftime(dateBuf, sizeof(dateBuf), "%a %b %d %Y", &t);
  oledCentered(29, String(timeBuf));
  oledCentered(45, String(dateBuf));
  oledCentered(61, WiFi.status()==WL_CONNECTED ? "SOURCE WIFI" : "SOURCE USB");
}

static void oledRenderLights() {
  oledCentered(13, "LIGHTS");
  oledCentered(29, "L1  " + compactRgb(ledColor[0]));
  oledCentered(45, "L2  " + compactRgb(ledColor[1]));
  oledCentered(61, patternName + "  " + String(brightnessPercent) + "%");
}

static void oledRenderGames() {
  oledCentered(13, "GAMES");
  oledCentered(29, "COMING SOON");
  oledCentered(45, "TINY CONSOLE");
  oledCentered(61, "B BACK");
}

static void oledRenderSettings() {
  oledCentered(13, "SETTINGS");
  oledCentered(29, "DISPLAY " + String(displayBrightness) + "%");
  oledCentered(45, alarmEnabled ? "ALARM ON" : "ALARM OFF");
  oledCentered(61, timerText());
}

static void oledRenderSystem() {
  oledCentered(13, "SYSTEM");
  oledCentered(29, String(HJ_SERIAL_ID) + "  FW " + HJ_FW_VERSION);
  oledCentered(45, WiFi.status()==WL_CONNECTED ? "WIFI CONNECTED" : "WIFI OFFLINE");
  oledCentered(61, timezoneName);
}

static void uiOpenMainMenu() {
  uiScreen = UI_MAIN_MENU;
  uiCursor = 0;
  uiScroll = 0;
  oledDirty = true;
}

static void uiGoHome() {
  uiScreen = UI_HOME;
  uiCursor = 0;
  uiScroll = 0;
  oledDirty = true;
}

static void uiSelectMain() {
  switch (uiCursor) {
    case 0: uiScreen = UI_CLOCK; break;
    case 1: uiScreen = UI_LIGHTS; break;
    case 2: uiScreen = UI_GAMES; break;
    case 3: uiScreen = UI_SETTINGS; break;
    default: uiScreen = UI_SYSTEM; break;
  }
  oledDirty = true;
}

static void serviceOled() {
  if (!oledReady || !oled) return;
  unsigned long now = millis();
  if (!oledDirty && now - oledLastDrawMs < 250) return;
  oledLastDrawMs = now;
  oledDirty = false;
  oled->clearBuffer();
  oled->setFont(u8g2_font_6x12_tr);
  switch (uiScreen) {
    case UI_HOME: oledRenderHome(); break;
    case UI_MAIN_MENU: oledRenderMainMenu(); break;
    case UI_CLOCK: oledRenderClock(); break;
    case UI_LIGHTS: oledRenderLights(); break;
    case UI_GAMES: oledRenderGames(); break;
    case UI_SETTINGS: oledRenderSettings(); break;
    default: oledRenderSystem(); break;
  }
  oled->sendBuffer();
}
'''

s = s.replace(marker, marker + block, 1)

# Replace local touch handling entry so menus capture controls only while open.
nav_needle = '''  if (inputMode == "JAR") {
    if (q[IN_A] && !latched[IN_A]) { paletteIndex1=(paletteIndex1+1)%9; Rgb c=palette[paletteIndex1]; hjSetLed(1,c.r,c.g,c.b); }
    if (q[IN_B] && !latched[IN_B]) { paletteIndex2=(paletteIndex2+1)%9; Rgb c=palette[paletteIndex2]; hjSetLed(2,c.r,c.g,c.b); }
    if (q[IN_UP] && !latched[IN_UP]) { localPatternIndex=(localPatternIndex+1)%6; hjSetPattern(patterns[localPatternIndex]); }
    if (q[IN_DOWN] && !latched[IN_DOWN]) { localPatternIndex=(localPatternIndex+5)%6; hjSetPattern(patterns[localPatternIndex]); }
  }
'''
nav_repl = '''  if (inputMode == "JAR") {
    if (uiScreen == UI_HOME) {
      if (q[IN_A] && !latched[IN_A]) { uiOpenMainMenu(); }
      else {
        if (q[IN_B] && !latched[IN_B]) { paletteIndex2=(paletteIndex2+1)%9; Rgb c=palette[paletteIndex2]; hjSetLed(2,c.r,c.g,c.b); oledDirty=true; }
        if (q[IN_UP] && !latched[IN_UP]) { localPatternIndex=(localPatternIndex+1)%6; hjSetPattern(patterns[localPatternIndex]); oledDirty=true; }
        if (q[IN_DOWN] && !latched[IN_DOWN]) { localPatternIndex=(localPatternIndex+5)%6; hjSetPattern(patterns[localPatternIndex]); oledDirty=true; }
        if (q[IN_LEFT] && !latched[IN_LEFT]) { paletteIndex1=(paletteIndex1+8)%9; Rgb c=palette[paletteIndex1]; hjSetLed(1,c.r,c.g,c.b); oledDirty=true; }
        if (q[IN_RIGHT] && !latched[IN_RIGHT]) { paletteIndex1=(paletteIndex1+1)%9; Rgb c=palette[paletteIndex1]; hjSetLed(1,c.r,c.g,c.b); oledDirty=true; }
      }
    } else if (uiScreen == UI_MAIN_MENU) {
      if (q[IN_UP] && !latched[IN_UP]) { uiCursor=(uiCursor+4)%5; oledDirty=true; }
      if (q[IN_DOWN] && !latched[IN_DOWN]) { uiCursor=(uiCursor+1)%5; oledDirty=true; }
      if (q[IN_A] && !latched[IN_A]) { uiSelectMain(); }
      if (q[IN_B] && !latched[IN_B]) { uiGoHome(); }
    } else {
      if (q[IN_B] && !latched[IN_B]) { uiOpenMainMenu(); }
      if (q[IN_A] && !latched[IN_A] && uiScreen == UI_LIGHTS) { uiGoHome(); }
    }
  }
'''
if nav_needle not in s:
    raise SystemExit("OLED menu patch failed: JAR input block not found")
s = s.replace(nav_needle, nav_repl, 1)

old_bri = '''  if(line.startsWith("SET DISPLAY BRIGHTNESS ")){int v=line.substring(23).toInt();if(v<0||v>100)err("display brightness must be 0-100");else{displayBrightness=v;ack("SET DISPLAY BRIGHTNESS");}return;}'''
new_bri = '''  if(line.startsWith("SET DISPLAY BRIGHTNESS ")){int v=line.substring(23).toInt();if(v<0||v>100)err("display brightness must be 0-100");else{displayBrightness=v;oledApplyBrightness();oledDirty=true;ack("SET DISPLAY BRIGHTNESS");}return;}'''
if old_bri in s:
    s = s.replace(old_bri, new_bri, 1)

setup_needle = '''  loadSettings();
  if(!initApa106Rmt())'''
setup_repl = '''  loadSettings();
  oledInit();
  if(!initApa106Rmt())'''
if setup_needle not in s:
    raise SystemExit("OLED patch failed: setup insertion point not found")
s = s.replace(setup_needle, setup_repl, 1)

loop_needle = '''  serviceTimer();
  static bool timeStarted=false;'''
loop_repl = '''  serviceTimer();
  serviceOled();
  static bool timeStarted=false;'''
if loop_needle not in s:
    raise SystemExit("OLED patch failed: loop insertion point not found")
s = s.replace(loop_needle, loop_repl, 1)

p.write_text(s, encoding="utf-8")
