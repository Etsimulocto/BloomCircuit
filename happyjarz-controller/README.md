# HAPPY JARZ Controller

**Current platform release pair:** desktop app **v1.5.0** + firmware **v0.12.0**

This subsystem is the PC/Raspberry Pi field-service and control layer for the HAPPY JARZ powered stand. It sits above the known-good ESP32-S3 light/touch/OLED hardware layer and is designed so desktop-side changes do not casually rewrite the proven APA106 timing.

## Release/version discipline

Authoritative files:

```text
happyjarz-controller/VERSION          # desktop app version
happyjarz-controller/firmware/VERSION # firmware version
```

Current values:

```text
App      1.5.0
Firmware 0.12.0
```

Legacy filenames such as `happyjarz_controller_v0_3_3.py`, `happyjarz_integrated_v0_5.ino`, and `flash_happyjarz_v0_5.sh` are compatibility names only. The flasher reads `firmware/VERSION`, injects it into `HJ_FW_VERSION`, and verifies the final staged build before upload.

## Current proven behavior

- identify a Jar over USB serial and reconnect after unplug/replug
- independent Light 1 / Light 2 / Light 3 / Light 4 color control
- full **0-100% LED brightness range** in firmware
- on-device SOLID brightness tuning under `MENU -> LIGHTS`
- expanded sensory/holiday/color pattern library
- six capacitive-touch controls
- OLED HOME/menu/status pages
- standalone CLOCK date/time editor with no PC or Wi-Fi required while powered
- SETTINGS editors for ALARM and TIMER
- board-native HAPPY ARCADE with seven mini-games
- board-local **INFO / MANUAL** with 12 help pages
- Fuel Gauge / `GET POWER` telemetry
- 30-second screensaver timeout with SAYINGS / SPIRAL / TRIPPY / PARTICLES
- persistent custom marquee sayings
- transient desktop MENU/GAME input modes that fall back to local JAR control when the USB CDC session disappears

## Bench-proven hardware map

Controller: **ESP32-S3 SuperMini**

### APA106 lighting

- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- APA106 #2 DOUT -> APA106 #3 DIN
- APA106 #3 DOUT -> APA106 #4 DIN
- common GND with ESP32
- proven byte order: **RGB**
- ESP32 data is 3.3V logic

Bench baseline, October 2, 2026:

- the original two-lamp prototype operated through the full **0-100%** firmware range with lamp VCC at **3.3V**
- the same prototype also operated through the full **0-100%** range with lamp VCC at **5V**
- no blue-collapse / blue-shift was observed during this test
- **24% at 3.3V** was already visually plenty for normal jar use
- **5V at 100% is extremely bright** and is better treated as an intentional high-output / room-glow mode than a normal default

The old 50% firmware hard cap is therefore retired. The product can keep the full range available while using a much lower normal brightness setting.

Do not route 5V into an ESP32 GPIO. The successful 5V test applies to the APA106 lamp supply, not the ESP32 data pin.

Known-good RMT timing:

- 10 MHz clock
- bit 0 ~= 4 ticks high / 14 low
- bit 1 ~= 14 high / 4 low
- ~100 us reset/latch

### Capacitive touch

Physical map:

- GPIO4 = UP
- GPIO5 = DOWN
- GPIO9 = LEFT
- GPIO10 = RIGHT
- GPIO1 = A
- GPIO2 = B

Current HOME behavior:

- UP = next pattern
- DOWN = previous pattern
- LEFT = next Light 1 color
- RIGHT = next Light 2 color
- A = open OLED menu
- B = no HOME action

The proven touch layer uses direct `touchRead()`, roughly +20% thresholding, ~60 ms qualification, slow baseline drift and one action per touch/release cycle.

### OLED

Current 4-wire I2C OLED:

- VCC -> 3.3V
- GND -> GND
- SDA -> GPIO8
- SCL -> GPIO6
- address `0x3C`
- U8g2 renderer
- 128x64 layout

## MENU behavior

Main menu includes:

- CLOCK
- LIGHTS
- GAMES
- SETTINGS
- SYSTEM
- INFO

### CLOCK

CLOCK can be set entirely on the board:

- LEFT / RIGHT = choose MONTH / DAY / YEAR / HOUR / MINUTE
- UP / DOWN = change selected value
- A = save
- B = cancel/back

Without a battery-backed RTC, the ESP32 cannot account for elapsed time while fully powered off.

### LIGHTS / SOLID brightness

The current board-local brightness editor exposes the real 0-100% range:

- UP / DOWN = +/-5%
- LEFT / RIGHT = +/-1%
- A = save
- B = save/back

Bench preference for normal sensory use is approximately **24% at 3.3V**. Higher values remain available for brighter wall/ceiling illumination.

### SETTINGS

Current SETTINGS entries:

- ALARM
- TIMER

The earlier DISPLAY brightness editor was removed because it did not provide a useful product control for this OLED module/build.

### INFO / MANUAL

INFO is a 12-page built-in manual that works with no PC or Wi-Fi. It covers HOME controls, colors, brightness, clock/date, alarm/timer, arcade, screensavers, power/battery, USB/Wi-Fi behavior, and firmware/system information.

Controls:

