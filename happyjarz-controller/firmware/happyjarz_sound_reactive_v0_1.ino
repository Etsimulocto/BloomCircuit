// HAPPY JARZ — sound-reactive light show v0.2
// BloomCore standalone hardware test.
//
// PURPOSE
//   Prove HW-484 microphone input on GPIO8 while preserving the known-good
//   HAPPY JARZ APA106 RMT lighting layer on GPIO7.
//
// HARDWARE
//   Controller: ESP32-S3 SuperMini
//   Mic: HW-484 v0.2
//
// WIRING
//   HW-484 +   -> 3V3
//   HW-484 G   -> GND
//   HW-484 A0  -> GPIO8
//   HW-484 D0  -> unused
//
//   GPIO7 -> 220R -> APA106 #1 DIN
//   APA106 #1 DOUT -> APA106 #2 DIN
//
// KNOWN-GOOD APA106 LAYER — DO NOT CHANGE WHILE TUNING SOUND
//   RMT clock: 10 MHz
//   0 bit: 4 ticks HIGH / 14 ticks LOW
//   1 bit: 14 ticks HIGH / 4 ticks LOW
//   latch/reset: 100 us LOW
//
// v0.2 SOUND CHANGES
//   - Auto-calibrates room noise at boot.
//   - Much lower full-scale sound target for normal speech.
//   - Fast attack / slower release so words visibly punch the lights.
//   - Square-root response expands quiet/medium speech instead of requiring yelling.
//   - Burst threshold lowered for claps, taps, and sharp syllables.
//
// DIAGNOSTICS
//   Serial 115200 prints RAW, LEVEL, ENERGY, FLOOR, FULL every ~100 ms.

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;

// -----------------------------
// Sound tuning
// -----------------------------
// These become the starting points; calibration updates FLOOR/FULL at boot.
static float noiseFloor = 18.0f;
static float fullScale = 220.0f;
static constexpr float MIN_FULL_SCALE = 180.0f;
static constexpr float ATTACK_SMOOTHING = 0.42f;
static constexpr float RELEASE_SMOOTHING = 0.82f;
static constexpr float BURST_AMOUNT = 55.0f;

// -----------------------------
// Runtime state
// -----------------------------
struct Rgb { uint8_t r, g, b; };

static float soundLevel = 0.0f;
static float previousLevel = 0.0f;
static uint16_t hue = 0;
static unsigned long burstUntil = 0;

