# BloomTunes

Pi-first procedural audio lab for HAPPY JARZ and future BloomCircuit builds.

## Goal

Prototype sounds on the Raspberry Pi using generated tones/noise instead of stored samples, tune them by ear, then port the successful recipes to the ESP32-S3.

## Initial sound ideas

- Solfeggio-style tone sets
- Random chimes
- Rain
- Wind
- Falling-particle / glitter plinks
- Soft drones
- Preset-specific light-show sound recipes

## Why procedural audio

The sound is generated mathematically at runtime, so presets can have lots of variation without storing large WAV/MP3 files. The recipes are small: frequencies, timing, envelopes, noise parameters, and randomization rules.

## Raspberry Pi prototype

Start with:

```bash
python3 BloomTunes/bloomtunes.py
```

The first prototype writes 16-bit mono PCM into a temporary WAV file and plays it through an available command-line audio player (`aplay`, `paplay`, or `ffplay`). This keeps the Python dependencies minimal while we tune the sound engine.

## Planned HAPPY JARZ integration

- GPIO11: audio signal/control path to a small mono amplifier
- GPIO12: separate motor-driver control
- Speaker target: compact Same Sky full-range driver
- No speaker may be driven directly from an ESP32 GPIO
- Motor remains isolated through its own proper driver/MOSFET and flyback protection

## Status

Experimental. Pi sound design comes first. ESP32 implementation follows only after the recipes sound good.
