# BloomPulse

**BloomPulse** is the HAPPY JARZ / CLUB BOX music-reactive light controller.

It combines the ESP32-S3 line-in EQ firmware with the Raspberry Pi tuner for live audio visualization, threshold control, band/color tuning, and the planned 16-bulb light array.

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

The USB auto-launch watcher remains separate. Plugging in the controller can still open BloomPulse automatically, while the menu entry lets it be launched manually.

## Current control model

- GPIO9 = mono line input
- GPIO10 = physical threshold / noise-floor knob
- GPIO7 = APA106 data
- 8 EQ bands
- Single-bulb bench mode
- 16-bulb target mode: two bulbs per band
- Reset restores the original band ranges, colors, gain, brightness, single-bulb mode, and live knob state

The proven custom RMT timing and physical RGB byte order remain the low-level LED layer.
