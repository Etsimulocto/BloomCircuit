// HAPPY JARZ — stabilized raw-peak 8-band sound color meter v2.1
//
// PURPOSE
//   Keep the proven raw microphone path and 25 FPS APA106 update ceiling.
//   Keep the sensitive v2.0 thresholds, but prevent rapid color chatter by
//   requiring neighboring-band changes to persist briefly before switching.
//   A true clap/red event still jumps to red immediately.
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

// Temporal hysteresis at 25 FPS:
//   rise:  2 consecutive frames (~80 ms)
//   fall:  4 consecutive frames (~160 ms)
//   red:   immediate
static constexpr uint8_t RISE_CONFIRM_FRAMES = 2;
static constexpr uint8_t FALL_CONFIRM_FRAMES = 4;

struct Rgb { uint8_t r, g, b; };

static unsigned long lastLedFrame = 0;
static float framePeak = 0.0f;
static uint8_t currentBand = 0;
static uint8_t pendingBand = 0;
static uint8_t pendingCount = 0;

static const Rgb BAND_COLORS[8] = {
  {0,   0,  72},  // raw 0-6    blue
  {0,  32,  72},  // raw 7-8    cyan-blue
  {0,  64,  48},  // raw 9-10   cyan-green
  {0,  72,   0},  // raw 11-13  green
  {48, 72,   0},  // raw 14-16  yellow-green
  {72, 48,   0},  // raw 17-20  yellow
  {72, 20,   0},  // raw 21-26  orange
  {72,  0,   0}   // raw 27+    red
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
  if (raw <= 6.0f)  return 0;
  if (raw <= 8.0f)  return 1;
  if (raw <= 10.0f) return 2;
  if (raw <= 13.0f) return 3;
  if (raw <= 16.0f) return 4;
  if (raw <= 20.0f) return 5;
  if (raw <= 26.0f) return 6;
  return 7;
}

static void updateStableBand(uint8_t targetBand) {
  // Clap / strong transient: show red immediately.
  if (targetBand == 7) {
    currentBand = 7;
    pendingBand = 7;
    pendingCount = 0;
    return;
  }

  if (targetBand == currentBand) {
    pendingBand = currentBand;
    pendingCount = 0;
    return;
  }

  if (targetBand != pendingBand) {
    pendingBand = targetBand;
    pendingCount = 1;
  } else if (pendingCount < 255) {
    ++pendingCount;
  }

  uint8_t needed = (targetBand > currentBand)
                     ? RISE_CONFIRM_FRAMES
                     : FALL_CONFIRM_FRAMES;

  if (pendingCount >= needed) {
    currentBand = targetBand;
    pendingCount = 0;
  }
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

  currentBand = 0;
  pendingBand = 0;
  pendingCount = 0;
  showBand(currentBand);
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

    uint8_t targetBand = rawToBand(framePeak);
    updateStableBand(targetBand);
    showBand(currentBand);

    framePeak = 0.0f;
  }
}
