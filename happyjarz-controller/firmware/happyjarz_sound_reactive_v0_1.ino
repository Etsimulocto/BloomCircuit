// HAPPY JARZ — APA106 update-path isolation test v1.3
//
// PURPOSE
//   Remove the microphone and all animation math.
//   Alternate BLUE OFF / BLUE ON once per second using the known-good
//   ESP32-S3 RMT timing and GRB byte order.
//
// If serial keeps printing ON/OFF but the physical LED sticks on one state,
// the fault is in the LED data/power path rather than sound processing.

#include <Arduino.h>
#include "esp32-hal-rmt.h"

static constexpr uint8_t LED_DATA_PIN = 7;
static constexpr uint8_t LED_COUNT = 2;

struct Rgb { uint8_t r, g, b; };

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
    // HAPPY JARZ APA106 physical batch: GRB packet order.
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

static void showBlue(uint8_t value) {
  Rgb frame[LED_COUNT] = {
    {0, 0, value},
    {0, 0, value}
  };
  writeFrame(frame);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HJ|BLINK|boot|fw=1.3|mode=BLUE_1HZ|packet=GRB|led=GPIO7");

  if (!initApa106Rmt()) {
    Serial.println("HJ|ERROR|rmt_init_failed");
    while (true) delay(1000);
  }

  showBlue(0);
  delay(500);
  Serial.println("HJ|BLINK|ready");
}

void loop() {
  static bool on = false;
  static unsigned long cycle = 0;

  on = !on;
  ++cycle;

  uint8_t blue = on ? 48 : 0;
  showBlue(blue);

  Serial.printf("HJ|BLINK|cycle=%lu|state=%s|blue=%u\n",
                cycle, on ? "ON" : "OFF", (unsigned)blue);

  delay(1000);
}
