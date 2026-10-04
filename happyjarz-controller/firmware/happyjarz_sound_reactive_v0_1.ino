// HAPPY JARZ — proven-RGB single-LED sound color meter v2.9
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
//   Local decoupling capacitor across LED VCC/GND
//
// SOUND PATH
//   10 ms peak-to-peak mic envelope
//   loudest value across 120 ms bucket
//   fixed 8-band mapping
//   upward moves immediate
//   fixed 240 ms peak hold, then direct fall to current target
//
// TELEMETRY
//   One line per 120 ms bucket for the Pi meter app.

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 1;
static constexpr unsigned long COLOR_BUCKET_MS = 120;
static constexpr unsigned long PEAK_HOLD_MS = 240;

struct Rgb { uint8_t r, g, b; };

static unsigned long bucketStart = 0;
static unsigned long lastRiseTime = 0;
static float bucketPeak = 0.0f;
static uint8_t currentBand = 0;

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
  writeRgb(c.r, c.g, c.b);
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

static void updateBandFromBucket(uint8_t targetBand, unsigned long now) {
  // Higher peaks show immediately and restart a short visual peak hold.
  if (targetBand > currentBand) {
    currentBand = targetBand;
    lastRiseTime = now;
    return;
  }

  if (targetBand == currentBand) {
    return;
  }

  // Do not require the same lower band repeatedly. After the fixed hold
  // expires, fall directly to the current measured target.
  if (now - lastRiseTime >= PEAK_HOLD_MS) {
    currentBand = targetBand;
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    while (true) delay(1000);
  }

  // Short proven RGB sanity sweep: red -> green -> blue.
  writeRgb(72, 0, 0); delay(350);
  writeRgb(0, 72, 0); delay(350);
  writeRgb(0, 0, 72); delay(350);

  currentBand = 0;
  bucketPeak = 0.0f;
  bucketStart = millis();
  lastRiseTime = 0;
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
    updateBandFromBucket(targetBand, now);
    showBand(currentBand);

    Serial.printf("HJ|METER|RAW=%.0f|TARGET=%u|BAND=%u\n",
                  measuredPeak,
                  (unsigned)(targetBand + 1),
                  (unsigned)(currentBand + 1));

    bucketPeak = 0.0f;
  }
}
