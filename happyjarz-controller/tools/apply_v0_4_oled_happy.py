#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FW = ROOT / "happyjarz-controller" / "firmware" / "happyjarz_integrated_v0_1.ino"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"PATCH FAILED: could not find {label}")
    return text.replace(old, new, 1)


s = FW.read_text()

s = replace_once(
    s,
    'static const char *HJ_FW_VERSION = "0.3";',
    'static const char *HJ_FW_VERSION = "0.4";',
    "firmware version 0.3",
)

s = replace_once(
    s,
    '#include <Preferences.h>\n#include "esp32-hal-rmt.h"',
    '#include <Preferences.h>\n#include <Wire.h>\n#include <Adafruit_GFX.h>\n#include <Adafruit_SSD1306.h>\n#include "esp32-hal-rmt.h"',
    "OLED includes anchor",
)

s = replace_once(
    s,
    'static constexpr uint8_t LED_COUNT = 2;\n',
    '''static constexpr uint8_t LED_COUNT = 2;\n\n// Tiny 128x64 I2C OLED (proven at address 0x3C)\nstatic constexpr uint8_t OLED_SDA_PIN = 8;\nstatic constexpr uint8_t OLED_SCL_PIN = 6;\nstatic constexpr uint8_t OLED_ADDR = 0x3C;\nstatic constexpr int OLED_WIDTH = 128;\nstatic constexpr int OLED_HEIGHT = 64;\nstatic constexpr int OLED_RESET = -1;\nstatic Adafruit_SSD1306 display(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET);\nstatic bool oledReady = false;\nstatic unsigned long oledBootStartedMs = 0;\nstatic unsigned long oledLastMessageMs = 0;\nstatic uint8_t oledMessageIndex = 0;\n\n''',
    "LED count anchor",
)

# OLED helper layer: compact, non-blocking, and independent of LED/touch timing.
oled_helpers = r'''
// -----------------------------
// OLED happy-message layer
// -----------------------------
static const char *happyMessages[][3] = {
  {"YOU GOT THIS", "ONE LITTLE", "STEP AT A TIME"},
  {"BE GENTLE", "WITH YOURSELF", "TODAY"},
  {"SMALL JOY", "STILL COUNTS", ":)"},
  {"KEEP GOING", "YOU ARE DOING", "BETTER THAN U THINK"},
  {"BREATHE IN", "BREATHE OUT", "YOU ARE HERE"},
  {"MAKE ROOM", "FOR A LITTLE", "HAPPY"},
  {"YOUR LIGHT", "MATTERS", "KEEP SHINING"},
  {"TODAY CAN", "STILL HAVE", "GOOD IN IT"},
  {"REST IS", "PART OF THE", "JOURNEY"},
  {"YOU DESERVE", "A SOFT", "MOMENT"},
  {"NOTICE ONE", "GOOD THING", "RIGHT NOW"},
  {"THE ANSWER", "IS WITHIN", "<3"},
};

static const uint8_t happyMessageCount = sizeof(happyMessages) / sizeof(happyMessages[0]);

static void oledClearAndHeader(const char *header) {
  if (!oledReady) return;
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(header);
  display.drawLine(0, 10, 127, 10, SSD1306_WHITE);
}

static void showBootStats() {
  if (!oledReady) return;
  oledClearAndHeader("HAPPY JARZ");
  display.setCursor(0, 16);
  display.print("FW: ");
  display.println(HJ_FW_VERSION);
  display.print("BRIGHT: ");
  display.print(brightnessPercent);
  display.println("%");
  display.print("PATTERN: ");
  display.println(patternName);
  display.print("OLED: 0x");
  display.println(OLED_ADDR, HEX);
  display.display();
}

static void showHappyMessage(uint8_t index) {
  if (!oledReady || happyMessageCount == 0) return;
  index %= happyMessageCount;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("HAPPY JARZ");
  display.drawLine(0, 10, 127, 10, SSD1306_WHITE);

  display.setTextSize(1);
  display.setCursor(4, 19);
  display.println(happyMessages[index][0]);
  display.setCursor(4, 33);
  display.println(happyMessages[index][1]);
  display.setCursor(4, 47);
  display.println(happyMessages[index][2]);
  display.display();
}

static void initOled() {
  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  oledReady = display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR);
  if (!oledReady) {
    Serial.println("HJ|WARN|message=OLED init failed");
    return;
  }

  oledBootStartedMs = millis();
  oledLastMessageMs = 0;
  oledMessageIndex = 0;
  showBootStats();
}

static void serviceOled() {
  if (!oledReady) return;

  unsigned long now = millis();

  // First four seconds: service/status screen.
  if (now - oledBootStartedMs < 4000UL) return;

  // Immediately show the first saying after the boot screen.
  if (oledLastMessageMs == 0) {
    showHappyMessage(oledMessageIndex);
    oledLastMessageMs = now;
    return;
  }

  // Then rotate sayings every seven seconds.
  if (now - oledLastMessageMs >= 7000UL) {
    oledMessageIndex = (oledMessageIndex + 1) % happyMessageCount;
    showHappyMessage(oledMessageIndex);
    oledLastMessageMs = now;
  }
}

'''

s = replace_once(
    s,
    '// -----------------------------\n// Non-blocking pattern engine\n// -----------------------------\n',
    oled_helpers + '// -----------------------------\n// Non-blocking pattern engine\n// -----------------------------\n',
    "pattern engine heading",
)

# Initialize the OLED only after the existing LED/touch boot calibration has completed,
# so the known-good commissioning behavior remains untouched.
s = replace_once(
    s,
    '  hjIdentity();\n}\n\nvoid loop() {',
    '  initOled();\n  hjIdentity();\n}\n\nvoid loop() {',
    "setup identity anchor",
)

s = replace_once(
    s,
    '  serviceLocalTouch();\n  servicePattern();\n  delay(5);',
    '  serviceLocalTouch();\n  servicePattern();\n  serviceOled();\n  delay(5);',
    "main loop services",
)

FW.write_text(s)

print("HAPPY JARZ v0.4 OLED patch applied")
print("Firmware:", FW)
print("OLED: SDA GPIO8, SCL GPIO6, address 0x3C")
print("Boot: 4-second stats screen")
print("Then: rotating happy sayings every 7 seconds")
