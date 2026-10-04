// HAPPY JARZ — sound-reactive light show v0.8
// Smooth voice-reactive show built on the stable v0.6 input layer.
//
// HARDWARE
//   ESP32-S3 SuperMini
//   HW-484 v0.2 mic: A0 -> GPIO8
//   APA106 chain: GPIO7 -> 220R -> LED1 DIN -> LED2 DIN
//
// IMPORTANT
//   The microphone calibration, spike guard, and known-good APA106 RMT timing
//   are preserved. v0.8 only changes the visual/show behavior.
//
// v0.8 SHOW
//   IDLE    -> slow breathing color drift
//   WHISPER -> soft smooth shimmer
//   VOICE   -> flowing two-color response, no hard LED swapping
//   LOUD    -> faster/brighter color sweep
//   CLAP    -> one short impact flash, edge-triggered with cooldown
//
// No rapid band-triggered strobing. No repeated burst retrigger while a clap
// remains above threshold.

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
// Smooth show tuning
// -----------------------------
static constexpr float VISUAL_ATTACK = 0.28f;
static constexpr float VISUAL_RELEASE = 0.08f;
static constexpr unsigned long CLAP_COOLDOWN_MS = 450;
static constexpr unsigned long IMPACT_MS = 70;
static constexpr unsigned long TAIL_MS = 180;

struct Rgb { uint8_t r, g, b; };

static float heldLevel = 0.0f;
static float previousControl = 0.0f;
static float visualEnergy = 0.0f;
static uint16_t hue = 0;
static float phase = 0.0f;
static unsigned long impactStart = 0;
static unsigned long lastClap = 0;
static bool clapArmed = true;

// -----------------------------
// Known-good APA106 RMT layer — preserve timing
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
  noiseFloor = constrain(max(average + FLOOR_MARGIN, peak * 0.85f), 6.0f, 18.0f);

  Serial.printf("HJ|SOUND|cal_done|AVG=%.1f|PEAK=%.0f|FLOOR=%.1f\n",
                average, peak, noiseFloor);

  show({0, 80, 0}, {0, 80, 0}); delay(250);
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

static void renderSmoothShow(float energy) {
  unsigned long now = millis();
  unsigned long age = now - impactStart;

  // One-shot clap effect: short white hit, then a smooth color tail.
  if (impactStart != 0 && age < IMPACT_MS + TAIL_MS) {
    if (age < IMPACT_MS) {
      float fade = 1.0f - ((float)age / (float)IMPACT_MS) * 0.35f;
      Rgb w = scaleColor({255, 255, 255}, fade);
      show(w, w);
      return;
    }

    float t = (float)(age - IMPACT_MS) / (float)TAIL_MS;
    float fade = 1.0f - t;
    uint16_t tailHue = (hue + (uint16_t)(t * 520.0f)) % 1536;
    Rgb a = scaleColor(colorWheel(tailHue), 0.85f * fade);
    Rgb b = scaleColor(colorWheel((tailHue + 500) % 1536), 0.65f * fade);
    show(a, b);
    return;
  }

  // Smooth continuous motion. Sound changes speed + brightness, not mode every loop.
  phase += 0.018f + visualEnergy * 0.055f;
  if (phase > 6.283185f) phase -= 6.283185f;

  uint16_t hueStep = 1 + (uint16_t)(visualEnergy * 7.0f);
  hue = (hue + hueStep) % 1536;

  float breath = 0.5f + 0.5f * sinf(phase);

  // Quiet = dim living glow. Voice brightens smoothly instead of snapping states.
  float baseBrightness = 0.018f + visualEnergy * 0.78f;
  float aBrightness = baseBrightness * (0.78f + 0.22f * breath);
  float bBrightness = baseBrightness * (0.78f + 0.22f * (1.0f - breath));

  // At stronger voice levels the LEDs separate more in hue, but still flow.
  uint16_t separation = 180 + (uint16_t)(visualEnergy * 500.0f);
  Rgb a = scaleColor(colorWheel(hue), aBrightness);
  Rgb b = scaleColor(colorWheel((hue + separation) % 1536), bBrightness);
  show(a, b);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HJ|SOUND|boot|fw=0.8|mic=GPIO8|led=GPIO7");

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERROR|rmt_init_failed");
    while (true) delay(1000);
  }

  startupTest();
  calibrateMicrophone();
  Serial.println("HJ|SOUND|ready|show=smooth_v2|one_shot_clap=1|spike_guard=1");
}

void loop() {
  float rawLevel = readSoundEnvelope();
  float above = rawLevel - noiseFloor;
  if (above < 0.0f) above = 0.0f;

  // Stable spike guard.
  float control = min(above, MAX_CONTROL_ABOVE);

  // Stable peak hold.
  if (control > heldLevel) {
    heldLevel = control;
  } else {
    heldLevel *= HOLD_DECAY;
    if (heldLevel < 0.15f) heldLevel = 0.0f;
  }

  const char *band = "IDLE";
  float targetEnergy = constrain(mapDynamics(heldLevel, &band), 0.0f, 1.0f);

  // Separate visual smoothing: sound detector can be fast without making LEDs twitch.
  float k = (targetEnergy > visualEnergy) ? VISUAL_ATTACK : VISUAL_RELEASE;
  visualEnergy += (targetEnergy - visualEnergy) * k;
  visualEnergy = constrain(visualEnergy, 0.0f, 1.0f);

  // Clap triggers once on the rising edge, then must fall below threshold to re-arm.
  float suddenRise = control - previousControl;
  bool clapNow = (control >= CLAP_ABOVE || suddenRise >= BURST_RISE);

  if (clapNow && clapArmed && (millis() - lastClap >= CLAP_COOLDOWN_MS)) {
    impactStart = millis();
    lastClap = impactStart;
    clapArmed = false;
    hue = (hue + 260) % 1536;
  }

  if (control < 20.0f) {
    clapArmed = true;
  }

  previousControl = control;

  renderSmoothShow(visualEnergy);

  static unsigned long lastPrint = 0;
  if (millis() - lastPrint >= 100) {
    lastPrint = millis();
    Serial.printf("HJ|SOUND|RAW=%.0f|ABOVE=%.1f|CONTROL=%.1f|HOLD=%.1f|ENERGY=%.2f|VIS=%.2f|BAND=%s|ARM=%d|FLOOR=%.1f\n",
                  rawLevel, above, control, heldLevel, targetEnergy, visualEnergy,
                  band, clapArmed ? 1 : 0, noiseFloor);
  }
}
