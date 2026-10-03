# BloomScope 0.1.0

A breadboard USB bench doctor for the Architect's ESP32-S3 SuperMini with damaged battery inputs. USB powers the board; the battery socket stays unused. This is a separate firmware/app pair, not a HAPPY JARZ controller patch.

## Get running today on the Pi

```bash
cd ~/BloomCircuit
git checkout main
git pull
bash BloomScope/install_pi.sh
python3 BloomScope/bloomscope.py --demo
```

Demo is explicitly simulated and needs no ESP32. Close it when ready for real measurements.

1. Disconnect every probe. Verify the board's printed GPIO labels against the proposed map below; the photo cannot establish the precise vendor pinout. Do not use header position as a GPIO number.
2. Plug only the damaged bench ESP32 into USB. Close the HAPPY JARZ controller and its plug watcher, if running, so neither grabs this board. Flashing overwrites the connected board's firmware. Select the bench board's port explicitly.
3. Use the existing HAPPY JARZ `arduino-cli`/ESP32 board installation:

```bash
arduino-cli board list
bash BloomScope/flash.sh /dev/ttyACM0
python3 BloomScope/bloomscope.py
```

Choose the actual port from `board list`, which may differ from `/dev/ttyACM0`. If the board will not enter download mode, hold BOOT while tapping RESET, then retry. The generic ESP32-S3 target uses USB CDC on boot and requires no extra Arduino libraries. In Arduino IDE, open `firmware/BloomScope/BloomScope.ino`, select ESP32S3 Dev Module and enable USB CDC On Boot.

4. Refresh ports, select the bench board, Connect. The app requires a BloomScope protocol handshake, so another Jar cannot silently become a measuring instrument.
5. Assemble the voltage input below, then select METER and Start. Test GND first, then known 3V3 and 5V rails. Compare against your multimeter once; enter `known voltage / displayed voltage` as the calibration gain. Gain is session-only and assumes the fixed 2:1 divider.
6. Add the digital inputs, piezo, and touch pads one subsystem at a time. Do not attach bare probes straight to GPIO.

Windows: install Python with Tk support, then `py -m pip install -r BloomScope/requirements.txt` and `py BloomScope/bloomscope.py`. Select the ESP32's COM port. Flash through Arduino IDE or the equivalent `arduino-cli` commands above.

## Proposed bench pin map

These are new bench assignments. They do not change the HAPPY JARZ design. Verify that all are exposed on your specific SuperMini before wiring; change the firmware constants if the board differs.

| Function | GPIO | Wiring |
|---|---:|---|
| Voltage / scope | 1 | Protected 2:1 divider below |
| Continuity sense | 2 | Dedicated continuity node below |
| Touch: next mode | 4 | Short wire to copper/brass pad |
| Touch: start / stop | 5 | Short wire to copper/brass pad |
| Touch: mute | 6 | Short wire to copper/brass pad |
| Logic CH1 / PWM | 7 | Protected 3.3 V digital input |
| Logic CH2 | 8 | Protected 3.3 V digital input |
| Logic CH3 | 9 | Protected 3.3 V digital input |
| Logic CH4 | 10 | Protected 3.3 V digital input |
| Passive piezo signal | 11 | Small passive piezo through 220 Ω, or verified module signal |
| Continuity excitation | 12 | Through 10 kΩ to continuity node |
| Ground | GND | Target ground / black probe |

GPIO3 and USB GPIO19/20 are avoided. No encoder or display is required. Leave touch disabled until pads are fitted. With fingers away, click **Enable + calibrate touch**. S3 touch counts rise when touched; firmware uses a provisional 1.5× idle threshold and one action per touch. If unreliable, disable touch and inspect pad/wire geometry before adjusting thresholds. A touch can stop continuity, but cannot arm it.

## Parts / voltage input

- Equal **10 kΩ + 10 kΩ**, preferably 1%, for the voltage divider.
- **1 kΩ** between the divider midpoint and GPIO1.
- Two Schottky clamps (e.g. BAT54 / 1N5817), with verified orientation: lower diode **anode GND, cathode GPIO1**; upper diode **anode GPIO1, cathode 3V3**.
- **10 kΩ** continuity excitation resistor, **1 kΩ** sense protection resistor; the same pair of clamps at GPIO2.
- **1 kΩ series + Schottky clamp pair per digital input**. Short leads for logic/PWM.
- **220 Ω** for a bare small passive piezo. The pictured module is not identified: read its labels and confirm whether it is active/passive and its current/rating before wiring. For a module, connect GND, its rated supply, and signal GPIO11 only if it accepts 3.3 V control and includes a suitable driver. Do not power a buzzer module from GPIO11. Active buzzers may require changing tone/noTone to their documented on/off polarity.
- Dupont leads, labeled probes, breadboard; optional 100 nF across board 3V3/GND. Do not put a large smoothing capacitor on the scope input: it hides waveform detail.

