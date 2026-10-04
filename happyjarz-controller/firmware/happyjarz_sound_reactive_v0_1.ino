// HAPPY JARZ — sound-reactive light show v0.6
// BloomCore standalone hardware test.
//
// PURPOSE
//   Stable HW-484 sound response using the real measured microphone range while
//   rejecting brief ESP32 ADC/envelope spikes that can otherwise pin the visual
//   peak-hold at full output.
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
// REAL BENCH RANGE
//   quiet floor: roughly 6-12 RAW
//   whisper/soft voice: roughly 15-25 RAW
//   ordinary voice: roughly 25-40 RAW
//   loud clap: roughly 50-60 RAW
//
// v0.6 FIX
//   v0.5 exposed short unprinted ADC/envelope spikes in the hundreds/thousands.
//   Those spikes could enter HOLD even though the next printed RAW value looked
//   normal. The diagnostic RAW remains untouched, but the LIGHT CONTROL path is
//   clamped to a sane maximum above the measured floor. A real clap still reaches
//   PEAK; nonsense spikes can no longer pin the show at full energy.
//
// DIAGNOSTICS
//   Serial 115200 prints RAW, ABOVE, CONTROL, HOLD, ENERGY, BAND, FLOOR.

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;

// -----------------------------
// Sound tuning
// -----------------------------
static float noiseFloor = 12.0f;
static constexpr float FLOOR_MARGIN = 1.5f;
static constexpr float HOLD_DECAY = 0.86f;
static constexpr float MAX_CONTROL_ABOVE = 60.0f; // measured clap range tops out around here
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

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HJ|SOUND|boot|fw=0.6|mic=GPIO8|led=GPIO7");

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERROR|rmt_init_failed");
    while (true) delay(1000);
  }

  startupTest();
  calibrateMicrophone();
  Serial.println("HJ|SOUND|ready|spike_guard=1|bands=IDLE,WHISPER,VOICE,LOUD,PEAK");
}

void loop() {
  float rawLevel = readSoundEnvelope();
  float above = rawLevel - noiseFloor;
  if (above < 0.0f) above = 0.0f;

  // Preserve raw ABOVE for diagnostics, but never let a single ADC/envelope
  // glitch inject hundreds/thousands into the visual state.
  float control = min(above, MAX_CONTROL_ABOVE);

  // Instant attack, quick musical decay.
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
    burstUntil = millis() + 100;
    hue = (hue + 230) % 1536;
  }
  previousControl = control;

  uint16_t hueStep = 1 + (uint16_t)(energy * 48.0f);
  hue = (hue + hueStep) % 1536;

  Rgb c1 = colorWheel(hue);
  Rgb c2 = colorWheel((hue + 500) % 1536);

  float brightness = (energy <= 0.0f) ? 0.012f : (0.025f + energy * 0.975f);
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
    Serial.printf("HJ|SOUND|RAW=%.0f|ABOVE=%.1f|CONTROL=%.1f|HOLD=%.1f|ENERGY=%.2f|BAND=%s|FLOOR=%.1f\n",
                  rawLevel, above, control, heldLevel, energy, band, noiseFloor);
  }
}
