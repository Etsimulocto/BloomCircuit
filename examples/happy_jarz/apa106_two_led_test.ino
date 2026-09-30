/*
  HAPPY JARZ — Two APA106 LED Hardware Diagnostic
  BloomCore diagnostic: prove the light chain before building features.

  HARDWARE
  --------
  Controller: ESP32-S3 SuperMini
  LEDs:       2x APA106 8 mm addressable RGB LEDs
  Protocol:   GRB, 800 kHz

  DATA PATH
  ---------
  ESP32 DATA_PIN
      -> SN74AHCT125 level shifter
      -> 470 ohm series resistor
      -> LED #1 DIN
  LED #1 DOUT
      -> LED #2 DIN

  LED PIN ORDER (APA106-F8 datasheet numbering)
  ---------------------------------------------
  1 = DIN
  2 = VCC / +5 V
  3 = GND
  4 = DOUT

  POWER
  -----
  Both LEDs: +5 V and common GND.
  ESP32, AHCT125, LED #1, LED #2, and supply MUST share ground.
  Keep a local bypass capacitor across VCC/GND at each LED.

  AHCT125 CHANNEL 1
  -----------------
  pin 14 = +5 V
  pin 7  = GND
  pin 1  = /OE -> GND
  pin 2  = input from ESP32 DATA_PIN
  pin 3  = output -> 470 ohm -> LED #1 DIN

  LIBRARY
  -------
  Install "Adafruit NeoPixel" from Arduino Library Manager.

  IMPORTANT
  ---------
  Set DATA_PIN below to the GPIO you physically wired to AHCT125 pin 2.
  Do not change known-good power/data wiring while diagnosing software.
*/

#include <Adafruit_NeoPixel.h>

// CHANGE THIS to the ESP32-S3 GPIO actually wired to AHCT125 pin 2.
#define DATA_PIN 7
#define LED_COUNT 2

// APA106 uses WS2812-style 800 kHz timing and is normally GRB.
Adafruit_NeoPixel leds(LED_COUNT, DATA_PIN, NEO_GRB + NEO_KHZ800);

const uint8_t TEST_BRIGHTNESS = 40;  // intentionally low for bench testing

void showPair(uint32_t led0, uint32_t led1, uint16_t holdMs = 900) {
  leds.clear();
  leds.setPixelColor(0, led0);
  leds.setPixelColor(1, led1);
  leds.show();
  delay(holdMs);
}

void allOff(uint16_t holdMs = 500) {
  leds.clear();
  leds.show();
  delay(holdMs);
}

void diagnosticSequence() {
  const uint32_t RED   = leds.Color(255, 0, 0);
  const uint32_t GREEN = leds.Color(0, 255, 0);
  const uint32_t BLUE  = leds.Color(0, 0, 255);
  const uint32_t WHITE = leds.Color(255, 255, 255);
  const uint32_t OFF   = leds.Color(0, 0, 0);

  // 1. Prove each address independently.
  showPair(BLUE, OFF);
  showPair(OFF, BLUE);

  // 2. Prove all three color channels on both LEDs.
  showPair(RED, RED);
  showPair(GREEN, GREEN);
  showPair(BLUE, BLUE);

  // 3. Low-brightness white checks simultaneous RGB and power stability.
  showPair(WHITE, WHITE);

  // 4. Verify that both LEDs can be commanded fully off.
  allOff(1000);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("HAPPY JARZ APA106 TWO-LED DIAGNOSTIC");
  Serial.println("Expected sequence:");
  Serial.println("1) LED1 blue / LED2 off");
  Serial.println("2) LED1 off / LED2 blue");
  Serial.println("3) both red");
  Serial.println("4) both green");
  Serial.println("5) both blue");
  Serial.println("6) both white (low brightness)");
  Serial.println("7) both off");

  leds.begin();
  leds.setBrightness(TEST_BRIGHTNESS);
  allOff(300);
}

void loop() {
  diagnosticSequence();
  delay(1200);
}
