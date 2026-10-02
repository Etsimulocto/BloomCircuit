# HAPPY JARZ Arcade — Board Integration Boundary

Status: board-native arcade logic is present in `happyjarz_arcade.h/.cpp`.

## Proven layers that must remain intact

- APA106 custom RMT layer from firmware v0.5
- GPIO7 LED data path
- six-input capacitive calibration/debounce layer
- input map:
  - GPIO4 = UP
  - GPIO5 = DOWN
  - GPIO9 = LEFT
  - GPIO10 = RIGHT
  - GPIO1 = A / SELECT
  - GPIO2 = B / BACK; hold B = HOME
- USB protocol / Wi-Fi / clock / alarm / timer services

## Arcade input bridge

Firmware v0.5 already computes edge-triggered input events in `serviceInputs()` using the `latched[]` array.

When `inputMode == "MENU"` or `inputMode == "GAME"`, each new qualified edge should call:

```cpp
if (q[IN_UP]    && !latched[IN_UP])    hjArcadeButton(HJ_BTN_UP);
if (q[IN_DOWN]  && !latched[IN_DOWN])  hjArcadeButton(HJ_BTN_DOWN);
if (q[IN_LEFT]  && !latched[IN_LEFT])  hjArcadeButton(HJ_BTN_LEFT);
if (q[IN_RIGHT] && !latched[IN_RIGHT]) hjArcadeButton(HJ_BTN_RIGHT);
if (q[IN_A]     && !latched[IN_A])     hjArcadeButton(HJ_BTN_A);
if (q[IN_B]     && !latched[IN_B])     hjArcadeButton(HJ_BTN_B);
```

The existing one-second B hold should additionally call:

```cpp
hjArcadeButton(HJ_BTN_HOME);
```

Do not duplicate touch calibration inside the arcade module.

## Main loop bridge

When arcade mode is active:

```cpp
hjArcadeService(millis());
```

The existing pattern/alarm/timer/serial services can continue to run non-blocking around it.

## OLED adapter — intentionally not guessed

The 128x64 OLED is confirmed at I2C address `0x3C`, but the known-good ESP32 OLED source and exact SDA/SCL GPIO assignments are not currently present in GitHub. Firmware v0.5 explicitly documents this gap.

Therefore the arcade uses `HjArcadeDisplay`, a small rendering interface:

```cpp
struct HjArcadeDisplay {
  void (*clear)();
  void (*pixel)(int16_t x, int16_t y, bool on);
  void (*line)(int16_t x0, int16_t y0, int16_t x1, int16_t y1, bool on);
  void (*rect)(int16_t x, int16_t y, int16_t w, int16_t h, bool fill, bool on);
  void (*text)(int16_t x, int16_t y, const char *s, uint8_t size);
  void (*present)();
};
```

Bind those seven functions to the already-proven OLED driver once its source is recovered. Do **not** replace the proven OLED initialization merely to make the games compile.

## Games currently board-native

1. Catch the Glitter
2. Glitter Dodge
3. Bloom Snake
4. Memory Spark
5. Jar Pong
6. Meteor Tap
7. Bloom Runner

## Runner controls

- UP / DOWN = vertical lane
- LEFT / RIGHT = move runner backward / forward
- A = jump
- B = duck

## Next safe hardware step

Recover the currently flashed/known-good OLED initialization or its exact SDA/SCL pins, bind the seven display callbacks, compile as a new firmware version, and run the display diagnostic before enabling the arcade menu.
