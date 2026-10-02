# BloomSaver

BloomSaver is the standalone HAPPY JARZ / BLOOMCORE generative visual laboratory. It is intentionally separate from the controller UI so visual systems can be tuned, abused, saved, and iterated without touching jar-control code.

## Run on Raspberry Pi

```bash
cd ~/BloomSaver
python3 bloomsaver_pi.py
```

No npm or external Python packages are required.

## Base visual families

- **Particle Universe**
- **Silk Flow**
- **Crystal Bloom**
- **Orbital Garden**
- **Signal Rain**

These are no longer treated as a short playlist of fixed screensavers. They are visual families / DNA parents that the generative layer can blend and mutate.

## Living generative engine

The fullscreen generator continuously creates and destroys simple actors instead of replaying one canned loop:

- moving emitters that can start from edges, corners, the center, rings, or random locations
- attractors and repulsors with their own lifetimes
- wander, orbit, figure-eight, spiral, edge-crawl, and bounce motion rules
- multiple particle/glitter shapes and sizes
- random bursts and edge storms
- gravity flips
- palette kicks
- moving flow fields
- trails that fade independently over the transparent overlay

The six visual DNA parents are **Universe, Silk, Crystal, Orbit, Rain, and Glitter**. A scene is born from a weighted blend of several parents, then mutates toward new blends over time. Presets are starting tendencies, not loops.

Every few seconds BloomSaver performs a small mutation. Independent random events happen on their own schedule. Emitters and force points also expire and regenerate, so the system can keep changing without returning to a fixed animation cycle.

## Live controls

The original controls remain useful as global biases:

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

The generative layer reads key controls such as speed, noise, swirl, and glow while its own actor system evolves independently.

## Generator controls

- **GENERATOR ON/OFF** — toggle the fullscreen generative overlay
- **Shift-click GENERATOR** — throw away the current DNA and generate a completely new living system
- `G` — toggle generator
- `Shift+G` — reseed the generator
- `X` — immediate reseed

The normal BloomSaver UI still auto-hides after five seconds of inactivity.

## Presets

Saved presets continue to live in browser `localStorage`. They remain useful as visual starting points, but the long-term direction is for presets to act as editable DNA bias profiles rather than deterministic animations.

## Design goal

BloomSaver should be simple at the primitive level and extremely complicated in combination. The goal is not a catalog of screensaver loops. It is a visual ecosystem that can keep inventing new scenes from a small set of rules.

Once a behavior feels right here, selected parameters can be reduced for the ESP32/OLED/LED hardware or embedded into the HAPPY JARZ desktop controller.
