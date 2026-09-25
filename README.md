# BloomCircuit

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

## Core editor

- 10 px = 2.54 mm snap grid
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
