# BloomFace 0.1.0

A playful robot-face prototype: the Pi/PC draws animated eyes and a mouth; the ESP32-S3 reads a rotary encoder over USB. No display, motor, or robot movement is connected to the ESP32.

Twelve expressions: Curious, Side Eye, Joy, Sleepy, Panic, Gremlin, Void, Lovestruck, Stubborn, Melting, Disco and Suspicious. Eyes blink and wander; Melting drips, Disco spins, Void stares, and a long press throws a little orbit of sparks. Mood, gaze, energy and eye color can all be controlled live.

## Start today

First close BloomScope and any other serial app. **Unplug USB, remove all BloomScope probe/resistor/diode wiring and any battery connection from this bench board.** This board is changing jobs. Keep the working HAPPY JARZ controller unplugged during flashing so the port is unambiguous.

For a typical five-pin KY-040-style encoder **module**, wire by its printed labels, not header position:

| Encoder label | ESP32 connection |
|---|---|
| GND / − | GND |
| + / VCC | **3V3**, not 5V |
| CLK / A | GPIO7 |
| DT / B | GPIO8 |
| SW | GPIO9 |

These are new bench assignments; they do not change HAPPY JARZ wiring. Only connect a module whose supply/pullups are compatible with 3.3 V. If yours is a bare encoder or has different labels, identify its pinout before wiring. ESP32 input pullups are enabled; switch and encoder contacts pull inputs to GND. Do not connect the damaged battery inputs.

```bash
cd ~/BloomCircuit
git checkout main
git pull
arduino-cli board list
bash BloomFace/flash.sh /dev/ttyACM0
bash BloomFace/install_pi.sh
python3 BloomFace/bloomface.py --port /dev/ttyACM0
```

Use the actual port from `board list`. **Flashing replaces BloomScope firmware on the bench board.** It preserves the BloomScope source files. The flash helper pauses the BloomScope/BloomFace watchers to free the serial port; close their windows yourself first. The installer starts the face watcher again, and future Pi desktop logins start it automatically. A handshake distinguishes BloomFace from BloomScope or other ESP32 firmware.

Preview without hardware:

```bash
python3 BloomFace/bloomface.py --demo
```

Windows: install Python with Tk, `py -m pip install -r BloomFace/requirements.txt`, then `py BloomFace/bloomface.py --port COM3` using the actual COM port. Flash through Arduino IDE: ESP32S3 Dev Module, USB CDC On Boot enabled, sketch `firmware/BloomFace/BloomFace.ino`. Auto-open watcher/installer is Pi/Linux desktop only.

## Knob controls

- **Turn:** change the selected control.
- **Click:** cycle EXPRESSION → GAZE → ENERGY → COLOR.
- **Hold 0.7 seconds:** random expression and spark burst; releasing does not also count as a click.
- **Reverse knob:** corrects direction without moving wires.
- **Edges/click:** default 4. If it takes two physical detents for one app step, try 2. Hardware encoders differ.
- Keyboard **← / →** turns, **Space** clicks, **Enter** bursts, **F** fullscreen, **Esc** leaves fullscreen. Mouse wheel turns and clicking the face cycles controls.
- **Copy debug:** copies a short timestamped event log for troubleshooting; keep the app open until pasted on Linux.

Inputs are cumulative quadrature-edge/tap/hold counters in newline-delimited JSON. The app takes a fresh baseline at connection or firmware reboot so old clicks do not replay. Firmware debounces the button for 25 ms and uses a quadrature transition table that cancels ordinary reversed bounce transitions. Very noisy/fast encoders still require physical validation. About 33 packets/second, nominal serial baud 115200. Firmware never enables a GPIO output. Desktop drawing targets about 30 frames/second, but actual speed depends on the Pi/display and window size.

## Back to BloomScope

Close BloomFace; remove encoder wiring with USB disconnected, then:

```bash
bash BloomScope/flash.sh /dev/ttyACM0
bash BloomScope/install_pi.sh
```

The face watcher rejects BloomScope firmware and releases the port. Rebuild the documented protected measurement input before probing again.

## Validation

`python3 -m unittest discover -s BloomFace/tests -v` checks control wrapping, limits, encoder accumulation, bounce cancellation, reconnect baselines and button events. `xvfb-run -a python3 BloomFace/tests/gui_smoke.py` checks every expression, mouse/keyboard-equivalent controls and clipboard. `bash BloomFace/flash.sh --compile-only` builds ESP32-S3 firmware without uploading.

On the physical bench, confirm one expression per detent, one control change per click, a burst for long hold with no extra release-click, and both directions. Native USB handshakes, actual encoder behavior and frame rate still need testing on your board.

App, firmware and protocol start at 0.1.0 / 0.1.0 / 1. Bump the changed component version for behavior changes; bump protocol for incompatible changes.
