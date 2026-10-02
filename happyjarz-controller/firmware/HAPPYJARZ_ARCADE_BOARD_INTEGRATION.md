# HAPPY JARZ Arcade — Board Integration

Status: board-native arcade logic is present in `happyjarz_arcade.h/.cpp` and is now staged automatically by the standard firmware flasher.

## Proven layers preserved

- APA106 custom RMT layer
- GPIO7 LED data path
- six-input capacitive calibration/debounce layer
- USB protocol / Wi-Fi / clock / alarm / timer / screensaver services

Confirmed input map:

- GPIO4 = UP
- GPIO5 = DOWN
- GPIO9 = LEFT
- GPIO10 = RIGHT
- GPIO1 = A / SELECT
- GPIO2 = B / BACK; hold B = HOME

The arcade consumes the existing qualified edge events. It does not call `touchRead()` or duplicate touch calibration.

## Confirmed OLED layer

The firmware README and OLED patch define the current known-good display path:

- SSD1306 128x64 monochrome OLED
- U8g2 renderer
- I2C address `0x3C`
- SDA = GPIO8
- SCL = GPIO6
- VCC = 3.3V
- GND = GND

The existing OLED initialization remains authoritative:

```cpp
Wire.begin(8, 6);
Wire.setClock(400000);
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oledSsd1306(U8G2_R0, U8X8_PIN_NONE);
oledSsd1306.setI2CAddress(0x3C << 1);
```

The arcade uses a small `HjArcadeDisplay` adapter bound directly to that existing U8g2 object. The game engine does not own or replace OLED initialization.

## Menu integration

Normal HOME behavior is preserved.

Path into the arcade:

```text
HOME
  -> RIGHT
MAIN MENU
  -> GAMES
  -> A
HAPPY ARCADE
```

Inside the arcade:

- UP/DOWN = menu navigation or game-specific vertical control
- LEFT/RIGHT = game-specific horizontal control
- A = select / primary action
- B = back / game-specific secondary action where used
- hold B = HOME escape back to the normal menu layer

When the arcade is active, its controls are captured so light/menu actions do not leak through.

## Board-native games

1. Catch the Glitter
2. Glitter Dodge
3. Bloom Snake
4. Memory Spark
5. Jar Pong
6. Meteor Tap
7. Bloom Runner

Bloom Runner controls:

- UP / DOWN = vertical lane
- LEFT / RIGHT = move runner backward / forward
- A = jump
- B = duck

## Standard flash staging

`patch_happyjarz_release_version.py` now performs the final arcade staging step automatically:

1. copy `happyjarz_arcade.h` into the Arduino sketch directory
2. copy `happyjarz_arcade.cpp` into the Arduino sketch directory
3. run `patch_happyjarz_arcade.py` against the fully staged firmware
4. inject the authoritative release number from `firmware/VERSION`

This means the existing normal flash command remains the product path; no manual arcade file copying is required.

## Release

Arcade integration is a firmware behavior change and therefore bumps the release to **0.7.0**.

Before uploading, the standard staged-firmware verifier must still report PASS. Do not flash if verification or compilation fails.
