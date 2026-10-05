# BloomPetz Architecture

BloomPetz is split into four major layers:

1. hardware/runtime — OLED, touch, LEDs, sound, USB, persistence
2. pet engine — state, daily progression, interaction, developmental stats, events
3. editable content/data — stats, reactions, traits, foods, milestones, growth
4. host app — mirror, library, backup, restore, editing, diagnostics

## Current v0.1 runtime

The working prototype runs on an ESP32-S3 SuperMini and currently includes:

- SSD1306 128x64 OLED
- six capacitive touch inputs
- two APA106 LEDs
- three persistent pet slots
- on-device pet creation/editing
- eight daily actions
- Simon-style D-pad interaction
- food/treat loop
- 200 persistent developmental floats
- 20-category / 200-stat on-device browser
- USB screen mirror and keyboard-input bridge
- Raspberry Pi mini companion app

## Stat model

The 200 developmental stats are a fixed save-space map:

- 20 categories
- 10 stats per category
- index range 0..199

The canonical category order is defined in `data/stats/stat_manifest.json`. Category JSON files supply the ten stat names for each range. Do not reorder the canonical mapping after saves exist; migrate save formats instead.

## UI model

The OLED remains a fixed four-line interface. HOME, menus, creator/editor, action screens, and STATS browsing all route through the same display abstraction and USB screen-mirror path.

The current main menu is FEED / TREAT / SLOT / EDIT|CREATE PET / STATS, rendered as a three-row scrolling window plus footer.

## Persistence

The physical device supports three active pet slots. Each save stores identity, lifetime counters, food/daily state, and all 200 stat values through ESP32 Preferences-backed persistence.

Host storage may later archive unlimited `.bloompet` files.

## Development rule

Prefer small modules and human-readable data over monolithic source files.

The repository baseline firmware can lag the known-good locally integrated OLED/touch build during bench development. Use targeted patch helpers under `tools/` rather than replacing the local working sketch wholesale.

BloomCore rule: each subsystem should expose an independent diagnostic path and preserve known-good lower layers.
