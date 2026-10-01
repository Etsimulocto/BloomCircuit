# HAPPY JARZ ESP32 firmware

**Current bench-proven firmware:** v0.4

This folder contains the integrated ESP32-S3 firmware plus the USB-serial control layer used by the HAPPY JARZ desktop/Pi controller.

## Preserve the known-good light layer

The proven APA106 driver uses the Arduino ESP32 HAL RMT path and should not be casually replaced while adding UI or protocol features.

Known-good timing:

- ESP32-S3 SuperMini
- GPIO7 for APA106 data
- 10 MHz RMT clock
- bit 0 ~= 4 ticks high / 14 ticks low
- bit 1 ~= 14 ticks high / 4 ticks low
- ~100 us reset/latch
- two APA106 lamps daisy chained

Generic NeoPixel/FastLED attempts were not the proven path for this hardware.

## Current wiring

### APA106 lamps

- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- both lamp VCC pins -> 5V
- common GND
- local decoupling capacitor at each lamp

The tested lamps accept the ESP32-S3's 3.3V GPIO data while powered from 5V, so this prototype currently runs without a separate level-shifter IC. Never feed 5V into an ESP32 GPIO.

### Capacitive touch

- GPIO1 = COLOR 1
- GPIO2 = COLOR 2
- GPIO4 = CYCLE UP
- GPIO5 = CYCLE DOWN

Behavior:

- COLOR 1 advances Light 1 through the palette
- COLOR 2 advances Light 2 through the palette
- CYCLE UP advances the scene pattern
- CYCLE DOWN moves to the previous scene pattern

Touch calibration uses a boot baseline, roughly 20% over-baseline qualification, ~60 ms valid-touch timing, and slow drift compensation while untouched.

### OLED

Bench-proven 4-wire I2C OLED:

- VCC -> 3.3V
- GND -> GND
- SDA -> GPIO8
- SCL -> GPIO6
- I2C address `0x3C`
- SSD1306 / Adafruit GFX library path confirmed

At boot the OLED shows device/status information for a few seconds, then rotates HAPPY JARZ positive messages.

## Patterns

The integrated firmware supports:

- `SOLID`
- `FADE`
- `PULSE`
- `RAINBOW`
- `RANDOM`
- `OFF`

`RANDOM` independently changes lamp colors at irregular intervals instead of behaving as a synchronized strobe.

## USB identity

At 115200 baud the firmware responds to `HELLO` with an identity line such as:

```text
HJ|IDENTITY|serial=HJ-001|hw=V1|fw=0.4
```

The Pi/PC watcher uses this identity to distinguish a HAPPY JARZ from unrelated serial devices.

## Serial protocol layer

`happyjarz_serial_shim.ino` provides the USB control surface and should call the product's already-proven functions instead of duplicating LED timing.

Required hooks:

```cpp
void hjSetLed(uint8_t led, uint8_t r, uint8_t g, uint8_t b);
void hjSetBrightness(uint8_t percent);
void hjSetPattern(const String &name);
void hjSaveSettings();
void hjRunRgbTest();
void hjRunTouchTest();
void hjReadTouch(uint32_t &c1, uint32_t &c2, uint32_t &up, uint32_t &down);
String hjStatusLine();
```

Main integration:

```cpp
void setup() {
  Serial.begin(115200);
  hjSerialBegin();
}

void loop() {
  hjSerialPoll();
}
```

The shim handles `HELLO`, configuration commands, diagnostics, and optional live touch telemetry.

## Known-good Pi compile/upload

The tested Arduino CLI FQBN is:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

Compile:

```bash
arduino-cli compile \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc \
  ~/hjflash/happyjarz_integrated_v0_1
```

Upload:

```bash
arduino-cli upload \
  -p /dev/ttyACM0 \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc \
  ~/hjflash/happyjarz_integrated_v0_1
```

## Failure boundary

If USB/controller behavior is wrong but local touch, LEDs, and OLED still work, debug the protocol/controller side first.

If local LEDs/touch/OLED fail, debug this firmware/hardware layer before changing the desktop application.