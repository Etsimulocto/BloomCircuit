// HAPPY JARZ / CLUB BOX — 16-pixel direct line-in bench diagnostic v3.5
//
// PURPOSE
//   Validate mono 1/8-inch line input on GPIO9 before FFT/EQ.
//   Drive/test a 16-pixel APA106 RGB chain using the proven custom RMT timing.
//   Telemetry is OFF unless the Pi app explicitly enables it.
//
// LINE INPUT — REBUILT BENCH CIRCUIT
//   TRS TIP -> 10uF coupling capacitor -> GPIO9 bias node
//   capacitor negative/striped side -> TRS TIP
//   capacitor positive side -> GPIO9 bias node
//   GPIO9 bias node -> 10k -> 3V3
//   GPIO9 bias node -> 10k -> GND
//   TRS SLEEVE -> common GND
//   TRS RING unused for mono test
//   No extra series 10k on TIP in this bench revision.
//
// LED OUTPUT
//   GPIO7 -> 220 ohm -> APA106 DIN
//   16 pixels expected in chain
//   Proven physical byte order: RGB
//
// IMPORTANT
//   16 LEDs must NOT be powered from ESP32 3V3 in the finished array.
//   Use an adequate external LED supply with common ground.

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t LINE_IN_PIN = 9;
static constexpr uint8_t LED_COUNT = 16;
static constexpr uint32_t SAMPLE_WINDOW_US = 20000;
static constexpr unsigned long TELEMETRY_MS = 100;

struct Rgb { uint8_t r, g, b; };

static bool streamEnabled = false;
static String commandBuffer;
static unsigned long lastTelemetry = 0;
static uint8_t brightness = 48;

struct LineStats {
  uint16_t minimum;
  uint16_t maximum;
  uint16_t center;
  uint16_t p2p;
  uint16_t lowHeadroom;
  uint16_t highHeadroom;
  bool clipped;
};

static uint8_t scaleChannel(uint8_t value) {
  return (uint8_t)(((uint16_t)value * brightness) / 255U);
}

