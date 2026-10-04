# BloomCircuit

**Current stable release:** v1.0.0

BloomCircuit is a browser-based physical wiring-map editor for maker projects. It is built around **physical wiring documentation**, a **2.54 mm snap grid**, and **laser-ready SVG export** rather than PCB routing or SPICE simulation.

The repository also contains the HAPPY JARZ controller/firmware work. On branch `happyjarz-controller-v0.1`, the active bench build is now the **HAPPY JARZ / CLUB BOX line-in EQ controller** described below.

## HAPPY JARZ / CLUB BOX — current active bench build

See [`happyjarz-controller/README.md`](happyjarz-controller/README.md) for the current controller/app workflow and [`happyjarz-controller/firmware/README.md`](happyjarz-controller/firmware/README.md) for the firmware/hardware layer.

Current proven bench hardware:

- ESP32-S3 SuperMini
- GPIO7 -> 220 ohm -> APA106 data
- current bench test uses one APA106 bulb
- future target: 16 APA106 bulbs in one daisy chain
- GPIO9 = mono AC-coupled line input
- GPIO10 = physical noise-floor / threshold potentiometer
- all grounds common
- current one-bulb bench test may run the bulb from 3.3V, but the finished 16-bulb array must use an adequate external LED supply with common ground

Current line-in wiring:

```text
TRS TIP ---- (-) 10uF (+) ----+---- GPIO9
                               |
                              10k
                               |
                              3.3V

GPIO9 -------------------------+
                               |
                              10k
                               |
                              GND

TRS SLEEVE -------------------- GND
TRS RING ---------------------- unused for current mono test
```

Physical threshold knob:

```text
outer leg -> GND
wiper     -> GPIO10
outer leg -> 3.3V
```

The physical knob is the **only threshold/noise-floor control**. The app does not expose a second threshold slider.

### Proven APA106 transport

The current bulbs use the custom ESP32-S3 RMT path and a proven physical **RGB** byte order.

Known-good timing:

- 10 MHz clock
- bit 0 ~= 4 ticks HIGH / 14 ticks LOW
- bit 1 ~= 14 ticks HIGH / 4 ticks LOW
- ~100 us LOW reset/latch

Do not casually replace this driver with a generic NeoPixel/FastLED path while tuning higher-level behavior.

### Audio / EQ behavior

The active firmware is:

```text
happyjarz-controller/firmware/happyjarz_sound_reactive_v0_1.ino
```

It uses an 8-band Goertzel analyzer at 8 kHz / 256 samples.

Default band edges:

```text
40, 90, 180, 350, 700, 1200, 2000, 3000, 3900 Hz
```

Default colors:

```text
1 Red
2 Orange
3 Amber
4 Lime
5 Green
6 Cyan
7 Blue
8 Violet
```

Modes:

- **Single bulb bench** — the dominant EQ band controls the current bulb
- **16 bulbs** — two bulbs per EQ band

The physical GPIO10 knob controls the live gate over its full useful range. Gain controls how strongly accepted audio drives light intensity; Max Brightness sets the output ceiling.

### Reset behavior

The app/firmware `RESET` command restores the original working defaults:

- Gain = 4.0
- Max Brightness = 255
- Single-bulb bench mode
- original 8 frequency ranges
- original 8 colors
- live physical-knob threshold state is reread
- stale app EQ/bulb display state is cleared and refreshed

### Current Raspberry Pi app

Current tuner:

```text
happyjarz-controller/tools/happyjarz_meter.py
```

It provides:

- live 8-band graphic EQ
- center / peak-to-peak / dominant band / energy telemetry
- physical knob raw value, percent and calculated gate
- gain and max-brightness controls
- editable band edges and colors
- single-bulb / 16-bulb mode selection
- 16-bulb live preview
- RGB, All 16 and Chase 16 tests
- Reset to known-good defaults
- CSV logging to `~/happyjarz_eq_log.csv`

### Plug-to-open behavior

The Pi auto-launch watcher is:

```text
happyjarz-controller/tools/happyjarz_autolaunch.py
```

Installer:

```text
happyjarz-controller/tools/install_happyjarz_autolaunch.sh
```

Expected behavior:

- plug the ESP32 in -> wait for a stable serial device -> app opens
- unplug the ESP32 -> app closes cleanly
- manually close the app while still plugged in -> it stays closed
- unplug/replug -> app may open again
- the watcher must not launch the app while `arduino-cli` or `esptool` is flashing

The watcher intentionally waits for the serial device to remain stable and checks for flashing tools before launching, preventing the controller app from stealing `/dev/ttyACM0` during upload.

### Current direct flash workflow

Device:

```text
/dev/ttyACM0
```

FQBN:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

Typical flash command:

