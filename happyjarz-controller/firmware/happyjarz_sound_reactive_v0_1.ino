// HAPPY JARZ — sound-reactive light show v0.9
// Power-safe voice-reactive show built on the stable v0.6 input layer.
//
// HARDWARE
//   ESP32-S3 SuperMini
//   HW-484 v0.2 mic: A0 -> GPIO8
//   APA106 chain: GPIO7 -> 220R -> LED1 DIN -> LED2 DIN
//
// IMPORTANT
//   Microphone calibration, spike guard, and known-good APA106 RMT timing are
//   preserved. v0.9 changes only the visual/output layer.
//
// v0.9 POWER-SAFE SHOW
//   - No full-white output anywhere.
//   - Blue/green-biased palette; red is deliberately limited.
//   - Hard per-LED channel and total-output limiter before RMT transmission.
//   - Smooth continuous fades instead of hard color swaps.
//   - Clap = one blue/cyan pulse, never white.
//   - Designed to avoid rail sag / APA106 data corruption on the 3.3 V bench.

#include <Arduino.h>
#include "esp32-hal-rmt.h"
#include <math.h>

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;

// -----------------------------
// Stable v0.6 sound layer
// -----------------------------
static float noiseFloor = 12.0f;
static constexpr float FLOOR_MARGIN = 1.5f;
static constexpr float HOLD_DECAY = 0.86f;
static constexpr float MAX_CONTROL_ABOVE = 60.0f;
static constexpr float IDLE_MAX = 2.0f;
static constexpr float WHISPER_MAX = 10.0f;
static constexpr float VOICE_MAX = 22.0f;
static constexpr float LOUD_MAX = 38.0f;
static constexpr float CLAP_ABOVE = 38.0f;
static constexpr float BURST_RISE = 18.0f;

// -----------------------------
// Visual / power tuning
// -----------------------------
static constexpr float VISUAL_ATTACK = 0.20f;
static constexpr float VISUAL_RELEASE = 0.055f;
static constexpr unsigned long CLAP_COOLDOWN_MS = 500;
static constexpr unsigned long PULSE_MS = 180;

// These are deliberate bench-safe limits, not LED absolute ratings.
static constexpr uint8_t MAX_RED = 58;
static constexpr uint8_t MAX_GREEN = 105;
static constexpr uint8_t MAX_BLUE = 145;
static constexpr uint16_t MAX_RGB_SUM = 175;

struct Rgb { uint8_t r, g, b; };

static float heldLevel = 0.0f;
static float previousControl = 0.0f;
static float visualEnergy = 0.0f;
static uint16_t hue = 700;  // start in green/cyan territory
static float phase = 0.0f;
static unsigned long pulseStart = 0;
static unsigned long lastClap = 0;
static bool clapArmed = true;

// -----------------------------
// Known-good APA106 RMT layer — timing unchanged
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

static Rgb powerLimit(Rgb c) {
  // Per-channel caps first.
  c.r = min(c.r, MAX_RED);
  c.g = min(c.g, MAX_GREEN);
  c.b = min(c.b, MAX_BLUE);

  // Then cap total simultaneous channel demand.
  uint16_t sum = (uint16_t)c.r + (uint16_t)c.g + (uint16_t)c.b;
  if (sum > MAX_RGB_SUM) {
    float scale = (float)MAX_RGB_SUM / (float)sum;
    c.r = (uint8_t)((float)c.r * scale);
    c.g = (uint8_t)((float)c.g * scale);
    c.b = (uint8_t)((float)c.b * scale);
  }
  return c;
}

