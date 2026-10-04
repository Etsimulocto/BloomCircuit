// HAPPY JARZ — sound-reactive isolation test v1.1
//
// PURPOSE
//   Verify the real APA106 behavior from the earlier HAPPY JARZ notes:
//   - GRB packet order
//   - blue-only runtime
//   - inverted brightness response for this bench test because the physical
//     bulb was observed to DIM when the commanded blue byte increased.
//
// HARDWARE
//   ESP32-S3 SuperMini
//   HW-484 v0.2 mic: A0 -> GPIO8
//   APA106 chain: GPIO7 -> 220R -> LED1 DIN -> LED2 DIN
//
// KNOWN-GOOD APA106 RMT TIMING — PRESERVED
//   RMT clock: 10 MHz
//   0 bit: 4 ticks HIGH / 14 ticks LOW
//   1 bit: 14 ticks HIGH / 4 ticks LOW
//   latch/reset: 100 us LOW

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t MIC_PIN = 8;
static constexpr uint8_t LED_COUNT = 2;

static float noiseFloor = 12.0f;
static constexpr float FLOOR_MARGIN = 1.5f;
static constexpr float HOLD_DECAY = 0.86f;
static constexpr float MAX_CONTROL_ABOVE = 60.0f;

// Bench-safe blue-only limits.
// IMPORTANT: response is inverted on purpose for this physical batch test.
static constexpr uint8_t BLUE_QUIET = 72;
static constexpr uint8_t BLUE_LOUD = 12;

struct Rgb { uint8_t r, g, b; };

static float heldLevel = 0.0f;
static float visualLevel = 0.0f;
static unsigned long frameCounter = 0;

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
    // HAPPY JARZ APA106 notes: physical batch uses GRB byte order.
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

static void showBlue(uint8_t aBlue, uint8_t bBlue) {
  Rgb frame[LED_COUNT] = {
    {0, 0, aBlue},
    {0, 0, bBlue}
  };
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
  Serial.println("HJ|ISO|calibrating|quiet_room=1");
  showBlue(30, 30);

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

  Serial.printf("HJ|ISO|cal_done|AVG=%.1f|PEAK=%.0f|FLOOR=%.1f\n",
                average, peak, noiseFloor);

  showBlue(0, 0);
  delay(150);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HJ|ISO|boot|fw=1.1|mode=BLUE_ONLY_GRB_INVERTED|mic=GPIO8|led=GPIO7");

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERROR|rmt_init_failed");
    while (true) delay(1000);
  }

  // Blue-only stepped startup test. No white/red/green commanded.
  showBlue(15, 15); delay(250);
  showBlue(35, 35); delay(250);
  showBlue(55, 55); delay(250);
  showBlue(0, 0);   delay(250);

  calibrateMicrophone();
  Serial.println("HJ|ISO|ready|packet=GRB|runtime=BLUE_ONLY|response=INVERTED");
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

  float target = constrain(heldLevel / 38.0f, 0.0f, 1.0f);
  float k = (target > visualLevel) ? 0.20f : 0.05f;
  visualLevel += (target - visualLevel) * k;

  // INVERTED bench mapping: quiet = higher byte, louder = lower byte.
  uint8_t b1 = BLUE_QUIET - (uint8_t)(visualLevel * (BLUE_QUIET - BLUE_LOUD));
  uint8_t b2 = BLUE_QUIET - (uint8_t)(visualLevel * 0.70f * (BLUE_QUIET - BLUE_LOUD));

  showBlue(b1, b2);
  ++frameCounter;

  static unsigned long lastPrint = 0;
  if (millis() - lastPrint >= 100) {
    lastPrint = millis();
    Serial.printf("HJ|ISO|RAW=%.0f|ABOVE=%.1f|HOLD=%.1f|VIS=%.2f|B1=%u|B2=%u|FRAME=%lu|FLOOR=%.1f\n",
                  rawLevel, above, heldLevel, visualLevel,
                  (unsigned)b1, (unsigned)b2, frameCounter, noiseFloor);
  }
}
