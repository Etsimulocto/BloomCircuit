# BloomPetz

Persistent idle/clicker/fidget virtual pets plus shared BLOOM SYSTEM games for the HAPPY JARZ ESP32-S3 platform.

BloomPetz is running as a working hardware prototype on the ESP32-S3 SuperMini with the 128x64 OLED, six copper capacitive inputs, two APA106 LEDs, persistent saves, a Raspberry Pi mirror/controller, pet creation/editing, daily interactions, Simon-style action play, the full 200-stat developmental model, a shared BLOOM SYSTEM launcher, and a playable DND hardware slice.

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

- UP / DOWN = select / move
- LEFT / RIGHT = edit, change, page, or move
- A = enter / perform / action modifier
- B = back / menu

The same six logical inputs are exposed in the Pi Mini controller as:

```text
↑  ↓  ←  →  A  B
```

Keyboard control in the Pi Mini uses the arrow keys plus A and B.

## BLOOM SYSTEM launcher

Boot now enters a shared launcher instead of going directly into BloomPetz.

Current launcher entries:

```text
BLOOMPETZ
DND
```

The launcher also shows the host-supplied local clock/date. The Pi companion sends the current Unix time and UTC offset over the existing USB serial connection on connect and periodically afterward. No Wi-Fi credentials are required for time sync.

BloomPetz can return to BLOOM SYSTEM from its menu, and DND can return from its own menu.

## BloomPetz menu

Current BloomPetz menu:

```text
FEED
TREAT
STATS
SLOT
EDIT PET / CREATE PET
SYSTEM MENU
```

The menu uses a three-row scrolling window plus a footer.

## OLED home screen

The physical OLED is a 128x64 SSD1306 using a four-line text layout with decorative particle art in the side gutters while BloomPetz is active.

Current HOME behavior:

1. Pet art / symbol alternating with rotating pet sayings. Long sayings marquee.
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

The current on-device STATS browser exposes all 200 stats directly in one flat LEFT/RIGHT sequence. Values are shown as percentages with four decimal places.

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

## DND current hardware slice

DND is now playable from BLOOM SYSTEM.

Current physical layout uses the full 21-character OLED width:

```text
7-column HUD + 14-column map = 21 columns
4 rows total
```

DND bypasses BloomPetz side-art/gutters and owns the full OLED width.

Current playable behavior includes:

- `@` player
- D-pad movement
- tap A, then direction within about 700 ms for directional attack
- B opens DND menu
- Rat, Goblin, and Skeleton autonomous movement
- collision-triggered combat/interactions
- chest, trap, gold, potion, and door interactions
- d20-style event/roll feed
- rotating status HUD
- Character / Inventory / Symbols / System Menu entries
- return to BLOOM SYSTEM

The starter room currently uses a real 14 x 4 map viewport. DND gameplay and persistence are still early-stage; the current goal is to prove the hardware movement/combat loop before expanding systems.

## Raspberry Pi companion

`desktop/bloompetz_mini.py` is the current lightweight Pi mirror/controller.

Current known-good behavior:

- mirrors all four OLED text rows over USB
- supports full 21-column DND frames
- dynamically measures a monospaced DND font so all 21 columns fit the 192 px mirror without clipping
- BloomPetz/System retain their normal centered presentation
- DND hides BloomPetz side-art lanes and the pet-name header
- six clickable controller buttons: `↑ ↓ ← → A B`
- keyboard controls: arrow keys + A/B
- controller colors follow the app's two-color theme
- host clock is sent to firmware on connect and periodically while connected
- physical controls remain primary

Important display rule: the Pi companion mirrors the same logical 21 DND columns shown on the physical OLED. It should not expose a wider dungeon viewport than the hardware.

## Display ownership rule

Only the active app/mode should repaint the OLED.

This became important when the old BloomPetz side-art refresh service continued repainting shared `screenLines[]` while DND was using its own full-width renderer. The result was a visible DND/BLOOM SYSTEM strobe. The current architecture pauses that BloomPetz repaint path while DND owns the OLED.

DND's full-width renderer also updates the shared mirror lines so the Pi app receives current DND frames.

## Known-good flashing target

Current bench target:

```text
ESP32-S3 SuperMini
Arduino core: esp32 3.3.12
FQBN: esp32:esp32:esp32s3:CDCOnBoot=cdc
Upload speed: 115200
```

Typical compile:

```bash
cd ~/BloomCircuit/BloomPetz/firmware
arduino-cli compile \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc \
  bloompetz_v0_1
```

Before upload, stop BloomPetz Mini so it does not own the serial device:

```bash
pkill -f '[b]loompetz_mini.py' 2>/dev/null || true
```

There is one physical ESP32 USB device. Linux may re-enumerate that same board as `/dev/ttyACM0` or `/dev/ttyACM1` after a reset. Resolve the currently existing device node instead of assuming one fixed number:

```bash
PORT=$(ls /dev/ttyACM* 2>/dev/null | head -n1)

echo "Flashing: $PORT"

arduino-cli upload \
  -p "$PORT" \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc,UploadSpeed=115200 \
  bloompetz_v0_1
```

Important: compile and upload are separate operations. A successful compile alone does not change the firmware currently running on the ESP32. After firmware uploads, restart the Pi companion if needed because flashing/resetting ends the previous serial session.
