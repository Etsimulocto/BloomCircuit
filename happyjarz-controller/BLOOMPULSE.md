# BloomPulse

**BloomPulse** is the HAPPY JARZ / CLUB BOX music-reactive light controller.

It combines the ESP32-S3 line-in EQ firmware with the Raspberry Pi tuner for live audio visualization, physical threshold control, band/color tuning, and the planned 16-bulb light array.

## Proven bench state — October 4, 2026

The current bench path is working end-to-end:

- live audio drives the EQ and APA106 output
- muting the source stops the lights
- unplugging the 3.5 mm audio input stops the lights
- no-source ADC noise is rejected by the firmware silence/activity detector
- 16-bulb mode logic is working with the current one-bulb bench setup
- the Raspberry Pi app survives brief USB/serial hiccups and only closes after a real disconnect grace period

This is the current known-good behavior to preserve while the physical 16-bulb build and enclosure are developed.

## Raspberry Pi app

Install BloomPulse into the Raspberry Pi application menu with:

```bash
cd ~/BloomCircuit
git pull
chmod +x happyjarz-controller/tools/install_bloompulse_pi_app.sh
./happyjarz-controller/tools/install_bloompulse_pi_app.sh
```

After installation, open:

```text
Raspberry Pi menu -> Sound & Video -> BloomPulse
```

The launcher runs:

```text
~/BloomCircuit/happyjarz-controller/tools/happyjarz_meter.py
```

The USB auto-launch watcher remains separate. Plugging in the controller can open BloomPulse automatically, while the menu entry lets it be launched manually.

## Current control model

- GPIO9 = mono line input
- GPIO10 = physical threshold / noise-floor knob
- GPIO7 = APA106 data
- 8 EQ bands
- Single-bulb bench mode
- 16-bulb target mode: two bulbs per band
- Reset restores the original band ranges, colors, gain, brightness, single-bulb mode, and live knob state

The physical knob is the only threshold/noise-floor control. Gain changes how hard accepted audio drives the lights; Max Brightness sets the output ceiling.

## Silence behavior

A quiet ESP32 ADC can still generate random sample movement even when no audio source is attached. BloomPulse therefore tracks average waveform activity rather than trusting peak-to-peak alone.

Telemetry includes:

```text
ACT
SILENT
```

When the input is considered silent, band energy is cleared and the LEDs are forced off. The detector uses hysteresis so one random ADC spike cannot wake the visualizer.

## Auto-open / disconnect behavior

The watcher waits for `/dev/ttyACM0` to be stable before opening BloomPulse and will not launch during `arduino-cli` or `esptool` flashing.

Inside the tuner, a brief serial/USB hiccup no longer means immediate shutdown. The controller must remain absent for roughly 3 seconds before the app treats it as a real unplug and closes.

## LED transport

The proven custom ESP32-S3 RMT timing and physical **RGB** byte order remain the low-level APA106 layer.

Do not replace that layer while debugging higher-level EQ, silence detection, UI, or behavior unless the LED transport itself is proven broken.
