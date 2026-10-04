// HAPPY JARZ — 8-band sound color meter v1.5
//
// PURPOSE
//   Keep the proven v1.4 microphone + 25 FPS APA106 update path, but replace
//   continuous full-range color/brightness behavior with eight discrete bands.
//
// IMPORTANT
//   The HW-484 is NOT acoustically calibrated in true dB SPL. We use the stable
//   0..60 control range as a 0..60 display scale, split into eight equal bands.
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
static constexpr unsigned long LED_FRAME_MS = 40; // 25 FPS

static float noiseFloor = 12.0f;
static constexpr float FLOOR_MARGIN = 1.5f;
static constexpr float HOLD_DECAY = 0.86f;
static constexpr float MAX_CONTROL_ABOVE = 60.0f;

struct Rgb { uint8_t r, g, b; };

static float heldLevel = 0.0f;
static unsigned long frameCounter = 0;
static unsigned long lastLedFrame = 0;

// 8 fixed colors, low sound -> high sound.
// Intentionally discrete: no interpolation between colors.
static const Rgb BAND_COLORS[8] = {
  {0,   0,  72},  //  0.0 -  7.4  blue
  {0,  32,  72},  //  7.5 - 14.9  cyan-blue
  {0,  64,  48},  // 15.0 - 22.4  cyan-green
  {0,  72,   0},  // 22.5 - 29.9  green
  {48, 72,   0},  // 30.0 - 37.4  yellow-green
  {72, 48,   0},  // 37.5 - 44.9  yellow/orange
  {72, 20,   0},  // 45.0 - 52.4  orange
  {72,  0,   0}   // 52.5 - 60.0  red
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
  Serial.println("HJ|METER|calibrating|quiet_room=1");
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

  Serial.printf("HJ|METER|cal_done|AVG=%.1f|PEAK=%.0f|FLOOR=%.1f\n",
                average, peak, noiseFloor);
}

static uint8_t controlToBand(float control) {
  control = constrain(control, 0.0f, 60.0f);
  uint8_t band = (uint8_t)(control / 7.5f);
  if (band > 7) band = 7;
  return band;
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HJ|METER|boot|fw=1.5|mode=8_BANDS|scale=0_60|packet=GRB|mic=GPIO8|led=GPIO7");

  pinMode(MIC_PIN, INPUT);
  analogReadResolution(12);

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERROR|rmt_init_failed");
    while (true) delay(1000);
  }

  // Slow startup color sweep through all eight bands.
  for (uint8_t band = 0; band < 8; ++band) {
    showBand(band);
    delay(180);
  }

  calibrateMicrophone();
  lastLedFrame = millis();
  Serial.println("HJ|METER|ready|bands=8|band_width=7.5|led_fps=25");
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

  uint8_t band = controlToBand(heldLevel);

  unsigned long now = millis();
  if (now - lastLedFrame >= LED_FRAME_MS) {
    lastLedFrame = now;
    showBand(band);
    ++frameCounter;
  }

  static unsigned long lastPrint = 0;
  if (millis() - lastPrint >= 100) {
    lastPrint = millis();
    Serial.printf("HJ|METER|RAW=%.0f|ABOVE=%.1f|LEVEL=%.1f|BAND=%u|FRAME=%lu|FLOOR=%.1f\n",
                  rawLevel, above, heldLevel, (unsigned)(band + 1), frameCounter, noiseFloor);
  }
}
