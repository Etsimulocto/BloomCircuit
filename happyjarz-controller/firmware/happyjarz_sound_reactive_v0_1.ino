// HAPPY JARZ — standalone direct-threshold sound color meter v1.8
//
// PURPOSE
//   Keep the proven 25 FPS APA106 update path, but remove gain/smoothing/hold.
//   Sound response is now direct:
//     raw peak-to-peak -> subtract calibrated floor -> fixed thresholds -> color
//
// IMPORTANT
//   The HW-484 is not calibrated in true acoustic dB SPL.
//   These are direct envelope-above-floor thresholds chosen from observed bench values.
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

static float noiseFloor = 12.0f;
static constexpr float FLOOR_MARGIN = 1.5f;

struct Rgb { uint8_t r, g, b; };

static unsigned long lastLedFrame = 0;

static const Rgb BAND_COLORS[8] = {
  {0,   0,  72},  // 0-5 blue
  {0,  32,  72},  // 6-10 cyan-blue
  {0,  64,  48},  // 11-15 cyan-green
  {0,  72,   0},  // 16-20 green
  {48, 72,   0},  // 21-25 yellow-green
  {72, 48,   0},  // 26-30 yellow
  {72, 20,   0},  // 31-40 orange
  {72,  0,   0}   // 41+ red
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

static void calibrateMicrophone() {
  showBand(0);

  constexpr int CAL_SAMPLES = 100;
  float sum = 0.0f;
  float peak = 0.0f;

  for (int i = 0; i < CAL_SAMPLES; ++i) {
    float v = readSoundEnvelope();
    sum += v;
    if (v > peak) peak = v;
  }

  float average = sum / (float)CAL_SAMPLES;
  noiseFloor = constrain(max(average + FLOOR_MARGIN, peak * 0.85f), 6.0f, 18.0f);
}

static uint8_t levelToBand(float level) {
  if (level <= 5.0f)  return 0;
  if (level <= 10.0f) return 1;
  if (level <= 15.0f) return 2;
  if (level <= 20.0f) return 3;
  if (level <= 25.0f) return 4;
  if (level <= 30.0f) return 5;
  if (level <= 40.0f) return 6;
  return 7;
}

void setup() {
  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    while (true) delay(1000);
  }

  // Slow visual startup sweep to confirm LED chain initialized.
  for (uint8_t band = 0; band < 8; ++band) {
    showBand(band);
    delay(120);
  }

  calibrateMicrophone();
  lastLedFrame = millis();
}

void loop() {
  float rawLevel = readSoundEnvelope();
  float above = rawLevel - noiseFloor;
  if (above < 0.0f) above = 0.0f;

  uint8_t band = levelToBand(above);

  unsigned long now = millis();
  if (now - lastLedFrame >= LED_FRAME_MS) {
    lastLedFrame = now;
    showBand(band);
  }
}
