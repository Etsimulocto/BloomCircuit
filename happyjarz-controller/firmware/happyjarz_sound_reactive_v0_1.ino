// HAPPY JARZ — sound-reactive light show v0.7
// BloomCore standalone hardware test.
//
// PURPOSE
//   Build the first real voice-reactive light show on top of the stable v0.6
//   microphone + spike-guard layer while preserving the known-good APA106 RMT
//   lighting layer on GPIO7.
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
// KNOWN-GOOD APA106 LAYER — DO NOT CHANGE
//   RMT clock: 10 MHz
//   0 bit: 4 ticks HIGH / 14 ticks LOW
//   1 bit: 14 ticks HIGH / 4 ticks LOW
//   latch/reset: 100 us LOW
//
// STABLE INPUT LAYER FROM v0.6 — DO NOT CHANGE WHILE TUNING SHOW
//   quiet floor: roughly 6-12 RAW
//   whisper/soft voice: roughly 15-25 RAW
//   ordinary voice: roughly 25-40 RAW
//   loud clap: roughly 50-60 RAW
//   control path capped at 60 above-floor to reject ADC spikes
//
// v0.7 SHOW LAYER
//   IDLE    -> very slow breathing complementary colors
//   WHISPER -> soft synchronized shimmer / gentle hue drift
//   VOICE   -> two-LED alternating chase driven by syllables
//   LOUD    -> bright opposing colors, faster snap/chase
//   PEAK    -> white + rainbow burst
//
// DIAGNOSTICS
//   Serial 115200 prints RAW, ABOVE, CONTROL, HOLD, ENERGY, BAND, FLOOR.

#include <Arduino.h>
#include "esp32-hal-rmt.h"
#include <math.h>

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;

// -----------------------------
// Stable sound tuning (v0.6)
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
// Runtime state
// -----------------------------
struct Rgb { uint8_t r, g, b; };

static float heldLevel = 0.0f;
static float previousControl = 0.0f;
static uint16_t hue = 0;
static float showPhase = 0.0f;
static bool chaseFlip = false;
static unsigned long lastChaseFlip = 0;
static unsigned long burstUntil = 0;
static unsigned long burstStart = 0;

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
// Microphone envelope — stable v0.6 input layer
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

// -----------------------------
// v0.7 show layer
// -----------------------------
static void renderShow(const char *band, float energy) {
  unsigned long now = millis();

  // A clap/shout owns the frame briefly: white impact, then rainbow tail.
  if (now < burstUntil) {
    unsigned long age = now - burstStart;
    if (age < 45) {
      show({255, 255, 255}, {255, 255, 255});
    } else {
      uint16_t burstHue = (hue + (uint16_t)(age * 14U)) % 1536;
      Rgb a = colorWheel(burstHue);
      Rgb b = colorWheel((burstHue + 768) % 1536);
      show(a, b);
    }
    return;
  }

  if (strcmp(band, "IDLE") == 0) {
    // Barely-alive slow breathing glow.
    showPhase += 0.025f;
    if (showPhase > 6.283185f) showPhase -= 6.283185f;
    float breath = 0.018f + 0.022f * (0.5f + 0.5f * sinf(showPhase));
    hue = (hue + 1) % 1536;
    Rgb a = scaleColor(colorWheel(hue), breath);
    Rgb b = scaleColor(colorWheel((hue + 768) % 1536), breath * 0.75f);
    show(a, b);
    return;
  }

  if (strcmp(band, "WHISPER") == 0) {
    // Soft shimmer: both LEDs breathe together and drift slowly through color.
    showPhase += 0.07f + energy * 0.10f;
    if (showPhase > 6.283185f) showPhase -= 6.283185f;
    hue = (hue + 1 + (uint16_t)(energy * 5.0f)) % 1536;
    float shimmer = 0.10f + energy * 0.55f;
    shimmer *= 0.72f + 0.28f * (0.5f + 0.5f * sinf(showPhase));
    Rgb a = scaleColor(colorWheel(hue), shimmer);
    Rgb b = scaleColor(colorWheel((hue + 220) % 1536), shimmer * 0.82f);
    show(a, b);
    return;
  }

  if (strcmp(band, "VOICE") == 0) {
    // Syllable chase: alternate which LED carries the strong color.
    unsigned long interval = (unsigned long)(150.0f - energy * 115.0f);
    interval = constrain(interval, 38UL, 130UL);
    if (now - lastChaseFlip >= interval) {
      lastChaseFlip = now;
      chaseFlip = !chaseFlip;
      hue = (hue + 70 + (uint16_t)(energy * 120.0f)) % 1536;
    }

    Rgb hot = scaleColor(colorWheel(hue), 0.35f + energy * 0.65f);
    Rgb cool = scaleColor(colorWheel((hue + 500) % 1536), 0.08f + energy * 0.28f);
    if (chaseFlip) show(hot, cool);
    else show(cool, hot);
    return;
  }

  // LOUD / PEAK without an active burst: aggressive opposing-color chase.
  unsigned long interval = (unsigned long)(75.0f - energy * 45.0f);
  interval = constrain(interval, 22UL, 60UL);
  if (now - lastChaseFlip >= interval) {
    lastChaseFlip = now;
    chaseFlip = !chaseFlip;
    hue = (hue + 150 + (uint16_t)(energy * 180.0f)) % 1536;
  }

  Rgb a = scaleColor(colorWheel(hue), 0.72f + energy * 0.28f);
  Rgb b = scaleColor(colorWheel((hue + 768) % 1536), 0.55f + energy * 0.40f);
  if (chaseFlip) show(a, b);
  else show(b, a);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HJ|SOUND|boot|fw=0.7|mic=GPIO8|led=GPIO7");

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERROR|rmt_init_failed");
    while (true) delay(1000);
  }

  startupTest();
  calibrateMicrophone();
  Serial.println("HJ|SOUND|ready|show=voice_reactive_v1|spike_guard=1");
}

void loop() {
  float rawLevel = readSoundEnvelope();
  float above = rawLevel - noiseFloor;
  if (above < 0.0f) above = 0.0f;

  // Stable v0.6 spike guard.
  float control = min(above, MAX_CONTROL_ABOVE);

  // Stable v0.6 instant attack + musical decay.
  if (control > heldLevel) {
    heldLevel = control;
  } else {
    heldLevel *= HOLD_DECAY;
    if (heldLevel < 0.15f) heldLevel = 0.0f;
  }

  const char *band = "IDLE";
  float energy = constrain(mapDynamics(heldLevel, &band), 0.0f, 1.0f);

  float suddenRise = control - previousControl;
  if (control >= CLAP_ABOVE || suddenRise >= BURST_RISE) {
    burstStart = millis();
    burstUntil = burstStart + 150;
    hue = (hue + 230) % 1536;
  }
  previousControl = control;

  renderShow(band, energy);

  static unsigned long lastPrint = 0;
  if (millis() - lastPrint >= 100) {
    lastPrint = millis();
    Serial.printf("HJ|SOUND|RAW=%.0f|ABOVE=%.1f|CONTROL=%.1f|HOLD=%.1f|ENERGY=%.2f|BAND=%s|FLOOR=%.1f\n",
                  rawLevel, above, control, heldLevel, energy, band, noiseFloor);
  }
}
