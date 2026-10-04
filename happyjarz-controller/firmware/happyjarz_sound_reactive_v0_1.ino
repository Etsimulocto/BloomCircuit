// HAPPY JARZ — standalone raw-peak 8-band sound color meter v1.9
//
// PURPOSE
//   Preserve the proven APA106 RMT driver and 25 FPS LED ceiling.
//   Remove all microphone floor subtraction, gain, hold, smoothing, and caps.
//   The LED color uses the loudest raw 10 ms envelope observed during each
//   40 ms LED frame window so short claps/transients are not missed.
//
// HARDWARE
//   ESP32-S3 SuperMini
//   HW-484 A0 -> GPIO8
//   GPIO7 -> 220 ohm -> APA106 #1 DIN -> APA106 #2 DIN
//   Local decoupling capacitor(s) across LED VCC/GND
//
// APA106 PHYSICAL BATCH
//   GRB packet order
//   RMT 10 MHz
//   0 = 4 high / 14 low ticks
//   1 = 14 high / 4 low ticks
//   latch = 100 us low
//   LED refresh capped at 25 FPS

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;
static constexpr unsigned long LED_FRAME_MS = 40;

struct Rgb { uint8_t r, g, b; };

static unsigned long lastLedFrame = 0;
static float framePeak = 0.0f;

static const Rgb BAND_COLORS[8] = {
  {0,   0,  72},  // raw 0-8    blue
  {0,  32,  72},  // raw 9-14   cyan-blue
  {0,  64,  48},  // raw 15-20  cyan-green
  {0,  72,   0},  // raw 21-27  green
  {48, 72,   0},  // raw 28-35  yellow-green
  {72, 48,   0},  // raw 36-45  yellow
  {72, 20,   0},  // raw 46-60  orange
  {72,  0,   0}   // raw 61+    red
};

static bool initApa106Rmt() {
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  if (!rmtInit(LED_DATA_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) {
    return false;
  }
  rmtSetEOT(LED_DATA_PIN, 0);
  return true;
}

static void writeFrame(const Rgb frame[LED_COUNT]) {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;

  for (uint8_t led = 0; led < LED_COUNT; ++led) {
    uint8_t bytes[3] = { frame[led].g, frame[led].r, frame[led].b };

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
  Rgb c = BAND_COLORS[band];
  Rgb frame[LED_COUNT] = { c, c };
  writeFrame(frame);
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
  if (raw <= 8.0f)  return 0;
  if (raw <= 14.0f) return 1;
  if (raw <= 20.0f) return 2;
  if (raw <= 27.0f) return 3;
  if (raw <= 35.0f) return 4;
  if (raw <= 45.0f) return 5;
  if (raw <= 60.0f) return 6;
  return 7;
}

void setup() {
  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    while (true) delay(1000);
  }

  // Visual startup sweep only. No microphone calibration is performed.
  for (uint8_t band = 0; band < 8; ++band) {
    showBand(band);
    delay(120);
  }

  showBand(0);
  framePeak = 0.0f;
  lastLedFrame = millis();
}

void loop() {
  float rawLevel = readSoundEnvelope();

  // Keep the loudest 10 ms envelope seen during this 40 ms LED frame.
  if (rawLevel > framePeak) framePeak = rawLevel;

  unsigned long now = millis();
  if (now - lastLedFrame >= LED_FRAME_MS) {
    lastLedFrame = now;

    uint8_t band = rawToBand(framePeak);
    showBand(band);

    // Start collecting the next 40 ms frame peak.
    framePeak = 0.0f;
  }
}
