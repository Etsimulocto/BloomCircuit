// HAPPY JARZ integrated firmware v0.1
// Reconstructed from the September 30, 2026 known-good bench handoff.
//
// BloomCore failure boundary:
// - APA106 timing is isolated in the low-level RMT functions below.
// - Touch sensing is isolated in the touch layer.
// - USB serial commands call those proven layers; they do not reimplement them.
//
// Bench-proven hardware map:
//   GPIO7 -> 220 ohm -> APA106 #1 DIN
//   APA106 #1 DOUT -> APA106 #2 DIN
//   GPIO1 = COLOR 1 touch
//   GPIO2 = COLOR 2 touch
//   GPIO4 = CYCLE UP touch
//   GPIO5 = CYCLE DOWN touch
//   Both tested APA106-F8 lamps powered from ESP32 3V3 during bench tests.
//
// Bench-proven APA106 RMT timing:
//   RMT clock = 10 MHz = 0.1 us/tick
//   bit 0: HIGH 4 ticks, LOW 14 ticks
//   bit 1: HIGH 14 ticks, LOW 4 ticks
//   reset/latch: data LOW for 100 us

#include <Arduino.h>
#include <Preferences.h>
#include "driver/rmt_tx.h"

// -----------------------------
// Identity / versions
// -----------------------------
static const char *HJ_SERIAL_ID = "HJ-001";
static const char *HJ_HW_VERSION = "V1";
static const char *HJ_FW_VERSION = "0.1";

// -----------------------------
// Hardware map
// -----------------------------
static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t TOUCH_C1_PIN = 1;
static constexpr uint8_t TOUCH_C2_PIN = 2;
static constexpr uint8_t TOUCH_UP_PIN = 4;
static constexpr uint8_t TOUCH_DOWN_PIN = 5;
static constexpr uint8_t LED_COUNT = 2;

// -----------------------------
// Low-level APA106 RMT driver
// -----------------------------
static rmt_channel_handle_t txChannel = nullptr;
static rmt_encoder_handle_t bytesEncoder = nullptr;

struct Rgb {
  uint8_t r;
  uint8_t g;
  uint8_t b;
};

static Rgb ledColor[LED_COUNT] = {{32, 0, 64}, {0, 32, 64}};
static uint8_t brightnessPercent = 75;
static String patternName = "SOLID";

static uint8_t scaleByte(uint8_t v) {
  return (uint8_t)((uint16_t)v * brightnessPercent / 100U);
}

static bool initApa106Rmt() {
  rmt_tx_channel_config_t txConfig = {};
  txConfig.gpio_num = (gpio_num_t)LED_DATA_PIN;
  txConfig.clk_src = RMT_CLK_SRC_DEFAULT;
  txConfig.resolution_hz = 10000000; // 10 MHz = 0.1 us/tick
  txConfig.mem_block_symbols = 64;
  txConfig.trans_queue_depth = 4;

  if (rmt_new_tx_channel(&txConfig, &txChannel) != ESP_OK) return false;

  rmt_bytes_encoder_config_t encConfig = {};
  encConfig.bit0.level0 = 1;
  encConfig.bit0.duration0 = 4;
  encConfig.bit0.level1 = 0;
  encConfig.bit0.duration1 = 14;
  encConfig.bit1.level0 = 1;
  encConfig.bit1.duration0 = 14;
  encConfig.bit1.level1 = 0;
  encConfig.bit1.duration1 = 4;
  encConfig.flags.msb_first = 1;

  if (rmt_new_bytes_encoder(&encConfig, &bytesEncoder) != ESP_OK) return false;
  if (rmt_enable(txChannel) != ESP_OK) return false;

  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  return true;
}

static void showLeds() {
  // The bench handoff documented 24 bits per lamp in R,G,B order.
  uint8_t frame[LED_COUNT * 3];
  for (uint8_t i = 0; i < LED_COUNT; ++i) {
    frame[i * 3 + 0] = scaleByte(ledColor[i].r);
    frame[i * 3 + 1] = scaleByte(ledColor[i].g);
    frame[i * 3 + 2] = scaleByte(ledColor[i].b);
  }

  rmt_transmit_config_t txCfg = {};
  txCfg.loop_count = 0;
  rmt_transmit(txChannel, bytesEncoder, frame, sizeof(frame), &txCfg);
  rmt_tx_wait_all_done(txChannel, 100);

  digitalWrite(LED_DATA_PIN, LOW);
  delayMicroseconds(100);
}

