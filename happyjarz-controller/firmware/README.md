# HAPPY JARZ ESP32 Firmware

**Current firmware release:** **v0.17.9**

**Compatibility staging base:** `happyjarz_integrated_v0_5.ino` + standard patch pipeline

The integrated base filename is retained for compatibility. The authoritative firmware release is:

```text
happyjarz-controller/firmware/VERSION
```

The flash pipeline injects that value into `HJ_FW_VERSION` after staging and verifies the final sketch before upload.

## Preserve the known-good hardware layer

The proven APA106 driver uses the Arduino ESP32 HAL RMT path and should not be casually replaced while adding UI or protocol features.

Known-good timing:

- ESP32-S3 SuperMini
- GPIO7 for APA106 data
- 10 MHz RMT clock
- bit 0 ~= 4 ticks high / 14 ticks low
- bit 1 ~= 14 high / 4 low
- ~100 us reset/latch
- four APA106 lamps daisy chained
- proven byte order: **RGB**

## Current wiring

### APA106 lamps

- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- APA106 #2 DOUT -> APA106 #3 DIN
- APA106 #3 DOUT -> APA106 #4 DIN
- common GND
- ESP32 data remains 3.3V logic

Bench testing on October 2, 2026 established the original two-lamp electrical baseline working through the full firmware **0-100% brightness range** with lamp VCC at both **3.3V** and **5V**. No blue-collapse / blue-shift was observed in this test.

Practical visual result:

- **24% at 3.3V** is already plenty for normal sensory-jar use
- **5V at 100% is extremely bright** and can throw substantial light onto nearby walls/ceiling
- the earlier 50% hard cap is no longer used
- full 0-100% remains available for tuning and intentional high-output use

Never feed 5V into an ESP32 GPIO. The 5V test applies to the lamp supply only.

### Capacitive touch

Current six-control map:

- GPIO4 = UP
- GPIO5 = DOWN
- GPIO9 = LEFT
- GPIO10 = RIGHT
- GPIO1 = A
- GPIO2 = B

Current HOME behavior:

- UP = next pattern
- DOWN = previous pattern
- LEFT = next Light 1 palette color
- RIGHT = next Light 2 palette color
- A = open OLED menu
- B = no HOME action

The proven touch path uses direct `touchRead()`, roughly +20% thresholding, ~60 ms qualification, baseline drift and one action per touch/release cycle.

### OLED

Current 4-wire I2C OLED:

- VCC -> 3.3V
- GND -> GND
- SDA -> GPIO8
- SCL -> GPIO6
- I2C address `0x3C`
- U8g2 renderer
- 128x64 layout

## Board-local UI

Main menu:

- CLOCK
- LIGHTS
- GAMES
- SETTINGS
- SYSTEM
- INFO

### CLOCK

The clock/date can be set entirely on the board with no PC or Wi-Fi:

- LEFT / RIGHT = select MONTH / DAY / YEAR / HOUR / MINUTE
- UP / DOWN = change value
- A = save
- B = cancel

The ESP32 system clock runs while powered. Without a battery-backed RTC, it cannot know elapsed time while fully powered off.

### LIGHTS / SOLID brightness

Brightness is a real board-local 0-100% setting:

- UP / DOWN = +/-5%
- LEFT / RIGHT = +/-1%
- A = save
- B = save/back

Normal prototype preference is around **24% at 3.3V**. Higher values are intentionally available for brighter room-glow effects.

### SETTINGS

Current entries:

- ALARM
- TIMER

The DISPLAY brightness editor was removed because it was not useful on this OLED module/build.

### INFO / MANUAL

INFO is a 12-page built-in board manual. It requires no PC or Wi-Fi and covers:

- HOME button map
- Light 1 / Light 2 color controls
- SOLID brightness controls and 0-100% range
- clock/date setup
- alarm and timer
- HAPPY ARCADE
- screensavers
- power/battery status
- USB/Wi-Fi behavior
- firmware/system information

Navigation:

- RIGHT / DOWN / A = next page
- LEFT / UP = previous page
- B = back to main menu

## Fuel Gauge / power status

Current sensing path:

- GPIO3 = onboard battery/supply ADC path
- divider ratio = `2.0`
- calibrated `BATTERY_CAL_FACTOR = 0.802`
- percentage is voltage-estimated, not coulomb counted

Bench reference:

```text
V 4.16
BAT 98%
PWR BAT
```

`CHG ?` is intentional when USB is present because the charger IC charging/full signal is not wired to an ESP32 GPIO.

## Four-lamp behavior

Firmware v0.11.0 keeps the proven APA106 RMT timing unchanged and expands the staged logical lamp count from two to four.

