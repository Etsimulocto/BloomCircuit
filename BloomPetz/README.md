# BloomPetz

Persistent idle/clicker/fidget virtual pets for the HAPPY JARZ ESP32-S3 platform.

This directory is intentionally split into small, obvious subsystems. Behavior code and editable game/pet data should remain separate wherever practical.

## Layout

- `firmware/` — ESP32-S3 runtime and hardware-facing code
- `data/` — editable stats, reactions, traits, foods, events, milestones, evolution data
- `pets/` — pet-type definitions
- `desktop/` — Raspberry Pi / PC companion app
- `saves/` — save-format documentation and fixtures
- `docs/` — architecture, display, USB, and pet-file specifications

## Core UI contract

- UP / DOWN = select
- LEFT / RIGHT = edit or change
- A = enter / perform
- B = back

OLED home layout:

1. Pet art + side-scrolling saying
2. Name + live information/stat
3. Current action/event/interaction
4. A action / B menu

Pet art is one line, maximum 16 character cells.

## Storage model

The physical device supports three active pet slots. PC/Raspberry Pi storage may archive unlimited `.bloompet` files.

Stats definitions are kept as human-editable data files. A pet save stores that individual pet's current values and history rather than redefining the stat system.
