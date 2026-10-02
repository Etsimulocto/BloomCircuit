# BloomTunes

Pi-first procedural audio lab for HAPPY JARZ and future BloomCircuit builds.

## Current app: BloomTunes Studio v0.5

Launch:

```bash
python3 BloomTunes/bloomtunes_studio_v0_5.py
```

BloomTunes Studio is a dark-mode, sample-free mono synth/sequencer intended for tuning sounds on the Raspberry Pi before porting compact recipes to the ESP32-S3.

### Sequencer

- 8 synth tracks
- full 88-key MIDI range: A0 through C8
- four-bar piano-roll editing window
- songs can store up to 256 bars
- bar navigation in four-bar pages
- BPM control
- note sizes from very short steps through a full bar
- click a grid cell to place a note
- placing a note immediately auditions that pitch
- click an existing note to erase it
- notes store absolute MIDI pitch
- per-track waveform: sine, square, triangle, saw, noise
- per-track volume
- pulse width / PWM control
- attack and release
- detune
- harmonics
- per-track mute

The Pi preview renders the visible four-bar page rather than allocating a giant whole-song Python float buffer during every edit. The song data itself can still span 256 bars.

## Meditation Mode

v0.5 adds a compact long-form tone builder layered on top of the stable v0.4 sequencer.

Controls:

- START Hz
- END Hz
- duration in minutes
- volume
- waveform: sine, triangle, saw, square
- sweep curve: linear or logarithmic
- PLAY / STOP
- built-in meditation preset bank

Built-in starting presets include:

- 100 -> 528 Hz / 5 minutes
- 174 -> 528 Hz / 10 minutes
- 396 -> 963 Hz / 8 minutes
- 528 Hz hold / 10 minutes
- 80 -> 174 Hz / 5 minutes
- 55 -> 285 Hz / 10 minutes

Meditation output is forced mono. Long sessions are streamed to a mono WAV in chunks rather than storing the entire session in a giant Python float list. Master volume plus lightweight drive, tremolo and PWM-style modulation from the master FX rack are applied during meditation rendering.

### Instrument patch bank

Built-in starting patches include:

- Pure Sine
- Soft Bell
- Warm Pad
- PWM Pluck
- Glass
- Bass
- Noise Hit

Instrument patches can also be saved as JSON.

### Forced mono signal path

All eight tracks are mixed to one mono bus before effects and playback. The WAV output is one-channel mono so Pi auditioning represents the single-speaker HAPPY JARZ architecture.

```text
Track 1 --\
Track 2 ---\
...         > MONO MIX -> MASTER FX -> MONO WAV -> Pi audio output
Track 8 ---/
```

### Master effects rack

End-of-chain controls include:

- master volume
- drive / saturation
- three parametric-style EQ bands
  - frequency
  - Q
  - gain
- compressor
  - threshold
  - ratio
  - attack
  - release
  - makeup gain
- tremolo
  - rate
  - depth
- PWM-style rhythmic amplitude modulation
  - rate
  - depth
- phaser
  - rate
  - depth
- echo
  - milliseconds
  - mix
- high-pass filter
- low-pass filter

Reset buttons are provided for EQ, dynamics, modulation, delay/filter, all FX, and the current track.

### FX patch bank

Built-in FX presets include:

- Clean
- Soft Glow
- Dream Phaser
- Rain Wash
- Deep Calm
- Sparkle
- Tremolo Pulse
- Crunch

FX patches can also be saved as JSON.

### Song files

SAVE SONG and LOAD SONG use JSON. Songs store BPM, bar count, all eight tracks, note data, synth controls and master FX parameters.

## Earlier prototypes

`bloomtunes.py` — first command-line procedural sound test.

`bloomtunes_app.py` — first GUI synth workbench for tuning individual procedural patches.

`bloomtunes_studio.py` — stable v0.4 sequencer/workstation base used by v0.5.

## HAPPY JARZ target

- one mono speaker
- compact Same Sky full-range driver
- small mono amplifier
- ESP32-generated procedural tones/noise rather than stored WAV/MP3 samples where practical
- audio control path remains separate from the future motor-driver path

Sound recipes can eventually be associated with HAPPY JARZ light presets after they are tuned on the Pi.
