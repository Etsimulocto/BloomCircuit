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

Host app v1.5.0 on the platform branch now includes:

- four Light cards with separate BASE and LIVE swatches
- 12-input gamepad tester: UP/DOWN/LEFT/RIGHT, A/B/X/Y, L/R, START/SELECT
- SIMPLE capability fallback that leaves FULL-only controls visible but disabled
- HJ|CAPS|controls=... parsing for future explicit capability advertisement
- HJ|LED_FRAME|... parsing for future live lamp telemetry
- HJ|INPUT| parsing for all 12 logical controls

Current integrated firmware does not yet publish continuous HJ|LED_FRAME telemetry, so animated LIVE swatches are host-ready but not yet fed by firmware.

The integrated Mini is now implemented in LIGHTS + CONTROL:
- actual 128x64 device framebuffer mirror
- 12 visible app gamepad controls
- capability gating for SIMPLE vs FULL
- one shared serial connection
- returned device input events pulse the Mini controls
- semantic Linux gamepad routing: event* preferred, js* fallback
- D-pad/hat/stick plus A/B/X/Y/L/R/START/SELECT logical mapping
- blue OLED mirror pixels matching the physical blue display

The Mini appearance editor remains planned until the production wood stand geometry is finalized.


## Current visual convention

The OLED mirror is blue-on-black to match the blue physical SSD1306 modules used by HAPPY JARZ.

The current Mini is a functional placeholder layout. Once the production wood stand geometry is finalized, the Mini appearance editor should reproduce the real stand's OLED position, lamp positions, control positions, labels and overall outline without changing the underlying logical input or synchronization model.


## OLED saver modes

The host exposes all seven device-local saver modes without reimplementing their graphics:

```text
SAYINGS
SPIRAL
TRIPPY
PARTICLES
BLOOM
BREATHE
GLITTER
```

The ESP32 remains the renderer and source of truth. The app only sends saver commands and mirrors the returned 1024-byte OLED framebuffer. This keeps BLOOM, BREATHE, GLITTER, arcade screens and future device-local visuals synchronized with the physical display.

For BLOOM/BREATHE/GLITTER, `HJ|SAVER|` reports the shared `visual_speed` value used by the host status readout.


### Multiple live OLED viewers

Multiple UI surfaces may display the same OLED framebuffer. App 1.7.1 shows the device framebuffer in both LIGHTS + CONTROL and OLED + PROCEDURAL SCREENSAVERS.

These are not separate mirrors or serial consumers. Both widgets are updated from the same decoded `HJ|OLED|` frame, preserving one serial owner and one authoritative device-rendered OLED state.
