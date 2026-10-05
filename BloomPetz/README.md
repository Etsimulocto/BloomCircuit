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

The tested external 8BitDo controller mapping is:

```text
D-pad LEFT/RIGHT = Linux joystick axis 6
D-pad UP/DOWN    = Linux joystick axis 7
A                = button 0
B                = button 1
```

The Pi Mini converts these to the same `KEY UP/DOWN/LEFT/RIGHT/A/B` serial commands used by the other controller paths.

## BLOOM SYSTEM launcher

Boot now enters a shared launcher instead of going directly into BloomPetz.

Current launcher entries:

```text
BLOOMPETZ
DND
```

The launcher also shows the host-supplied local clock/date. The Pi companion sends the current Unix time and UTC offset over the existing USB serial connection on connect and periodically afterward. No Wi-Fi credentials are required for time sync.

Firmware command format:

```text
SET HOSTTIME <unix_epoch_seconds> <utc_offset_minutes>
```

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

DND is now a real playable subsystem inside BLOOM SYSTEM rather than a placeholder.

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
- collision-triggered combat/interactions
- chest, trap, gold, potion, weapon, and door interactions
- d20-style event/roll feed
- rotating status HUD
- Character / Inventory / Symbols / System Menu entries
- return to BLOOM SYSTEM

### DND economy and inventory

Gold is now spendable instead of being only a score/counter.

The Inventory path includes a shop backed by a 48-item authored catalog. The shop presents four randomized offers at a time and rerolls when the player enters a new room, preventing repeated menu-open rerolls.

Current item categories include:

- weapons
- armor
- healing items
- stat/charm items

Purchases deduct gold and apply their gameplay effects immediately. Weapons replace the active weapon, armor increases AC, healing items restore HP, and charms can modify STR, DEX, and/or maximum HP. Purchased item names are retained in the compact inventory history.

### DND content depth

The current content target is 48 entries for the major reusable content pools:

```text
48 authored items
48 enemy species
48 symbol/entity reference entries
48 room themes
```

The 48 room themes sit on top of the eight proven geometry archetypes. Theme variety is intentionally separated from room-generation geometry so the map generator remains stable while content variety grows.

The 48 enemy species are a possible-species pool, not 48 simultaneous monsters. The active enemy array stays intentionally small because the physical display is only 128x64 and the current viewport is 14 x 4 map cells. Deeper rooms progressively unlock higher enemy tiers while some lower-tier creatures can continue appearing later.

The Symbols browser has been expanded from the original 15 entries to a 48-entry entity/reference catalog covering map objects, loot, hazards, enemies, and special entities.

### DND player progression

Player HP is no longer effectively capped at the original 18/18 starting value.

The player still begins at 18 HP, but XP-driven level progression can now increase maximum HP and gradually improve combat stats. Current progression affects:

- level
- maximum HP
- STR
- DEX
- AC

Death still returns the player to room 1 and halves carried gold, but HP restores to the player's current progressed maximum rather than forcing the character permanently back to an 18-HP ceiling.

The starter room uses a real 14 x 4 map viewport. DND gameplay and persistence are still evolving, but the hardware movement/combat/economy/content loop is now established.

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
- tested raw 8BitDo gamepad input via `/dev/input/js0`
- controller colors follow the app's two-color theme
- host clock is sent to firmware on connect and periodically while connected
- physical controls remain primary

Important display rule: the Pi companion mirrors the same logical 21 DND columns shown on the physical OLED. It should not expose a wider dungeon viewport than the hardware.

Important implementation rule: the live `_handle_line()` must actually use `MIRROR_COLS = 21` and call the DND detection / mode-switch path for incoming `BP|SCREEN` frames. Merely having `_looks_like_dnd()` and `_set_dnd_mode()` helper functions somewhere in the file is not enough.

## Pi serial-open rule: no second boot

