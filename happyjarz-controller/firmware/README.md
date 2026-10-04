# HAPPY JARZ / CLUB BOX ESP32 Firmware

## Active branch firmware

On branch `happyjarz-controller-v0.1`, the active bench firmware is:

```text
happyjarz_sound_reactive_v0_1.ino
```

This is the current **line-in, physical-threshold-knob, 8-band EQ visualizer** firmware. Older integrated HAPPY JARZ firmware files remain in the repository as reference for the separate touch/OLED/Wi-Fi prototype.

## Preserve the known-good APA106 layer

The proven APA106 path uses the Arduino ESP32 HAL RMT API:

```cpp
#include "esp32-hal-rmt.h"
rmtInit(...)
rmtSetEOT(...)
rmtWrite(...)
```

Known-good transport:

- ESP32-S3 SuperMini
- GPIO7 data
- 220 ohm series resistor on data
- 10 MHz RMT clock
- bit 0 ~= 4 ticks HIGH / 14 LOW
- bit 1 ~= 14 HIGH / 4 LOW
- ~100 us LOW reset/latch
- physical byte order: **RGB**

Generic NeoPixel/FastLED attempts were not the proven path for these bulbs. Do not replace the low-level transport while debugging EQ/app behavior unless the LED transport itself is proven broken.

## Current pins

```text
GPIO7  = APA106 data
GPIO9  = mono line input
GPIO10 = physical threshold/noise-floor potentiometer
```

## Line input

Current mono line-input circuit:

```text
TRS TIP ---- (-) 10uF (+) ----+---- GPIO9
                               |
                              10k
                               |
                              3.3V

GPIO9 -------------------------+
                               |
                              10k
                               |
                              GND

TRS SLEEVE -------------------- GND
TRS RING ---------------------- unused
```

Important:

- electrolytic negative/striped side faces the audio source
- ESP32 side of the capacitor is biased around mid-supply
- do not feed 3.3V into the source/jack
- all grounds must actually be common; a floating/blank breadboard rail can produce nonsense ADC values

The current Pi/monitor headphone output was observed to be relatively quiet, so stronger normal sources may produce larger line-input swings.

## Physical threshold knob

Current wiring:

```text
outer leg -> GND
wiper     -> GPIO10
outer leg -> 3.3V
```

The firmware reads GPIO10 as the **only threshold/noise-floor control**.

Expected direct ADC checks:

```text
GPIO10 -> GND   ~= 0
GPIO10 -> 3.3V  ~= 4095
```

If direction is backwards, swap the two outer pot legs. Keep the wiper on GPIO10.

## EQ analyzer

Current analyzer:

- Goertzel, no extra DSP dependency
- 8 bands
- 8 kHz sample rate
- 256 samples per block
- three probe frequencies per band; strongest result becomes that band's energy

Default edges:

```text
40, 90, 180, 350, 700, 1200, 2000, 3000, 3900 Hz
```

Default colors:

```text
1  255,0,0      Red
2  255,70,0     Orange
3  255,180,0    Amber
4  80,255,0     Lime
5  0,255,90     Green
6  0,180,255    Cyan
7  40,40,255    Blue
8  180,0,255    Violet
```

## Output modes

### Mode 1 — single bulb bench

The dominant EQ band controls the current bulb color and energy controls brightness.

### Mode 16 — sixteen bulbs

Two bulbs are assigned to each band:

```text
1-2   Band 1
3-4   Band 2
5-6   Band 3
7-8   Band 4
9-10  Band 5
11-12 Band 6
13-14 Band 7
15-16 Band 8
```

Each band can light independently from its own energy.

## Brightness response

The threshold knob decides what audio energy is ignored. Accepted energy is then shaped by EQ gain and a soft compression curve so quieter sources can still produce visible, punchy output.

The threshold knob spans the full useful gate range directly in firmware. There is no software threshold slider in the current tuner.

## Reset contract

`RESET` must restore the known-good baseline:

- Gain = 4.0
- Max Brightness = 255
- output mode = 1
- original band edges
- original colors
- physical knob filter/state reset and reread
- stale band-energy state cleared
- LED output cleared, then normal reactive behavior resumes

Reset must not leave the bulb stuck on a stale color.

## Serial telemetry

Streaming is **off by default**. The tuner enables it with:

```text
STREAM 1
```

and disables it on close with:

```text
STREAM 0
```

Current live EQ telemetry includes fields such as:

```text
CENTER
P2P
CLIP
DOM
ENERGY
KNOB
KNOBPCT
GATE
MODE
B1 ... B8
```

The app depends on this stream for the graphic EQ and 16-bulb preview.

## Current commands

Core commands include:

```text
STREAM 1
STREAM 0
GET
RESET
TEST RGB
TEST ALL16
TEST CHASE16
SET MODE 1
SET MODE 16
SET GAIN <value>
SET BRIGHT <value>
SET EDGE <index> <hz>
SET COLOR <band> <r,g,b>
```

## Compile/upload

Current Arduino CLI FQBN:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

Current direct Pi workflow stages the sketch into:

```text
~/hjflash/happyjarz_sound_reactive_v0_1/
```

Typical compile/upload:

```bash
cp ~/BloomCircuit/happyjarz-controller/firmware/happyjarz_sound_reactive_v0_1.ino \
  ~/hjflash/happyjarz_sound_reactive_v0_1/happyjarz_sound_reactive_v0_1.ino

arduino-cli compile \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc \
  ~/hjflash/happyjarz_sound_reactive_v0_1

arduino-cli upload \
  -p /dev/ttyACM0 \
  --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc \
  ~/hjflash/happyjarz_sound_reactive_v0_1
```

Before flashing, close/stop the tuner and plug watcher so the serial port is free. The current watcher also checks for `arduino-cli` / `esptool` and waits for a stable port before auto-launching.

## Power note

The current **single physical bench bulb** has been proven on the ESP32 3.3V rail for testing.

Do **not** power the finished 16-bulb array from the ESP32 3.3V rail. Use an adequate external LED supply with common ground to the ESP32.

## Diagnostics / failure boundary

Preserve known-good layers.

If `TEST RGB` works but music reaction does not:

- inspect GPIO9 center/P2P
- inspect band energies
- inspect GPIO10 knob raw/gate
- verify actual breadboard ground continuity
- verify source volume
- verify the app has enabled streaming

If the graphic EQ stops while the LED still reacts, debug serial telemetry/app streaming before touching the RMT driver.

If the LED is stuck on a color after a test/reset, clear output/state in the behavior layer before changing the proven RGB/RMT transport.

## Legacy firmware material

Older files in this directory document a different integrated HAPPY JARZ build with touch controls, OLED, Wi-Fi, battery/power telemetry, patterns, sayings and procedural screensavers.

Those files are intentionally retained as reference. Their GPIO map is not the current CLUB BOX line-in map.

**Preserve the proven low-level hardware layer; tune behavior above it.**