static bool initApa106Rmt() {
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  if (!rmtInit(LED_DATA_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) return false;
  rmtSetEOT(LED_DATA_PIN, 0);
  return true;
}

static void writePixels(const Rgb pixels[LED_COUNT]) {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;

  for (uint8_t led = 0; led < LED_COUNT; ++led) {
    uint8_t bytes[3] = {
      scaleChannel(pixels[led].r),
      scaleChannel(pixels[led].g),
      scaleChannel(pixels[led].b)
    };

    for (uint8_t c = 0; c < 3; ++c) {
      for (int bit = 7; bit >= 0; --bit) {
        bool one = bytes[c] & (1U << bit);
        symbols[n].level0 = 1;
        symbols[n].duration0 = one ? 14 : 4;
        symbols[n].level1 = 0;
        symbols[n].duration1 = one ? 4 : 14;
        ++n;
      }
    }
  }

  rmtWrite(LED_DATA_PIN, symbols, n, RMT_WAIT_FOR_EVER);
  digitalWrite(LED_DATA_PIN, LOW);
  delayMicroseconds(100);
}

static void allOff() {
  Rgb pixels[LED_COUNT] = {};
  writePixels(pixels);
}

static void allColor(uint8_t r, uint8_t g, uint8_t b) {
  Rgb pixels[LED_COUNT];
  for (uint8_t i = 0; i < LED_COUNT; ++i) pixels[i] = {r, g, b};
  writePixels(pixels);
}

static void rgbTest() {
  allColor(255, 0, 0); delay(300);
  allColor(0, 255, 0); delay(300);
  allColor(0, 0, 255); delay(300);
  allOff();
}

static void chaseTest() {
  Rgb pixels[LED_COUNT] = {};
  for (uint8_t i = 0; i < LED_COUNT; ++i) {
    for (uint8_t j = 0; j < LED_COUNT; ++j) pixels[j] = {0, 0, 0};
    switch (i % 6) {
      case 0: pixels[i] = {255, 0, 0}; break;
      case 1: pixels[i] = {255, 100, 0}; break;
      case 2: pixels[i] = {0, 255, 0}; break;
      case 3: pixels[i] = {0, 180, 255}; break;
      case 4: pixels[i] = {0, 0, 255}; break;
      default: pixels[i] = {180, 0, 255}; break;
    }
    writePixels(pixels);
    delay(100);
  }
  allOff();
}

static LineStats sampleLine() {
  uint32_t start = micros();
  uint32_t sum = 0;
  uint32_t count = 0;
  uint16_t minimum = 4095;
  uint16_t maximum = 0;

  while ((uint32_t)(micros() - start) < SAMPLE_WINDOW_US) {
    uint16_t s = (uint16_t)analogRead(LINE_IN_PIN);
    if (s < minimum) minimum = s;
    if (s > maximum) maximum = s;
    sum += s;
    ++count;
  }

  uint16_t center = count ? (uint16_t)(sum / count) : 0;
  uint16_t p2p = maximum - minimum;
  uint16_t lowHeadroom = minimum;
  uint16_t highHeadroom = 4095 - maximum;
  bool clipped = (minimum <= 25 || maximum >= 4070);
  return {minimum, maximum, center, p2p, lowHeadroom, highHeadroom, clipped};
}

static void printStats(const LineStats &s) {
  if (!Serial) return;
  Serial.printf("HJ|LINE|CENTER=%u|MIN=%u|MAX=%u|P2P=%u|LOWHR=%u|HIGHHR=%u|CLIP=%u|BRIGHT=%u|LEDS=%u\n",
                (unsigned)s.center,
                (unsigned)s.minimum,
                (unsigned)s.maximum,
                (unsigned)s.p2p,
                (unsigned)s.lowHeadroom,
                (unsigned)s.highHeadroom,
                s.clipped ? 1U : 0U,
                (unsigned)brightness,
                (unsigned)LED_COUNT);
}

static void handleCommand(String cmd) {
  cmd.trim();
  if (!cmd.length()) return;

  if (cmd == "STREAM 1") { streamEnabled = true; Serial.println("HJ|ACK|STREAM=1"); return; }
  if (cmd == "STREAM 0") { streamEnabled = false; Serial.println("HJ|ACK|STREAM=0"); return; }
  if (cmd == "GET") { printStats(sampleLine()); return; }
  if (cmd == "TEST RGB") { Serial.println("HJ|ACK|TEST=RGB"); rgbTest(); return; }
  if (cmd == "TEST CHASE") { Serial.println("HJ|ACK|TEST=CHASE"); chaseTest(); return; }
  if (cmd == "TEST ALL") { Serial.println("HJ|ACK|TEST=ALL"); allColor(255,255,255); delay(600); allOff(); return; }
  if (cmd == "TEST OFF") { allOff(); Serial.println("HJ|ACK|TEST=OFF"); return; }
  if (cmd.startsWith("SET BRIGHT ")) {
    int v = cmd.substring(11).toInt();
    if (v >= 4 && v <= 128) brightness = (uint8_t)v;
    Serial.printf("HJ|ACK|BRIGHT=%u\n", (unsigned)brightness);
    return;
  }
}

static void serviceSerial() {
  while (Serial.available() > 0) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (commandBuffer.length()) {
        handleCommand(commandBuffer);
        commandBuffer = "";
      }
    } else if (commandBuffer.length() < 96) {
      commandBuffer += ch;
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LINE_IN_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) while (true) delay(1000);

  rgbTest();
  lastTelemetry = millis();
}

void loop() {
  serviceSerial();

  unsigned long now = millis();
  if (streamEnabled && now - lastTelemetry >= TELEMETRY_MS) {
    lastTelemetry = now;
    LineStats s = sampleLine();
    if (Serial.availableForWrite() >= 96) printStats(s);
  }
}