Voltage path: **red probe → 10 kΩ → divider midpoint → 1 kΩ → GPIO1**. A second **10 kΩ runs midpoint → GND**. Put the clamps at GPIO1. Connect target GND to bench GND. The app multiplies calibrated ADC millivolts by two, so 5 V becomes 2.5 V at the divider midpoint. Intended probe range is **0–5 V DC**, not a general-purpose 30 V meter. Negative signals, mains, and high-energy circuits are outside this build.

The earlier direct 3.3 V ADC suggestion and 10 kΩ/20 kΩ 5 V divider are superseded: the S3's documented ADC range at maximum attenuation is roughly 3.1 V. A 2:1 divider leaves margin for both rails. Ordinary 1N4148 clamps can let the voltage rise too far above 3V3; use Schottky clamps for this build. Clamps supplement range discipline; they do not guarantee survival of arbitrary faults. The tester must be powered before connecting a live probe, to avoid back-powering its rail through clamps.

Digital path per channel: **3.3 V target GPIO → 1 kΩ → bench input**, with clamps at the input. Digital channels are **3.3 V only**: use a separately designed level shifter/divider for 5 V logic. Shared GND is mandatory. Do not connect the boards' 3V3 outputs together.

## Continuity / piezo

This checks for a low-resistance path; it is not calibrated conductance or resistance measurement.

Dedicated path: **GPIO12 → 10 kΩ → continuity probe/node**. From that node, **1 kΩ → GPIO2**, with clamps at GPIO2. The other probe is **GND**. Do not connect this node to the voltage-divider input. The 10 kΩ resistor limits the nominal test current to about 0.33 mA. A reading below 35 mV beeps; nominally this corresponds to around 100 Ω, but ADC low-end error makes the actual threshold approximate.

Disconnect target USB, battery, and every other supply; discharge capacitors. Then click **Arm continuity** and confirm that power is removed. OPEN should stay quiet; touching the continuity and GND probes should beep. Use Mute to silence it. Stop/disarm, switching away from continuity, or a missing host heartbeat disables the excitation pin and piezo. The 3-second timeout is a software safeguard, not galvanic isolation. The low-current test can still make semiconductor junctions conduct, so in-circuit results may differ from isolated parts.

## What V1 measures honestly

| Mode | Implemented behavior | Limits |
|---|---|---|
| Meter | Calibrated ADC voltage, 16-reading average, 2:1 divider correction | Bench estimate; compare once to a known meter |
| PWM | GPIO7 interrupt timestamps, frequency, duty, high pulse width | Initially test servo/PWM up to about 1 kHz; accuracy/load limits need hardware validation |
| Scope | 128-point bursts, nominal 1,000 samples/s, actual timestamps, CSV | Slow waveform viewer; useful initial signals ≤50 Hz. Not LED-data/UART decoding or power-ripple metrology |
| Logic | Four channels sampled in the same nominal 1 ms loop; CSV | Channels read sequentially, not simultaneously. Short pulses can be missed. No UART/I²C/SPI decoder |
| Continuity | Current-limited dedicated probe; local piezo feedback | Only unpowered targets; approximate closed/open |

Scope and logic have gaps between bursts while records are sent. Touch and commands are handled between bursts; PWM edges are timestamped by an interrupt. Wi-Fi/Bluetooth are not used. USB transport is newline-delimited JSON at 115200 nominal baud. Each capture carries `t_us` and `values`; scope values are ADC millivolts, logic values are a four-bit mask. App CSV records demo status, actual time, values and channel states. Stopped captures remain available for export, but the readout explicitly marks stopped readings stale.

Firmware version and app version are both 0.1.0. Any behavior change must bump both release labels and the handshake as appropriate; protocol-breaking changes must bump `protocol`. App `--demo` is a preview, not hardware validation.

## Validation before relying on it

- Voltage: GND, known 3V3, known 5V. Verify divider orientation before touching a powered target.
- PWM: a separate ESP32 outputs 50 Hz / 5% (1 ms high), then 1 kHz / 50%; compare the app.
- Scope: separate ESP32 slow PWM at 10 Hz; confirm the time axis and amplitude.
- Logic: walk one channel HIGH at a time; verify CH1–CH4 order.
- Continuity: open probes, shorted probes, then isolated 100 Ω and 1 kΩ resistors; record the actual beep threshold. Unplug USB to check that the buzzer stops; also stop the host while leaving board power on to exercise the timeout.
- Touch: calibrate untouched, test each pad, and verify that touch never arms continuity.

Software tests: `python3 -m unittest discover -s BloomScope/tests -v`. Compile check: `bash BloomScope/flash.sh --compile-only`. Real USB, touch sensitivity, ADC accuracy, buzzer behavior, and damaged power-path stability must be validated on the physical board.

Primary API references: [Espressif ADC](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/adc.html), [Espressif touch](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/touch.html).
