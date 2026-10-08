# HAPPY JARZ Unified Host App

## One host app

Pi and future Windows versions expose the same logical HAPPY JARZ application.

Do not create separate SIMPLE and FULL host apps. The full interface exists once and adapts to the connected device profile.

## Major surfaces

### Device
- connection state
- identity
- SIMPLE / FULL profile
- US / EU region
- firmware version
- updater state
- battery/power telemetry

### Lights
- Light 1 through Light 4
- base color controls
- live physical output-color swatches
- brightness
- patterns
- live pattern state

### OLED Mirror
- live 128x64 device framebuffer mirror

### Controls
- D-pad
- A / B
- FULL-only extra controls
- keyboard mapping
- gamepad mapping
- live pressed-state visualization

Unsupported controls remain visible but disabled.

### Games / Screens
- device-native mini-games
- device-native screensavers
- host-native Mini experiences
- host-native BloomSaver/screensaver integration

Each feature should identify whether it runs on DEVICE, HOST, or BOTH.

### Mini Appearance
- theme
- OLED frame/bezel
- bulb indicator layout
- button/control presentation
- labels
- scale
- saved presets

## Synchronization model

Host commands are requests, not final truth:

    user changes control
      -> host sends command
      -> ESP32 applies state
      -> ESP32 publishes authoritative state
      -> host redraws from received state

This applies to physical touch changes, animated patterns, OLED navigation, games, reconnects, and device-local settings.

See SYNCHRONICITY.md.
## Current implementation status

Host app v1.3.0 on the platform branch now includes:

- four Light cards with separate BASE and LIVE swatches
- 12-input gamepad tester: UP/DOWN/LEFT/RIGHT, A/B/X/Y, L/R, START/SELECT
- SIMPLE capability fallback that leaves FULL-only controls visible but disabled
- HJ|CAPS|controls=... parsing for future explicit capability advertisement
- HJ|LED_FRAME|... parsing for future live lamp telemetry
- HJ|INPUT| parsing for all 12 logical controls

Current integrated firmware does not yet publish continuous HJ|LED_FRAME telemetry, so animated LIVE swatches are host-ready but not yet fed by firmware.

OLED mirror and Mini appearance editor remain planned host surfaces and are not implemented by this Lights/Controls patch.
