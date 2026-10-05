# BloomPetz

Persistent idle/clicker/fidget virtual pets for the HAPPY JARZ ESP32-S3 platform.

BloomPetz is now running as a working hardware prototype on the ESP32-S3 SuperMini with the 128x64 OLED, six copper capacitive inputs, two APA106 LEDs, persistent saves, a Raspberry Pi mirror/controller, pet creation/editing, daily interactions, Simon-style action play, and the full 200-stat developmental model.

This directory is intentionally split into small, obvious subsystems. Behavior code and editable game/pet data should remain separate wherever practical.

## Layout

- `firmware/` — ESP32-S3 runtime and hardware-facing code
- `data/` — editable stats, reactions, traits, foods, events, milestones, evolution data
- `pets/` — pet-type definitions
- `desktop/` — Raspberry Pi / PC companion app
- `saves/` — save-format documentation and fixtures
- `docs/` — architecture, display, USB, and pet-file specifications
- `tools/` — patch/build helpers used to evolve the working local firmware without replacing known-good hardware integration

## Current hardware UI

Six copper touch inputs act like a compact gamepad:

- UP / DOWN = select
- LEFT / RIGHT = edit, change, or page
- A = enter / perform
- B = back / menu

Current main menu:

```text
FEED
TREAT
SLOT
EDIT PET / CREATE PET
STATS
```

The menu uses a three-row scrolling window plus a footer. When `STATS` is selected, the lower menu view is:

```text
  SLOT 1
  EDIT PET
> STATS
A ENTER B BACK
```

## OLED home screen

The physical OLED is a 128x64 SSD1306 using a four-line text layout with decorative particle art in the side gutters.

Current HOME behavior:

1. Pet art / symbol and rotating pet sayings. Long sayings marquee.
2. Pet name alternating with live stat + value information. Long stat strings marquee.
3. Current selected daily action.
4. A/B controls plus rotating energy / treats / daily-action status.

The pet-art field is one text line and supports up to 16 ASCII characters.

## Pet creation and editing

Pets can be created and edited directly on the device.

Editable fields:

- Name — up to 12 printable ASCII characters
- Type — up to 12 printable ASCII characters
- Design / art — up to 16 printable ASCII characters

The editor uses all six touch controls and does not require the desktop app.

## Stats system

Each pet stores 200 persistent developmental floats organized as 20 canonical categories x 10 named stats.

The canonical mapping is defined by `data/stats/stat_manifest.json` and the category JSON files. Do not reorder those indexes after public save files exist; use save migration instead.

The on-device STATS browser exposes the full model:

- UP / DOWN — move across the 20 categories
- A — open the selected category
- LEFT / RIGHT — move across that category's 10 named stats
- B — back

Values are shown as percentages with four decimal places in the detailed browser.

## Daily interaction model

Current v0.1 actions:

- CHECK
- CLEAN
- PET
- PLAY
- REST
- SCRATCH
- SOCIALIZE
- TRAIN

Each successful first completion for the day applies weighted developmental growth, costs 12.5 energy, and records the action. Repeating an already-completed action is allowed for fun but does not re-award the daily growth reward.

Feeding only refills an empty stomach to 100. Treats are limited to three per day and each rolls developmental growth into one random stat. Midnight resets daily action/treat flags but does not reset food energy.

## Storage model

The physical device supports three active pet slots. PC/Raspberry Pi storage may later archive unlimited `.bloompet` files.

A pet save currently stores identity, history counters, food state, daily state, and all 200 developmental floats in ESP32 Preferences-backed persistent storage.

## Raspberry Pi companion

`desktop/bloompetz_mini.py` is the current lightweight Pi mirror/controller.

It mirrors the four OLED text lines over USB, accepts keyboard controls that feed the same input path as the physical touch controls, shows app-only color themes, and includes matching decorative side-particle lanes. Physical controls remain primary.

## Known-good flashing target

Current bench target:

```text
ESP32-S3 SuperMini
Arduino core: esp32 3.3.12
FQBN: esp32:esp32:esp32s3:CDCOnBoot=cdc
```

Typical compile/upload:

```bash
cd ~/BloomCircuit/BloomPetz/firmware
arduino-cli compile --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc bloompetz_v0_1
arduino-cli upload -p /dev/ttyACM0 --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc bloompetz_v0_1
```

Important: compile and upload are separate operations. A successful compile alone does not change the firmware currently running on the ESP32.
