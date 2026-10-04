// HAPPY JARZ — peak-bucket meter diagnostic v2.5
//
// PURPOSE
//   Keep the proven microphone thresholds, 120 ms peak bucket, fall hold,
//   RMT timing, and telemetry exactly as v2.4.
//   Only change the LED red/green wire-byte order based on live evidence:
//     TARGET=8 and BAND=8 were logged while the physical LED appeared green.
//   Therefore the first two transmitted color bytes were reversed relative
//   to the previous assumption. This build sends physical RGB byte order.
//
// HARDWARE
//   ESP32-S3 SuperMini
//   HW-484 A0 -> GPIO8
//   GPIO7 -> 220 ohm -> APA106 #1 DIN -> APA106 #2 DIN
//   Local decoupling capacitor(s) across LED VCC/GND
//
// APA106 PHYSICAL BATCH
//   RMT 10 MHz
//   0 = 4 high / 14 low ticks
//   1 = 14 high / 4 low ticks
//   latch = 100 us low

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;
static constexpr unsigned long COLOR_BUCKET_MS = 120;
static constexpr uint8_t FALL_CONFIRM_BUCKETS = 2;

struct Rgb { uint8_t r, g, b; };

static unsigned long bucketStart = 0;
static float bucketPeak = 0.0f;
static uint8_t currentBand = 0;
static uint8_t pendingLowerBand = 0;
static uint8_t pendingLowerCount = 0;

static const Rgb BAND_COLORS[8] = {
  { 0,  0, 72},  // blue
  { 0, 32, 72},  // cyan-blue
  { 0, 64, 48},  // cyan-green
  { 0, 72,  0},  // green
  {48, 72,  0},  // yellow-green
  {72, 48,  0},  // yellow
  {72, 20,  0},  // orange
  {72,  0,  0}   // red
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
    // Live meter proved red/green were reversed in the previous wire order.
    // Send bytes in physical RGB order for this LED batch.
    uint8_t bytes[3] = { frame[led].r, frame[led].g, frame[led].b };

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
  // Serial is telemetry only. The light logic never waits for a monitor.
  Serial.begin(115200);

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    while (true) delay(1000);
  }

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

    float measuredPeak = bucketPeak;
    uint8_t targetBand = rawToBand(measuredPeak);
    updateBandFromBucket(targetBand);
    showBand(currentBand);

    Serial.printf("HJ|METER|RAW=%.0f|TARGET=%u|BAND=%u\n",
                  measuredPeak,
                  (unsigned)(targetBand + 1),
                  (unsigned)(currentBand + 1));

    bucketPeak = 0.0f;
  }
}