static void writeFrame(const Rgb frame[LED_COUNT], uint8_t brightnessPercent) {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;

  for (uint8_t led = 0; led < LED_COUNT; ++led) {
    Rgb safe = powerLimit(frame[led]);

    // Preserve the packet order already proven on this physical APA106 batch.
    uint8_t bytes[3] = {
      (uint8_t)((uint16_t)safe.r * brightnessPercent / 100U),
      (uint8_t)((uint16_t)safe.g * brightnessPercent / 100U),
      (uint8_t)((uint16_t)safe.b * brightnessPercent / 100U)
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

static void show(const Rgb &a, const Rgb &b) {
  Rgb frame[LED_COUNT] = {a, b};
  writeFrame(frame, 100);
}

static Rgb scaleColor(Rgb c, float amount) {
  amount = constrain(amount, 0.0f, 1.0f);
  c.r = (uint8_t)((float)c.r * amount);
  c.g = (uint8_t)((float)c.g * amount);
  c.b = (uint8_t)((float)c.b * amount);
  return c;
}

// Blue/green-safe palette. Red appears only as a small accent.
static Rgb safePalette(uint16_t h) {
  h %= 1024;

  if (h < 256) {
    uint8_t x = h;
    return {0, (uint8_t)(35 + x / 4), (uint8_t)(80 + x / 4)};
  }
  if (h < 512) {
    uint8_t x = h - 256;
    return {(uint8_t)(x / 10), (uint8_t)(99 + x / 10), (uint8_t)(144 - x / 4)};
  }
  if (h < 768) {
    uint8_t x = h - 512;
    return {(uint8_t)(25 + x / 12), (uint8_t)(124 - x / 3), (uint8_t)(80 + x / 4)};
  }

  uint8_t x = h - 768;
  return {(uint8_t)(46 - x / 7), (uint8_t)(39 + x / 5), (uint8_t)(144 - x / 5)};
}

// -----------------------------
// Stable microphone envelope
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
  // Single-channel low-power test only. No white test.
  show({32, 0, 0}, {32, 0, 0}); delay(180);
  show({0, 48, 0}, {0, 48, 0}); delay(180);
  show({0, 0, 64}, {0, 0, 64}); delay(180);
  show({0, 0, 0}, {0, 0, 0}); delay(180);
}

static void calibrateMicrophone() {
  Serial.println("HJ|SOUND|calibrating|hands_off=1|quiet_room=1");
  show({0, 0, 28}, {0, 0, 28});

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

  Serial.printf("HJ|SOUND|cal_done|AVG=%.1f|PEAK=%.0f|FLOOR=%.1f\n",
                average, peak, noiseFloor);

  show({0, 40, 20}, {0, 40, 20}); delay(220);
  show({0, 0, 0}, {0, 0, 0});
}

static float mapDynamics(float level, const char **bandOut) {
  if (level <= IDLE_MAX) {
    *bandOut = "IDLE";
    return 0.0f;
  }
  if (level <= WHISPER_MAX) {
    *bandOut = "WHISPER";
    float t = (level - IDLE_MAX) / (WHISPER_MAX - IDLE_MAX);
    return 0.04f + t * 0.18f;
  }
  if (level <= VOICE_MAX) {
    *bandOut = "VOICE";
    float t = (level - WHISPER_MAX) / (VOICE_MAX - WHISPER_MAX);
    return 0.22f + t * 0.33f;
  }
  if (level <= LOUD_MAX) {
    *bandOut = "LOUD";
    float t = (level - VOICE_MAX) / (LOUD_MAX - VOICE_MAX);
    return 0.55f + t * 0.30f;
  }

  *bandOut = "PEAK";
  float t = constrain((level - LOUD_MAX) / (MAX_CONTROL_ABOVE - LOUD_MAX), 0.0f, 1.0f);
  return 0.85f + t * 0.15f;
}

static void renderPowerSafeShow() {
  unsigned long now = millis();

  // One-shot clap pulse: cyan/blue only, never white.
  if (pulseStart != 0 && now - pulseStart < PULSE_MS) {
    float t = (float)(now - pulseStart) / (float)PULSE_MS;
    float fade = 1.0f - t;
    Rgb a = scaleColor({0, 90, 140}, 0.65f * fade + 0.15f);
    Rgb b = scaleColor({0, 45, 145}, 0.55f * fade + 0.12f);
    show(a, b);
    return;
  }

  // Continuous smooth show. No mode jumps.
  phase += 0.012f + visualEnergy * 0.026f;
  if (phase > 6.283185f) phase -= 6.283185f;

  hue = (hue + 1 + (uint16_t)(visualEnergy * 2.0f)) % 1024;

  float wave = 0.5f + 0.5f * sinf(phase);
  float base = 0.10f + visualEnergy * 0.52f;
  float aLevel = base * (0.82f + 0.18f * wave);
  float bLevel = base * (0.82f + 0.18f * (1.0f - wave));

  uint16_t separation = 120 + (uint16_t)(visualEnergy * 250.0f);
  Rgb a = scaleColor(safePalette(hue), aLevel);
  Rgb b = scaleColor(safePalette((hue + separation) % 1024), bLevel);
  show(a, b);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HJ|SOUND|boot|fw=0.9|mic=GPIO8|led=GPIO7");

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERROR|rmt_init_failed");
    while (true) delay(1000);
  }

  startupTest();
  calibrateMicrophone();
  Serial.println("HJ|SOUND|ready|show=power_safe_v1|white=disabled|spike_guard=1");
}

void loop() {
  float rawLevel = readSoundEnvelope();
  float above = rawLevel - noiseFloor;
  if (above < 0.0f) above = 0.0f;

  float control = min(above, MAX_CONTROL_ABOVE);

  if (control > heldLevel) {
    heldLevel = control;
  } else {
    heldLevel *= HOLD_DECAY;
    if (heldLevel < 0.15f) heldLevel = 0.0f;
  }

  const char *band = "IDLE";
  float targetEnergy = constrain(mapDynamics(heldLevel, &band), 0.0f, 1.0f);

  float k = (targetEnergy > visualEnergy) ? VISUAL_ATTACK : VISUAL_RELEASE;
  visualEnergy += (targetEnergy - visualEnergy) * k;
  visualEnergy = constrain(visualEnergy, 0.0f, 1.0f);

  float suddenRise = control - previousControl;
  bool clapNow = (control >= CLAP_ABOVE || suddenRise >= BURST_RISE);

  if (clapNow && clapArmed && (millis() - lastClap >= CLAP_COOLDOWN_MS)) {
    pulseStart = millis();
    lastClap = pulseStart;
    clapArmed = false;
  }

  if (control < 20.0f) {
    clapArmed = true;
  }

  previousControl = control;

  renderPowerSafeShow();

  static unsigned long lastPrint = 0;
  if (millis() - lastPrint >= 100) {
    lastPrint = millis();
    Serial.printf("HJ|SOUND|RAW=%.0f|ABOVE=%.1f|CONTROL=%.1f|HOLD=%.1f|ENERGY=%.2f|VIS=%.2f|BAND=%s|ARM=%d|FLOOR=%.1f\n",
                  rawLevel, above, control, heldLevel, targetEnergy, visualEnergy,
                  band, clapArmed ? 1 : 0, noiseFloor);
  }
}