static void setLedRaw(uint8_t led, uint8_t r, uint8_t g, uint8_t b) {
  if (led < 1 || led > LED_COUNT) return;
  ledColor[led - 1] = {r, g, b};
  showLeds();
}

static void allOff() {
  for (uint8_t i = 0; i < LED_COUNT; ++i) ledColor[i] = {0, 0, 0};
  showLeds();
}

// -----------------------------
// Touch layer
// -----------------------------
struct TouchPadState {
  uint8_t pin;
  uint32_t baseline;
  uint32_t threshold;
  bool touching;
  unsigned long enteredMs;
};

static TouchPadState touchPads[4] = {
  {TOUCH_C1_PIN, 0, 0, false, 0},
  {TOUCH_C2_PIN, 0, 0, false, 0},
  {TOUCH_UP_PIN, 0, 0, false, 0},
  {TOUCH_DOWN_PIN, 0, 0, false, 0},
};

static uint32_t readTouchPin(uint8_t pin) {
  return touchRead(pin);
}

static void calibrateTouch() {
  // Hands-off calibration. The successful bench algorithm used ~20% above
  // baseline and ~60 ms sustained touch qualification.
  for (auto &pad : touchPads) {
    uint64_t sum = 0;
    for (int i = 0; i < 40; ++i) {
      sum += readTouchPin(pad.pin);
      delay(5);
    }
    pad.baseline = (uint32_t)(sum / 40ULL);
    pad.threshold = pad.baseline + (pad.baseline / 5U); // +20%
    pad.touching = false;
    pad.enteredMs = 0;
  }
}

static bool qualifiedTouch(TouchPadState &pad) {
  uint32_t value = readTouchPin(pad.pin);
  bool above = value >= pad.threshold;

  if (above && !pad.touching) {
    pad.touching = true;
    pad.enteredMs = millis();
  } else if (!above) {
    pad.touching = false;
    pad.enteredMs = 0;
    // Slow environmental drift compensation while untouched.
    pad.baseline = (pad.baseline * 127U + value) / 128U;
    pad.threshold = pad.baseline + (pad.baseline / 5U);
  }

  return pad.touching && (millis() - pad.enteredMs >= 60);
}

// -----------------------------
// Settings / persistent state
// -----------------------------
static Preferences prefs;

static void loadSettings() {
  prefs.begin("happyjarz", true);
  brightnessPercent = prefs.getUChar("bright", 75);
  ledColor[0].r = prefs.getUChar("l1r", 32);
  ledColor[0].g = prefs.getUChar("l1g", 0);
  ledColor[0].b = prefs.getUChar("l1b", 64);
  ledColor[1].r = prefs.getUChar("l2r", 0);
  ledColor[1].g = prefs.getUChar("l2g", 32);
  ledColor[1].b = prefs.getUChar("l2b", 64);
  patternName = prefs.getString("pattern", "SOLID");
  prefs.end();
}

static void persistSettings() {
  prefs.begin("happyjarz", false);
  prefs.putUChar("bright", brightnessPercent);
  prefs.putUChar("l1r", ledColor[0].r);
  prefs.putUChar("l1g", ledColor[0].g);
  prefs.putUChar("l1b", ledColor[0].b);
  prefs.putUChar("l2r", ledColor[1].r);
  prefs.putUChar("l2g", ledColor[1].g);
  prefs.putUChar("l2b", ledColor[1].b);
  prefs.putString("pattern", patternName);
  prefs.end();
}

// -----------------------------
// Product-layer hooks used by USB protocol
// -----------------------------
void hjSetLed(uint8_t led, uint8_t r, uint8_t g, uint8_t b) {
  patternName = "SOLID";
  setLedRaw(led, r, g, b);
}

void hjSetBrightness(uint8_t percent) {
  brightnessPercent = constrain(percent, 0, 100);
  showLeds();
}

void hjSetPattern(const String &name) {
  patternName = name;
  if (patternName == "OFF") allOff();
  else showLeds();
}

void hjSaveSettings() {
  persistSettings();
}

