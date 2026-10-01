# HAPPY JARZ Controller

**Status:** bench-proven controller + field-service layer, firmware v0.4

This subsystem is the PC/Raspberry Pi side of the HAPPY JARZ powered stand. It sits above the bench-proven ESP32-S3 light/touch/display layer and is intentionally designed so desktop-side changes do not rewrite the known-good APA106 timing.

## Current proven behavior

- identify a Jar over USB serial with `HJ|IDENTITY|serial=HJ-001|hw=V1|fw=0.4`
- reconnect after unplug/replug
- independently control LED 1 and LED 2 colors
- set brightness
- select patterns: `SOLID`, `FADE`, `PULSE`, `RAINBOW`, `RANDOM`, `OFF`
- watch all four capacitive-touch channels live
- run RGB / touch diagnostics
- save settings to the Jar
- keep session/service logs
- launch the controller automatically when a Jar is plugged in
- check the tracked GitHub branch on startup and every 6 hours
- apply only safe fast-forward updates; never overwrite local edits
- restart the watcher after a safe update when the controller is not open

## Bench-proven hardware map

Controller: **ESP32-S3 SuperMini**

### APA106 lighting

- GPIO7 -> 220 ohm -> APA106 #1 DIN
- APA106 #1 DOUT -> APA106 #2 DIN
- APA106 VCC -> **5V**
- common GND with ESP32
- local decoupling capacitor at each lamp

The tested lamps accept the ESP32-S3's 3.3V GPIO data while powered from 5V, so the current prototype does not require a separate logic-level-shifter IC. Do not route 5V into an ESP32 GPIO.

### Capacitive touch

- GPIO1 = COLOR 1 -> next color for Light 1
- GPIO2 = COLOR 2 -> next color for Light 2
- GPIO4 = CYCLE UP -> next pattern
- GPIO5 = CYCLE DOWN -> previous pattern

Touch calibration samples a boot baseline, requires roughly 20% over baseline, uses ~60 ms qualification, and applies slow drift compensation only while untouched.

### OLED

Small 4-wire I2C OLED:

- VCC -> 3.3V
- GND -> GND
- SDA -> GPIO8
- SCL -> GPIO6
- address -> `0x3C`
- tested successfully with Adafruit SSD1306 / Adafruit GFX

Firmware shows startup stats for a few seconds, then rotates short positive HAPPY JARZ messages.

## Known-good APA106 timing

Do not replace this casually. The integrated firmware uses the Arduino ESP32 HAL RMT driver:

- 10 MHz RMT clock
- bit 0 ~= 4 ticks high / 14 ticks low
- bit 1 ~= 14 ticks high / 4 ticks low
- ~100 us reset/latch

Generic NeoPixel/FastLED attempts were not the proven path for this hardware.

## Desktop requirements

### Raspberry Pi / Debian

Install once:

```bash
cd ~/BloomCircuit/happyjarz-controller
bash install_pi_autostart.sh
```

The installer uses Debian packages (`python3`, `python3-tk`, `python3-serial`) so it does not fight Bookworm's PEP 668 protected Python environment.

The autostart entry runs `happyjarz_plug_watch.py`, not the full GUI. The watcher stays quiet until a HAPPY JARZ is detected, then opens `happyjarz_controller.py`.

Manual watcher test:

```bash
python3 ~/BloomCircuit/happyjarz-controller/happyjarz_plug_watch.py
```

### Windows

From PowerShell in this directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_windows_autostart.ps1
```

Windows does not allow arbitrary old-style USB autorun, so the installer places the lightweight watcher in the user's Startup flow. After that, plugging in a HAPPY JARZ opens the controller automatically.

## Auto-update behavior

The watcher also acts as the field updater.

- checks the configured upstream branch when it starts
- checks again every 6 hours
- uses fast-forward-only Git updates
- skips update if local edits would be overwritten
- keeps running if the internet is unavailable
- logs update decisions
- restarts itself after its own code changes when safe

This is intended for deployed units in other regions/countries so fixes, compatibility patches, regional content, sayings, and controller changes can be delivered through the repository without requiring manual `git pull` each time.

## Logs

Service logs are stored under:

```text
~/.happyjarz/plug_watch.log
~/.happyjarz/controller_launch.log
```

These are the first files to request when diagnosing a remote unit.

## USB protocol

See [`PROTOCOL.md`](PROTOCOL.md).

## Firmware

See [`firmware/README.md`](firmware/README.md).

## BloomCore failure boundary

Preserve known-good layers.

If the desktop UI is wrong but the ESP32's local LED/touch/display behavior still passes, troubleshoot the watcher/controller/protocol layer first.

If the ESP32's local behavior fails, troubleshoot the firmware/hardware layer before changing the desktop app.

Every feature should carry its own diagnostic path.