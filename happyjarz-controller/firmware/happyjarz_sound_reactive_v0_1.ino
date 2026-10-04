// HAPPY JARZ — slow raw-channel diagnostic v2.7
//
// PURPOSE
//   Make the LED byte-order test unmistakable.
//   No sound-reactive runtime in this build.
//   Each raw byte is shown for 3 seconds with 1 second OFF between steps.
//   After step 3, hold blue so the test is clearly finished.
//
// TEST SEQUENCE
//   STEP 1: raw byte1 only -> {72,0,0}
//   OFF 1 sec
//   STEP 2: raw byte2 only -> {0,72,0}
//   OFF 1 sec
//   STEP 3: raw byte3 only -> {0,0,72}
//   OFF 1 sec
//   FINAL: hold byte3/blue
//
// HARDWARE
//   ESP32-S3 SuperMini
//   GPIO7 -> 220 ohm -> APA106 #1 DIN -> APA106 #2 DIN
//   Local decoupling capacitor(s) across LED VCC/GND

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t LED_COUNT = 2;

static bool initApa106Rmt() {
  pinMode(LED_DATA_PIN, OUTPUT);
  digitalWrite(LED_DATA_PIN, LOW);
  if (!rmtInit(LED_DATA_PIN, RMT_TX_MODE, RMT_MEM_NUM_BLOCKS_1, 10000000)) {
    return false;
  }
  rmtSetEOT(LED_DATA_PIN, 0);
  return true;
}

static void writeRawBytes(uint8_t b1, uint8_t b2, uint8_t b3) {
  rmt_data_t symbols[LED_COUNT * 24];
  size_t n = 0;

  for (uint8_t led = 0; led < LED_COUNT; ++led) {
    uint8_t bytes[3] = { b1, b2, b3 };

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

void setup() {
  if (!initApa106Rmt()) {
    while (true) delay(1000);
  }

  // Clear first so the start is obvious.
  writeRawBytes(0, 0, 0);
  delay(1500);

  // STEP 1
  writeRawBytes(72, 0, 0);
  delay(3000);
  writeRawBytes(0, 0, 0);
  delay(1000);

  // STEP 2
  writeRawBytes(0, 72, 0);
  delay(3000);
  writeRawBytes(0, 0, 0);
  delay(1000);

  // STEP 3
  writeRawBytes(0, 0, 72);
  delay(3000);
  writeRawBytes(0, 0, 0);
  delay(1000);

  // Final marker: hold byte 3 continuously.
  writeRawBytes(0, 0, 72);
}

void loop() {
  // Diagnostic-only build. Hold final channel indefinitely.
  delay(1000);
}
