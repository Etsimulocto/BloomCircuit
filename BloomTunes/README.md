# BloomTunes

Pi-first procedural audio lab for HAPPY JARZ and future BloomCircuit builds.

## Goal

Prototype sounds on the Raspberry Pi using generated tones/noise instead of stored samples, tune them by ear, save the successful settings as tiny JSON recipes, then port those recipes to the ESP32-S3.

## BloomTunes Synth Lab

Launch the graphical tuning app with:

```bash
python3 BloomTunes/bloomtunes_app.py
```

The app uses Tkinter and the Python standard library only. It renders temporary 44.1 kHz stereo WAV previews and plays them through the first available player: `aplay`, `paplay`, or `ffplay`.

### Controls

**Oscillator**
- Modes: Tone, Drone, Chimes, Rain, Wind, Particles, Galaxy
- Waveforms: sine, square/PWM, triangle, saw, noise
- Base frequency
- Detune in cents
- Pulse width
- Harmonic count
- Harmonic falloff
- Master level

**Envelope**
- Attack
- Decay
- Sustain
- Release

**Modulation / filtering**
- Amplitude LFO rate and depth
- Vibrato rate and depth
- Noise mix
- Low-pass amount
- High-pass amount

**Texture / performance**
- Event density
- Randomness
- Preview duration
- Random seed
- Reserved glide control for a later engine revision

### Factory patches

- Pure 528
- Warm Drone
- Soft Chimes
- Rain
- Wind
- Particles
- Galaxy

The **SOLFEGGIO** button cycles through:

`174, 285, 396, 417, 528, 639, 741, 852, 963 Hz`

**SAVE PATCH** writes the current control settings to JSON. These files are intended to become the compact source-of-truth sound recipes for the later ESP32 implementation.

## Command-line prototype

The original v0.1 sound generator remains available:

```bash
python3 BloomTunes/bloomtunes.py
```

It provides simple procedural chimes, rain, wind, particles, and galaxy previews.

## Design approach

BloomTunes deliberately does not depend on prerecorded WAV/MP3 sound libraries. Sound is generated mathematically from oscillator frequencies, pulse width, harmonics, ADSR envelopes, modulation, filtered pseudo-random noise, event timing, and seeded randomness.

This makes it possible to create many variations while keeping the eventual HAPPY JARZ firmware recipes small.

The Raspberry Pi app uses normal PCM audio output for auditioning. The eventual ESP32 version can translate the proven recipes into its own hardware audio/PWM implementation; the Pi app is not claiming to electrically reproduce that final output stage.

## Planned HAPPY JARZ integration

- GPIO11: audio signal/control path to a small mono amplifier
- GPIO12: separate motor-driver control
- Speaker target: compact Same Sky full-range driver
- No speaker may be driven directly from an ESP32 GPIO
- Motor remains isolated through its own proper driver/MOSFET and flyback protection

## Status

Experimental sound-design workbench. Pi tuning comes first. ESP32 implementation follows after the recipes sound good.
