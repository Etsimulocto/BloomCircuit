# HAPPY JARZ ESP32 firmware

**Current staging path:** `happyjarz_integrated_v0_5.ino` + standard patch pipeline

This folder contains the integrated ESP32-S3 firmware used by the HAPPY JARZ desktop/Pi controller. The current product build is intentionally assembled through the Pi flash helper so the known-good hardware layer can stay stable while newer OLED, menu, pattern, sayings, screensaver, power-status and protocol behavior is applied in controlled stages.

## Preserve the known-good light layer

The proven APA106 driver uses the Arduino ESP32 HAL RMT path and should not be casually replaced while adding UI or protocol features.

Known-good timing:

- ESP32-S3 SuperMini
- GPIO7 for APA106 data
- 10 MHz RMT clock
- bit 0 ~= 4 ticks high / 14 ticks low
- bit 1 ~= 14 high / 4 low
- ~100 us reset/latch
- two APA106 lamps daisy chained
- proven byte order: **RGB**

Generic NeoPixel/FastLED attempts were not the proven path for this hardware.

## Current wiring

### APA106 lamps

- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- both lamp VCC pins -> 5V
- common GND

The tested lamps accept the ESP32-S3's 3.3V GPIO data while powered from 5V, so this prototype currently runs without a separate level-shifter IC. Never feed 5V into an ESP32 GPIO.

### Capacitive touch

Current six-control map:

- GPIO4 = UP
- GPIO5 = DOWN
- GPIO9 = LEFT
- GPIO10 = RIGHT
- GPIO1 = A
- GPIO2 = B

HOME behavior:

- A advances Light 1 through the palette
- B advances Light 2 through the palette
- UP advances the pattern
- DOWN moves to the previous pattern
- RIGHT enters the OLED menu
- LEFT currently has no HOME action

Menu/detail screens own the controls while active, preventing HOME light actions from leaking through menu navigation.

The proven touch path uses direct `touchRead()`, the original roughly +20% threshold, ~60 ms qualification, baseline drift behavior and simple latch semantics. The later hysteresis/cooldown/release experiment was removed because it caused same-button repeat failures.

### OLED

Current 4-wire I2C OLED:

- VCC -> 3.3V
- GND -> GND
- SDA -> GPIO8
- SCL -> GPIO6
- I2C address `0x3C`
- U8g2 rendering path
- 128x64 layout

The OLED provides centered HOME/menu/detail/status pages and the current idle screensaver system.

## Fuel Gauge / power status

The standard staging pipeline applies `patch_happyjarz_fuel_gauge.py` after the current saver/protocol layers, then applies `patch_happyjarz_home_power_cycle.py` as the final standalone HOME polish layer.

The Fuel Gauge adds:

- `POWER` item in the OLED main menu
- battery voltage display
- estimated battery percentage
- raw ADC diagnostics
- USB data-link diagnostics
- `GET POWER` serial diagnostic
- standalone HOME power-state cycle

### Bench-proven prototype calibration

Current sensing path:

- GPIO3 = onboard battery/supply ADC sense path on the current ESP32-S3 SuperMini prototype
- divider ratio = `2.0`
- current provisional `BATTERY_CAL_FACTOR` = **`1.370`**
- percentage is a LiPo voltage estimate, not a coulomb counter

October 2, 2026 bench test:

- battery physically connected to the board's B+/B- pads
- battery-only operation initially read about `3.06 V` with calibration factor `1.000`
- applying calibration factor `1.370` produced about **`4.16 V` and `98%`** on the charged battery
- HOME correctly reported **`PWR BAT`**

That 4.16 V / 98% battery-only result is the current bench-proven reference for this prototype board. Do not assume the same factor for a different ESP32-S3 SuperMini revision without checking it.

### USB behavior

With USB connected, the ADC path rises outside the plausible LiPo range. The firmware therefore refuses to present that value as a battery percentage and reports an unverified battery sensor state instead of inventing a number.

Example USB-connected response observed during bench testing:

```text
HJ|POWER|sensor=UNVERIFIED|adc_mv=2384|voltage=4.768|percent=-1|usb_data=1|charge=HW_ONLY
```

`usb_data=1` means the native USB CDC data link is present. It is not a universal USB-power detector; a wall charger may provide power without enumerating as a data device.

### HOME footer cycle

The HOME footer keeps the menu affordance visible and rotates power information about every **2.5 seconds**.

Battery-only operation cycles:

```text
A MENU  BAT 98%
A MENU  V 4.16
A MENU  PWR BAT
```

With USB present it reports `PWR USB`; battery percentage is shown as unavailable while the sensed voltage is outside the valid LiPo range. The USB cycle also exposes:

```text
A MENU  CHG ?
```

`CHG ?` is intentional. The onboard charger IC's CHARGING/FULL signal is **not currently exposed to an ESP32 GPIO**, so firmware cannot honestly distinguish `CHARGING` from `FULL` yet. Do not infer charger state from USB CDC presence.

The detailed POWER page and serial protocol retain the same hardware-only limitation for charge state.

## Brightness ceiling

The current product build uses a **50% hard maximum LED brightness**.

Bench testing showed that abrupt high-brightness WHITE commands above roughly 50% could collapse toward blue, while lower-level RGB/white frames were correct and 50% was already bright enough for the sensory/fidget use case. The firmware and desktop controller therefore agree on 50% as the normal ceiling.

