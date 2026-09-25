# BloomCircuit

BloomCircuit is a tiny browser-based wiring-map editor built for maker projects that need a clear physical wiring plan and clean SVG output for laser engraving.

## v0.1 goals

- Snap-to-grid circuit layout
- Drag components around a measured canvas
- Click pin -> click pin wiring
- Net types: 5V, 3V3, GND, DATA, OTHER
- Raspberry Pi 40-pin header
- SN74AHCT125N level shifter
- APA106 addressable RGB LED
- Resistor, capacitor, buses, and generic nodes
- Happy Jarz starter circuit
- Save/load JSON projects
- Export SVG for xTool / laser engraving
- Etch mode for monochrome fabrication drawings
- Basic warning when a 5V net is connected directly to a GPIO/3V3 pin

## Run

No build step is required.

Open `index.html` directly in a browser, or serve the folder:

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080`.

## Scale

The workspace uses a 10 px snap grid representing **2.54 mm** (0.1 inch), the common breadboard / header pitch. SVG exports include physical dimensions in millimeters.

## Happy Jarz template

The included starter template models the bench circuit used during Happy Jarz development:

`Pi 5 GPIO10/MOSI -> SN74AHCT125N -> 1K -> APA106 #1 -> APA106 #2`

with shared 5V/GND buses and 104 decoupling capacitors.

## Status

Early working prototype. The editor intentionally focuses on visual wiring documentation and laser-friendly output rather than PCB routing, SPICE simulation, or Gerber generation.
