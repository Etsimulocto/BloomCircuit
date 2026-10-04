// HAPPY JARZ — RGB single-LED sound color meter v3.1
//
// PROVEN ON BENCH
//   raw byte 1 = RED
//   raw byte 2 = GREEN
//   raw byte 3 = BLUE
//   therefore this physical APA106 is RGB wire order.
//
// HARDWARE
//   ESP32-S3 SuperMini
//   HW-484 A0 -> GPIO8
//   GPIO7 -> 220 ohm -> ONE APA106 DIN
//
// LIVE TRIM
//   The Pi trim app can adjust FLOOR, PEAK, HOLD and BRIGHTNESS live.
//   Telemetry is OFF unless the app explicitly sends STREAM 1, so the
//   controller remains standalone and cannot fill a Serial output buffer.
//   SAVE stores the current trim values in ESP32 NVS.

#include <Arduino.h>
#include <Preferences.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 1;
static constexpr unsigned long COLOR_BUCKET_MS = 120;

struct Rgb { uint8_t r, g, b; };

static Preferences prefs;
static unsigned long bucketStart = 0;
static unsigned long lastRiseTime = 0;
static float bucketPeak = 0.0f;
static uint8_t currentBand = 0;
static bool streamEnabled = false;
static String commandBuffer;

// Defaults match the working bench behavior, but are now tunable.
static float floorRaw = 6.0f;
static float peakRaw = 30.0f;
static uint16_t peakHoldMs = 240;
static uint8_t brightness = 72;

// Full-strength palette. Brightness is applied when written.
static const Rgb BAND_COLORS[8] = {
  {  0,   0, 255},  // blue
  {  0, 110, 255},  // cyan-blue
  {  0, 220, 170},  // cyan-green
  {  0, 255,   0},  // green
  {170, 255,   0},  // yellow-green
  {255, 170,   0},  // yellow
  {255,  70,   0},  // orange
  {255,   0,   0}   // red
};

static uint8_t scaleChannel(uint8_t value) {
  return (uint8_t)(((uint16_t)value * brightness) / 255U);
}