// -----------------------------
// LED layer — preserve known-good timing
// -----------------------------
static bool initApa106Rmt() {
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  if (!rmtInit(LED_DATA_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) {
    return false;
  }
  rmtSetEOT(LED_DATA_PIN, 0);
  return true;
}

static void writeFrame(const Rgb frame[LED_COUNT], uint8_t brightnessPercent) {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;

  for (uint8_t led = 0; led < LED_COUNT; ++led) {
    uint8_t bytes[3] = {
      (uint8_t)((uint16_t)frame[led].r * brightnessPercent / 100U),
      (uint8_t)((uint16_t)frame[led].g * brightnessPercent / 100U),
      (uint8_t)((uint16_t)frame[led].b * brightnessPercent / 100U)
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

static void show(const Rgb &a, const Rgb &b, uint8_t brightnessPercent = 100) {
  Rgb frame[LED_COUNT] = {a, b};
  writeFrame(frame, brightnessPercent);
}

static Rgb colorWheel(uint16_t h) {
  h %= 1536;
  uint8_t region = h / 256;
  uint8_t x = h % 256;

  switch (region) {
    case 0: return {255, x, 0};
    case 1: return {(uint8_t)(255 - x), 255, 0};
    case 2: return {0, 255, x};
    case 3: return {0, (uint8_t)(255 - x), 255};
    case 4: return {x, 0, 255};
    default: return {255, 0, (uint8_t)(255 - x)};
  }
}

static Rgb scaleColor(Rgb c, float amount) {
  amount = constrain(amount, 0.0f, 1.0f);
  c.r = (uint8_t)(c.r * amount);
  c.g = (uint8_t)(c.g * amount);
  c.b = (uint8_t)(c.b * amount);
  return c;
}

// -----------------------------
// Microphone envelope
// -----------------------------
static float readSoundEnvelope() {
  // Peak-to-peak ADC swing over ~10 ms. This ignores DC bias and measures
  // sound amplitude from the analog microphone output.
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

static void startupTest() {
  show({255, 0, 0}, {255, 0, 0});
  delay(200);
  show({0, 255, 0}, {0, 255, 0});
  delay(200);
  show({0, 0, 255}, {0, 0, 255});
  delay(200);
  show({0, 0, 0}, {0, 0, 0});
  delay(200);
}

static void calibrateMicrophone() {
  Serial.println("HJ|SOUND|calibrating|hands_off=1|quiet_room=1");

  // Blue while listening to ambient room noise.
  show({0, 0, 40}, {0, 0, 40});

  constexpr int CAL_SAMPLES = 100;
  float sum = 0.0f;
  float peak = 0.0f;

  for (int i = 0; i < CAL_SAMPLES; ++i) {
    float v = readSoundEnvelope();
    sum += v;
    if (v > peak) peak = v;
  }

  float average = sum / (float)CAL_SAMPLES;

  // Give the room a little headroom above its average noise.
  // Clamp prevents one accidental startup sound from making the mic deaf.
  noiseFloor = constrain((average * 1.25f) + 6.0f, 10.0f, 80.0f);

  // Normal speech should reach a substantial fraction of full output.
  // On the first bench test, quiet was ~10-50 RAW and loud events were 2000+.
  fullScale = max(MIN_FULL_SCALE, noiseFloor * 5.0f);

  Serial.printf("HJ|SOUND|cal_done|AVG=%.1f|PEAK=%.0f|FLOOR=%.1f|FULL=%.1f\n",
                average, peak, noiseFloor, fullScale);

  // Green flash = calibration complete.
  show({0, 80, 0}, {0, 80, 0});
  delay(250);
  show({0, 0, 0}, {0, 0, 0});
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HJ|SOUND|boot|fw=0.2|mic=GPIO8|led=GPIO7");

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERROR|rmt_init_failed");
    while (true) delay(1000);
  }

  startupTest();
  calibrateMicrophone();

  Serial.println("HJ|SOUND|ready|normal_voice_should_react=1");
}

void loop() {
  float rawLevel = readSoundEnvelope();
  float adjusted = rawLevel - noiseFloor;
  if (adjusted < 0.0f) adjusted = 0.0f;

  // Fast attack: react immediately to a word/beat.
  // Slow release: visually decay instead of blinking off between syllables.
  float smoothing = (adjusted > soundLevel) ? ATTACK_SMOOTHING : RELEASE_SMOOTHING;
  soundLevel = (soundLevel * smoothing) +
               (adjusted * (1.0f - smoothing));

  float linearEnergy = constrain(soundLevel / fullScale, 0.0f, 1.0f);

  // Expand the lower half of the microphone range so normal speech is useful.
  float energy = sqrtf(linearEnergy);

  // Sudden transient = clap/shout/beat burst.
  float suddenRise = soundLevel - previousLevel;
  if (suddenRise > BURST_AMOUNT) {
    burstUntil = millis() + 90;
    hue = (hue + 190) % 1536;
  }
  previousLevel = soundLevel;

  // Louder sound moves through color space faster.
  hue = (hue + 1 + (uint16_t)(energy * 34.0f)) % 1536;

  Rgb c1 = colorWheel(hue);
  Rgb c2 = colorWheel((hue + 500) % 1536);

  // Small idle glow. Normal speech now gets a strong visible response.
  float brightness = 0.015f + (energy * 0.985f);
  c1 = scaleColor(c1, brightness);
  c2 = scaleColor(c2, brightness);

  if (millis() < burstUntil) {
    c1 = {255, 255, 255};
    c2 = colorWheel((hue + 768) % 1536);
  }

  show(c1, c2);

  static unsigned long lastPrint = 0;
  if (millis() - lastPrint >= 100) {
    lastPrint = millis();
    Serial.printf("HJ|SOUND|RAW=%.0f|LEVEL=%.1f|ENERGY=%.2f|FLOOR=%.1f|FULL=%.1f\n",
                  rawLevel, soundLevel, energy, noiseFloor, fullScale);
  }
}