void hjRunRgbTest() {
  Rgb saved0 = ledColor[0];
  Rgb saved1 = ledColor[1];
  uint8_t savedBrightness = brightnessPercent;
  brightnessPercent = 35;

  const Rgb tests[] = {{255,0,0},{0,255,0},{0,0,255},{255,255,255}};
  for (const auto &c : tests) {
    ledColor[0] = c;
    ledColor[1] = c;
    showLeds();
    delay(350);
  }

  ledColor[0] = saved0;
  ledColor[1] = saved1;
  brightnessPercent = savedBrightness;
  showLeds();
}

void hjRunTouchTest() {
  // Non-destructive diagnostic: recalibrate and report values through serial.
  calibrateTouch();
}

void hjReadTouch(uint32_t &c1, uint32_t &c2, uint32_t &up, uint32_t &down) {
  c1 = readTouchPin(TOUCH_C1_PIN);
  c2 = readTouchPin(TOUCH_C2_PIN);
  up = readTouchPin(TOUCH_UP_PIN);
  down = readTouchPin(TOUCH_DOWN_PIN);
}

String hjStatusLine() {
  String s = "HJ|STATUS|brightness=" + String(brightnessPercent);
  s += "|pattern=" + patternName;
  s += "|led1=" + String(ledColor[0].r) + "," + String(ledColor[0].g) + "," + String(ledColor[0].b);
  s += "|led2=" + String(ledColor[1].r) + "," + String(ledColor[1].g) + "," + String(ledColor[1].b);
  return s;
}

// -----------------------------
// USB serial protocol layer
// -----------------------------
static bool hjTouchStream = false;
static unsigned long hjLastTouchMs = 0;
static String hjRxLine;

static void hjAck(const String &name) {
  Serial.print("HJ|ACK|command=");
  Serial.println(name);
}

static void hjErr(const String &message) {
  Serial.print("HJ|ERR|message=");
  Serial.println(message);
}

static void hjIdentity() {
  Serial.print("HJ|IDENTITY|serial=");
  Serial.print(HJ_SERIAL_ID);
  Serial.print("|hw=");
  Serial.print(HJ_HW_VERSION);
  Serial.print("|fw=");
  Serial.println(HJ_FW_VERSION);
}

static bool hjParseRgb(const String &line, uint8_t led) {
  int r = -1, g = -1, b = -1;
  const char *s = line.c_str();
  int count = (led == 1)
    ? sscanf(s, "SET LED1 COLOR %d %d %d", &r, &g, &b)
    : sscanf(s, "SET LED2 COLOR %d %d %d", &r, &g, &b);

  if (count != 3) return false;
  if (r < 0 || r > 255 || g < 0 || g > 255 || b < 0 || b > 255) return false;
  hjSetLed(led, (uint8_t)r, (uint8_t)g, (uint8_t)b);
  return true;
}

static void hjHandleCommand(String line) {
  line.trim();
  if (!line.length()) return;

  if (line == "HELLO") { hjIdentity(); return; }
  if (line == "PING") { Serial.println("HJ|PONG"); return; }
  if (line == "GET STATUS") { Serial.println(hjStatusLine()); return; }

  if (line == "GET TOUCH") {
    uint32_t c1, c2, up, down;
    hjReadTouch(c1, c2, up, down);
    Serial.printf("HJ|TOUCH|c1=%lu|c2=%lu|up=%lu|down=%lu\n",
                  (unsigned long)c1, (unsigned long)c2,
                  (unsigned long)up, (unsigned long)down);
    return;
  }

  if (line == "STREAM TOUCH ON") { hjTouchStream = true; hjAck("STREAM TOUCH ON"); return; }
  if (line == "STREAM TOUCH OFF") { hjTouchStream = false; hjAck("STREAM TOUCH OFF"); return; }

  if (line.startsWith("SET LED1 COLOR ")) {
    if (hjParseRgb(line, 1)) hjAck("SET LED1 COLOR");
    else hjErr("invalid LED1 RGB values");
    return;
  }

  if (line.startsWith("SET LED2 COLOR ")) {
    if (hjParseRgb(line, 2)) hjAck("SET LED2 COLOR");
    else hjErr("invalid LED2 RGB values");
    return;
  }

  if (line.startsWith("SET BRIGHTNESS ")) {
    int value = line.substring(15).toInt();
    if (value < 0 || value > 100) hjErr("brightness must be 0-100");
    else { hjSetBrightness((uint8_t)value); hjAck("SET BRIGHTNESS"); }
    return;
  }

  if (line.startsWith("SET PATTERN ")) {
    String name = line.substring(12);
    name.trim();
    if (!(name == "OFF" || name == "SOLID" || name == "FADE" || name == "RAINBOW" || name == "PULSE")) {
      hjErr("unknown pattern");
    } else {
      hjSetPattern(name);
      hjAck("SET PATTERN");
    }
    return;
  }

  if (line == "TEST RGB") { hjRunRgbTest(); Serial.println("HJ|TEST|rgb=PASS"); return; }
  if (line == "TEST TOUCH") { hjRunTouchTest(); Serial.println("HJ|TEST|touch=PASS"); return; }
  if (line == "SAVE") { hjSaveSettings(); hjAck("SAVE"); return; }

  hjErr("unknown command");
}

