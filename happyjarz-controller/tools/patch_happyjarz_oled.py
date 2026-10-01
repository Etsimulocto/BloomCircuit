#!/usr/bin/env python3
"""Stage the HAPPY JARZ centered 4-line OLED dashboard into v0.5 firmware.

BloomCore intent:
- preserve the proven APA106/touch/time/USB layers
- OLED: I2C 0x3C, SDA GPIO8, SCL GPIO6
- default controller: SSD1306 128x64 via U8g2
- four centered text rows, 6x12 font
- LEFT/RIGHT browse pages without stealing UP/DOWN/A/B jar controls
- display brightness protocol drives OLED contrast

If the physical module later proves to be SH1106 rather than SSD1306, change only
HJ_OLED_SH1106 below and reflash; the UI/service layer remains unchanged.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_happyjarz_oled.py <staged .ino>")

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")

# Libraries.
if '#include <Wire.h>' not in s:
    s = s.replace('#include <WiFi.h>\n', '#include <WiFi.h>\n#include <Wire.h>\n#include <U8g2lib.h>\n', 1)

# Dashboard implementation lives after timerRemainingSeconds(), where all state
# it displays has already been declared.
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
// OLED dashboard — centered four-line UI
// -----------------------------
static constexpr uint8_t OLED_SDA_PIN = 8;
static constexpr uint8_t OLED_SCL_PIN = 6;
static constexpr uint8_t OLED_I2C_ADDR = 0x3C;
static constexpr uint8_t OLED_PAGE_COUNT = 4;
static constexpr bool HJ_OLED_SH1106 = false;

static U8G2_SSD1306_128X64_NONAME_F_HW_I2C oledSsd1306(U8G2_R0, U8X8_PIN_NONE);
static U8G2_SH1106_128X64_NONAME_F_HW_I2C oledSh1106(U8G2_R0, U8X8_PIN_NONE);
static U8G2 *oled = nullptr;
static bool oledReady = false;
static uint8_t oledPage = 0;
static bool oledDirty = true;
static unsigned long oledLastDrawMs = 0;

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

static void oledRenderClock() {
  if (!clockSynced()) {
    oledCentered(13, "HAPPY JARZ");
    oledCentered(29, "CLOCK NOT SET");
    oledCentered(45, patternName + "  " + String(brightnessPercent) + "%");
    oledCentered(61, WiFi.status()==WL_CONNECTED ? "WIFI CONNECTED" : "USB READY");
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
  String bottom = String(alarmBuf);
  if (timerEnabled) bottom = timerText();
  else bottom += WiFi.status()==WL_CONNECTED ? "  WIFI" : "  USB";
  oledCentered(61, bottom);
}

static void oledRenderLights() {
  oledCentered(13, "LIGHTS");
  oledCentered(29, "L1  " + compactRgb(ledColor[0]));
  oledCentered(45, "L2  " + compactRgb(ledColor[1]));
  oledCentered(61, patternName + "  " + String(brightnessPercent) + "%");
}

static void oledRenderAlarmTimer() {
  char alarmBuf[22];
  snprintf(alarmBuf, sizeof(alarmBuf), alarmEnabled ? "ALARM %02u:%02u ON" : "ALARM OFF", alarmHour, alarmMinute);
  oledCentered(13, "ALARM + TIMER");
  oledCentered(29, String(alarmBuf));
  oledCentered(45, timerText());
  oledCentered(61, clockSynced() ? (WiFi.status()==WL_CONNECTED ? "TIME VIA WIFI" : "TIME VIA USB") : "TIME NOT SET");
}

static void oledRenderSystem() {
  oledCentered(13, "HAPPY JARZ");
  oledCentered(29, String(HJ_SERIAL_ID) + "  FW " + HJ_FW_VERSION);
  oledCentered(45, WiFi.status()==WL_CONNECTED ? "WIFI CONNECTED" : "WIFI OFFLINE");
  oledCentered(61, timezoneName);
}

static void serviceOled() {
  if (!oledReady || !oled) return;
  unsigned long now = millis();
  // Clock/timer content changes continuously; other pages can still redraw when dirty.
  if (!oledDirty && oledPage != 0 && !timerEnabled && now - oledLastDrawMs < 1000) return;
  if (now - oledLastDrawMs < 200) return;
  oledLastDrawMs = now;
  oledDirty = false;
  oled->clearBuffer();
  oled->setFont(u8g2_font_6x12_tr);
  switch (oledPage) {
    case 0: oledRenderClock(); break;
    case 1: oledRenderLights(); break;
    case 2: oledRenderAlarmTimer(); break;
    default: oledRenderSystem(); break;
  }
  oled->sendBuffer();
}
'''

s = s.replace(marker, marker + block, 1)

# Page navigation on LEFT/RIGHT; preserve existing JAR UP/DOWN/A/B behavior.
nav_needle = '''  if (inputMode == "JAR") {
'''
nav_repl = '''  if (q[IN_LEFT] && !latched[IN_LEFT]) { oledPage=(oledPage+OLED_PAGE_COUNT-1)%OLED_PAGE_COUNT; oledDirty=true; }
  if (q[IN_RIGHT] && !latched[IN_RIGHT]) { oledPage=(oledPage+1)%OLED_PAGE_COUNT; oledDirty=true; }

  if (inputMode == "JAR") {
'''
if nav_needle not in s:
    raise SystemExit("OLED patch failed: input navigation insertion point not found")
s = s.replace(nav_needle, nav_repl, 1)

# Make OLED respond immediately to display brightness commands.
old_bri = '''  if(line.startsWith("SET DISPLAY BRIGHTNESS ")){int v=line.substring(23).toInt();if(v<0||v>100)err("display brightness must be 0-100");else{displayBrightness=v;ack("SET DISPLAY BRIGHTNESS");}return;}'''
new_bri = '''  if(line.startsWith("SET DISPLAY BRIGHTNESS ")){int v=line.substring(23).toInt();if(v<0||v>100)err("display brightness must be 0-100");else{displayBrightness=v;oledApplyBrightness();oledDirty=true;ack("SET DISPLAY BRIGHTNESS");}return;}'''
if old_bri in s:
    s = s.replace(old_bri, new_bri, 1)

# Initialize after settings are loaded, before the LED/touch startup sequence.
setup_needle = '''  loadSettings();
  if(!initApa106Rmt())'''
setup_repl = '''  loadSettings();
  oledInit();
  if(!initApa106Rmt())'''
if setup_needle not in s:
    raise SystemExit("OLED patch failed: setup insertion point not found")
s = s.replace(setup_needle, setup_repl, 1)

# Keep display refreshed from live state.
loop_needle = '''  serviceTimer();
  static bool timeStarted=false;'''
loop_repl = '''  serviceTimer();
  serviceOled();
  static bool timeStarted=false;'''
if loop_needle not in s:
    raise SystemExit("OLED patch failed: loop insertion point not found")
s = s.replace(loop_needle, loop_repl, 1)

p.write_text(s, encoding="utf-8")