Do not change the custom RMT timing/order as a first response to this historical brightness behavior; the RGB frame format was separately proven at safe brightness.

## Pattern library

Current pattern names:

- `SOLID`
- `FADE`
- `PULSE`
- `RAINBOW`
- `RANDOM`
- `HUE_FADE`
- `DUAL_HUE`
- `BREATH`
- `DRIFT`
- `AURORA`
- `OCEAN`
- `LAVENDER`
- `SUNSET`
- `CHRISTMAS`
- `HALLOWEEN`
- `VALENTINE`
- `EASTER`
- `FOURTH`
- `THANKSGIVING`
- `CANDY`
- `GALAXY`
- `FIRE`
- `ICE`
- `FOREST`
- `NEON`
- `TWINKLE`
- `SPARKLE`
- `COLOR_SWAP`
- `COMET`
- `FIREFLY`
- `BUBBLEGUM`
- `OFF`

Many generated modes use continuous/intermediate RGB values rather than only the small physical-button color palette.

## OLED screensaver system

Screensaver mode starts automatically after **30 seconds of inactivity**.

The original first-pass timeout was 10 seconds. Bench use showed that 10 seconds interrupted normal menu/power-status reading, so the final HOME power-cycle patch extends the idle timeout to 30 seconds.

Current saver modes:

### SAYINGS

- horizontal marquee
- varied vertical lanes
- large built-in positive/funny/maker/glitter saying bank
- persistent custom sayings
- saying source modes: `BUILTIN`, `CUSTOM`, `MIXED`

Custom business/user messages:

- 8 slots
- up to 96 characters per slot
- stored in ESP32 Preferences
- survive unplug/restart

### SPIRAL

Procedural spiral generator. A stable seed creates a recipe that animates smoothly until reseeded.

### TRIPPY

Procedural geometry engine built from simple drawing primitives, including waves, dots, rings, line fields, graphic-EQ bars, Lissajous-like point clouds and lattice patterns.

### PARTICLES

Procedural particle-universe saver layered into the current saver stack.

### Art-saver controls

While a screensaver is active:

- LEFT / RIGHT = previous / next saver
- B = exit screensaver
- SPIRAL/TRIPPY/PARTICLES: UP = faster
- SPIRAL/TRIPPY/PARTICLES: DOWN = slower
- SPIRAL/TRIPPY/PARTICLES: A = reseed / generate a new universe

The procedural seed mixes live board state such as `millis()`, `micros()`, ESP32 temperature, Wi-Fi RSSI, all six touch readings, brightness, current LED RGB state and PRNG state.

## Saver serial controls

The current firmware patch pipeline adds saver control/status commands used by the v0.3.3 desktop controller:

```text
GET SAVER STATUS
SAVER ENTER
SAVER EXIT
SAVER NEXT
SAVER PREV
SAVER RESEED
SAVER SPEED UP
SAVER SPEED DOWN
SET SAVER MODE SAYINGS|SPIRAL|TRIPPY|PARTICLES
```

Custom-sayings protocol includes:

```text
GET CUSTOM SAYINGS
SET CUSTOM SAYING <1-8> <text>
CLEAR CUSTOM SAYINGS
SET SAYING SOURCE BUILTIN|CUSTOM|MIXED
```

Power diagnostic:

```text
GET POWER
```

## USB identity

At 115200 baud the firmware responds to `HELLO` with an `HJ|IDENTITY|...` line. The Pi/PC watcher uses this identity to distinguish a HAPPY JARZ from unrelated serial devices.

The base identity string currently still reports `fw=0.5`; the later patch stack adds current OLED/saver/power behavior on top of that known-good v0.5 base.

## Current Pi compile/upload path

Use the standard helper:

```bash
cd ~/BloomCircuit
git pull --ff-only
bash happyjarz-controller/tools/flash_happyjarz_v0_5.sh
```

The helper stages:

```text
happyjarz-controller/firmware/happyjarz_integrated_v0_5.ino
```

and applies the current patch stack before compiling/uploading.

Current patch stages include:

- compatibility/Wi-Fi/USB host-time integration
- proven touch behavior
- OLED pages/menu
- HOME/menu control isolation
- expanded sensory pattern library
- screensavers
- expanded marquee sayings
- persistent custom sayings
- procedural SPIRAL/TRIPPY controls
- particle-universe saver
- saver serial protocol/status
- Fuel Gauge POWER menu + GPIO3 ADC + `GET POWER`
- final HOME power-cycle + **30-second** idle timeout

The tested Arduino CLI FQBN is:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

The helper auto-detects `/dev/ttyACM*` or `/dev/ttyUSB*`, stops the controller/watcher before compile/upload, and restarts the watcher after a successful upload.

## Diagnostics / failure boundary

Preserve known-good layers.

If USB/controller behavior is wrong but local touch, LEDs and OLED still work, debug the protocol/controller side first.

If local LEDs/touch/OLED fail, debug the firmware/hardware layer before changing the desktop application.

Useful diagnostics include RGB tests, touch/input tests, status requests, `GET POWER`, saver status, Wi-Fi status/scan and service logs.

**Every feature should carry its own diagnostic path.**