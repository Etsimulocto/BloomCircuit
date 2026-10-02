# HAPPY JARZ Controller

**Status:** bench-proven controller + field-service layer, current firmware staging path v0.5, desktop controller v0.3.3

This subsystem is the PC/Raspberry Pi side of the HAPPY JARZ powered stand. It sits above the known-good ESP32-S3 light/touch/OLED layer and is intentionally designed so desktop-side changes do not rewrite the proven APA106 timing.

## Current proven behavior

- identify a Jar over USB serial
- reconnect after unplug/replug
- independently control LED 1 and LED 2 colors
- enforce the current **50% maximum brightness** used by the bench-proven build
- expose the expanded sensory/holiday/color pattern library
- watch six capacitive-touch inputs live
- run RGB / touch / input diagnostics
- configure Wi-Fi and scan networks visible to the ESP32-S3
- set/sync the clock over Wi-Fi or directly from the host computer over USB
- save persistent Jar settings
- keep session/service logs
- launch `happyjarz_controller_v0_3_3.py` automatically when a Jar is plugged in
- show Fuel Gauge / `GET POWER` telemetry in the desktop SERVICE tab
- check the tracked GitHub branch on startup and every 6 hours
- apply only safe fast-forward updates; never overwrite local edits
- restart the watcher after a safe update when the controller is not open

## Bench-proven hardware map

Controller: **ESP32-S3 SuperMini**

### APA106 lighting

- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- APA106 VCC -> **5V**
- common GND with ESP32

The tested lamps accept the ESP32-S3's 3.3V GPIO data while powered from 5V, so the current prototype does not require a separate logic-level-shifter IC. Do not route 5V into an ESP32 GPIO.

The working data order is **RGB**, not GRB.

### Capacitive touch

Physical map:

- GPIO4 = UP
- GPIO5 = DOWN
- GPIO9 = LEFT
- GPIO10 = RIGHT
- GPIO1 = A
- GPIO2 = B

Current HOME behavior:

- A = next Light 1 palette color
- B = next Light 2 palette color
- UP = next pattern
- DOWN = previous pattern
- RIGHT = enter OLED menu
- LEFT = no HOME action

Inside OLED menus, navigation owns the controls so HOME light actions do not fall through.

The touch layer uses the original proven direct `touchRead()` behavior with the roughly +20% threshold and ~60 ms qualification. Do not reintroduce the abandoned hysteresis/cooldown/release state machine that caused same-button repeat failures.

### OLED

Current 4-wire I2C OLED:

- VCC -> 3.3V
- GND -> GND
- SDA -> GPIO8
- SCL -> GPIO6
- I2C address `0x3C`
- U8g2 renderer
- 128x64 layout

The UI uses centered text and HOME/menu/detail/status pages.

### Battery / power telemetry

The current prototype uses GPIO3 as the onboard battery/supply ADC sense path.

Bench calibration on October 2, 2026 established a provisional `BATTERY_CAL_FACTOR` of **1.370** for this board. With the charged battery powering the Jar by itself, the OLED reported approximately:

```text
V 4.16
BAT 98%
PWR BAT
```

That is the current bench-proven prototype calibration. Battery percentage is still a voltage-derived LiPo estimate, not a coulomb counter, so future board revisions should be calibrated independently.

The HOME footer keeps `A MENU` visible and cycles standalone power information about every 2.5 seconds. Battery-only operation cycles battery %, voltage, and `PWR BAT`. With USB present it reports `PWR USB`; charging state remains `CHG ?` because the charger IC's CHARGING/FULL signal is not currently wired to an ESP32 GPIO.

Do not infer `CHARGING` or `FULL` from USB CDC presence. A wall charger may provide power without a PC/data link.

## Lighting + pattern library

Current maximum LED brightness is **50%**. This is an intentional bench decision: higher abrupt white loads could drive the lamps blue, while 50% is already bright enough for the sensory/fidget use case.

Current pattern names:

`SOLID`, `FADE`, `PULSE`, `RAINBOW`, `RANDOM`, `HUE_FADE`, `DUAL_HUE`, `BREATH`, `DRIFT`, `AURORA`, `OCEAN`, `LAVENDER`, `SUNSET`, `CHRISTMAS`, `HALLOWEEN`, `VALENTINE`, `EASTER`, `FOURTH`, `THANKSGIVING`, `CANDY`, `GALAXY`, `FIRE`, `ICE`, `FOREST`, `NEON`, `TWINKLE`, `SPARKLE`, `COLOR_SWAP`, `COMET`, `FIREFLY`, `BUBBLEGUM`, `OFF`.

Many modes calculate continuous RGB values instead of stepping only through the small physical-button palette.

## OLED screensavers

The current firmware automatically enters screensaver mode after **30 seconds of inactivity**. The original 10-second bench value was increased because it interrupted normal menu/status reading.

Modes:

- **SAYINGS** — horizontally scrolling marquee with a large built-in positive/funny/maker/glitter saying bank
- **SPIRAL** — procedural spiral generator
- **TRIPPY** — procedural waves, rings, graphic-EQ bars, point fields, line lattices, dots and related geometry
- **PARTICLES** — procedural particle-universe saver

Physical controls while a saver is active:

- LEFT / RIGHT = previous / next saver
- B = exit saver
- SPIRAL/TRIPPY/PARTICLES: UP = faster
- SPIRAL/TRIPPY/PARTICLES: DOWN = slower
- SPIRAL/TRIPPY/PARTICLES: A = reseed / generate a new universe

The art modes do not randomize every frame. A seed creates a coherent recipe; that recipe animates smoothly until it is reseeded.

Procedural entropy currently mixes live board state including uptime, microsecond timing jitter, ESP32 temperature, Wi-Fi RSSI when available, all six touch readings, brightness, current LED RGB state and PRNG state.

## Custom/business marquee sayings

The controller includes an editable marquee panel intended for banks, clinics, shops, offices, events, gifts and other installations.

- 8 persistent custom message slots
- up to 96 characters per slot
- saved in ESP32 Preferences
- survives unplug/restart
- `BUILTIN`, `CUSTOM`, or `MIXED` saying source
- custom messages use the same scrolling marquee display

The desktop UI can load the current messages from the Jar, edit them, send/save them, clear them, and switch the saying source.

## Current desktop controller

`happyjarz_controller_v0_3_3.py` is the current launcher target used by `happyjarz_plug_watch.py`.

The OLED/Screensaver panel reflects the current firmware and includes saver mode selection, reseed/new-universe controls, speed controls, exit, live saver status, the 30-second idle behavior and the custom marquee editor.

The SERVICE tab adds the current Fuel Gauge card:

- Battery %
- Voltage
- USB DATA IN/OUT
- Charge status
- Raw ADC mV
- Refresh Power
- automatic `GET POWER` polling

The firmware deliberately reports charger state as hardware-only/unknown until a real charger-status signal is available.

## BloomSaver desktop integration target

The standalone `BloomSaver/` app on `main` is now a **Glitter-first** visual engine intended to be patched into the HAPPY JARZ desktop controller after tuning.

Current BloomSaver behavior includes:

- continuously generated Glitter instead of a timed background-mode playlist
- moving emitters, attractors and repulsors
- bursts, drift, swirl, field noise, trails, glow and twinkle
- particle sizes up to **24**
- a large ASCII/symbol glyph pool mixed with geometric glitter shapes
- simple randomized dark background fades
- saved user Glitter presets that do not auto-cycle

### Match Jar Colors on Start

BloomSaver now exposes a persistent **MATCH JAR COLORS ON START** toggle.

The intended integration rule is:

```text
active Jar light pattern
        ↓
controller resolves a representative palette
        ↓
BloomSaver receives that palette once at startup
        ↓
Glitter + initial background match the physical Jar
        ↓
user may freely change BloomSaver controls afterward
```

