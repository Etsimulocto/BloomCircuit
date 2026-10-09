# HAPPY JARZ Platform

This folder is the production-oriented scaffold for the next HAPPY JARZ architecture.

It is intentionally separated from BloomPulse and from unrelated BloomCircuit tools.

## Device classes

### SIMPLE

Target: ESP32-S3 Mini / 4 MB flash.

Current proven integrated base:
- six capacitive-touch inputs
- 128x64 OLED
- four daisy-chained APA106 lamps on GPIO7
- battery/power telemetry
- local clock, settings, screensavers, games and USB control

Current platform development firmware baseline: `0.17.11`.
Current host app baseline: `1.8.4`.

### FULL

Target: full-size ESP32-S3 with substantially more flash and PSRAM.

Expected target discussed during planning:
- 16 MB flash
- 8 MB PSRAM
- more touch/button inputs
- larger native game/screensaver/content budget

The exact FULL production board and GPIO map are **not yet bench-verified**. Do not publish a FULL firmware image until the real board is received and documented.

## Region lanes

The release system is designed for four lanes:

- `simple-us`
- `simple-eu`
- `full-us`
- `full-eu`

Region is a provisioned device property, not something inferred from USB hardware.

## Host layer

Pi/PC software will eventually:
1. detect the connected HAPPY JARZ
2. read device identity/capabilities
3. determine SIMPLE vs FULL
4. read the stored region
5. compare installed version against the release manifest
6. install only a compatible update
7. verify the flashed identity/version
8. launch the correct Mini/host experience

The updater is not implemented yet. This branch establishes the contract first so firmware, Pi and future PC support do not fragment into unrelated builds.

See:
- `docs/BOARD_PROFILES.md`
- `docs/UPDATE_SYSTEM.md`
- `docs/US_EU_PROFILES.md`
- `releases/manifest.json`


## Current synchronized Mini

The host app currently embeds a Mini controller in the bottom of LIGHTS + CONTROL.

Current behavior:
- actual device OLED framebuffer mirrored over the existing USB link
- blue pixels on black to match the physical blue OLED module
- 12 visible gamepad-style controls
- SIMPLE enables UP/DOWN/LEFT/RIGHT/A/B
- FULL-only X/Y/L/R/START/SELECT stay visible but disabled until advertised by hardware capabilities
- Linux gamepads use semantic mappings rather than fixed axis/button guesses
- `/dev/input/event*` is preferred; semantic `/dev/input/js*` is fallback
- gamepad and clickable controls both send through the same logical `KEY ...` protocol
- returned device input events pulse the matching Mini control

The physical device remains authoritative for live OLED state, inputs, lights and games.


Current SIMPLE platform build includes **100 registered light patterns**, with the newer 56 effects implemented through a compact shared descriptor engine rather than duplicated per-pattern code.


Current SIMPLE platform build includes seven OLED screensaver modes: SAYINGS, SPIRAL, TRIPPY, PARTICLES, BLOOM, BREATHE and GLITTER.


## Current visual stack

The current SIMPLE build carries:
- **100** registered four-lamp light patterns
- **7** OLED screensavers
- actual OLED framebuffer mirroring into the host Mini
- blue-on-black host rendering to match the physical blue SSD1306 display

The seven saver modes are:

```text
SAYINGS
SPIRAL
TRIPPY
PARTICLES
BLOOM
BREATHE
GLITTER
```

BLOOM is a procedural opening/closing lotus. BREATHE creates a perceived fade on the monochrome OLED using changing geometry and pixel density. GLITTER is a persistent falling mixed-shape field with independent drift, fall speed and occasional flash-stars.

Firmware `0.17.1` is the compile-fix release for this saver pack. It moves the visual-saver speed/state declarations ahead of saver-status telemetry and uses the installed U8g2 five-argument `drawArc()` signature.

## Power and sleep behavior

Current SIMPLE firmware `0.17.9` keeps the ESP32 alive while visible outputs can pause or sleep.

- GPIO3 battery telemetry is calibrated and filtered before percentage conversion.
- HOME keeps showing battery percentage while USB is attached.
- At 10% or lower, bulb 4 flashes red and the OLED shows `LOW BATTERY / CHARGE ME!!!`.
- The warning clears at 15% to prevent threshold chatter.
- OLED + four APA106 lamps may share a switched 3.3V accessory rail.
- OLED `0x3C` presence is used to detect accessory pause/resume.
- After one hour of no physical input, software sleep powers down the OLED display state, blanks all lamps and freezes pattern advancement.
- Any physical touch wakes the Jar without also executing that first button action.
- Alarm firing wakes the output stack before the alarm pattern runs.

This is software sleep, not ESP32 deep sleep, because clock, alarm, USB, Wi-Fi and capacitive touch must remain active.