static bool initApa106Rmt() {
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  if (!rmtInit(LED_DATA_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) {
    return false;
  }
  rmtSetEOT(LED_DATA_PIN, 0);
  return true;
}

static void writeRgb(uint8_t r, uint8_t g, uint8_t b) {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;
  uint8_t bytes[3] = { r, g, b };  // proven physical wire order

  for (uint8_t led = 0; led < LED_COUNT; ++led) {
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

static void showBand(uint8_t band) {
  if (band > 7) band = 7;
  const Rgb &c = BAND_COLORS[band];
  writeRgb(scaleChannel(c.r), scaleChannel(c.g), scaleChannel(c.b));
}

static float readSoundEnvelope() {
  constexpr uint32_t SAMPLE_WINDOW_US = 10000;
  uint32_t start = micros();
  int minimum = 4095;
  int maximum = 0;

  while ((uint32_t)(micros() - start) < SAMPLE_WINDOW_US) {
    int sample = analogRead(MIC_PIN);
    if (sample < minimum) minimum = sample;
    if (sample > maximum) maximum = sample;
  }

  return (float)(maximum - minimum);
}

static uint8_t rawToBand(float raw) {
  if (raw <= floorRaw) return 0;
  if (raw >= peakRaw) return 7;

  float span = peakRaw - floorRaw;
  if (span < 1.0f) span = 1.0f;
  float normalized = (raw - floorRaw) / span;

  // Anything above the floor gets bands 2..7, with peak reserved for red.
  uint8_t band = 1 + (uint8_t)(normalized * 6.0f);
  if (band > 6) band = 6;
  return band;
}

static void updateBandFromBucket(uint8_t targetBand, unsigned long now) {
  if (targetBand > currentBand) {
    currentBand = targetBand;
    lastRiseTime = now;
    return;
  }

  if (targetBand == currentBand) return;

  if (now - lastRiseTime >= peakHoldMs) {
    currentBand = targetBand;
  }
}

static void printConfig() {
  if (!Serial) return;
  Serial.printf("HJ|CFG|FLOOR=%.0f|PEAK=%.0f|HOLD=%u|BRIGHT=%u\n",
                floorRaw, peakRaw, (unsigned)peakHoldMs, (unsigned)brightness);
}

static void saveConfig() {
  prefs.begin("happyjarz", false);
  prefs.putFloat("floor", floorRaw);
  prefs.putFloat("peak", peakRaw);
  prefs.putUShort("hold", peakHoldMs);
  prefs.putUChar("bright", brightness);
  prefs.end();
}

static void loadConfig() {
  prefs.begin("happyjarz", true);
  floorRaw = prefs.getFloat("floor", 6.0f);
  peakRaw = prefs.getFloat("peak", 30.0f);
  peakHoldMs = prefs.getUShort("hold", 240);
  brightness = prefs.getUChar("bright", 72);
  prefs.end();

  if (floorRaw < 0.0f || floorRaw > 200.0f) floorRaw = 6.0f;
  if (peakRaw <= floorRaw + 1.0f || peakRaw > 1000.0f) peakRaw = 30.0f;
  if (peakHoldMs > 3000) peakHoldMs = 240;
  if (brightness < 4) brightness = 72;
}

static void handleCommand(String cmd) {
  cmd.trim();
  if (!cmd.length()) return;

  if (cmd == "STREAM 1") {
    streamEnabled = true;
    Serial.println("HJ|ACK|STREAM=1");
    printConfig();
    return;
  }
  if (cmd == "STREAM 0") {
    streamEnabled = false;
    Serial.println("HJ|ACK|STREAM=0");
    return;
  }
  if (cmd == "GET") {
    printConfig();
    return;
  }
  if (cmd == "SAVE") {
    saveConfig();
    Serial.println("HJ|ACK|SAVED=1");
    printConfig();
    return;
  }
  if (cmd == "DEFAULTS") {
    floorRaw = 6.0f;
    peakRaw = 30.0f;
    peakHoldMs = 240;
    brightness = 72;
    Serial.println("HJ|ACK|DEFAULTS=1");
    printConfig();
    return;
  }

  if (cmd.startsWith("SET FLOOR ")) {
    float v = cmd.substring(10).toFloat();
    if (v >= 0.0f && v < peakRaw - 1.0f) floorRaw = v;
    printConfig();
    return;
  }
  if (cmd.startsWith("SET PEAK ")) {
    float v = cmd.substring(9).toFloat();
    if (v > floorRaw + 1.0f && v <= 1000.0f) peakRaw = v;
    printConfig();
    return;
  }
  if (cmd.startsWith("SET HOLD ")) {
    int v = cmd.substring(9).toInt();
    if (v >= 0 && v <= 3000) peakHoldMs = (uint16_t)v;
    printConfig();
    return;
  }
  if (cmd.startsWith("SET BRIGHT ")) {
    int v = cmd.substring(11).toInt();
    if (v >= 4 && v <= 255) brightness = (uint8_t)v;
    showBand(currentBand);
    printConfig();
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
  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);
  loadConfig();

  if (!initApa106Rmt()) {
    while (true) delay(1000);
  }

  // Short proven RGB sanity sweep.
  writeRgb(scaleChannel(255), 0, 0); delay(250);
  writeRgb(0, scaleChannel(255), 0); delay(250);
  writeRgb(0, 0, scaleChannel(255)); delay(250);

  currentBand = 0;
  bucketPeak = 0.0f;
  bucketStart = millis();
  lastRiseTime = 0;
  showBand(currentBand);
}

void loop() {
  serviceSerial();

  float rawLevel = readSoundEnvelope();
  if (rawLevel > bucketPeak) bucketPeak = rawLevel;

  unsigned long now = millis();
  if (now - bucketStart >= COLOR_BUCKET_MS) {
    bucketStart = now;

    float measuredPeak = bucketPeak;
    uint8_t targetBand = rawToBand(measuredPeak);
    updateBandFromBucket(targetBand, now);
    showBand(currentBand);

    // Telemetry only exists while the app explicitly requests it.
    if (streamEnabled && Serial.availableForWrite() >= 48) {
      Serial.printf("HJ|METER|RAW=%.0f|TARGET=%u|BAND=%u\n",
                    measuredPeak,
                    (unsigned)(targetBand + 1),
                    (unsigned)(currentBand + 1));
    }

    bucketPeak = 0.0f;
  }
}
