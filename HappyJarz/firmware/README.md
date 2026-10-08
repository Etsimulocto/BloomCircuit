# Firmware Lanes

This folder will become the clean build surface for HAPPY JARZ firmware.

Planned layout:

```text
firmware/
  common/
  simple/
  full/
```

## common

Shared code:
- APA106 transport
- logical input layer
- OLED primitives
- serial protocol
- settings/persistence
- common games/screensavers where size allows
- power telemetry

## simple

S3 Mini / 4 MB target.

The current integrated firmware in the existing `happyjarz-controller` tree remains the proven development source while this new structure is introduced.

Do not move working low-level code merely for cosmetic cleanup.

## full

Full-size S3 target with more flash/PSRAM and additional inputs.

Do not implement the final FULL target until the actual board is bench-tested.

## Current SIMPLE firmware snapshot

Current proven SIMPLE development release: **0.17.9**.

The active integrated source remains in `happyjarz-controller` and is assembled by the staged patch pipeline.

Current product-level behavior includes:

- 100 four-lamp light patterns
- seven OLED screensavers
- seven native OLED mini-games
- calibrated and filtered battery telemetry
- low-battery bulb/OLED warning
- switched accessory-rail pause/resume
- one-hour software sleep with touch wake and alarm wake
- host OLED and LED-frame mirrors
- logical host/gamepad input routed through the device input layer

The ESP32 remains powered during both accessory pause and one-hour software sleep so clock, alarm and host communication can continue.
