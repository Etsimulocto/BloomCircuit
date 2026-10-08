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

Current platform development firmware baseline: `0.17.0`.
Current host app baseline: `1.7.0`.

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
