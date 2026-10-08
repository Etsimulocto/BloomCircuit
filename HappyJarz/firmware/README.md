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
