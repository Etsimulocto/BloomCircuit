# HAPPY JARZ Hardware / USB / App Synchronicity

## Primary product rule

HAPPY JARZ behaves like one synchronized system:

    physical hardware
          ⇅
    ESP32 device state
          ⇅
    USB protocol
          ⇅
    Pi / PC host app

The device remains usable by itself, but when a host app is connected, both sides represent the same current state.

The app must not merely remember the last command it sent.

## Device-authoritative state

The ESP32 is authoritative for hardware state:

- Light 1 / 2 / 3 / 4 current output color
- selected/base colors
- active pattern
- brightness
- OLED framebuffer/state
- input mode
- battery/power state
- clock/settings
- active mini-game/screensaver where applicable

If a physical touch control changes the Jar, the host app updates. If the host app changes the Jar, the physical device updates and then reports the new authoritative state back.

## Capability-aware host UI

The Pi/PC app contains the complete HAPPY JARZ interface.

The connected device advertises capabilities. The host enables or disables controls from that capability set.

    SIMPLE
      D-pad + A/B enabled
      FULL-only controls visible but disabled

    FULL
      D-pad + A/B enabled
      additional controls enabled

Do not maintain separate host apps merely because one board has fewer controls.

## Live lamp display

The four lamp swatches must show the actual current lamp output, not only the last manually selected SOLID color.

Current limitation:
- the existing controller remembers the last chosen colors
- animated patterns can change the real lamps without changing those swatches

Target:

    ESP32 output frame
        -> LED telemetry
        -> host app
        -> Light 1..4 swatches repaint live

Protocol state should distinguish:

- base_led1..base_led4 = persistent/user-selected colors
- live_led1..live_led4 = actual current physical output

The color picker edits base color. The live swatch follows physical output.

## OLED mirror

The host app includes a live 128x64 OLED mirror.

The ESP32 owns OLED rendering. The host should mirror the framebuffer actually sent to the display rather than maintaining a competing screen implementation.

A 128x64 monochrome framebuffer is 1024 raw bytes. Mirror transport should use change-only frames, a modest rate, and framing/checksum. Compression such as RLE can be evaluated on the bench.

USB mirror traffic must not interfere with controls, telemetry, or firmware updates.

## Logical input synchronization

All input sources map to the same logical action bus:

    physical touch
    host on-screen controls
    keyboard
    USB/Bluetooth gamepad
            ↓
      logical actions
            ↓
      active app/game/menu

The host visually indicates button activity regardless of where the action originated.

Common SIMPLE actions:

- ACTION_UP
- ACTION_DOWN
- ACTION_LEFT
- ACTION_RIGHT
- ACTION_A
- ACTION_B

FULL adds more actions only after the real board GPIO/input map is verified.

## Mini appearance editor

The host app includes a Mini appearance editor for host-side presentation.

Initial scope:

- Mini background/theme
- OLED bezel/frame appearance
- bulb indicator arrangement
- button/control presentation
- labels
- scale/zoom
- saved appearance presets

Appearance settings are separate from hardware configuration. A visual preset must never change GPIO identity or board profile.

## Connection synchronization

On connection/reconnection:

1. HELLO / identity
2. capability query
3. full state snapshot
4. start requested telemetry streams
5. host renders from received device state

Suggested message families:

- HJ|IDENTITY|...
- HJ|CAPS|...
- HJ|STATE|...
- HJ|LED_FRAME|...
- HJ|OLED_FRAME|...
- HJ|INPUT|...
- HJ|POWER|...
- HJ|EVENT|...

## Non-negotiable rule

Never treat host-side cached state as proof of physical device state.

When synchronization matters, state comes from the device.