Persistent color state and USB control are available independently for Light 1, Light 2, Light 3 and Light 4. `GET STATUS` reports all four RGB values.

High-level patterns are four-lamp aware: two-color scenes alternate across the chain; RAINBOW uses four phase offsets; RANDOM generates four independent colors; TWINKLE/SPARKLE retain each lamp's chosen base color; COLOR_SWAP rotates all four chosen colors.

## Brightness behavior

The firmware range is **0-100%**.

The old 50% clamp came from an earlier bench result where high-output white appeared to collapse toward blue. The later direct test on this prototype did not reproduce that behavior at either 3.3V or 5V lamp supply, so the cap was removed and the board-local tuner was added.

For product use, a lower default remains sensible because the lamps become visually excessive well before 100%.

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
- BLOOM
- BREATHE
- GLITTER

Controls:

- LEFT / RIGHT = previous / next saver
- B = exit
- SPIRAL/TRIPPY/PARTICLES: UP/DOWN = speed
- SPIRAL/TRIPPY/PARTICLES: A = reseed / new universe

## HAPPY ARCADE

The native OLED arcade is staged into the firmware and currently contains seven mini-games:

1. Catch the Glitter
2. Glitter Dodge
3. Bloom Snake
4. Memory Spark
5. Jar Pong
6. Meteor Tap
7. Bloom Runner

A long B press acts as HOME/escape from the arcade.

## Desktop input-mode fail-safe

`MENU` and `GAME` input modes are temporary desktop/service modes. They are not persisted as product state. If the USB CDC session disappears, firmware falls back to `JAR` mode and local physical controls regain ownership.

## USB identity and release version

At 115200 baud the firmware responds to `HELLO` with an `HJ|IDENTITY|...` line. For this branch/release it should report:

```text
fw=0.17.9
```

## Current Pi compile/upload path

```bash
cd ~/BloomCircuit
git pull
bash happyjarz-controller/tools/flash_happyjarz_v0_5.sh
```

The legacy helper filename remains for compatibility; it does **not** mean the release is v0.5.

The staging chain includes compatibility/Wi-Fi/host-time support, touch, OLED/menu, patterns, screensavers, sayings, particle saver, Fuel Gauge, HOME power cycle, standalone clock, standalone settings, 0-100 SOLID brightness editing, INFO/manual pages, board-native arcade, release-version injection, final verification, compile and upload.

Arduino CLI FQBN:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

## Version bump rule

Firmware behavior changes require a firmware version bump before merge, including touch behavior, OLED/menu behavior, battery/power handling, LED patterns/brightness, screensavers, serial protocol, startup/shutdown behavior, and hardware pins/calibration.

## Diagnostics / failure boundary

Preserve known-good layers. If USB/controller behavior is wrong but local touch, LEDs and OLED still work, debug watcher/controller/protocol deployment first. If local LEDs/touch/OLED fail, debug firmware/hardware before changing the desktop application.

## Low-battery warning

Firmware `0.17.9` uses the calibrated/filtered Fuel Gauge for warning decisions.

- enter warning at 10% or lower
- clear only at 15% or higher
- bulb 4 / right-side accent flashes red at 1 Hz
- bulbs 1-3 continue the current pattern
- OLED shows `LOW BATTERY`, `CHARGE ME!!!`, percentage and the USB-side cue
- invalid/unverified battery readings never trigger the warning

Battery voltage is lightly filtered before percentage conversion so normal ADC noise does not produce large visible percentage jumps.

## Switched accessory pause

OLED + four APA106 lamps can share a physical SPST-switched 3.3V accessory rail while the ESP32 remains powered.

Firmware probes OLED address `0x3C` and reports:

```text
HJ|ACCESSORY|state=PAUSED|sensor=OLED
HJ|ACCESSORY|state=ACTIVE|sensor=OLED
```

PAUSED freezes pattern progression, stops OLED rendering and holds the LED data path inactive. When the rail returns, the OLED is reinitialized and the current UI/pattern resumes.

## One-hour software sleep

After one hour without physical input:

- OLED enters controller power-save
- all four lamps are blanked
- pattern progression freezes
- ESP32 clock, alarm, USB, Wi-Fi and touch scanning remain active

Wake sources:

- any physical touch button
- alarm trigger

The first touch is consumed as a wake event so it does not also perform the normal button action. Alarm wake occurs before the normal alarm light pattern is applied.

```text
HJ|SLEEP|state=ASLEEP|reason=IDLE_1H
HJ|SLEEP|state=AWAKE|reason=TOUCH
HJ|SLEEP|state=AWAKE|reason=ALARM
```
