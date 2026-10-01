# BloomCircuit

**Current stable release:** v1.0.0

BloomCircuit is a browser-based physical wiring-map editor for maker projects. It is built around **physical wiring documentation**, a **2.54 mm snap grid**, and **laser-ready SVG export** rather than PCB routing or SPICE simulation.

The repository also contains the current **HAPPY JARZ controller/firmware stack**, built around an ESP32-S3 SuperMini, six capacitive-touch controls, two APA106 lamps, a 128x64 I2C OLED, USB control, a desktop controller, plug-to-launch service tooling, logs, and safe GitHub fast-forward updates.

## HAPPY JARZ current prototype

See [`happyjarz-controller/README.md`](happyjarz-controller/README.md) for the controller/service workflow and [`happyjarz-controller/firmware/README.md`](happyjarz-controller/firmware/README.md) for the ESP32 firmware layer.

Current proven hardware:

- ESP32-S3 SuperMini
- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- APA106 VCC -> **5V**
- common GND
- GPIO4 = UP touch
- GPIO5 = DOWN touch
- GPIO9 = LEFT touch
- GPIO10 = RIGHT touch
- GPIO1 = A touch
- GPIO2 = B touch
- OLED SDA -> GPIO8
- OLED SCL -> GPIO6
- OLED VCC -> 3.3V
- OLED address `0x3C`

The tested APA106 lamps accept the ESP32-S3's 3.3V data signal while powered from 5V, so the current working prototype does **not** require the earlier planned SN74AHCT125 level-shifter stage. The proven custom RMT timing and RGB byte order should be treated as a known-good hardware layer.

Current HAPPY JARZ firmware is staged from `happyjarz_integrated_v0_5.ino` and patched by the normal Pi flasher. Current behavior includes:

- independent Light 1 / Light 2 color control
- a **50% hard brightness ceiling** based on bench testing
- expanded sensory/holiday/color pattern library
- HOME controls: A/B colors, UP/DOWN patterns, RIGHT menu
- OLED HOME/menu/status pages
- 10-second idle screensaver entry
- SAYINGS marquee screensaver with a large built-in positive/funny saying bank
- persistent editable business/custom sayings with BUILTIN / CUSTOM / MIXED modes
- procedural SPIRAL and TRIPPY art screensavers
- LEFT/RIGHT saver switching, B exit, UP/DOWN art speed, A reseed / "new universe"
- procedural seeds mixed from live board state such as uptime, timing jitter, temperature, Wi-Fi RSSI, touch readings, brightness and RGB state
- USB control/status for saver preview, reseed, speed and live saver status

The pattern library currently includes:

`SOLID`, `FADE`, `PULSE`, `RAINBOW`, `RANDOM`, `HUE_FADE`, `DUAL_HUE`, `BREATH`, `DRIFT`, `AURORA`, `OCEAN`, `LAVENDER`, `SUNSET`, `CHRISTMAS`, `HALLOWEEN`, `VALENTINE`, `EASTER`, `FOURTH`, `THANKSGIVING`, `CANDY`, `GALAXY`, `FIRE`, `ICE`, `FOREST`, `NEON`, `TWINKLE`, `SPARKLE`, `COLOR_SWAP`, `COMET`, `FIREFLY`, `BUBBLEGUM`, `OFF`.

The desktop controller is currently layered through `happyjarz_controller_v0_3_2.py`. It provides:

- light color/brightness/pattern control
- Wi-Fi scan/setup and status
- USB host-time sync
- touch/input diagnostics
- current OLED/screensaver controls
- SAYINGS / SPIRAL / TRIPPY preview controls
- live saver status
- persistent 8-slot custom marquee editor for banks, clinics, shops, offices, events, gifts, and similar installations

The PC/Pi service layer can:

- detect a HAPPY JARZ over USB
- open the current controller app when a Jar is plugged in
- reconnect after unplug/replug
- keep diagnostic logs
- auto-check the tracked GitHub branch on startup and every 6 hours
- fast-forward only when safe, without overwriting local edits
- support remote compatibility/content/controller patches for deployed units

### Current Pi flash/update workflow

```bash
cd ~/BloomCircuit
git pull --ff-only
bash happyjarz-controller/tools/flash_happyjarz_v0_5.sh
```

The flasher stops the controller/watcher, stages the integrated v0.5 firmware, applies the current touch/OLED/menu/pattern/screensaver/custom-sayings/procedural-art patches, compiles with Arduino CLI, uploads, and restarts the watcher.

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

## HAPPY JARZ Pi service install

From the controller folder:

```bash
cd ~/BloomCircuit/happyjarz-controller
bash install_pi_autostart.sh
```

This installs the lightweight USB watcher. The full controller GUI remains closed until a HAPPY JARZ is detected.

Service logs:

```text
~/.happyjarz/plug_watch.log
~/.happyjarz/controller_launch.log
```

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