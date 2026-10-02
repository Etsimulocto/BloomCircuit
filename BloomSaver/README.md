# BloomSaver

BloomSaver is the standalone HAPPY JARZ / BLOOMCORE procedural screensaver laboratory. It is intentionally separate from the controller UI so visual systems can be tuned, abused, saved, and iterated without touching jar-control code.

## Run on Raspberry Pi

```bash
cd ~/BloomCircuit/BloomSaver
python3 bloomsaver_pi.py
```

No npm or external Python packages are required.

## Visual modes

- **Particle Universe** — moving particles, attractors, repulsion, orbit bias, trails, and optional links.
- **Silk Flow** — mirrored field-flow particles that form soft ribbons and symmetry blooms.
- **Crystal Bloom** — rotating procedural radial growth with pulse, symmetry, hue spread, and glow.
- **Orbital Garden** — nested procedural orbital systems with living eccentricity and pulse.
- **Signal Rain** — drifting procedural glyph rain for the more control-room / sci-fi side of BloomSaver.

## Live controls

BloomSaver exposes:

- particle count
- speed
- trail persistence
- link distance
- attraction
- repulsion
- field noise
- swirl
- glow
- symmetry
- hue
- hue spread
- pulse
- visual scale

The entire parameter set can be randomized or mutated.

## Evolution

**Randomize** makes a new universe from scratch.

**Mutate** keeps the current universe recognizable while nudging its parameters.

**Auto evolve** periodically mutates the current state, making a screensaver that can continue changing indefinitely without simply repeating a canned animation.

Mutation strength and evolution timing are editable.

## Presets

Saved presets live in browser `localStorage`, so tuning experiments survive reloads on the same Pi/browser profile.

Each preset stores:

- seed
- visual mode
- all visual parameters
- auto-evolve state
- evolution interval
- mutation strength

## Keyboard

- `R` — randomize
- `M` — mutate
- `Space` — pause/resume
- `F` — fullscreen
- `H` — hide/show controls

## Design goal

BloomSaver is a visual laboratory first. Once a visual family feels right here, selected parameters and behavior can be reduced for the ESP32/OLED/LED hardware or embedded into the HAPPY JARZ desktop controller as its app screensaver.
