# BloomOS

Tiny appliance-style runtime for HAPPY JARZ electronics built around the ESP32-S3.

## Reference hardware — v0.0.1

- ESP32-S3 SuperMini: 4 MB flash, 2 MB PSRAM
- SH1106 128x64 I2C OLED at 0x3C
  - SDA GPIO7
  - SCL GPIO8
- HW-504 joystick powered from 3.3 V
  - VRX GPIO4
  - VRY GPIO5
  - SW GPIO6
- Planned main display: 2.4 inch 240x320 SPI TFT, controller/touch IC still to be verified before wiring.

## UI philosophy

BloomOS is an appliance, not a tiny desktop.

- Simple screens
- Large controls
- Joystick and touch should operate the same UI
- OLED is the permanent CORE/status/diagnostic display
- Color TFT becomes the main UI when fitted
- LAB is a first-class feature

## Initial navigation

- Joystick up/down: select
- Joystick click: open / back from a diagnostic
- HOME: BLOOM, LAB, TOOLS, SETTINGS
- LAB: I2C Scanner, Analog Scope, Input Test

## Build

Requires Arduino ESP32 core and U8g2.

Example:

```bash
arduino-cli compile --fqbn "esp32:esp32:esp32s3:CDCOnBoot=cdc" firmware/BloomOS
arduino-cli upload -p /dev/ttyACM0 --fqbn "esp32:esp32:esp32s3:CDCOnBoot=cdc" firmware/BloomOS
```

## Safety / bench rule

Verify wiring and voltage before power. Solder with USB/battery disconnected. Add a driver and its diagnostic together whenever practical.