```bash
cd ~/BloomCircuit && \
pkill -f happyjarz_meter.py 2>/dev/null || true; \
pkill -f happyjarz_autolaunch.py 2>/dev/null || true; \
git pull && \
cp happyjarz-controller/firmware/happyjarz_sound_reactive_v0_1.ino ~/hjflash/happyjarz_sound_reactive_v0_1/happyjarz_sound_reactive_v0_1.ino && \
arduino-cli compile --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc ~/hjflash/happyjarz_sound_reactive_v0_1 && \
arduino-cli upload -p /dev/ttyACM0 --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc ~/hjflash/happyjarz_sound_reactive_v0_1
```

If Git refuses a pull because only the auto-launch files have local edits and those local edits are not wanted, restore only those specific files before pulling:

```bash
git restore happyjarz-controller/tools/happyjarz_autolaunch.py happyjarz-controller/tools/install_happyjarz_autolaunch.sh
```

## Legacy / integrated HAPPY JARZ work

Older controller files in this repository document a different integrated Jar prototype with six capacitive-touch controls, OLED menus, Wi-Fi, battery telemetry, screensavers, sayings, and two APA106 lamps. Those files remain useful reference material, but they are **not the active CLUB BOX line-in wiring map on `happyjarz-controller-v0.1`**.

Do not mix the old integrated touch/OLED GPIO assignments with the current line-in controller without deliberately remapping the hardware.

## Raspberry Pi offline BloomCircuit app

BloomCircuit itself can run as a local desktop-style app on Raspberry Pi with no internet connection.

From the cloned repository:

```bash
cd ~/BloomCircuit
git pull
bash install_pi.sh
```

After install, BloomCircuit is available from the Raspberry Pi desktop/menu and through:

```bash
bloomcircuit
```

The launcher uses Python's built-in local HTTP server and Chromium app mode. HTML, CSS, JavaScript, component data, embedded component images, project saves, and SVG export stay local.

## Electrical boards

Board underlays are real electrical objects instead of passive background graphics.

- every visible board hole is a clickable connection node
- breadboard terminal groups model connected holes on each side of the center trench
- breadboard power rails are real connection groups
- stripboard rows are continuous copper groups
- perfboard holes remain isolated unless explicitly wired
- wires can run component -> board hole, board hole -> board hole, or board hole -> component
- project JSON preserves board-hole wire endpoints
- routing uses short escape segments and staggered lanes to reduce overlap

## Physical-layout workflow

BloomCircuit uses a common physical coordinate system:

- **10 px = 2.54 mm = one standard breadboard/perfboard hole pitch**
- built-in pin locations land on grid intersections
- DIP parts use 2.54 mm pin pitch with standard row spacing
- components and boards rotate in 90 degree steps
- exact numeric scaling is supported
- connected wires follow scaled and rotated pins

### Visual Component Maker

The custom component maker lets you:

1. Set a footprint size in X/Y grid holes.
2. Upload a real component image.
3. Overlay it on the 2.54 mm grid.
4. Click grid intersections to create pins.
5. Drag pins from hole to hole.
6. Enter exact Grid X / Grid Y positions.
7. Name pins and assign electrical roles.
8. Zoom the footprint editor or use Fit.
9. Save the image and pin layout into a reusable component definition.

Custom component images can travel with projects and exported component packs.

## Component library

Built-in categories include controllers, buses, connectors, passives, lights/displays, ICs, switches, motors/sound, power modules, and common I2C/SPI/UART modules.

The library includes parts such as:

- Raspberry Pi 40-pin
- ESP32 DevKit / WROOM-32
- Raspberry Pi Pico
- Arduino Nano
- APA106-F8 addressable LED
- generic I2C OLED
- SN74AHCT125N
- JST-PH connectors
- capacitive touch pads
- common power/charger modules

Some hobby boards have vendor-specific pinout variants. Verify the exact hardware before treating a template as electrical authority.

See [`COMPONENT_PACKS.md`](COMPONENT_PACKS.md) for the component-pack format.

## Core editor

- 2.54 mm shared snap grid
- drag components
- click pin -> click pin wiring
- wire types: 5V, 3V3, GND, DATA, OTHER
- simple power/GPIO warnings
- save/load project JSON
- etch mode
- SVG export with millimeter dimensions for xTool
- board underlays and real board-hole connectivity
- custom component maker
- HAPPY JARZ project documentation

## Run in a browser

No build step is required.

```bash
git clone https://github.com/Etsimulocto/BloomCircuit.git
cd BloomCircuit
python3 -m http.server 8080
```

Open:

```text
http://localhost:8080
```

If already cloned:

```bash
cd ~/BloomCircuit
git pull
python3 -m http.server 8080
```

## License

BloomCircuit is **free and open source** under the [MIT License](LICENSE).

You may use, copy, modify, fork, publish, and redistribute BloomCircuit, including in personal, educational, and commercial projects, as long as the MIT license notice is kept with the software.

There is no warranty; verify wiring and component pinouts against actual hardware and datasheets before powering a circuit.

## Scope

BloomCircuit is intentionally a wiring-map and fabrication-documentation tool. It does not replace KiCad, SPICE, PCB DRC, or a datasheet. The goal is to make a physical maker circuit easy to understand, reproduce, service, and engrave.