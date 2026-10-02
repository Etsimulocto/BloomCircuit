# HAPPY JARZ Controller

**Current release pair:** desktop app **v1.1.0** + firmware **v0.6.0**

This subsystem is the PC/Raspberry Pi field-service and control layer for the HAPPY JARZ powered stand. It sits above the known-good ESP32-S3 light/touch/OLED hardware layer and is designed so desktop-side changes do not casually rewrite the proven APA106 timing.

## Release/version discipline

Version numbers are now mandatory release data, not decorative strings.

Authoritative files:

```text
happyjarz-controller/VERSION          # desktop app version
happyjarz-controller/firmware/VERSION # firmware version
```

Current values:

```text
App      1.1.0
Firmware 0.6.0
```

See [`VERSIONING.md`](VERSIONING.md) for the required bump rules. Any runtime or behavior-changing app/firmware change must bump the relevant version before merge. If a change affects both sides, bump both.

Legacy filenames such as `happyjarz_controller_v0_3_3.py`, `happyjarz_integrated_v0_5.ino`, and `flash_happyjarz_v0_5.sh` are retained for compatibility only. **They are not release-version sources.**

The desktop launcher reads the app release from `VERSION`. The flasher reads `firmware/VERSION`, injects it into `HJ_FW_VERSION`, and the staged verifier refuses to upload a binary whose embedded version does not match.

## Current proven behavior

- identify a Jar over USB serial
- reconnect after unplug/replug
- independently control Light 1 and Light 2 colors
- enforce the current **50% maximum brightness**
- expose the expanded sensory/holiday/color pattern library
- watch six capacitive-touch inputs live
- run RGB / touch / input diagnostics
- configure Wi-Fi and scan networks visible to the ESP32-S3
- set/sync the clock over Wi-Fi or directly from the host computer over USB
- save persistent Jar settings
- keep service logs
- show Fuel Gauge / `GET POWER` telemetry
- run OLED menus and procedural screensavers
- store custom marquee sayings
- use a lightweight USB watcher to open the desktop controller when a Jar is detected

## Bench-proven hardware map

Controller: **ESP32-S3 SuperMini**

### APA106 lighting

- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- APA106 VCC -> **5V**
- common GND with ESP32
- proven byte order: **RGB**

The tested lamps accept ESP32-S3 3.3V GPIO data while powered from 5V. Do not route 5V into an ESP32 GPIO.

Known-good RMT timing:

- 10 MHz clock
- bit 0 ~= 4 ticks high / 14 low
- bit 1 ~= 14 high / 4 low
- ~100 us reset/latch

Generic NeoPixel/FastLED attempts were not the proven path for this hardware.

### Capacitive touch

Physical map:

- GPIO4 = UP
- GPIO5 = DOWN
- GPIO9 = LEFT
- GPIO10 = RIGHT
- GPIO1 = A
- GPIO2 = B

HOME behavior:

- A = next Light 1 palette color
- B = next Light 2 palette color
- UP = next pattern
- DOWN = previous pattern
- RIGHT = enter OLED menu
- LEFT = no HOME action

The proven touch layer uses direct `touchRead()`, roughly +20% thresholding, ~60 ms qualification, slow baseline drift and one action per touch/release cycle. Do not reintroduce the abandoned hysteresis/cooldown/release experiment that caused same-button repeat failures.

### OLED

Current 4-wire I2C OLED:

- VCC -> 3.3V
- GND -> GND
- SDA -> GPIO8
- SCL -> GPIO6
- address `0x3C`
- U8g2 renderer
- 128x64 layout

The HOME footer keeps `A MENU` visible and cycles power information instead of the old early-build `ALARM OFF` footer.

## Battery / power telemetry

Current prototype sensing path:

- GPIO3 ADC
- divider ratio `2.0`
- provisional `BATTERY_CAL_FACTOR = 1.370`
- battery percentage is voltage-estimated, not coulomb counted

October 2, 2026 bench reference with charged battery-only operation:

```text
V 4.16
BAT 98%
PWR BAT
```

HOME cycles about every 2.5 seconds.

Battery-only:

```text
BAT xx%
V x.xx
PWR BAT
```

USB present:

```text
BAT --%
PWR USB
CHG ?
```

`CHG ?` is intentional. The charger IC charging/full signal is not wired to an ESP32 GPIO, so firmware must not invent a charger state from USB CDC presence.

## Lighting + pattern library

Current maximum LED brightness is **50%**.

Current patterns:

`SOLID`, `FADE`, `PULSE`, `RAINBOW`, `RANDOM`, `HUE_FADE`, `DUAL_HUE`, `BREATH`, `DRIFT`, `AURORA`, `OCEAN`, `LAVENDER`, `SUNSET`, `CHRISTMAS`, `HALLOWEEN`, `VALENTINE`, `EASTER`, `FOURTH`, `THANKSGIVING`, `CANDY`, `GALAXY`, `FIRE`, `ICE`, `FOREST`, `NEON`, `TWINKLE`, `SPARKLE`, `COLOR_SWAP`, `COMET`, `FIREFLY`, `BUBBLEGUM`, `OFF`.