This must remain a **startup handoff**, not a continuous override. The user should always be able to move the Glitter hue, spread, background and other sliders after launch without the controller fighting those edits.

The browser-side bridge accepts a direct call such as:

```javascript
window.BloomSaver.setJarPalette({
  name: "OCEAN",
  colors: ["#0066ff", "#00d8ff", "#6f4cff"]
});
```

It can also consume compatible RGB/HSL/hue objects, `primary` / `secondary` / `accent` fields, palette `postMessage` events, supported globals, localStorage palette entries and startup URL color parameters.

Controller integration should therefore expose or derive a small representative palette for each active lighting pattern rather than trying to mirror the LED animation frame-for-frame. The physical light animation and desktop Glitter physics stay independent while sharing the same visual color family.

## Known-good APA106 timing

Do not replace this casually. The integrated firmware uses the Arduino ESP32 HAL RMT driver:

- 10 MHz RMT clock
- bit 0 ~= 4 ticks high / 14 ticks low
- bit 1 ~= 14 ticks high / 4 ticks low
- ~100 us reset/latch
- RGB byte order

Generic NeoPixel/FastLED attempts were not the proven path for this hardware.

## Current Pi flash workflow

Use the standard helper instead of manually rebuilding the staged sketch:

```bash
cd ~/BloomCircuit
git pull --ff-only
bash happyjarz-controller/tools/flash_happyjarz_v0_5.sh
```

The helper:

1. stops the controller and plug watcher so the serial port is free
2. stages `firmware/happyjarz_integrated_v0_5.ino`
3. applies the current compatibility, touch, OLED/menu, sensory-pattern, screensaver, expanded-sayings, custom-sayings, procedural-art, saver-protocol, Fuel Gauge and HOME power-cycle patches
4. compiles with Arduino CLI
5. uploads to the detected `/dev/ttyACM*` or `/dev/ttyUSB*` port
6. restarts the plug watcher

Current Arduino CLI FQBN:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

## Desktop requirements

### Raspberry Pi / Debian

Install once:

```bash
cd ~/BloomCircuit/happyjarz-controller
bash install_pi_autostart.sh
```

The installer uses Debian packages (`python3`, `python3-tk`, `python3-serial`) so it does not fight Bookworm's PEP 668 protected Python environment.

The autostart entry runs `happyjarz_plug_watch.py`, not the full GUI. The watcher stays quiet until a HAPPY JARZ is detected, then opens the current v0.3.3 controller.

Manual watcher test:

```bash
python3 ~/BloomCircuit/happyjarz-controller/happyjarz_plug_watch.py
```

### Windows

From PowerShell in this directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows_autostart.ps1
```

Windows does not allow arbitrary old-style USB autorun, so the installer places the lightweight watcher in the user's Startup flow. After that, plugging in a HAPPY JARZ opens the controller automatically.

## Auto-update behavior

The watcher also acts as the field updater.

- checks the configured upstream branch when it starts
- checks again every 6 hours
- uses fast-forward-only Git updates
- skips update if local edits would be overwritten
- keeps running if the internet is unavailable
- logs update decisions
- restarts itself after its own code changes when safe

## Logs

Service logs are stored under:

```text
~/.happyjarz/plug_watch.log
~/.happyjarz/controller_launch.log
~/.happyjarz/controller.log
```

These are the first files to request when diagnosing a remote unit.

## Protocol + firmware

See [`PROTOCOL.md`](PROTOCOL.md), [`APP_PROTOCOL_V0_3.md`](APP_PROTOCOL_V0_3.md), and [`firmware/README.md`](firmware/README.md).

## BloomCore failure boundary

Preserve known-good layers.

If the desktop UI is wrong but the ESP32's local LED/touch/display behavior still passes, troubleshoot the watcher/controller/protocol layer first.

If the ESP32's local behavior fails, troubleshoot the firmware/hardware layer before changing the desktop app.

**Every feature should carry its own diagnostic path.**