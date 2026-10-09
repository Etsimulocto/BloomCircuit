# BloomCircuit

**Current stable release:** v1.0.0

BloomCircuit is a browser-based physical wiring-map editor for maker projects. It is built around **physical wiring documentation**, a **2.54 mm snap grid**, and **laser-ready SVG export** rather than PCB routing or SPICE simulation.

The repository also contains the current **HAPPY JARZ controller/firmware stack**, built around an ESP32-S3 SuperMini, six capacitive-touch controls, four APA106 lamps, a 128x64 I2C OLED, USB control, a desktop controller, plug-to-launch service tooling, logs, and safe GitHub fast-forward updates.

## HAPPY JARZ current prototype

See [`happyjarz-controller/README.md`](happyjarz-controller/README.md) for the controller/service workflow and [`happyjarz-controller/firmware/README.md`](happyjarz-controller/firmware/README.md) for the ESP32 firmware layer.

Current integrated hardware-development firmware on `feature/happyjarz-catch-the-glitter`: **v0.11.0**. The newer platform branch `feature/happyjarz-platform` carries the synchronized HAPPY JARZ stack at **app v1.8.4 + firmware v0.17.13**.

Current proven hardware:

- ESP32-S3 SuperMini
- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- APA106 #2 DOUT -> APA106 #3 DIN
- APA106 #3 DOUT -> APA106 #4 DIN
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

The tested APA106 lamps accept the ESP32-S3's 3.3V data signal. The original two-lamp electrical baseline was bench-tested through the full **0-100% firmware brightness range** with lamp VCC at both **3.3V and 5V**, with no blue-collapse observed in the latest test. Never route 5V into an ESP32 GPIO.

Practical brightness result:

- **24% at 3.3V** is already plenty for normal HAPPY JARZ sensory use
- **5V at 100% is extremely bright** and can create a strong wall/ceiling glow
- the previous 50% hard brightness ceiling has been removed
- full 0-100% remains available for tuning and intentional high-output use

Current HOME controls:

- UP = next pattern
- DOWN = previous pattern
- LEFT = next Light 1 color
- RIGHT = next Light 2 color
- A = open menu
- B = no HOME action

Current on-device UI includes:

- CLOCK with standalone date/time setting
- LIGHTS with live SOLID brightness editing from 0-100%
- GAMES with seven native OLED mini-games
- SETTINGS with ALARM and TIMER
- SYSTEM status
- 30-second SAYINGS / SPIRAL / TRIPPY / PARTICLES / BLOOM / BREATHE / GLITTER screensavers

The pattern library currently includes:

`SOLID`, `FADE`, `PULSE`, `RAINBOW`, `RANDOM`, `HUE_FADE`, `DUAL_HUE`, `BREATH`, `DRIFT`, `AURORA`, `OCEAN`, `LAVENDER`, `SUNSET`, `CHRISTMAS`, `HALLOWEEN`, `VALENTINE`, `EASTER`, `FOURTH`, `THANKSGIVING`, `CANDY`, `GALAXY`, `FIRE`, `ICE`, `FOREST`, `NEON`, `TWINKLE`, `SPARKLE`, `COLOR_SWAP`, `COMET`, `FIREFLY`, `BUBBLEGUM`, `OFF`.

### Current Pi flash/update workflow

```bash
cd ~/BloomCircuit
git pull
bash happyjarz-controller/tools/flash_happyjarz_v0_5.sh
```

The flasher stops the controller/watcher, stages the compatibility base, applies the current firmware patch chain, verifies the final sketch, compiles with Arduino CLI, uploads, and restarts the watcher.

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

## License

BloomCircuit is **free and open source** under the [MIT License](LICENSE).

You may use, copy, modify, fork, publish, and redistribute BloomCircuit, including in personal, educational, and commercial projects, as long as the MIT license notice is kept with the software.

There is no warranty; verify wiring and component pinouts against actual hardware and datasheets before powering a circuit.

## Scope

BloomCircuit is intentionally a wiring-map and fabrication-documentation tool. It does not replace KiCad, SPICE, PCB DRC, or a datasheet. The goal is to make a physical maker circuit easy to understand, reproduce, service, and engrave.


## HAPPY JARZ platform branch

`feature/happyjarz-platform` is the clean forward-development branch for the synchronized HAPPY JARZ product stack.

Current platform release pair:

```text
Host app  1.8.4
Firmware  0.17.13
```

Key additions on the platform branch:
- four-lamp host UI with separate BASE and LIVE color concepts
- integrated Mini in the LIGHTS + CONTROL panel
- actual 128x64 U8g2 OLED framebuffer mirror
- blue-on-black OLED rendering to match the physical blue OLED modules
- 12 visible logical controls: D-pad, A/B/X/Y, L/R, START/SELECT
- SIMPLE capability gating: only D-pad + A/B active
- semantic Linux gamepad support with event* preferred and js* fallback
- one shared serial connection for control + telemetry + OLED mirror
- host `KEY ...` commands entering the same firmware input path as physical touch
- SIMPLE / FULL and US / EU release-lane architecture

The production FULL board GPIO map remains intentionally uncommitted until the actual board is received and bench-tested.


### Current HAPPY JARZ platform snapshot

`feature/happyjarz-platform` currently targets:

```text
Host app  1.8.4
Firmware  0.17.13
Patterns  100
Savers    7
```

The firmware includes 100 registered four-lamp light patterns plus seven board-local OLED screensavers. The newest saver pack adds BLOOM, BREATHE and GLITTER, while the host app mirrors the actual blue SSD1306 framebuffer over the same USB serial connection used for control and telemetry.

Firmware 0.17.1 is the compile-fix release for that saver pack: visual-saver state is declared before saver-status telemetry uses it, and BLOOM uses the installed U8g2 five-argument `drawArc(x, y, radius, start, end)` API.

### Power, battery and sleep snapshot

Current SIMPLE firmware `0.17.13` includes:

- calibrated + filtered GPIO3 battery telemetry
- HOME battery percentage while USB is connected
- low-battery warning at <=10%, clearing at >=15%
- bulb 4 / right-side accent flashes red during low battery
- OLED `LOW BATTERY / CHARGE ME!!!` warning overlay
- SPST-switched 3.3V OLED/lamp accessory rail with automatic pause/resume detection
- one-hour software sleep with OLED power-save, lamps dark and pattern freeze
- any physical touch wakes the Jar; the wake touch is consumed
- alarm events wake the Jar before firing the alarm light pattern

The ESP32 itself remains running during accessory pause and software sleep so clock, alarm, USB, Wi-Fi and touch services stay alive.

### Input and accessory-resume fixes

Firmware `0.17.13` carries the latest HAPPY JARZ development fixes:

- switched accessory resume rebinds GPIO7 to the ESP32 RMT peripheral before sending APA106 data again
- the accessory rail still clamps GPIO7 LOW while OLED/lamp power is off
- all late menu routers receive the same merged logical input stream
- physical touch, app Mini buttons and semantic USB gamepad input therefore share UP/DOWN/LEFT/RIGHT/A/B across CLOCK, SETTINGS, INFO, LIGHTS, GAMES/ARCADE, MAIN MENU and HOME
- the one-hour sleep wake check remains physical-touch-only before host/gamepad events are merged

The staged verifier checks both the accessory RMT rebind and the final unified menu/gamepad input ordering.