The ESP32-S3 previously appeared to boot twice when the Pi Mini launched. Hardware testing showed the sequence was:

1. ESP32 boots once normally.
2. Mini opens the USB CDC serial device.
3. USB briefly disconnects/re-enumerates.
4. ESP32 boots again.

This was not two firmware images. The second boot was tied to serial attach/control-line behavior.

The current proven Pi-side open pattern follows the working HAPPY JARZ controller and avoids explicit DTR/RTS manipulation:

```python
serial.Serial(port, BAUD, timeout=0.25, write_timeout=0.25)
```

Do not reintroduce manual `dtr` / `rts` toggling unless retested on the real ESP32-S3. With the current pattern, hardware testing confirmed: Mini opens, gamepad works, and there is no second boot.

## Display ownership rule

Only the active app/mode should repaint the OLED.

This became important when the old BloomPetz side-art refresh service continued repainting shared `screenLines[]` while DND was using its own full-width renderer. The result was a visible DND/BLOOM SYSTEM strobe. The current architecture pauses that BloomPetz repaint path while DND owns the OLED.

DND's full-width renderer also updates the shared mirror lines so the Pi app receives current DND frames.

## Current Pi recovery / deployment rule

The October 2026 recovery exposed a mixed-generation Mini file: current V3 helpers existed while older methods remained active, and several class methods had been deleted by earlier patching.

Do not infer app generation from a few marker functions. Verify the active code path.

Known-good verification points:

```text
MIRROR_COLS = 21
_set_dnd_mode(...)
_looks_like_dnd(...)
_handle_line(...) uses 21 columns and invokes DND mode detection
raw 8BitDo reader is active
serial open does not manually toggle DTR/RTS
host-time path sends SET HOSTTIME
```

If the Mini becomes structurally damaged, prefer rebuilding from the consolidated current source/tool and then reapplying the proven no-reset/gamepad fixes rather than restoring missing methods one at a time.

Known authoritative Pi paths:

```text
~/BloomCircuit/BloomPetz/desktop/bloompetz_mini.py
~/BloomCircuit/BloomPetz/desktop/bloompetz_plug_watch.py
~/.config/autostart/bloompetz-plug-watch.desktop
```

The watcher launches the Mini from its own directory. An October 2026 audit confirmed one watcher process, one Mini process, and one Mini file under the user's home directory; the stale DND side-art issue was an active-method mismatch, not a hidden secondary copy.

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

The October 2026 expanded DND content build compiled at:

```text
Sketch uses 430874 bytes (32%) of program storage space.
Global variables use 30192 bytes (9%) of dynamic memory.
```

Before upload, stop BloomPetz Mini so it does not own the serial device:

```bash
pkill -f '[b]loompetz_mini.py' 2>/dev/null || true
pkill -f '[b]loompetz_plug_watch.py' 2>/dev/null || true
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

Important: compile and upload are separate operations. A successful compile alone does not change the firmware currently running on the ESP32. After firmware uploads, restart the Pi companion because flashing/resetting ends the previous serial session.

## Current bench acceptance test

After a Pi rebuild or firmware deployment, verify the whole stack together:

```text
1. ESP32 boots once.
2. Pi Mini opens automatically.
3. Opening Mini does not cause a second ESP32 boot.
4. Physical copper controls work.
5. Keyboard controls work.
6. 8BitDo D-pad and A/B work.
7. BLOOM SYSTEM / BloomPetz use normal Mini chrome.
8. DND uses the full 21-column mirror and hides side art/header.
9. Pi DND layout matches the physical OLED logical frame.
10. Host time/date appears and stays synchronized.
11. Inventory opens the DND shop.
12. Shop shows four offers and buying deducts gold.
13. Entering a new room rerolls shop stock.
14. Symbols browser reports 48 entries.
15. Deeper rooms can draw from progressively higher enemy tiers.
16. Player maximum HP can grow beyond the initial 18 through progression/items.
```