Many modes calculate continuous RGB values rather than stepping only through the small physical-button palette.

## OLED screensavers

The firmware enters screensaver mode after **30 seconds of inactivity**.

Modes:

- **SAYINGS** — scrolling built-in/custom marquee
- **SPIRAL** — procedural spiral generator
- **TRIPPY** — procedural waves/rings/bars/fields/lattices
- **PARTICLES** — procedural particle-universe saver

Saver controls:

- LEFT / RIGHT = previous / next saver
- B = exit
- SPIRAL/TRIPPY/PARTICLES: UP/DOWN = speed
- SPIRAL/TRIPPY/PARTICLES: A = reseed / new universe

Custom sayings:

- 8 persistent slots
- up to 96 characters each
- `BUILTIN`, `CUSTOM`, or `MIXED`
- stored in ESP32 Preferences

## Current desktop controller

The compatibility launcher target remains:

```text
happyjarz_controller_v0_3_3.py
```

but the actual displayed/reported app release is read from:

```text
happyjarz-controller/VERSION
```

Current app release: **v1.1.0**.

The SERVICE tab includes:

- Battery %
- Voltage
- USB DATA IN/OUT
- Charge status
- Raw ADC mV
- Refresh Power
- automatic `GET POWER` polling

## Raspberry Pi split-app layout

The normal Pi layout is:

```text
~/BloomCircuit          # main Git checkout / wiring editor
~/HappyJarzController   # current controller snapshot
~/BloomTunes            # audio/meditation snapshot
~/BloomSaver            # generative Glitter snapshot
```

Refresh all snapshots from the current repository branches with:

```bash
cd ~/BloomCircuit
git checkout main
git pull
bash ./tools/split_pi_apps.sh
```

Using `bash` explicitly is safe even if a local checkout has temporarily lost the executable bit.

The split script refreshes `~/HappyJarzController`, rewrites the Pi login autostart entry to use that stable path, and restarts the watcher.

Manual app launch:

```bash
cd ~/HappyJarzController
python3 happyjarz_controller_v0_3_3.py
```

Expected title:

```text
HAPPY JARZ Controller v1.1.0
```

### Desktop icon

The Pi desktop launcher must point at the current split controller copy, not the retired `happyjarz_os.py` path.

Expected launcher command:

```text
Exec=/usr/bin/python3 /home/quarterbitgames/HappyJarzController/happyjarz_controller_v0_3_3.py
Path=/home/quarterbitgames/HappyJarzController
```

## Current Pi flash workflow

Refresh the controller snapshot first, then flash from that same copy:

```bash
cd ~/BloomCircuit
git checkout main
git pull
bash ./tools/split_pi_apps.sh
bash ~/HappyJarzController/tools/flash_happyjarz_v0_5.sh
```

The helper now:

1. reads the authoritative firmware release from `firmware/VERSION`
2. stops the controller/watcher so the serial port is free
3. stages the known-good integrated base sketch
4. applies compatibility, touch, OLED/menu, pattern, screensaver, sayings, particle, Fuel Gauge and HOME power-cycle layers
5. injects the release firmware version into `HJ_FW_VERSION`
6. verifies the **final staged sketch before compile/upload**
7. refuses to flash if required features or the expected version are missing
8. compiles and uploads only after verification passes
9. restarts the plug watcher

Current firmware release: **v0.6.0**.

Expected verification output includes:

```text
HAPPY JARZ staged firmware verification: PASS
  firmware version 0.6.0
```

Do not flash if the PASS line is absent.

Current Arduino CLI FQBN:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

## BloomSaver integration target

`BloomSaver/` on `main` is the Glitter-first visual engine intended to integrate with the controller.

The controller should hand BloomSaver a small representative Jar palette at startup. BloomSaver's `MATCH JAR COLORS ON START` behavior is a startup handoff only; user Glitter controls remain free afterward.

Example browser bridge:

```javascript
window.BloomSaver.setJarPalette({
  name: "OCEAN",
  colors: ["#0066ff", "#00d8ff", "#6f4cff"]
});
```

## Logs

Pi service logs:

```text
~/.happyjarz/plug_watch.log
~/.happyjarz/plug_watch_manual_start.log
~/.happyjarz/controller_launch.log
~/.happyjarz/controller.log
```

These are the first files to inspect when a remote unit will not auto-open or connect.

## Protocol + firmware

See [`PROTOCOL.md`](PROTOCOL.md), [`APP_PROTOCOL_V0_3.md`](APP_PROTOCOL_V0_3.md), [`firmware/README.md`](firmware/README.md), and [`VERSIONING.md`](VERSIONING.md).

## Failure boundary

Preserve known-good layers.

If local LED/touch/OLED behavior works but the desktop UI does not, debug watcher/controller/protocol deployment first.

If local LED/touch/OLED behavior fails, debug firmware/hardware before changing the desktop app.

**Every feature should carry its own diagnostic path.**