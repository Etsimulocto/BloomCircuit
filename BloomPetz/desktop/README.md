# BloomPetz Desktop / Raspberry Pi App

The Raspberry Pi companion is a working mirror/controller for the HAPPY JARZ BloomPetz / BLOOM SYSTEM firmware.

## Current mini app

`bloompetz_mini.py` currently provides:

- automatic serial connection to the BloomPetz ESP32-S3
- four-line OLED screen mirroring
- full 21-column DND mirror support
- DND-aware chrome: DND hides the BloomPetz pet-name header and side-art lanes
- BloomPetz/System restore the normal centered presentation and side art
- six clickable controls: `↑ ↓ ← → A B`
- keyboard arrow + A/B controls routed into the same firmware input path as the physical touch controls
- raw Linux joystick support for the proven 8BitDo controller mapping
- compact Pi desktop window with app-only color themes
- host time sync over USB serial
- disconnect handling suitable for plug/unplug use

`bloompetz_plug_watch.py` and `install_bloompetz_autostart.sh` provide the Raspberry Pi auto-launch path.

Physical copper controls remain primary; the desktop app is a mirror/controller, not a replacement for device-local play.

## Proven 8BitDo mapping

Current tested controller:

```text
8BitDo Ultimate wireless Controller for PC
USB ID: 2dc8:3106
/dev/input/js0
```

The D-pad is exposed by the Linux joystick API as:

```text
axis 6 = LEFT / RIGHT
axis 7 = UP / DOWN
button 0 = A
button 1 = B
```

The Mini reads the 8-byte Linux joystick event packets directly and converts those inputs to the same logical firmware commands used by keyboard and touch:

```text
KEY LEFT
KEY RIGHT
KEY UP
KEY DOWN
KEY A
KEY B
```

Do not remap this controller to analog stick axes 0/1 unless hardware testing proves the controller mode changed.

## Current USB behavior

The firmware emits `BP|SCREEN|...` records whenever the four-line display changes. The Mini mirrors those records rather than maintaining a second copy of game UI state.

For DND, the Mini uses the full 21 logical columns sent by firmware. The physical OLED remains authoritative for layout; the Pi must not invent a wider dungeon viewport than the hardware.

Keyboard, clickable controls, and gamepad input are sent back as logical UP / DOWN / LEFT / RIGHT / A / B events and handled by the same firmware input path used by the hardware controls.

## Serial open / no-double-boot rule

A major Raspberry Pi integration bug appeared as an apparent double boot:

1. ESP32 booted normally.
2. The Pi Mini opened the USB CDC port.
3. The OLED briefly went black.
4. The same firmware booted again after USB re-enumeration.

The important discovery was that the second boot happened when the Mini opened serial; it was not an old firmware image loading first.

The proven fix is to use the simple Happy Jarz serial-open pattern and **not manually toggle DTR/RTS around the open**:

```python
serial.Serial(port, BAUD, timeout=0.25, write_timeout=0.25)
```

Do not reintroduce code that explicitly drives `dtr` / `rts` before or after `open()` unless the exact ESP32-S3 CDC behavior has been retested on hardware.

There is one physical ESP32. Linux may re-enumerate it as `/dev/ttyACM0` or `/dev/ttyACM1`; that does not mean two boards are present.

## Host time sync

The Pi supplies local time to firmware over the existing USB serial connection. The firmware command format is:

```text
SET HOSTTIME <unix_epoch_seconds> <utc_offset_minutes>
```

The intended Mini behavior is to send host time after connection and periodically while connected. No Wi-Fi credentials are required for the device clock/date display.

## DND mirror ownership

DND has a different display contract from BloomPetz:

- `MIRROR_COLS = 21`
- DND owns the full logical display width
- DND hides pet-name chrome
- DND hides BloomPetz side-art lanes
- returning to BLOOM SYSTEM / BloomPetz restores normal chrome

A critical failure mode occurred when V3 helper functions existed in the file, but `_handle_line()` was still an older 16-column implementation. Symptoms were:

- physical OLED DND looked correct
- Pi Mini still showed side art
- Mini truncated incoming rows to 16 characters
- `_looks_like_dnd()` and `_set_dnd_mode()` existed but were never called

The correct screen path must build 21-column rows and call DND detection for each incoming `BP|SCREEN` frame before repainting the labels.

A file containing V3 helper functions is **not enough** to prove the live handler is V3.

## Authoritative Pi paths

Known working local layout:

```text
~/BloomCircuit/BloomPetz/desktop/bloompetz_mini.py
~/BloomCircuit/BloomPetz/desktop/bloompetz_plug_watch.py
~/.config/autostart/bloompetz-plug-watch.desktop
```

The watcher intentionally launches the Mini from its own directory:

```python
HERE = Path(__file__).resolve().parent
APP = HERE / "bloompetz_mini.py"
```

An audit during the October 2026 recovery confirmed one watcher, one Mini process, and one copy under the user's home directory. If runtime UI still looks old, inspect the live file's active methods before assuming a second copy exists.

Useful audit:

```bash
pgrep -af 'bloompetz|BloomPetz'
find ~ -type f \( -name 'bloompetz_mini.py' -o -name 'bloompetz_plug_watch.py' \) 2>/dev/null
```

## Current rebuild / recovery rule

Do not repair a damaged Mini by restoring one missing method at a time unless there is no alternative. During the October 2026 recovery, an earlier patch left a mixed-generation file where `_serial_worker`, `_gamepad_worker`, `_drain_rx`, `send`, `_fields`, and the current DND screen handler were missing or stale in sequence.

Preferred recovery:

1. Stop Mini and watcher.
2. Rebuild the Pi Mini from the consolidated current source/tool.
3. Reapply only proven hardware-specific fixes such as no-reset serial open and raw 8BitDo input.
4. Run `python3 -m py_compile`.
5. Launch Mini directly once and watch terminal output.
6. Restart the watcher only after direct launch is clean.
7. Verify on hardware: one boot, Mini opens, gamepad works, DND has no side art, 21-column mirror matches OLED, host time appears.

A Python syntax check only proves syntax. It does not prove the active runtime path is current.

## Planned expansion

The larger desktop layer can grow into:

- full 200-stat/history views and graphs
- archive of unlimited `.bloompet` files
- restore archived pets to one of three device slots
- automatic backup on USB connection
- pet library and metadata editing
- firmware/content installation
- diagnostics/service tools
- richer pet and screensaver management

Keep desktop backup/library behavior separate from ESP32 pet simulation logic. The ESP32 remains authoritative for active pet state and the core interaction loop.
