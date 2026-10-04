// HAPPY JARZ — raw-channel diagnostic + meter v2.6
//
// PURPOSE
//   Revert the failed v2.5 RGB-byte experiment back to the prior GRB behavior.
//   Add a deterministic raw 3-channel startup test so the physical byte order
//   can be identified directly instead of inferred from mixed colors.
//
// STARTUP TEST
//   STEP 1: transmit byte1 only  -> {72,0,0}
//   STEP 2: transmit byte2 only  -> {0,72,0}
//   STEP 3: transmit byte3 only  -> {0,0,72}
//   Each step lasts 900 ms with a brief OFF gap.
//   Tell us the PHYSICAL color seen for step 1, step 2, step 3.
//
// HARDWARE
//   ESP32-S3 SuperMini
//   HW-484 A0 -> GPIO8
//   GPIO7 -> 220 ohm -> APA106 #1 DIN -> APA106 #2 DIN
//   Local decoupling capacitor(s) across LED VCC/GND

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;
static constexpr unsigned long COLOR_BUCKET_MS = 120;
static constexpr uint8_t FALL_CONFIRM_BUCKETS = 2;

struct Grb { uint8_t g, r, b; };

static unsigned long bucketStart = 0;
static float bucketPeak = 0.0f;
static uint8_t currentBand = 0;
static uint8_t pendingLowerBand = 0;
static uint8_t pendingLowerCount = 0;

// Prior v2.4/v2.3 palette, expressed in G,R,B fields.
static const Grb BAND_COLORS[8] = {
  { 0,  0, 72},
  {32,  0, 72},
  {64,  0, 48},
  {72,  0,  0},
  {72, 48,  0},
  {48, 72,  0},
  {20, 72,  0},
  { 0, 72,  0}
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

static void writeRawBytes(uint8_t b1, uint8_t b2, uint8_t b3) {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;

  for (uint8_t led = 0; led < LED_COUNT; ++led) {
    uint8_t bytes[3] = { b1, b2, b3 };

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

static void writeFrame(const Grb frame[LED_COUNT]) {
  // Back to the prior native GRB assumption for runtime.
  writeRawBytes(frame[0].g, frame[0].r, frame[0].b);
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

static void startupRawChannelTest() {
  Serial.println("HJ|CHANNEL_TEST|STEP=1|BYTES=72,0,0");
  writeRawBytes(72, 0, 0);
  delay(900);
  writeRawBytes(0, 0, 0);
  delay(250);

  Serial.println("HJ|CHANNEL_TEST|STEP=2|BYTES=0,72,0");
  writeRawBytes(0, 72, 0);
  delay(900);
  writeRawBytes(0, 0, 0);
  delay(250);

  Serial.println("HJ|CHANNEL_TEST|STEP=3|BYTES=0,0,72");
  writeRawBytes(0, 0, 72);
  delay(900);
  writeRawBytes(0, 0, 0);
  delay(350);
}

void setup() {
  Serial.begin(115200);

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    while (true) delay(1000);
  }

  startupRawChannelTest();

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