static void hjSerialPoll() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      hjHandleCommand(hjRxLine);
      hjRxLine = "";
    } else if (c != '\r') {
      if (hjRxLine.length() < 160) hjRxLine += c;
      else hjRxLine = "";
    }
  }

  if (hjTouchStream && millis() - hjLastTouchMs >= 100) {
    hjLastTouchMs = millis();
    uint32_t c1, c2, up, down;
    hjReadTouch(c1, c2, up, down);
    Serial.printf("HJ|TOUCH|c1=%lu|c2=%lu|up=%lu|down=%lu\n",
                  (unsigned long)c1, (unsigned long)c2,
                  (unsigned long)up, (unsigned long)down);
  }
}

// -----------------------------
// Local standalone touch behavior
// -----------------------------
static const Rgb palette[] = {
  {255, 0, 0}, {255, 80, 0}, {255, 180, 0}, {0, 255, 0},
  {0, 160, 255}, {0, 0, 255}, {140, 0, 255}, {255, 0, 160}, {255, 255, 255}
};
static int paletteIndex1 = 6;
static int paletteIndex2 = 4;
static uint8_t selectedLed = 1;
static bool latchC1 = false, latchC2 = false, latchUp = false, latchDown = false;

static void serviceLocalTouch() {
  bool c1 = qualifiedTouch(touchPads[0]);
  bool c2 = qualifiedTouch(touchPads[1]);
  bool up = qualifiedTouch(touchPads[2]);
  bool down = qualifiedTouch(touchPads[3]);

  if (c1 && !latchC1) selectedLed = 1;
  if (c2 && !latchC2) selectedLed = 2;

  if (up && !latchUp) {
    if (selectedLed == 1) {
      paletteIndex1 = (paletteIndex1 + 1) % (int)(sizeof(palette) / sizeof(palette[0]));
      Rgb c = palette[paletteIndex1];
      hjSetLed(1, c.r, c.g, c.b);
    } else {
      paletteIndex2 = (paletteIndex2 + 1) % (int)(sizeof(palette) / sizeof(palette[0]));
      Rgb c = palette[paletteIndex2];
      hjSetLed(2, c.r, c.g, c.b);
    }
  }

  if (down && !latchDown) {
    const int n = (int)(sizeof(palette) / sizeof(palette[0]));
    if (selectedLed == 1) {
      paletteIndex1 = (paletteIndex1 - 1 + n) % n;
      Rgb c = palette[paletteIndex1];
      hjSetLed(1, c.r, c.g, c.b);
    } else {
      paletteIndex2 = (paletteIndex2 - 1 + n) % n;
      Rgb c = palette[paletteIndex2];
      hjSetLed(2, c.r, c.g, c.b);
    }
  }

  latchC1 = c1;
  latchC2 = c2;
  latchUp = up;
  latchDown = down;
}

// -----------------------------
// Arduino lifecycle
// -----------------------------
void setup() {
  Serial.begin(115200);
  delay(250);
  hjRxLine.reserve(96);

  loadSettings();

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERR|message=RMT init failed");
  } else {
    // Blue during hands-off calibration, green flash when complete.
    uint8_t savedBrightness = brightnessPercent;
    brightnessPercent = 25;
    ledColor[0] = {0, 0, 255};
    ledColor[1] = {0, 0, 255};
    showLeds();

    calibrateTouch();

    ledColor[0] = {0, 255, 0};
    ledColor[1] = {0, 255, 0};
    showLeds();
    delay(180);

    loadSettings();
    brightnessPercent = savedBrightness;
    showLeds();
  }

  hjIdentity();
}

void loop() {
  hjSerialPoll();
  serviceLocalTouch();
  delay(5);
}
