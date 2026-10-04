// HAPPY JARZ — sound-reactive light show v0.4
// BloomCore standalone hardware test.
//
// PURPOSE
//   Tune the sound-response bands from real HW-484 bench logs while preserving
//   the known-good HAPPY JARZ APA106 RMT lighting layer on GPIO7.
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
// v0.4 SOUND RESPONSE — based on v0.3 bench data
//   Observed floor ~12.7, useful smoothed LEVEL mostly ~7-40+.
//   - IDLE:    residual / settled room noise
//   - WHISPER: very quiet speech
//   - VOICE:   normal speech
//   - LOUD:    strong nearby speech / music
//   - PEAK:    shout / clap / sharp transient
//   The upper bands are intentionally moved down so the real microphone range
//   drives the entire visual range instead of living almost entirely in VOICE.
//
// DIAGNOSTICS
//   Serial 115200 prints RAW, LEVEL, ENERGY, BAND, FLOOR, FULL every ~100 ms.

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;

// -----------------------------
// Sound tuning
// -----------------------------
static float noiseFloor = 18.0f;
static float fullScale = 90.0f;
static constexpr float MIN_FULL_SCALE = 70.0f;
static constexpr float ATTACK_SMOOTHING = 0.34f;
static constexpr float RELEASE_SMOOTHING = 0.80f;
static constexpr float BURST_AMOUNT = 22.0f;
static constexpr float DEADBAND = 3.0f;

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
  show({255, 0, 0}, {255, 0, 0}); delay(200);
  show({0, 255, 0}, {0, 255, 0}); delay(200);
  show({0, 0, 255}, {0, 0, 255}); delay(200);
  show({0, 0, 0}, {0, 0, 0}); delay(200);
}

static void calibrateMicrophone() {
  Serial.println("HJ|SOUND|calibrating|hands_off=1|quiet_room=1");
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
  noiseFloor = constrain((average * 1.25f) + 6.0f, 10.0f, 80.0f);

  // v0.3 showed that this HW-484's useful everyday range is much smaller
  // than the earlier conservative 220 full-scale target.
  fullScale = max(MIN_FULL_SCALE, noiseFloor * 5.5f);

  Serial.printf("HJ|SOUND|cal_done|AVG=%.1f|PEAK=%.0f|FLOOR=%.1f|FULL=%.1f\n",
                average, peak, noiseFloor, fullScale);

  show({0, 80, 0}, {0, 80, 0});
  delay(250);
  show({0, 0, 0}, {0, 0, 0});
}

// Piecewise dynamics curve tuned from the real v0.3 log.
// Input is LEVEL after floor subtraction and attack/release smoothing.
static float mapDynamics(float level, const char **bandOut) {
  if (level <= DEADBAND) {
    *bandOut = "IDLE";
    return 0.0f;
  }

  // Very quiet speech and near-room-level detail.
  if (level <= 12.0f) {
    *bandOut = "WHISPER";
    float t = (level - DEADBAND) / (12.0f - DEADBAND);
    return 0.02f + t * 0.16f;
  }

  // Ordinary conversational range from the bench logs.
  if (level <= 25.0f) {
    *bandOut = "VOICE";
    float t = (level - 12.0f) / (25.0f - 12.0f);
    return 0.18f + t * 0.30f;
  }

  // Strong nearby speech / music should now use most of the light output.
  if (level <= 45.0f) {
    *bandOut = "LOUD";
    float t = (level - 25.0f) / (45.0f - 25.0f);
    return 0.48f + t * 0.34f;
  }

  // Peaks no longer require an unrealistic LEVEL > 140.
  *bandOut = "PEAK";
  float t = constrain((level - 45.0f) / max(1.0f, fullScale - 45.0f), 0.0f, 1.0f);
  return 0.82f + t * 0.18f;
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HJ|SOUND|boot|fw=0.4|mic=GPIO8|led=GPIO7");

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERROR|rmt_init_failed");
    while (true) delay(1000);
  }

  startupTest();
  calibrateMicrophone();

  Serial.println("HJ|SOUND|ready|dynamic_bands=IDLE,WHISPER,VOICE,LOUD,PEAK");
}

void loop() {
  float rawLevel = readSoundEnvelope();
  float adjusted = rawLevel - noiseFloor;
  if (adjusted < 0.0f) adjusted = 0.0f;

  float smoothing = (adjusted > soundLevel) ? ATTACK_SMOOTHING : RELEASE_SMOOTHING;
  soundLevel = (soundLevel * smoothing) +
               (adjusted * (1.0f - smoothing));

  const char *band = "IDLE";
  float energy = constrain(mapDynamics(soundLevel, &band), 0.0f, 1.0f);

  float suddenRise = soundLevel - previousLevel;
  if (suddenRise > BURST_AMOUNT || soundLevel > 60.0f) {
    burstUntil = millis() + 95;
    hue = (hue + 210) % 1536;
  }
  previousLevel = soundLevel;

  // Whisper drifts; ordinary voice moves; loud/peak runs quickly through color.
  uint16_t hueStep = 0;
  if (energy > 0.0f) {
    hueStep = 1 + (uint16_t)(energy * 44.0f);
  }
  hue = (hue + hueStep) % 1536;

  Rgb c1 = colorWheel(hue);
  Rgb c2 = colorWheel((hue + 500) % 1536);

  float brightness = (energy <= 0.0f) ? 0.003f : (0.01f + energy * 0.99f);
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
    Serial.printf("HJ|SOUND|RAW=%.0f|LEVEL=%.1f|ENERGY=%.2f|BAND=%s|FLOOR=%.1f|FULL=%.1f\n",
                  rawLevel, soundLevel, energy, band, noiseFloor, fullScale);
  }
}
