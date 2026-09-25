# BloomCircuit

## Raspberry Pi offline app

BloomCircuit can run as a local desktop-style app on Raspberry Pi with no internet connection.

From the cloned repository:

```bash
cd ~/BloomCircuit
git pull
bash install_pi.sh
```

After install, BloomCircuit is available in three places:

- a **BloomCircuit icon on the Raspberry Pi desktop/home screen**
- the Raspberry Pi application menu
- the terminal command:

```bash
bloomcircuit
```

The launcher uses Python's built-in local HTTP server and opens Chromium in app mode. All HTML, CSS, JavaScript, component data, embedded component images, project saves, and SVG export stay local. No Node.js, Electron, cloud service, or internet connection is required.

Updating the installed app is just:

```bash
cd ~/BloomCircuit
git pull
```

Then close and reopen BloomCircuit. Re-running `bash install_pi.sh` is only needed if the desktop/menu launcher itself changes.

## v0.5 physical-layout workflow

BloomCircuit's built-in parts, custom parts, and board maker now use the same physical coordinate system:

- **10 px = 2.54 mm = one standard breadboard/perfboard hole pitch**
- all 47 built-in library parts were re-laid onto that grid
- built-in pin locations land on grid intersections
- built-in component dimensions land on the same 10 px grid
- DIP parts use 2.54 mm pin pitch and a 0.3 inch row spacing
- components and board underlays can be rotated in 90° steps
- components and boards use exact numeric scale controls instead of scale sliders
- exact scale values such as 123%, 144%, or 184% are accepted
- connected wires follow scaled and rotated component pins
- endpoint-note + / edit handles sit 20% in from each end of the routed wire so they stay visible instead of hiding under components

### Visual Component Maker

The custom component maker is now built around the same breadboard grid.

You can:

1. Set the footprint size in X/Y grid holes.
2. Upload a real component image.
3. Overlay the image on the 2.54 mm grid.
4. Click grid intersections to create pins.
5. Drag pins from hole to hole.
6. Enter exact Grid X / Grid Y positions.
7. Name pins and assign roles such as VCC, GND, GPIO, input, output, I2C, SPI, UART, PWM, and more.
8. Zoom the footprint editor from 25% to 800%, enter an exact zoom percentage, or use **Fit**.
9. Use the visible cutout outline to see the saved component footprint boundary.
10. Save the image and pin layout into the component library / component pack.

Custom component images are embedded in the saved component definition so the part can travel with its project or exported component pack.

## v0.4 board underlays

BloomCircuit now includes a configurable physical-board underlay maker:

- square perfboard / isolated-hole grid
- stripboard / rail board
- standard breadboard with center trench
- breadboard with center trench plus power rails
- configurable hole counts on X and Y
- fixed 2.54 mm hobby-board pitch
- multiple boards per project
- draggable underlays that stay behind components and wires
- board and hole colors
- board geometry saved in project JSON and included in SVG export

## v0.3.1 inspector fix

- component editor now stays open after a normal click
- component editor stays open after drag/reposition
- blank-canvas clicks still deselect normally

BloomCircuit is a small browser-based wiring-map editor for maker projects. It is built around **physical wiring documentation**, a **2.54 mm snap grid**, and **laser-ready SVG export** rather than PCB routing or SPICE simulation.

## v0.2

BloomCircuit now has a patchable hobby-electronics component library.

### Component library

Built-in categories currently include:

- Controllers
  - Raspberry Pi 40-pin
  - ESP32 DevKit / WROOM-32
  - Raspberry Pi Pico
  - Arduino Nano
- Power & Wiring
  - 5V, 3V3, and GND buses
  - junction nodes
- Connectors
  - JST-PH 2-pin
  - screw terminals
  - pin headers
  - DC barrel jack
- Passives
  - resistor
  - ceramic capacitor
  - electrolytic capacitor
  - diode
  - potentiometer
- Lights & Displays
  - standard LED
  - 4-pin RGB LED
  - APA106-F8 addressable LED
  - generic I2C OLED
- ICs & Logic
  - SN74AHCT125N
  - generic DIP-8 / 14 / 16 / 28
- Switches & Controls
  - pushbutton
  - SPST / SPDT / DPDT switches
  - capacitive touch pad
- Motors & Sound
  - DC motor
  - 3-wire servo
  - speaker
  - buzzer
- Power
  - 1S / 2-cell 18650 blocks
  - boost converter
  - buck converter
  - TP4056 charger
- Sensors & Modules
  - generic I2C module
  - generic SPI module
  - generic UART module
  - 1-channel relay module

Some hobby boards have multiple vendor pinout variants. Verify the exact board/module before using a template as an electrical authority.

### Patch components as you go

The **Patch Library** section lets you:

1. Create a custom component directly in the browser.
2. Define its pins, roles, sides, and physical layout.
3. Save custom components locally in the browser.
4. Export custom components as a portable JSON component pack.
5. Import a component pack later or on another machine.
6. Embed custom definitions inside saved BloomCircuit projects so a project can travel with its non-standard parts.

The palette is searchable and filterable by category.

See [COMPONENT_PACKS.md](COMPONENT_PACKS.md) for the pack format.

## v0.3 visual editor

The right-side Editor panel adds quick fabrication/layout controls:

- rotate selected components in 90° steps
- exact component scaling by percentage
- per-component fill color and text color
- per-component title font size
- selected-wire net type, color, width, and label font size
- canvas background, minor-grid, and major-grid colors
- global pin-label font size
- canvas zoom from 25% to 200%
- visual settings saved with project JSON
- rotated pin geometry stays attached to wires

## Core editor

- 10 px = 2.54 mm snap grid shared by boards and components
- drag components
- click pin -> click pin wiring
- wire types: 5V, 3V3, GND, DATA, OTHER
- simple power/GPIO wiring warnings
- save/load project JSON
- etch mode
- SVG export with millimeter dimensions for xTool
- Happy Jarz starter circuit

## Run

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

If the repo is already cloned:

```bash
cd ~/BloomCircuit
git pull
python3 -m http.server 8080
```

## Happy Jarz starter template

The included template models:

```text
Pi 5 GPIO10/MOSI
    ->
SN74AHCT125N
    ->
1K
    ->
APA106 #1
    ->
APA106 #2
```

with shared 5V/GND buses and 104 decoupling capacitors.

## Scope

BloomCircuit is intentionally a wiring-map and fabrication-documentation tool. It does not currently replace KiCad, SPICE, PCB DRC, or a datasheet. The goal is to make a physical maker circuit easy to understand, reproduce, and engrave.
