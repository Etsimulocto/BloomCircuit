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

Current SIMPLE development release: **0.17.13**.

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

### Final logical-input order

Firmware `0.17.13` applies a final staging pass after CLOCK, SETTINGS, INFO, ARCADE and sleep integration so those late UI handlers cannot get ahead of the host/gamepad input merge.

```text
physical q[] scan
-> physical-only sleep wake
-> merge pending host/gamepad KEY events into q[]
-> all UI/game/saver/HOME routers
```

This keeps the one-hour wake behavior tied to real touch while making every normal menu screen use the same logical controls.

### APA106 resume after switched accessory power

The switched accessory pause intentionally holds GPIO7 LOW while the OLED and APA106 rail is off. On resume, firmware now deinitializes and reinitializes the ESP32 RMT transport on GPIO7 before restoring lamp output. This addresses the failure mode where firmware state and menus continued normally while the physical lamps remained frozen after a switch cycle.
