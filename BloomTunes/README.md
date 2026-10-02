# BloomTunes

Pi-first procedural audio lab for HAPPY JARZ and future BloomCircuit builds.

## Current app: BloomTunes Studio v0.3

Launch:

```bash
python3 BloomTunes/bloomtunes_studio.py
```

BloomTunes Studio is a dark-mode, sample-free synth/sequencer intended for tuning sounds by ear on the Raspberry Pi before porting compact sound recipes to the ESP32-S3.

### Sequencer

- 8 synth tracks
- 16-step piano-roll style editor
- 24 visible pitches per track
- BPM control
- note sizes: 1/16, 1/8, 3/16, 1/4
- click a grid cell to place a note
- click an existing note to erase it
- per-track waveform: sine, square, triangle, saw, noise
- per-track volume
- octave shift
- pulse width / PWM control
- attack and release
- per-track mute

### Forced mono signal path

All eight tracks are mixed to one mono bus before output. WAV export/playback is one-channel mono so Pi auditioning represents the single-speaker HAPPY JARZ architecture instead of using artificial stereo spread.

Signal path:

```text
Track 1 --\
Track 2 ---\
...         > MONO MIX -> MASTER FX -> MONO WAV -> Pi audio output
Track 8 ---/
```

### Master effects rack

The end-of-chain rack currently provides:

- master volume
- LOW / MID / HIGH tone shaping
- drive / saturation
- PWM-style rhythmic amplitude modulation: rate + depth
- lightweight phaser: rate + depth
- echo: milliseconds + mix
- low-pass filtering
- high-pass filtering

The effects intentionally use lightweight algorithms so the useful recipes can later be simplified for the ESP32 rather than depending on a desktop DAW or sample library.

### Song files

SAVE and LOAD use JSON. Songs store BPM, all eight tracks, notes, synth controls and master FX parameters.

## Earlier prototypes

`bloomtunes.py` — first command-line procedural sound test.

`bloomtunes_app.py` — first GUI synth workbench for tuning individual procedural patches.

These remain in the repository as development references.

## HAPPY JARZ target

- one mono speaker
- compact Same Sky full-range driver
- small mono amplifier
- ESP32-generated procedural tones/noise rather than stored WAV/MP3 samples where practical
- audio control path remains separate from the future motor-driver path

Sound recipes can eventually be associated with HAPPY JARZ light presets after they are tuned on the Pi.
