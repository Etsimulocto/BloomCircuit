// HAPPY JARZ — standalone 8-band sound color meter v1.7
//
// PURPOSE
//   Run continuously with NO serial-monitor dependence.
//   The HW-484 samples continuously and the APA106 pair updates at 25 FPS.
//   Eight discrete colors map the expanded 0..60 display range.
//
// IMPORTANT
//   The HW-484 is not calibrated in true acoustic dB SPL.
//   Normal speech on this mic is roughly 0..30 above the calibrated floor.
//   Display level = control * 2, capped at 60.
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
static constexpr float MAX_CONTROL_ABOVE = 60.0f;
static constexpr float DISPLAY_GAIN = 2.0f;

struct Rgb { uint8_t r, g, b; };

static unsigned long lastLedFrame = 0;

static const Rgb BAND_COLORS[8] = {
  {0,   0,  72},
  {0,  32,  72},
  {0,  64,  48},
  {0,  72,   0},
  {48, 72,   0},
  {72, 48,   0},
  {72, 20,   0},
  {72,  0,   0}
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

static uint8_t displayToBand(float displayLevel) {
  displayLevel = constrain(displayLevel, 0.0f, 60.0f);
  uint8_t band = (uint8_t)(displayLevel / 7.5f);
  if (band > 7) band = 7;
  return band;
}

void setup() {
  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    while (true) delay(1000);
  }

  // Slow visual startup sweep so we know the LED chain initialized.
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

  float control = min(above, MAX_CONTROL_ABOVE);
  float displayLevel = min(control * DISPLAY_GAIN, 60.0f);
  uint8_t band = displayToBand(displayLevel);

  unsigned long now = millis();
  if (now - lastLedFrame >= LED_FRAME_MS) {
    lastLedFrame = now;
    showBand(band);
  }
}
