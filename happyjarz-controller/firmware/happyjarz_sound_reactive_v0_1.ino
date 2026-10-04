// HAPPY JARZ — native-GRB peak-bucket 8-band sound color meter v2.3
//
// PURPOSE
//   Treat APA106 color bytes as GRB from end to end with no RGB->GRB swap.
//   Preserve the raw microphone capture and proven RMT timing.
//   Accumulate the loudest mic peak across a 120 ms bucket so speech peaks
//   are not missed, then update color once per bucket to avoid flicker.
//
// HARDWARE
//   ESP32-S3 SuperMini
//   HW-484 A0 -> GPIO8
//   GPIO7 -> 220 ohm -> APA106 #1 DIN -> APA106 #2 DIN
//   Local decoupling capacitor(s) across LED VCC/GND
//
// APA106 PHYSICAL BATCH
//   NATIVE GRB packet order
//   RMT 10 MHz
//   0 = 4 high / 14 low ticks
//   1 = 14 high / 4 low ticks
//   latch = 100 us low

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;

// Mic envelope window remains 10 ms. We collect the loudest value across
// 120 ms before choosing a new color.
static constexpr unsigned long COLOR_BUCKET_MS = 120;
static constexpr uint8_t FALL_CONFIRM_BUCKETS = 2; // ~240 ms fall hold

struct Grb { uint8_t g, r, b; };

static unsigned long bucketStart = 0;
static float bucketPeak = 0.0f;
static uint8_t currentBand = 0;
static uint8_t pendingLowerBand = 0;
static uint8_t pendingLowerCount = 0;

// Native GRB values: low sound -> high sound.
static const Grb BAND_COLORS[8] = {
  { 0,  0, 72},  // blue
  {32,  0, 72},  // cyan-blue
  {64,  0, 48},  // cyan-green
  {72,  0,  0},  // green
  {72, 48,  0},  // yellow-green
  {48, 72,  0},  // yellow
  {20, 72,  0},  // orange
  { 0, 72,  0}   // red
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

static void writeFrame(const Grb frame[LED_COUNT]) {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;

  for (uint8_t led = 0; led < LED_COUNT; ++led) {
    // Already stored in the exact APA106 wire order: G, R, B.
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
  Grb c = BAND_COLORS[band];
  Grb frame[LED_COUNT] = { c, c };
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
  if (raw <= 6.0f)  return 0;
  if (raw <= 8.0f)  return 1;
  if (raw <= 10.0f) return 2;
  if (raw <= 13.0f) return 3;
  if (raw <= 16.0f) return 4;
  if (raw <= 20.0f) return 5;
  if (raw <= 26.0f) return 6;
  return 7;
}

static void updateBandFromBucket(uint8_t targetBand) {
  // Any higher peak wins immediately at the end of the 120 ms bucket.
  if (targetBand > currentBand) {
    currentBand = targetBand;
    pendingLowerBand = currentBand;
    pendingLowerCount = 0;
    return;
  }

  if (targetBand == currentBand) {
    pendingLowerBand = currentBand;
    pendingLowerCount = 0;
    return;
  }

  // Falling requires two complete lower buckets (~240 ms).
  if (targetBand != pendingLowerBand) {
    pendingLowerBand = targetBand;
    pendingLowerCount = 1;
  } else if (pendingLowerCount < 255) {
    ++pendingLowerCount;
  }

  if (pendingLowerCount >= FALL_CONFIRM_BUCKETS) {
    currentBand = targetBand;
    pendingLowerCount = 0;
  }
}

void setup() {
  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    while (true) delay(1000);
  }

  // Slow native-GRB startup sweep.
  for (uint8_t band = 0; band < 8; ++band) {
    showBand(band);
    delay(140);
  }

  currentBand = 0;
  pendingLowerBand = 0;
  pendingLowerCount = 0;
  bucketPeak = 0.0f;
  bucketStart = millis();
  showBand(currentBand);
}

void loop() {
  float rawLevel = readSoundEnvelope();
  if (rawLevel > bucketPeak) bucketPeak = rawLevel;

  unsigned long now = millis();
  if (now - bucketStart >= COLOR_BUCKET_MS) {
    bucketStart = now;

    uint8_t targetBand = rawToBand(bucketPeak);
    updateBandFromBucket(targetBand);
    showBand(currentBand);

    bucketPeak = 0.0f;
  }
}
