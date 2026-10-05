# BloomPetz Architecture

BloomPetz is split into five major layers:

1. hardware/runtime — OLED, touch, LEDs, sound, USB, persistence
2. pet engine — state, daily progression, interaction, developmental stats, events
3. editable content/data — stats, reactions, traits, foods, milestones, growth
4. BLOOM SYSTEM game layer — shared launcher plus device-local games such as DND
5. host app — mirror, library, backup, restore, editing, diagnostics

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
- BLOOM SYSTEM launcher
- playable DND hardware game
- USB screen mirror and keyboard-input bridge
- Raspberry Pi Mini companion app
- tested external 8BitDo input through the Pi

## Stat model

The 200 developmental stats are a fixed save-space map:

- 20 categories
- 10 stats per category
- index range 0..199

The canonical category order is defined in `data/stats/stat_manifest.json`. Category JSON files supply the ten stat names for each range. Do not reorder the canonical mapping after saves exist; migrate save formats instead.

## UI model

The OLED remains a fixed four-line interface for BloomPetz, while shared games may use specialized renderers when necessary.

BloomPetz HOME, menus, creator/editor, action screens, and STATS browsing route through the normal display abstraction and USB screen-mirror path.

DND owns the full logical 21-character OLED width and uses a 7-column HUD plus a 14-column map viewport across four rows. Its full-width renderer must also update the shared `screenLines[]` mirror state and emit `BP|SCREEN` frames so the Pi Mini sees the same logical display as the hardware.

Only the active app/mode may repaint the OLED. BloomPetz side-art/background refresh paths must pause while DND owns the display.

## BLOOM SYSTEM game layer

The shared launcher currently exposes:

```text
BLOOMPETZ
DND
```

DND is no longer a placeholder. It now has a compact RPG loop with movement, combat, rooms, enemies, loot, gold, inventory, shop purchases, symbols/reference pages, and player progression.

### DND content pools

The current content target is 48 entries for major reusable pools:

```text
48 items
48 enemy species
48 symbol/entity reference entries
48 room themes
```

The 48 room themes are layered over eight proven room-geometry archetypes. This deliberately separates presentation/content variety from geometry code so room generation can stay stable.

The 48 enemy entries are species definitions, not simultaneous actors. The live actor array remains intentionally small to fit the tiny map and OLED. Room depth controls which enemy tiers are eligible, with some lower-tier carryover for variety.

### DND economy

Gold is earned through enemies and dungeon loot and can be spent through Inventory -> Shop.

The current shop:

- rolls four offers
- draws from the 48-item authored catalog
- rerolls on entry to a new room rather than every menu open
- deducts gold on purchase
- applies purchased effects immediately

Item classes currently include weapons, armor, healing items, and stat/charm items.

### DND player progression

The original prototype initialized the character at 18 HP. Eighteen remains the starting value, but it is no longer the effective lifetime ceiling.

XP-driven level progression can increase:

- maximum HP
- STR
- DEX
- AC

Items can further modify those values. Death returns the player to room 1, halves carried gold, and restores HP to the player's current maximum.

## Persistence

The physical device supports three active BloomPetz pet slots. Each pet save stores identity, lifetime counters, food/daily state, and all 200 stat values through ESP32 Preferences-backed persistence.

Host storage may later archive unlimited `.bloompet` files.

DND persistence is still an evolving subsystem. Current development priority is keeping the gameplay/content loop stable before freezing a long-term DND save schema.

## Host companion architecture

The Raspberry Pi Mini is a mirror/controller, not a second game engine. The ESP32 remains authoritative for active BloomPetz and DND state.

The Pi Mini:

- mirrors `BP|SCREEN` rows
- uses a 21-column DND-aware layout
- hides BloomPetz chrome while DND is active
- provides clickable, keyboard, and tested 8BitDo controls
- sends host time through `SET HOSTTIME`
- opens serial without manually toggling DTR/RTS to avoid the proven second-boot failure mode

## Development rule

Prefer small modules and human-readable data over monolithic source files.

The repository baseline firmware can lag the known-good locally integrated OLED/touch build during bench development. Use targeted patch helpers under `tools/` rather than replacing the local working sketch wholesale.

Before modifying a live subsystem:

1. inspect the actual local code path being compiled
2. patch the smallest authoritative path
3. compile cleanly
4. upload only after compile success
5. physically test the resulting behavior

Arduino `.ino` auto-prototype behavior is a known hazard. Custom types used in function signatures must be visible before generated prototypes; use early declarations or headers rather than assuming ordinary C++ source ordering.

BloomCore rule: each subsystem should expose an independent diagnostic path and preserve known-good lower layers.
