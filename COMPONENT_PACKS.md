# BloomCircuit Component Packs

Component packs let BloomCircuit gain parts without changing the editor code.

## File shape

```json
{
  "format": "BloomCircuitComponentPack",
  "version": 1,
  "name": "My parts",
  "components": [
    {
      "id": "example_sensor",
      "definition": {
        "title": "Example Sensor",
        "palette": "Example Sensor",
        "category": "Sensors & Modules",
        "kind": "rect",
        "width": 160,
        "height": 100,
        "subtitle": "Example module",
        "keywords": ["sensor", "example"],
        "defaultValue": "",
        "pins": [
          { "id": "vcc", "name": "VCC", "role": "power", "x": 0, "y": 25, "side": "left" },
          { "id": "gnd", "name": "GND", "role": "gnd", "x": 0, "y": 75, "side": "left" },
          { "id": "sig", "name": "SIGNAL", "role": "gpio", "x": 160, "y": 50, "side": "right" }
        ]
      }
    }
  ]
}
```

## Supported shapes

- `rect`
- `dip`
- `led`
- `resistor`
- `capacitor`
- `bus`
- `node`

Unknown shapes fall back to `rect`.

## Supported pin roles

- `5v`
- `3v3`
- `gnd`
- `gpio`
- `input`
- `output`
- `control`
- `power`
- `passive`
- `analog`
- `i2c`
- `spi`
- `uart`
- `pwm`
- `nc`

## Pin sides

- `left`
- `right`
- `top`
- `bottom`

Coordinates are editor pixels. BloomCircuit uses **10 px = 2.54 mm**.

## Fast in-app component syntax

The custom component dialog accepts one pin per line:

```text
id | label | role | side | position%
```

Example:

```text
vcc | VCC | power | left | 30
gnd | GND | gnd | left | 70
sig | SIGNAL | gpio | right | 50
```

This is intended for quick bench work: make the part while it is in your hand, use it immediately, then export the component pack and commit it to the project later.
