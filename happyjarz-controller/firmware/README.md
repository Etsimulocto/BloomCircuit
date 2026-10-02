# HAPPY JARZ ESP32 Firmware

**Current firmware release:** **v0.6.0**

**Compatibility staging base:** `happyjarz_integrated_v0_5.ino` + standard patch pipeline

The filename of the integrated base sketch is now intentionally separated from the firmware release number. The authoritative firmware version is:

```text
happyjarz-controller/firmware/VERSION
```

The flash pipeline injects that value into `HJ_FW_VERSION` after the current patch stack is applied and refuses to upload if the staged firmware does not report the same version.

See [`../VERSIONING.md`](../VERSIONING.md) for the mandatory version-bump rules.

## Preserve the known-good hardware layer

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

The tested lamps accept the ESP32-S3's 3.3V GPIO data while powered from 5V. Never feed 5V into an ESP32 GPIO.

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

The proven touch path uses direct `touchRead()`, roughly +20% thresholding, ~60 ms qualification, baseline drift and one action per touch/release cycle. Do not reintroduce the abandoned hysteresis/cooldown/release experiment that caused same-button repeat failures.

### OLED

Current 4-wire I2C OLED:

- VCC -> 3.3V
- GND -> GND
- SDA -> GPIO8
- SCL -> GPIO6
- I2C address `0x3C`
- U8g2 renderer
- 128x64 layout

The current HOME path uses the battery/power footer whether the clock is synced or not. The early-build `ALARM OFF` footer is no longer a valid current HOME screen.

## Fuel Gauge / power status

Current sensing path:

- GPIO3 = onboard battery/supply ADC path
- divider ratio = `2.0`
- provisional `BATTERY_CAL_FACTOR = 1.370`
- percentage is voltage-estimated, not coulomb counted

October 2, 2026 bench reference:

```text
V 4.16
BAT 98%
PWR BAT
```

HOME cycles power information about every **2.5 seconds**.

Battery-only:

```text
A MENU  BAT xx%
A MENU  V x.xx
A MENU  PWR BAT
```

USB present:

```text
A MENU  BAT --%
A MENU  PWR USB
A MENU  CHG ?
```

`CHG ?` is intentional. The onboard charger IC's charging/full signal is not currently wired to an ESP32 GPIO. USB CDC presence must not be interpreted as proof of charging or full state.

Serial diagnostic:

```text
GET POWER
```

## Brightness ceiling

The current product build uses a **50% hard maximum LED brightness**.

Bench testing showed that abrupt higher-brightness white loads could collapse toward blue while 50% was already bright enough for the sensory use case. The firmware and desktop controller therefore agree on 50% as the normal ceiling.

## Pattern library

Current patterns:

`SOLID`, `FADE`, `PULSE`, `RAINBOW`, `RANDOM`, `HUE_FADE`, `DUAL_HUE`, `BREATH`, `DRIFT`, `AURORA`, `OCEAN`, `LAVENDER`, `SUNSET`, `CHRISTMAS`, `HALLOWEEN`, `VALENTINE`, `EASTER`, `FOURTH`, `THANKSGIVING`, `CANDY`, `GALAXY`, `FIRE`, `ICE`, `FOREST`, `NEON`, `TWINKLE`, `SPARKLE`, `COLOR_SWAP`, `COMET`, `FIREFLY`, `BUBBLEGUM`, `OFF`.

Many generated modes use continuous/intermediate RGB values rather than only the small physical-button color palette.

## OLED screensavers

Screensaver mode starts after **30 seconds of inactivity**.

Current modes:

- **SAYINGS** — scrolling built-in/custom marquee
- **SPIRAL** — procedural spiral generator
- **TRIPPY** — procedural geometry engine
- **PARTICLES** — procedural particle-universe saver

Controls:

- LEFT / RIGHT = previous / next saver
- B = exit
- SPIRAL/TRIPPY/PARTICLES: UP/DOWN = speed
- SPIRAL/TRIPPY/PARTICLES: A = reseed / new universe

Custom sayings:

- 8 persistent slots
- up to 96 characters each
- `BUILTIN`, `CUSTOM`, or `MIXED`
- stored in ESP32 Preferences

Useful saver commands:

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

Custom-sayings commands:

```text
GET CUSTOM SAYINGS
SET CUSTOM SAYING <1-8> <text>
CLEAR CUSTOM SAYINGS
SET SAYING SOURCE BUILTIN|CUSTOM|MIXED
```

## USB identity and release version

At 115200 baud the firmware responds to `HELLO` with an `HJ|IDENTITY|...` line used by the Pi/PC watcher.

For the current release, identity must report:

```text
fw=0.6.0
```

The base sketch may still contain an older implementation version before staging. That is expected. The standard flasher injects the authoritative value from `firmware/VERSION` as the final release-version step before verification.

If `HJ|IDENTITY` does not match `firmware/VERSION`, treat the device as a stale/wrong build.

## Current Pi compile/upload path

First refresh the split controller snapshot:

```bash
cd ~/BloomCircuit
git checkout main
git pull
bash ./tools/split_pi_apps.sh
```

Then flash from that refreshed copy:

```bash
bash ~/HappyJarzController/tools/flash_happyjarz_v0_5.sh
```

The legacy helper filename remains for compatibility; it does **not** mean the release is still v0.5.

The helper stages the compatibility base and applies the current layers, including:

- compatibility / Wi-Fi / USB host-time integration
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
- final HOME power cycle + 30-second idle timeout
- release-version injection from `firmware/VERSION`

Before compiling or uploading, the verifier confirms the final staged sketch contains the required current features and the expected firmware release number.

Expected output for this release:

```text
HAPPY JARZ staged firmware verification: PASS
  firmware version 0.6.0
```

If that PASS does not appear, **do not flash**.

Tested Arduino CLI FQBN:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

The helper auto-detects `/dev/ttyACM*` or `/dev/ttyUSB*`, stops the desktop controller/watcher before compile/upload, and restarts the watcher after a successful upload.

## Version bump rule

Firmware behavior changes require a firmware version bump before merge. This includes changes to:

- touch behavior
- OLED/menu behavior
- battery/power handling
- LED patterns/brightness
- screensavers
- serial protocol
- startup/shutdown behavior
- hardware pins/calibration

Do not keep rebuilding different firmware under the same release number.

## Diagnostics / failure boundary

Preserve known-good layers.

If USB/controller behavior is wrong but local touch, LEDs and OLED still work, debug watcher/controller/protocol deployment first.

If local LEDs/touch/OLED fail, debug firmware/hardware before changing the desktop application.

Useful diagnostics include RGB tests, touch/input tests, status requests, `GET POWER`, saver status, Wi-Fi status/scan and service logs.

**Every feature should carry its own diagnostic path.**