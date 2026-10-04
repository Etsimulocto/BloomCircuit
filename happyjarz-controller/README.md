# HAPPY JARZ Controller

## Active branch build: CLUB BOX line-in EQ controller

On branch `happyjarz-controller-v0.1`, the current active bench build is the **HAPPY JARZ / CLUB BOX audio-reactive controller**.

This is separate from the older integrated two-light/touch/OLED Jar controller still preserved in the repository for reference.

## Current hardware map

Controller: **ESP32-S3 SuperMini**

### APA106 lighting

- GPIO7 -> 220 ohm -> APA106 DIN
- proven physical byte order: **RGB**
- known-good custom ESP32 HAL RMT path
- current bench test: one APA106 bulb
- target build: 16 daisy-chained APA106 bulbs

Known-good timing:

- 10 MHz RMT clock
- bit 0 ~= 4 ticks HIGH / 14 LOW
- bit 1 ~= 14 HIGH / 4 LOW
- ~100 us LOW reset/latch

Do not casually replace this driver with generic NeoPixel/FastLED code while tuning the app or EQ layer.

### Mono line input

GPIO9 is the current analog line input.

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

The electrolytic capacitor's negative/striped side faces the audio source. The ESP32 side is biased around mid-supply by the two 10k resistors.

Do **not** feed 3.3V back into the audio jack.

### Physical threshold knob

GPIO10 is the only live threshold/noise-floor control.

```text
outer leg -> GND
wiper     -> GPIO10
outer leg -> 3.3V
```

If knob direction is backwards, swap the two outer legs only.

The app intentionally does not provide a second threshold slider.

## Current EQ engine

Firmware:

```text
firmware/happyjarz_sound_reactive_v0_1.ino
```

Analyzer:

- 8-band Goertzel
- 8 kHz sample rate
- 256 samples per block

Default edges:

```text
40, 90, 180, 350, 700, 1200, 2000, 3000, 3900 Hz
```

Default colors:

```text
Band 1  Red
Band 2  Orange
Band 3  Amber
Band 4  Lime
Band 5  Green
Band 6  Cyan
Band 7  Blue
Band 8  Violet
```

Current modes:

- **Single bulb bench** — dominant band drives the first bulb
- **16 bulbs** — two bulbs per EQ band

The physical knob maps across the full useful live gate range. Gain controls how hard accepted audio drives brightness. Max Brightness sets the output ceiling.

## Reset contract

`RESET` means restore the whole known-good visualizer state.

It must restore:

- Gain = 4.0
- Max Brightness = 255
- output mode = Single bulb bench
- original 8 band edges
- original 8 band colors
- physical knob state reread from GPIO10
- stale graphic-EQ / bulb-preview values cleared
- normal reactive output resumed

Reset must not leave a stale fixed bulb color or stale app dropdown/range state.

## Current Raspberry Pi tuner

App:

```text
tools/happyjarz_meter.py
```

Run manually:

```bash
python3 ~/BloomCircuit/happyjarz-controller/tools/happyjarz_meter.py
```

Dependencies:

```bash
sudo apt install -y python3-serial python3-tk
```

Current app features:

- live 8-band graphic EQ
- center / P2P / dominant band / energy / clipping telemetry
- physical knob raw / percent / gate display
- Gain
- Max Brightness
- editable band edges
- editable band colors
- Single / 16 bulb mode selection
- 16-bulb live preview
- RGB test
- All 16 test
- Chase 16 test
- Reset
- CSV log at `~/happyjarz_eq_log.csv`

The Python serial connection sets DTR/RTS false. Do not use `arduino-cli monitor` as the normal monitor path because it previously caused resets/glitches.

## Auto-open / unplug behavior

Watcher:

```text
tools/happyjarz_autolaunch.py
```

Installer:

```text
tools/install_happyjarz_autolaunch.sh
```

Expected behavior:

- ESP32 appears and stays stable -> tuner opens
- ESP32 is unplugged -> tuner closes cleanly
- user manually closes tuner while ESP32 remains connected -> tuner stays closed
- unplug/replug -> watcher rearms and may open it again
- watcher refuses to launch while `arduino-cli` or `esptool` is active

The stability delay and flashing-process check exist specifically to prevent the app from stealing `/dev/ttyACM0` during uploads.

## Current direct flash workflow

FQBN:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

Current staging path on the Pi:

```text
~/hjflash/happyjarz_sound_reactive_v0_1/
```

Normal command:

```bash
cd ~/BloomCircuit && \
pkill -f happyjarz_meter.py 2>/dev/null || true; \
pkill -f happyjarz_autolaunch.py 2>/dev/null || true; \
git pull && \
cp happyjarz-controller/firmware/happyjarz_sound_reactive_v0_1.ino ~/hjflash/happyjarz_sound_reactive_v0_1/happyjarz_sound_reactive_v0_1.ino && \
arduino-cli compile --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc ~/hjflash/happyjarz_sound_reactive_v0_1 && \
arduino-cli upload -p /dev/ttyACM0 --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc ~/hjflash/happyjarz_sound_reactive_v0_1
```

If Git blocks a pull because the two auto-launch files were locally edited and those edits are disposable:

```bash
git restore tools/happyjarz_autolaunch.py tools/install_happyjarz_autolaunch.sh
```

Run from `~/BloomCircuit/happyjarz-controller` for the short paths above, or use the full repository-relative paths from the repo root.

## Power note for 16 bulbs

The current one-bulb bench setup may be powered from the ESP32 3.3V rail for testing because that exact physical bulb has been proven there.

The finished 16-bulb array must **not** be powered from the ESP32 3.3V rail. Use an adequate external LED supply and common ground with the ESP32.

## Failure boundary

Preserve proven low-level layers.

If RGB Test works but reactive behavior is wrong, debug line input, knob, EQ, telemetry, and app state before changing the RMT driver.

If GPIO10 reads near 0 when grounded and near 4095 at 3.3V, the ADC pin is working; verify pot wiring/ground rails before changing firmware.

If `/dev/ttyACM0` is busy during flashing, close the tuner/watcher first and verify the auto-launch watcher is the current delayed/flasher-aware version.

## Legacy integrated controller material

Older files in this folder document a different HAPPY JARZ prototype with:

- two APA106 lights
- six capacitive-touch controls
- OLED menus/screensavers
- Wi-Fi
- battery/power telemetry
- sayings and procedural saver modes

Those files are intentionally retained as historical/reference material. Their GPIO assignments are **not** the current CLUB BOX line-in wiring map and should not be mixed into this branch without deliberate remapping.

**Rule: preserve the proven hardware/protocol layer; tune behavior above it.**