- RIGHT / DOWN / A = next page
- LEFT / UP = previous page
- B = back to main menu

## Battery / power telemetry

Current prototype sensing path:

- GPIO3 ADC
- divider ratio `2.0`
- provisional `BATTERY_CAL_FACTOR = 1.370`
- battery percentage is voltage-estimated, not coulomb counted

Bench reference:

```text
V 4.16
BAT 98%
PWR BAT
```

`CHG ?` is intentional when USB is present because the charger IC charging/full signal is not wired to an ESP32 GPIO.

## Four-lamp lighting

Firmware v0.11.0 expands the physical APA106 chain to four lamps while preserving the proven GPIO7/RMT transport.

- all four lamps remain on the same daisy-chain data pin
- Light 1 through Light 4 have independent persistent SOLID colors
- USB protocol exposes `SET LED1 COLOR` through `SET LED4 COLOR`
- `GET STATUS` reports `led1` through `led4`
- two-color presets alternate across all four lamps
- RAINBOW uses four phase-separated colors
- RANDOM generates four independent colors
- TWINKLE / SPARKLE use each lamp's own selected base color
- COLOR_SWAP rotates all four selected colors

The desktop Pi/PC controller shows four independent light cards in a 2x2 layout.

## Pattern library

Current patterns:

`SOLID`, `FADE`, `PULSE`, `RAINBOW`, `RANDOM`, `HUE_FADE`, `DUAL_HUE`, `BREATH`, `DRIFT`, `AURORA`, `OCEAN`, `LAVENDER`, `SUNSET`, `CHRISTMAS`, `HALLOWEEN`, `VALENTINE`, `EASTER`, `FOURTH`, `THANKSGIVING`, `CANDY`, `GALAXY`, `FIRE`, `ICE`, `FOREST`, `NEON`, `TWINKLE`, `SPARKLE`, `COLOR_SWAP`, `COMET`, `FIREFLY`, `BUBBLEGUM`, `OFF`.

## OLED screensavers

Screensaver mode starts after **30 seconds of inactivity**.

Modes:

- SAYINGS
- SPIRAL
- TRIPPY
- PARTICLES

Controls:

- LEFT / RIGHT = previous / next saver
- B = exit
- SPIRAL/TRIPPY/PARTICLES: UP/DOWN = speed
- SPIRAL/TRIPPY/PARTICLES: A = reseed / new universe

Custom sayings provide 8 persistent slots up to 96 characters each with `BUILTIN`, `CUSTOM`, and `MIXED` source modes.

## Current Pi flash workflow

From the feature branch during current development:

```bash
cd ~/BloomCircuit
git pull
bash happyjarz-controller/tools/flash_happyjarz_v0_5.sh
```

The helper stages the compatibility base, applies the current patch chain, verifies the final sketch, compiles with Arduino CLI, uploads, and restarts the watcher.

Current Arduino CLI FQBN:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

## Logs

```text
~/.happyjarz/plug_watch.log
~/.happyjarz/plug_watch_manual_start.log
~/.happyjarz/controller_launch.log
~/.happyjarz/controller.log
```

## Protocol + firmware

See [`PROTOCOL.md`](PROTOCOL.md), [`APP_PROTOCOL_V0_3.md`](APP_PROTOCOL_V0_3.md), [`firmware/README.md`](firmware/README.md), and [`VERSIONING.md`](VERSIONING.md).

## Failure boundary

Preserve known-good layers. If local LED/touch/OLED behavior works but the desktop UI does not, debug watcher/controller/protocol deployment first. If local LEDs/touch/OLED fail, debug firmware/hardware before changing the desktop app.


### Integrated Mini mirror/controller

App v1.4.0 / firmware v0.12.0 add the first synchronized Mini directly to the bottom of LIGHTS + CONTROL.

Current behavior:
- actual 128x64 U8g2 framebuffer mirror from the device
- one shared serial connection; no second OLED serial owner
- 12 visible app controls
- SIMPLE enables UP/DOWN/LEFT/RIGHT/A/B
- X/Y/L/R/START/SELECT remain visible but disabled until a FULL device advertises them
- app keys use the same firmware input path consumed by physical copper touch
- returned HJ|EVENT input messages pulse the matching Mini button
- OLED telemetry is change-driven, Base64 encoded and capped at 4 Hz

Do not reconstruct menus independently in the host app. The physical device framebuffer is authoritative.


### Gamepad routing

App v1.5.0 carries forward the proven BloomPetz Linux gamepad lessons without copying its early hard-coded-index behavior.

Routing order:
1. prefer semantic `/dev/input/event*`
2. fall back to semantic `/dev/input/js*`
3. never read both paths simultaneously for the same controller

Mapped logical controls:
- D-pad / hat / left stick -> UP DOWN LEFT RIGHT
- South -> A
- East -> B
- West -> X
- North -> Y
- TL -> L
- TR -> R
- START -> START
- SELECT -> SELECT

All gamepad events enter the same host `KEY ...` path used by clickable Mini controls. Device capability gating still applies, so SIMPLE ignores FULL-only actions until a FULL device advertises them.

The Mini OLED mirror uses blue pixels on black to match the physical blue OLED modules.
